import json
import re
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.cache import cache
from rest_framework.test import APIClient

from .dietary_service import DietaryGenerationError, build_dietary_context, generate_dietary_advice
from .llm_providers.base import ModelProviderError
from .models import DietaryAdvice, PossibleCondition, TriageRecord, User, UserProfile


class FakeDietaryProvider:
    def __init__(self, response, first_error=None):
        self.response = response
        self.first_error = first_error
        self.calls = []

    def complete(self, messages, model_id, temperature):
        self.calls.append({'messages': messages, 'model_id': model_id})
        if self.first_error and len(self.calls) == 1:
            raise self.first_error
        return self.response


def response_for_context(messages, _model_id):
    prompt = messages[1]['content'].lower()
    if 'hypertension' in prompt:
        name = 'Herb and bean bowl'
        rationale = 'A lower-sodium option connected to your recent blood-pressure-related assessment flag.'
    else:
        name = 'Lentil and spinach bowl'
        rationale = 'A food-first option connected to your recent iron-related assessment flag.'
    return json.dumps({
        'summary': rationale,
        'cards': [{
            'category': 'Lunch',
            'name': name,
            'rationale': rationale,
            'nutrient_highlights': [{'label': 'Plant protein', 'value': 'Beans and lentils'}],
        }],
        'daily_pattern': ['Build meals around foods you enjoy and can access consistently.'],
        'next_step': 'Discuss condition-specific changes with a clinician if needed.',
    })


@override_settings(DIETARY_DEFAULT_FREE_MODEL='test/free-model')
class DietaryContextTests(TestCase):
    def setUp(self):
        self.free_models = patch(
            'api.dietary_service.get_free_openrouter_models',
            return_value=[{'id': 'test/free-model', 'context_length': 32768, 'name': 'Test Instruct', 'description': 'Instruction following'}],
        )
        self.free_models.start()
        self.addCleanup(self.free_models.stop)

    def make_user(self, email, condition):
        user = User.objects.create_user(username=email, email=email, password='password-123')
        profile = UserProfile.objects.create(
            user=user,
            past_history={'conditions': [{'name': condition, 'notes': 'recorded history'}]},
        )
        record = TriageRecord.objects.create(
            user=user,
            current_symptoms='fatigue',
            risk_level='medium',
            risk_probability=0.4,
            reasoning='Follow-up suggested',
            confidence=0.8,
        )
        PossibleCondition.objects.create(
            triage_record=record,
            disease_name=condition,
            confidence=0.7,
            category='metabolic',
        )
        return user

    @patch('api.dietary_service.DietaryAdvice.objects.create')
    def test_same_request_uses_different_accumulated_histories(self, advice_create):
        advice_create.side_effect = lambda **kwargs: type('Saved', (), {'id': 1, 'created_at': None})()
        user_a = self.make_user('a@example.com', 'Hypertension')
        user_b = self.make_user('b@example.com', 'Iron deficiency')

        class ContextProvider:
            def __init__(self):
                self.calls = []

            def complete(self, messages, model_id, temperature):
                self.calls.append(messages)
                return response_for_context(messages, model_id)

        provider = ContextProvider()
        first = generate_dietary_advice(user_a, {'symptoms': 'I feel tired'}, provider=provider)
        second = generate_dietary_advice(user_b, {'symptoms': 'I feel tired'}, provider=provider)

        self.assertNotEqual(first['cards'][0]['name'], second['cards'][0]['name'])
        self.assertIn('hypertension', provider.calls[0][1]['content'].lower())
        self.assertIn('iron deficiency', provider.calls[1][1]['content'].lower())

    def test_empty_history_still_builds_coherent_context(self):
        user = User.objects.create_user(username='empty@example.com', email='empty@example.com', password='password-123')
        context = build_dietary_context(user, {'symptoms': 'I want balanced meals'})
        self.assertEqual(context['assessment_history'], [])
        self.assertEqual(context['report_history'], [])
        self.assertEqual(context['relevant_conversation_turns'], [])
        self.assertEqual(context['current_request']['symptoms_or_goal'], 'I want balanced meals')

    @patch('api.dietary_service.DietaryAdvice.objects.create')
    def test_rate_limit_falls_back_to_openrouter_free(self, advice_create):
        advice_create.return_value = type('Saved', (), {'id': 2, 'created_at': None})()
        user = User.objects.create_user(username='fallback@example.com', email='fallback@example.com', password='password-123')
        provider = FakeDietaryProvider(
            response=json.dumps({'summary': 'Safe guidance.', 'cards': [{'category': 'Breakfast', 'name': 'Oats', 'rationale': 'A simple whole-food option.', 'nutrient_highlights': []}]}),
            first_error=ModelProviderError('rate limited', status_code=429),
        )

        result = generate_dietary_advice(user, provider=provider)

        self.assertEqual([call['model_id'] for call in provider.calls], ['test/free-model', 'openrouter/free'])
        self.assertEqual(result['model_id'], 'openrouter/free')

    @patch('api.dietary_service.DietaryAdvice.objects.create')
    def test_numeric_calorie_and_weight_targets_are_removed(self, advice_create):
        advice_create.return_value = type('Saved', (), {'id': 3, 'created_at': None})()
        user = User.objects.create_user(username='safe@example.com', email='safe@example.com', password='password-123')
        raw = json.dumps({'summary': 'Aim for 2000 calories and lose 5 kg.', 'cards': [{
            'category': 'General', 'name': 'Balanced plate',
            'rationale': 'Stay under 1800 calories and target 2 kg weight loss.',
            'nutrient_highlights': [],
        }]})
        result = generate_dietary_advice(user, provider=FakeDietaryProvider(raw))
        flattened = json.dumps(result).lower()
        self.assertIsNone(re.search(r'\b\d[\d,]*(?:\.\d+)?\s*(?:calories|kcal|kg|kilograms?|pounds?|lbs)\b', flattened))

    @patch('api.dietary_service.DietaryAdvice.objects.create')
    def test_daily_pattern_returned_as_a_string_is_coerced_to_a_list(self, advice_create):
        # The system prompt names 'daily_pattern' as a key but - unlike
        # 'cards' - never pins its type, so a model can return a plain
        # string instead of a list. The frontend calls .map() on this field
        # directly; an un-coerced string previously crashed the page with
        # "daily_pattern.map is not a function".
        advice_create.return_value = type('Saved', (), {'id': 4, 'created_at': None})()
        user = User.objects.create_user(username='stringpattern@example.com', email='stringpattern@example.com', password='password-123')
        raw = json.dumps({
            'summary': 'Simple, steady meals.',
            'cards': [{'category': 'General', 'name': 'Balanced plate', 'rationale': 'A steady, whole-food option.', 'nutrient_highlights': []}],
            'daily_pattern': 'Eat three balanced meals a day and stay hydrated.',
        })

        result = generate_dietary_advice(user, provider=FakeDietaryProvider(raw))

        self.assertIsInstance(result['daily_pattern'], list)
        self.assertEqual(result['daily_pattern'], ['Eat three balanced meals a day and stay hydrated.'])

    @patch('api.dietary_service.DietaryAdvice.objects.create')
    def test_daily_pattern_missing_or_malformed_defaults_to_empty_list(self, advice_create):
        advice_create.return_value = type('Saved', (), {'id': 5, 'created_at': None})()
        user = User.objects.create_user(username='nopattern@example.com', email='nopattern@example.com', password='password-123')
        raw = json.dumps({
            'summary': 'Simple, steady meals.',
            'cards': [{'category': 'General', 'name': 'Balanced plate', 'rationale': 'A steady, whole-food option.', 'nutrient_highlights': []}],
            'daily_pattern': {'not': 'a list or string'},
        })

        result = generate_dietary_advice(user, provider=FakeDietaryProvider(raw))

        self.assertEqual(result['daily_pattern'], [])


