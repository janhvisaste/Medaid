"""Tests for real (previously stubbed) clarifying-question generation.

The old implementation built a prompt, discarded it, and returned a single
hardcoded question - it never called the model at all.
"""
import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch
from rest_framework.test import APIClient

from .llm_providers.base import ModelProviderError
from .models import ConsultationSession, UserProfile
from .triage_engine_v2 import TriageEngineV2

User = get_user_model()

GOOD_QUESTIONS = json.dumps([
    {"question": "How many days have you had the cough?", "type": "text"},
    {"question": "Rate your breathlessness right now.", "type": "scale"},
    {"question": "Have you coughed up any blood?", "type": "yes_no"},
])


class ScriptedProvider:
    is_available = True

    def __init__(self, response_text=None, error=None):
        self.response_text = response_text
        self.error = error
        self.calls = []

    def complete(self, messages, model_id, temperature):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.response_text


def make_engine(response_text=None, error=None):
    provider = ScriptedProvider(response_text=response_text, error=error)
    engine = TriageEngineV2(default_provider=provider, openrouter_provider=provider)
    return engine, provider


class ClarifyingQuestionGenerationTests(SimpleTestCase):
    def test_actually_calls_the_model(self):
        engine, provider = make_engine(GOOD_QUESTIONS)

        questions = engine.generate_clarifying_questions('cough for a while', {})

        self.assertEqual(len(provider.calls), 1, 'the model was never called')
        prompt = provider.calls[0][0]['content']
        self.assertIn('cough for a while', prompt)

    def test_returns_model_questions(self):
        engine, _ = make_engine(GOOD_QUESTIONS)

        questions = engine.generate_clarifying_questions('cough', {})

        self.assertEqual(len(questions), 3)
        self.assertEqual(questions[0]['question'], 'How many days have you had the cough?')
        self.assertEqual({q['type'] for q in questions}, {'text', 'scale', 'yes_no'})

    def test_questions_are_specific_not_the_old_hardcoded_stub(self):
        engine, _ = make_engine(GOOD_QUESTIONS)
        questions = engine.generate_clarifying_questions('cough', {})
        texts = [q['question'] for q in questions]
        self.assertNotEqual(texts, ['How long have you felt this way?'])

    def test_respects_max_questions(self):
        engine, _ = make_engine(GOOD_QUESTIONS)
        questions = engine.generate_clarifying_questions('cough', {}, max_questions=2)
        self.assertEqual(len(questions), 2)

    def test_handles_fenced_json(self):
        engine, _ = make_engine(f"Here you go:\n```json\n{GOOD_QUESTIONS}\n```")
        questions = engine.generate_clarifying_questions('cough', {})
        self.assertEqual(len(questions), 3)

    def test_handles_object_wrapped_array(self):
        engine, _ = make_engine(json.dumps({'questions': json.loads(GOOD_QUESTIONS)}))
        questions = engine.generate_clarifying_questions('cough', {})
        self.assertEqual(len(questions), 3)

    def test_handles_plain_string_list(self):
        engine, _ = make_engine(json.dumps(['How long?', 'Any fever?']))
        questions = engine.generate_clarifying_questions('cough', {})
        self.assertEqual(len(questions), 2)
        self.assertTrue(all(q['type'] == 'text' for q in questions))

    def test_normalises_unknown_question_type(self):
        engine, _ = make_engine(json.dumps([{'question': 'How long?', 'type': 'dropdown'}]))
        questions = engine.generate_clarifying_questions('cough', {})
        self.assertEqual(questions[0]['type'], 'text')

    def test_normalises_yesno_variants(self):
        engine, _ = make_engine(json.dumps([{'question': 'Fever?', 'type': 'yes-no'}]))
        questions = engine.generate_clarifying_questions('cough', {})
        self.assertEqual(questions[0]['type'], 'yes_no')

    def test_drops_duplicates_and_blanks(self):
        engine, _ = make_engine(json.dumps([
            {'question': 'How long?', 'type': 'text'},
            {'question': 'how long?', 'type': 'text'},
            {'question': '   ', 'type': 'text'},
            {'question': 'Any fever?', 'type': 'yes_no'},
        ]))
        questions = engine.generate_clarifying_questions('cough', {})
        self.assertEqual([q['question'] for q in questions], ['How long?', 'Any fever?'])

    def test_falls_back_when_provider_fails(self):
        engine, _ = make_engine(error=ModelProviderError('down', status_code=503))
        questions = engine.generate_clarifying_questions('cough', {})
        self.assertEqual(len(questions), 3)
        self.assertTrue(all(q['question'] for q in questions))

    def test_falls_back_on_malformed_response(self):
        engine, _ = make_engine('this is not json at all')
        questions = engine.generate_clarifying_questions('cough', {})
        self.assertEqual(len(questions), 3)

    def test_falls_back_on_empty_array(self):
        engine, _ = make_engine('[]')
        questions = engine.generate_clarifying_questions('cough', {})
        self.assertEqual(len(questions), 3)

    def test_no_questions_for_emergency_text(self):
        engine, provider = make_engine(GOOD_QUESTIONS)

        questions = engine.generate_clarifying_questions("severe chest pain and can't breathe", {})

        self.assertEqual(questions, [])
        self.assertEqual(provider.calls, [], 'must not spend an LLM round-trip on an emergency')

    def test_empty_symptoms_uses_defaults_without_calling_model(self):
        engine, provider = make_engine(GOOD_QUESTIONS)
        questions = engine.generate_clarifying_questions('', {})
        self.assertEqual(len(questions), 3)
        self.assertEqual(provider.calls, [])

    def test_prompt_includes_patient_context(self):
        engine, provider = make_engine(GOOD_QUESTIONS)

        engine.generate_clarifying_questions(
            'cough', {'age': 67, 'gender': 'M', 'past_history': [{'name': 'Asthma'}]}
        )

        prompt = provider.calls[0][0]['content']
        self.assertIn('67', prompt)
        self.assertIn('Asthma', prompt)

    def test_handles_dict_shaped_past_history(self):
        engine, provider = make_engine(GOOD_QUESTIONS)

        engine.generate_clarifying_questions(
            'cough', {'past_history': {'conditions': [{'name': 'Diabetes'}]}}
        )

        self.assertIn('Diabetes', provider.calls[0][0]['content'])


class ClarifyingQuestionEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cq_user', password='password123', email='cq@example.com'
        )
        UserProfile.objects.create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.session = ConsultationSession.objects.create(
            user=self.user, stage='questions', symptoms='cough and tiredness', is_active=True
        )

    def test_endpoint_returns_model_generated_questions(self):
        engine, _ = make_engine(GOOD_QUESTIONS)

        with patch('api.views.get_triage_engine_v2', return_value=engine):
            response = self.client.get(
                reverse('get_clarifying_questions', args=[self.session.id])
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['questions']), 3)
        self.assertIn('cough', response.data['questions'][0]['question'].lower())

    def test_endpoint_degrades_to_defaults_when_provider_is_down(self):
        engine, _ = make_engine(error=ModelProviderError('down', status_code=503))

        with patch('api.views.get_triage_engine_v2', return_value=engine):
            response = self.client.get(
                reverse('get_clarifying_questions', args=[self.session.id])
            )

        # The consultation must not dead-end just because the model failed.
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['questions'])
