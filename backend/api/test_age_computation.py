"""Regression tests for Fix 7: every triage entry point must send the LLM a
computed integer age, never a raw date_of_birth object.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from rest_framework.test import APIClient

from .models import ConsultationSession, UserProfile

User = get_user_model()

FAKE_ASSESSMENT = {
    "risk_level": "low",
    "risk_probability": 0.2,
    "confidence": 0.8,
    "reasoning": "mild",
    "possible_conditions": [{"disease": "Common cold", "confidence": 0.3}],
    "recommendations": ["Rest"],
    "when_to_seek_care": "If it worsens",
    "disclaimer": "test",
    "model_id": "test-model",
    "model_provider": "gemini",
    "degraded": False,
    "requires_human_review": False,
}


class CalculateAgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='age_user', password='password123', email='age_user@example.com'
        )

    def test_returns_none_without_date_of_birth(self):
        profile = UserProfile.objects.create(user=self.user)
        self.assertIsNone(profile.calculate_age())

    def test_returns_integer_age(self):
        profile = UserProfile.objects.create(user=self.user, date_of_birth=date(1990, 1, 1))
        age = profile.calculate_age()
        self.assertIsInstance(age, int)
        self.assertEqual(age, date.today().year - 1990 - ((date.today().month, date.today().day) < (1, 1)))

    def test_birthday_today_counts_as_full_year(self):
        today = date.today()
        profile = UserProfile.objects.create(
            user=self.user, date_of_birth=date(today.year - 30, today.month, today.day)
        )
        self.assertEqual(profile.calculate_age(), 30)

    def test_birthday_not_yet_reached_this_year_is_one_less(self):
        today = date.today()
        if (today.month, today.day) == (12, 31):
            self.skipTest('no later date in year exists to test against')
        # DOB on Dec 31 - a birthday that has not happened yet this year.
        profile = UserProfile.objects.create(
            user=self.user, date_of_birth=date(today.year - 30, 12, 31)
        )
        # Turns 30 only on Dec 31, so today they are still 29.
        self.assertEqual(profile.calculate_age(), 29)


class AgeSentToLLMFromAllEntryPointsTests(TestCase):
    """The prompt payload must carry an int age, not a date, everywhere."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='prompt_age_user', password='password123', email='prompt_age@example.com'
        )
        UserProfile.objects.create(user=self.user, date_of_birth=date(1990, 5, 14), gender='F')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.expected_age = UserProfile.objects.get(user=self.user).calculate_age()

    def _assert_age_is_int(self, mocked_engine):
        self.assertTrue(mocked_engine.return_value.assess.called, 'assess() was never called')
        kwargs = mocked_engine.return_value.assess.call_args.kwargs
        args = mocked_engine.return_value.assess.call_args.args
        user_data = kwargs.get('user_data') or (args[1] if len(args) > 1 else None)
        self.assertIsNotNone(user_data, 'user_data not passed to assess()')
        age = user_data['age']
        self.assertNotIsInstance(age, date, f'raw date leaked into prompt payload: {age!r}')
        self.assertIsInstance(age, int)
        self.assertEqual(age, self.expected_age)

    @patch('api.views.get_triage_engine_v2')
    def test_assess_symptoms_sends_integer_age(self, mocked_engine):
        mocked_engine.return_value.assess.return_value = dict(FAKE_ASSESSMENT)

        response = self.client.post(
            reverse('assess_symptoms'),
            {'current_symptoms': 'mild cough', 'skip_clarification': True},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self._assert_age_is_int(mocked_engine)

    @patch('api.views.get_triage_engine_v2')
    def test_submit_consultation_step_sends_integer_age(self, mocked_engine):
        mocked_engine.return_value.assess.return_value = dict(FAKE_ASSESSMENT)
        session = ConsultationSession.objects.create(
            user=self.user, stage='assessment', symptoms='mild cough', is_active=True
        )

        response = self.client.post(
            reverse('submit_consultation_step', args=[session.id]), {}, format='json'
        )

        self.assertEqual(response.status_code, 200)
        self._assert_age_is_int(mocked_engine)

    @patch('api.chat_service.TriageEngineV2')
    def test_chat_send_message_sends_integer_age(self, mocked_engine_cls):
        mocked_engine_cls.return_value.assess.return_value = dict(FAKE_ASSESSMENT)

        create_resp = self.client.post(reverse('chat_conversations_list'), {}, format='json')
        conversation_id = create_resp.data['conversation']['id']

        # A detailed message so the vague-input clarifying-question gate does
        # not short-circuit before the AI response (and its age handling) runs.
        response = self.client.post(
            reverse('chat_send_message', args=[conversation_id]),
            {'content': 'I have had a sharp throbbing headache on the left side of my head for the past three days and it gets worse every evening'},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self._assert_age_is_int(mocked_engine_cls)
