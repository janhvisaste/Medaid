import unittest
from unittest.mock import Mock

from reference_compat.assess import integrate_report_and_run_assessment


class ReferencePromptSnapshotTest(unittest.TestCase):
    def test_prompt_matches_reference_snapshot(self):
        client = Mock()
        client.is_available.return_value = True
        client.call.return_value = (
            '{"risk_level":"Low","risk_proba":0.2,"reason":"ok",'
            '"possible_conditions":[],"recommendations":[]}'
        )
        integrate_report_and_run_assessment(
            {"medical_tests": [{"test_name": "Hb", "value": 12, "status": "normal"}]},
            {"symptoms_text": "fever and cough", "city": "Pune"},
            {"past_history": {"allergies": "none"}},
            llm_client=client,
        )

        expected = """
You are a clinical triage assistant. You must respond with ONLY a valid JSON object and nothing else. Do not include any explanations, markdown formatting, or additional text.

CRITICAL INSTRUCTIONS:
1. Your entire response must be a single valid JSON object
2. Do not wrap the JSON in markdown code blocks (no MARKDOWN_FENCEjson)
3. Do not add any text before or after the JSON
4. Ensure all JSON keys are double-quoted strings
5. Ensure all string values are properly escaped
6. Ensure the JSON is syntactically correct

The JSON object must have exactly these keys:
- "possible_conditions": an array of objects, each with "disease" (string) and "confidence" (number between 0 and 1)
- "risk_level": one of these exact strings: "Low", "Medium", "High", "Emergency"
- "risk_proba": a number between 0 and 1
- "reason": a string with a short explanation (2-3 sentences)
- "recommendations": an array of strings (actionable recommendations, max 6)

Example response format (DO NOT INCLUDE THIS EXAMPLE IN YOUR RESPONSE):
{
  "possible_conditions": [
    {"disease": "Common Cold", "confidence": 0.8},
    {"disease": "Flu", "confidence": 0.2}
  ],
  "risk_level": "Low",
  "risk_proba": 0.1,
  "reason": "Symptoms suggest a minor viral infection. Rest and hydration are recommended.",
  "recommendations": [
    "Rest and drink plenty of fluids",
    "Monitor symptoms for worsening",
    "Contact a doctor if fever persists beyond 3 days"
  ]
}

Patient information:
Symptoms: fever and cough
Report summary: Hb: 12 (normal)
Past medical history:
allergies: none
Location: Pune

Respond ONLY with the JSON object. No other text, no markdown, no explanations. CRITICAL: Valid JSON only!
""".replace("MARKDOWN_FENCE", chr(96) * 3)

        self.assertEqual(client.call.call_args.args[0], expected)
