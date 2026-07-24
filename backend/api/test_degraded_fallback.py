"""Regression tests for Fix 3: degraded/failed LLM responses must not default
to risk_level='low', and must trigger clinician review via ClinicianAlert.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .llm_providers.base import ModelProviderError
from .models import ClinicianAlert, TriageRecord
from .safety.clinician_alerts import create_alert_for_triage_record
from .triage_engine_v2 import TriageEngineV2

User = get_user_model()


class FakeProvider:
    """Minimal provider double matching the LLMProvider contract."""

    def __init__(self, error=None, response_text=None, is_available=True):
        self.error = error
        self.response_text = response_text
        self.is_available = is_available

    def complete(self, messages, model_id, temperature):
        if self.error:
            raise self.error
        return self.response_text


class DegradedFallbackRiskLevelTests(SimpleTestCase):
    def test_provider_failure_does_not_default_to_low_risk(self):
        failing_provider = FakeProvider(error=ModelProviderError("boom"))
        engine = TriageEngineV2(default_provider=failing_provider, openrouter_provider=FakeProvider())

        result = engine.assess("fever and fatigue", {"age": 30, "gender": "F", "past_history": []})

        self.assertNotEqual(result["risk_level"], "low")
        self.assertEqual(result["risk_level"], "medium")
        self.assertTrue(result["requires_human_review"])
        self.assertTrue(result["degraded"])

    def test_malformed_json_does_not_default_to_low_risk(self):
        default_provider = FakeProvider(response_text="not valid json at all")
        engine = TriageEngineV2(default_provider=default_provider, openrouter_provider=FakeProvider())

        result = engine.assess("fever and fatigue", {"age": 30, "gender": "F", "past_history": []})

        self.assertNotEqual(result["risk_level"], "low")
        self.assertEqual(result["risk_level"], "medium")
        self.assertTrue(result["requires_human_review"])


class DegradedFallbackCreatesClinicianAlertTests(TestCase):
    """End-to-end: a degraded assessment persisted as a TriageRecord must
    result in a ClinicianAlert, exactly like a high/emergency one does."""

    def setUp(self):
        self.patient = User.objects.create_user(
            username='degraded_patient', password='password123',
            email='degraded_patient@example.com', role='patient'
        )
        self.clinician = User.objects.create_user(
            username='degraded_clinician', password='password123',
            email='degraded_clinician@example.com', role='clinician'
        )

    def test_degraded_medium_risk_record_creates_follow_up_alert(self):
        engine = TriageEngineV2(
            default_provider=FakeProvider(error=ModelProviderError("boom")),
            openrouter_provider=FakeProvider(),
        )
        assessment = engine.assess("fever and fatigue", {"age": 30, "gender": "F", "past_history": []})

        record = TriageRecord.objects.create(
            user=self.patient,
            current_symptoms="fever and fatigue",
            risk_level=assessment["risk_level"],
            reasoning=assessment["reasoning"],
            confidence=assessment["confidence"],
            requires_human_review=assessment["requires_human_review"],
        )

        alert = create_alert_for_triage_record(record)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, 'follow_up')
        self.assertEqual(alert.clinician, self.clinician)
        self.assertEqual(ClinicianAlert.objects.filter(patient=self.patient).count(), 1)

    def test_non_degraded_medium_risk_record_does_not_alert(self):
        # A normal, non-degraded 'medium' assessment (requires_human_review
        # False) must NOT alert - only degraded/flagged ones should.
        record = TriageRecord.objects.create(
            user=self.patient,
            current_symptoms="fever",
            risk_level='medium',
            reasoning='normal assessment',
            requires_human_review=False,
        )
        alert = create_alert_for_triage_record(record)
        self.assertIsNone(alert)
        self.assertEqual(ClinicianAlert.objects.filter(patient=self.patient).count(), 0)
