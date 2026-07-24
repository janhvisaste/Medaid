import unittest
from unittest.mock import Mock

from reference_compat.assess import integrate_report_and_run_assessment


class EndToEndReferenceFixtures(unittest.TestCase):
    def test_keyword_wins_before_report_threshold_and_llm(self):
        client = Mock()
        client.is_available.return_value = True
        result = integrate_report_and_run_assessment(
            {"medical_tests": [{"test_name": "SpO2", "value": 89}]},
            {"symptoms_text": "not breathing"},
            {},
            llm_client=client,
        )
        self.assertEqual(result["assessment"]["risk_level"], "Emergency")
        client.call.assert_not_called()

    def test_report_threshold_skips_llm(self):
        client = Mock()
        client.is_available.return_value = True
        result = integrate_report_and_run_assessment(
            {"medical_tests": [{"test_name": "oxygen saturation", "value": 89}]},
            {"symptoms_text": ""},
            {},
            llm_client=client,
        )
        self.assertEqual(result["assessment"]["risk_level"], "Emergency")
        client.call.assert_not_called()

    def test_report_only_input_is_accepted(self):
        client = Mock()
        client.is_available.return_value = True
        client.call.return_value = (
            '{"risk_level":"Low","risk_proba":0.2,"reason":"ok",'
            '"possible_conditions":[],"recommendations":[]}'
        )
        result = integrate_report_and_run_assessment(
            {"medical_tests": [{"test_name": "Hb", "value": 12, "status": "normal"}]},
            {"symptoms_text": ""},
            {"past_history": {"allergies": "none"}},
            llm_client=client,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["assessment"]["risk_level"], "Low")
        self.assertEqual(result["assessment"]["risk_proba"], 0.2)
        client.call.assert_called_once()

    def test_successful_response_preserves_reference_schema(self):
        client = Mock()
        client.is_available.return_value = True
        client.call.return_value = (
            '{"risk_level":"High","risk_proba":"0.8","reason":"reason",'
            '"possible_conditions":[{"disease":"Flu","confidence":"0.7"}],'
            '"recommendations":["See a doctor"]}'
        )
        result = integrate_report_and_run_assessment(
            None, {"symptoms_text": "fever", "city": "Pune"}, {}, llm_client=client
        )
        assessment = result["assessment"]
        self.assertEqual(
            set(assessment),
            {"possible_conditions", "risk_level", "risk_proba", "reason", "recommendations"},
        )
        self.assertEqual(assessment["risk_level"], "High")
        self.assertEqual(
            assessment["possible_conditions"],
            [{"disease": "Flu", "confidence": 0.7}],
        )
