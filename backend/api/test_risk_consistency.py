"""Regression tests for Fix 4: consistency check between emergency keywords
and the LLM's own risk tier, plus the low-confidence human-review rule.
"""
import json

from django.test import SimpleTestCase

from .triage_engine_v2 import TriageEngineV2

EMERGENCY_TEXT = "I have severe chest pain and can't breathe"


class FakeProvider:
    def __init__(self, response_text, is_available=True):
        self.response_text = response_text
        self.is_available = is_available

    def complete(self, messages, model_id, temperature):
        return self.response_text


class StructureAssessmentRiskFlooringTests(SimpleTestCase):
    """Fix 1's assess() gate already intercepts emergency-keyword text before
    any LLM call, so _structure_assessment's own floor never fires through
    the public assess() API today. These tests exercise the floor directly,
    the way this codebase already tests other private helpers
    (see tests.py: TriageAndHospitalRoutingTests calling
    _build_assessment_prompt directly) - it's the safety net that protects
    the system if the upstream gate is ever bypassed, refactored, or removed.
    """

    def setUp(self):
        self.engine = TriageEngineV2(default_provider=FakeProvider("{}"), openrouter_provider=FakeProvider("{}"))

    def test_emergency_keyword_text_floors_low_risk_to_high(self):
        raw_assessment = {
            "risk_level": "low",
            "risk_probability": 0.2,
            "confidence": 0.8,
            "reasoning": "Model under-called this one.",
            "possible_conditions": [{"disease": "Viral illness", "confidence": 0.3}],
            "recommendations": ["Rest"],
        }
        structured = self.engine._structure_assessment(raw_assessment, EMERGENCY_TEXT)

        self.assertEqual(structured["risk_level"], "high")
        self.assertTrue(structured["requires_human_review"])

    def test_emergency_keyword_text_does_not_downgrade_already_high_risk(self):
        raw_assessment = {
            "risk_level": "emergency",
            "confidence": 0.9,
            "reasoning": "Correctly flagged.",
            "possible_conditions": [{"disease": "Cardiac event", "confidence": 0.4}],
            "recommendations": ["Call emergency services"],
        }
        structured = self.engine._structure_assessment(raw_assessment, EMERGENCY_TEXT)

        # Floor logic must never downgrade - 'emergency' stays 'emergency'.
        self.assertEqual(structured["risk_level"], "emergency")

    def test_non_emergency_text_does_not_floor_risk(self):
        raw_assessment = {
            "risk_level": "low",
            "confidence": 0.8,
            "reasoning": "Mild cold symptoms.",
            "possible_conditions": [{"disease": "Common cold", "confidence": 0.3}],
            "recommendations": ["Rest"],
        }
        structured = self.engine._structure_assessment(raw_assessment, "runny nose and mild cough")

        self.assertEqual(structured["risk_level"], "low")
        self.assertFalse(structured["requires_human_review"])

    def test_low_confidence_flags_human_review_regardless_of_risk_level(self):
        raw_assessment = {
            "risk_level": "low",
            "confidence": 0.15,
            "reasoning": "Uncertain.",
            "possible_conditions": [{"disease": "Common cold", "confidence": 0.3}],
            "recommendations": ["Rest"],
        }
        structured = self.engine._structure_assessment(raw_assessment, "runny nose and mild cough")

        self.assertEqual(structured["risk_level"], "low")
        self.assertTrue(structured["requires_human_review"])

    def test_high_confidence_does_not_flag_human_review(self):
        raw_assessment = {
            "risk_level": "low",
            "confidence": 0.85,
            "reasoning": "Confident.",
            "possible_conditions": [{"disease": "Common cold", "confidence": 0.3}],
            "recommendations": ["Rest"],
        }
        structured = self.engine._structure_assessment(raw_assessment, "runny nose and mild cough")

        self.assertFalse(structured["requires_human_review"])


class AssessEndToEndEmergencyFloorTests(SimpleTestCase):
    """End-to-end via assess(): emergency-keyword text always yields
    risk_level >= 'high', even though the mocked LLM below is never actually
    consulted (Fix 1's gate intercepts first). This is the required contract
    from the caller's point of view - it must hold no matter which of the
    two safety nets is the one that actually fires.
    """

    def test_assess_yields_high_or_above_for_emergency_text_despite_low_mocked_response(self):
        low_risk_json = json.dumps({
            "risk_level": "low",
            "risk_probability": 0.1,
            "confidence": 0.9,
            "reasoning": "Model would have said this was mild.",
            "possible_conditions": [{"disease": "Viral illness", "confidence": 0.3}],
            "recommendations": ["Rest"],
        })
        engine = TriageEngineV2(
            default_provider=FakeProvider(low_risk_json),
            openrouter_provider=FakeProvider(low_risk_json),
        )

        result = engine.assess(EMERGENCY_TEXT, {"age": 30, "gender": "F", "past_history": []})

        self.assertIn(result["risk_level"], ("high", "emergency"))
