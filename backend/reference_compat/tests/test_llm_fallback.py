import unittest
from unittest.mock import Mock
from unittest.mock import patch

from reference_compat.assess import integrate_report_and_run_assessment


class LLMFallbackTests(unittest.TestCase):
    def test_empty_input_uses_reference_fallback(self):
        client = Mock()
        client.is_available.return_value = False
        result = integrate_report_and_run_assessment(None, {}, {}, llm_client=client)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["assessment"]["risk_level"], "Medium")
        client.call.assert_not_called()

    def test_missing_client_returns_medium_unknown(self):
        client = Mock()
        client.is_available.return_value = False
        result = integrate_report_and_run_assessment(
            None, {"symptoms_text": "mild cough"}, {}, llm_client=client
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["assessment"]["risk_level"], "Medium")
        self.assertEqual(
            result["assessment"]["possible_conditions"],
            [{"disease": "Unknown", "confidence": 0.3}],
        )
        client.call.assert_not_called()

    def test_malformed_json_uses_fallback_path(self):
        client = Mock()
        client.is_available.return_value = True
        client.call.return_value = "not json"
        with patch("reference_compat.assess.get_fallback_response", wraps=lambda message: {
            "possible_conditions": [{"disease": "Unknown", "confidence": 0.3}],
            "risk_level": "Medium",
            "risk_proba": 0.3,
            "reason": message,
            "recommendations": ["Consult physician", "Monitor symptoms", "Visit PHC if worsens"],
        }) as fallback:
            result = integrate_report_and_run_assessment(
                None, {"symptoms_text": "mild cough"}, {}, llm_client=client
            )
            fallback.assert_called_once_with("LLM returned unparsable JSON")
        self.assertEqual(result["assessment"]["risk_level"], "Medium")
        self.assertEqual(
            result["assessment"]["possible_conditions"][0]["disease"],
            "Unknown",
        )
        client.call.assert_called_once()
