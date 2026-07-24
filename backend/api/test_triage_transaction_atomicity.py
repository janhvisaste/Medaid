"""Regression tests for Fix 6: TriageRecord + child rows must be created
atomically in assess_symptoms and submit_consultation_step - a failure
partway through child-object creation must leave no TriageRecord committed.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import ConsultationSession, TriageRecord, UserProfile

User = get_user_model()

FAKE_ASSESSMENT = {
    "risk_level": "medium",
    "risk_probability": 0.4,
    "confidence": 0.6,
    "reasoning": "test reasoning",
    "possible_conditions": [{"disease": "Test Condition", "confidence": 0.3}],
    "recommendations": ["Rest", "Hydrate"],
    "when_to_seek_care": "If it worsens",
    "disclaimer": "test disclaimer",
    "model_id": "test-model",
    "model_provider": "gemini",
    "degraded": False,
    "requires_human_review": False,
}


class AssessSymptomsAtomicityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='atomic_user', password='password123', email='atomic_user@example.com'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch('api.views.Recommendation.objects.create', side_effect=RuntimeError('DB exploded'))
    @patch('api.views.get_triage_engine_v2')
    def test_partial_failure_leaves_no_triage_record_committed(self, mocked_get_engine, _mocked_recommendation_create):
        mocked_get_engine.return_value.assess.return_value = dict(FAKE_ASSESSMENT)

        response = self.client.post(
            reverse('assess_symptoms'), {'current_symptoms': 'mild fever', 'skip_clarification': True}, format='json'
        )

        # The view's outer except turns the unhandled RuntimeError into a 500,
        # but the important assertion is that nothing was left half-written.
        self.assertEqual(response.status_code, 500)
        self.assertEqual(TriageRecord.objects.filter(user=self.user).count(), 0)

    @patch('api.views.PossibleCondition.objects.create', side_effect=RuntimeError('DB exploded'))
    @patch('api.views.get_triage_engine_v2')
    def test_condition_failure_leaves_no_triage_record_committed(self, mocked_get_engine, _mocked_condition_create):
        mocked_get_engine.return_value.assess.return_value = dict(FAKE_ASSESSMENT)

        response = self.client.post(
            reverse('assess_symptoms'), {'current_symptoms': 'mild fever', 'skip_clarification': True}, format='json'
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(TriageRecord.objects.filter(user=self.user).count(), 0)


class SubmitConsultationStepAtomicityTests(TestCase):
    def setUp(self):
        # LLM quota counters (api/llm_quota.py) live in the shared cache and
        # persist across tests in a run; clear them so this test's triage call
        # is never pre-emptively 429'd by counters other tests accumulated.
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(
            username='atomic_wizard_user', password='password123', email='atomic_wizard@example.com'
        )
        UserProfile.objects.create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.session = ConsultationSession.objects.create(
            user=self.user, stage='assessment', symptoms='mild fever', is_active=True
        )

    @patch('api.views.Recommendation.objects.create', side_effect=RuntimeError('DB exploded'))
    @patch('api.views.get_triage_engine_v2')
    def test_partial_failure_leaves_no_triage_record_committed(self, mocked_get_engine, _mocked_recommendation_create):
        mocked_get_engine.return_value.assess.return_value = dict(FAKE_ASSESSMENT)

        response = self.client.post(
            reverse('submit_consultation_step', args=[self.session.id]), {}, format='json'
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(TriageRecord.objects.filter(user=self.user).count(), 0)
        # The session must not have been advanced/linked to a half-written record either.
        self.session.refresh_from_db()
        self.assertEqual(self.session.stage, 'assessment')
        self.assertIsNone(self.session.triage_record)