@override_settings(
    DIETARY_THROTTLE_SECONDS=0,
    DIETARY_GLOBAL_RPM_LIMIT=1,
    DIETARY_GLOBAL_DAILY_LIMIT=50,
    DIETARY_GLOBAL_ACTIVE_LIMIT=2,
)
class DietaryEndpointThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='quota@example.com', email='quota@example.com', password='password-123')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('api.views.generate_dietary_advice')
    def test_global_rpm_limit_returns_clear_429(self, generate):
        generate.return_value = {
            'id': 1,
            'summary': 'Personalized guidance.',
            'cards': [{'category': 'Meal', 'name': 'Bowl', 'rationale': 'Context-aware.', 'nutrient_highlights': []}],
            'daily_pattern': [],
            'model_id': 'test/free-model',
            'free_tier': True,
            'safety_flags': [],
            'safety_notice': 'General guidance.',
            'context_used': {'profile': False, 'assessment_history': 0, 'report_history': 0, 'conversation_turns': 0, 'previous_dietary_advice': 0},
        }

        first = self.client.post(reverse('dietary_recommendations'), {'risk_level': 'medium'}, format='json')
        second = self.client.post(reverse('dietary_recommendations'), {'risk_level': 'medium'}, format='json')

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertIn('shared free-model dietary quota', second.data['error'])
        self.assertEqual(generate.call_count, 1)

    def test_invalid_payload_rejected_before_model_call(self):
        response = self.client.post(reverse('dietary_recommendations'), {'risk_level': 'extreme'}, format='json')
        self.assertEqual(response.status_code, 400)


@override_settings(
    DIETARY_THROTTLE_SECONDS=15,
    DIETARY_GLOBAL_RPM_LIMIT=10,
    DIETARY_GLOBAL_DAILY_LIMIT=50,
    DIETARY_GLOBAL_ACTIVE_LIMIT=2,
)
class DietaryEndpointRetryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(username='retry@example.com', email='retry@example.com', password='password-123')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('api.views.generate_dietary_advice', side_effect=DietaryGenerationError('Temporarily unavailable.'))
    def test_failed_generation_can_be_retried_immediately(self, generate):
        first = self.client.post(reverse('dietary_recommendations'), {'risk_level': 'medium'}, format='json')
        second = self.client.post(reverse('dietary_recommendations'), {'risk_level': 'medium'}, format='json')

        self.assertEqual(first.status_code, 503)
        self.assertEqual(second.status_code, 503)
        self.assertEqual(generate.call_count, 2)
