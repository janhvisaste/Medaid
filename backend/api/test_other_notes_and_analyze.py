"""
Tests for:
  - other_notes field: persistence, prompt injection, empty-omission, character limit
  - Combined-context report analysis: different histories → different insights,
    no-history case, pending-report case, provider-failure degraded fallback
"""

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from api.models import (
    MedicalReport, MedicalTest, AbnormalResult, User, UserProfile,
)
from api.report_insight_engine import (
    _build_report_insight_prompt,
    _build_combined_report_prompt,
    build_report_insight_context,
    generate_combined_report_insights,
    generate_report_insights,
)
from api.triage_engine_v2 import TriageEngineV2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(email: str, other_notes: str | None = None, conditions: list | None = None):
    user = User.objects.create_user(
        username=email, email=email, password="testpass123"
    )
    profile = UserProfile.objects.create(
        user=user,
        gender="F",
        other_notes=other_notes,
        past_history={"conditions": conditions or []},
    )
    return user, profile


def _fake_report(user, extracted_text="", status_val="completed"):
    from django.core.files.uploadedfile import SimpleUploadedFile
    fake_file = SimpleUploadedFile("test.pdf", b"%PDF-test", content_type="application/pdf")
    return MedicalReport.objects.create(
        user=user,
        file=fake_file,
        file_name="test.pdf",
        file_type="application/pdf",
        file_size=9,
        extracted_text=extracted_text,
        status=status_val,
    )


# ---------------------------------------------------------------------------
# Part 1: other_notes persistence
# ---------------------------------------------------------------------------

class OtherNotesPersistenceTest(TestCase):
    """Save health history with other_notes → persists, round-trips on reload."""

    def setUp(self):
        self.user, _ = _make_user("persist@example.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_other_notes_saved_and_returned(self):
        resp = self.client.post(
            "/api/profile/update-history/",
            {
                "conditions": [{"name": "Diabetes", "selected": True, "notes": "Type 2"}],
                "other_notes": "Penicillin allergy. Appendix removed 2019.",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["other_notes"], "Penicillin allergy. Appendix removed 2019.")

        # Round-trip via profile endpoint
        profile_resp = self.client.get("/api/profile/")
        self.assertEqual(profile_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            profile_resp.data["other_notes"],
            "Penicillin allergy. Appendix removed 2019.",
        )

    def test_conditions_only_save_does_not_clear_other_notes(self):
        """If other_notes is not in the payload, the existing value must survive."""
        self.user.profile.other_notes = "Do not clear me."
        self.user.profile.save(update_fields=["other_notes"])

        # Save conditions only — no other_notes key in payload
        resp = self.client.post(
            "/api/profile/update-history/",
            {"conditions": []},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.other_notes, "Do not clear me.")

    def test_blank_other_notes_stored_as_none(self):
        resp = self.client.post(
            "/api/profile/update-history/",
            {"conditions": [], "other_notes": "   "},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertIsNone(self.user.profile.other_notes)


# ---------------------------------------------------------------------------
# Part 2: other_notes → prompt injection
# ---------------------------------------------------------------------------

class OtherNotesPromptInjectionTest(TestCase):
    """User with other_notes → assembled prompts contain that text."""

    def test_triage_prompt_includes_other_notes(self):
        engine = TriageEngineV2.__new__(TriageEngineV2)  # bypass __init__
        user_data = {
            "age": 35,
            "gender": "Female",
            # past_history from DB comes as list of dicts
            "past_history": [{"name": "Diabetes", "notes": "Type 2"}],
            "other_notes": "Penicillin allergy. Mother had breast cancer.",
        }
        prompt = engine._build_assessment_prompt("Cough", user_data, "", "")
        self.assertIn("Penicillin allergy", prompt)
        self.assertIn("Mother had breast cancer", prompt)
        self.assertIn("Additional info from patient", prompt)

    def test_report_insight_prompt_includes_other_notes(self):
        prompt = _build_report_insight_prompt(
            "Hemoglobin 9.2 g/dL",
            {"age": 28, "gender": "F", "past_history": [], "other_notes": "Thalassaemia trait."},
        )
        self.assertIn("Thalassaemia trait", prompt)
        self.assertIn("Additional info from patient", prompt)

    def test_combined_report_prompt_includes_other_notes(self):
        prompt = _build_combined_report_prompt(
            report_data={
                "file_name": "CBC.pdf",
                "extracted_text": "Hemoglobin 9.2 g/dL",
                "tests": [],
                "abnormal_findings": [],
            },
            user_context={
                "age": 28,
                "gender": "F",
                "past_history": [],
                "other_notes": "Thalassaemia trait, avoid iron supplements.",
                "past_triages": [],
                "prior_report_findings": [],
            },
        )
        self.assertIn("Thalassaemia trait", prompt)
        self.assertIn("Additional notes from patient", prompt)

    def test_dietary_context_includes_other_notes(self):
        """build_dietary_context returns other_notes in profile dict."""
        from api.dietary_service import build_dietary_context
        user, profile = _make_user(
            "dietary@example.com",
            other_notes="Lactose intolerant. Vegetarian.",
        )
        ctx = build_dietary_context(user)
        self.assertEqual(ctx["profile"]["other_notes"], "Lactose intolerant. Vegetarian.")


# ---------------------------------------------------------------------------
# Part 3: empty other_notes → no prompt noise
# ---------------------------------------------------------------------------

class EmptyOtherNotesNoNoiseTest(TestCase):
    """Empty other_notes must not inject 'Additional info: None' into prompts."""

    def test_triage_prompt_omits_when_empty(self):
        engine = TriageEngineV2.__new__(TriageEngineV2)
        user_data = {"age": 40, "gender": "M", "past_history": [], "other_notes": ""}
        prompt = engine._build_assessment_prompt("Headache", user_data, "", "")
        # 'History: None' is expected and fine — what must be ABSENT is the 'Additional info' line
        self.assertNotIn("Additional info from patient", prompt)

    def test_triage_prompt_omits_when_none(self):
        engine = TriageEngineV2.__new__(TriageEngineV2)
        user_data = {"age": 40, "gender": "M", "past_history": [], "other_notes": None}
        prompt = engine._build_assessment_prompt("Headache", user_data, "", "")
        self.assertNotIn("Additional info", prompt)

    def test_report_insight_prompt_omits_when_none(self):
        prompt = _build_report_insight_prompt("Hb 14.2", {"other_notes": None})
        self.assertNotIn("Additional info", prompt)

    def test_combined_prompt_omits_when_empty(self):
        prompt = _build_combined_report_prompt(
            report_data={"file_name": "r.pdf", "extracted_text": "Hb 14.2", "tests": [], "abnormal_findings": []},
            user_context={"age": 30, "gender": "M", "past_history": [], "other_notes": "",
                          "past_triages": [], "prior_report_findings": []},
        )
        self.assertNotIn("Additional notes from patient", prompt)


# ---------------------------------------------------------------------------
# Part 4: character limit enforcement
# ---------------------------------------------------------------------------

class OtherNotesLimitTest(TestCase):
    def setUp(self):
        self.user, _ = _make_user("limit@example.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_over_limit_returns_400(self):
        resp = self.client.post(
            "/api/profile/update-history/",
            {"conditions": [], "other_notes": "x" * 2001},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("2000", resp.data["error"])

    def test_exact_limit_saves_successfully(self):
        resp = self.client.post(
            "/api/profile/update-history/",
            {"conditions": [], "other_notes": "x" * 2000},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_non_string_returns_400(self):
        resp = self.client.post(
            "/api/profile/update-history/",
            {"conditions": [], "other_notes": 12345},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Part 5: combined context → different histories → different insights
# ---------------------------------------------------------------------------

SAMPLE_REPORT_TEXT = """
COMPLETE BLOOD COUNT
Hemoglobin: 9.2 g/dL (ref 12.0-16.0) LOW
WBC: 4500 /uL (ref 4000-11000) NORMAL
Platelets: 420000 /uL (ref 150000-400000) HIGH
"""

LLM_RESPONSE_DIABETIC = json.dumps({
    "tests": [{"test_name": "Hemoglobin", "value": "9.2", "unit": "g/dL",
               "reference_range": "12.0-16.0", "status": "low"}],
    "summary": "Anaemia noted. Given your Diabetes, anaemia can worsen glycaemic control.",
    "abnormal_findings": [{"test_name": "Hemoglobin", "value": "9.2", "status": "low",
                           "explanation": "Low Hb in a diabetic patient may indicate anaemia of chronic disease."}],
    "what_this_may_mean": "Your Diabetes may be contributing to this anaemia. Discuss with your doctor.",
    "consult_note": "Not a diagnosis.",
})

LLM_RESPONSE_NO_HISTORY = json.dumps({
    "tests": [{"test_name": "Hemoglobin", "value": "9.2", "unit": "g/dL",
               "reference_range": "12.0-16.0", "status": "low"}],
    "summary": "Anaemia detected with no significant complicating history.",
    "abnormal_findings": [{"test_name": "Hemoglobin", "value": "9.2", "status": "low",
                           "explanation": "Low Hb; causes include iron deficiency or blood loss."}],
    "what_this_may_mean": "Anaemia with no known history. Further investigation recommended.",
    "consult_note": "Not a diagnosis.",
})


class CombinedContextInsightTest(TestCase):
    """Two users with different histories + same report → different insights."""

    @patch("api.report_insight_engine.GeminiProvider")
    def test_different_histories_produce_different_insights(self, MockProvider):
        mock = MockProvider.return_value
        mock.is_available = True

        # User A: has Diabetes
        mock.complete.return_value = LLM_RESPONSE_DIABETIC
        result_a = generate_combined_report_insights(
            report_data={"file_name": "cbc.pdf", "extracted_text": SAMPLE_REPORT_TEXT,
                         "tests": [], "abnormal_findings": []},
            user_context={"age": 45, "gender": "F",
                          "past_history": [{"name": "Diabetes"}],
                          "other_notes": None, "past_triages": [], "prior_report_findings": []},
        )

        # User B: no history
        mock.complete.return_value = LLM_RESPONSE_NO_HISTORY
        result_b = generate_combined_report_insights(
            report_data={"file_name": "cbc.pdf", "extracted_text": SAMPLE_REPORT_TEXT,
                         "tests": [], "abnormal_findings": []},
            user_context={"age": 45, "gender": "F", "past_history": [],
                          "other_notes": None, "past_triages": [], "prior_report_findings": []},
        )

        # Summaries must differ
        self.assertNotEqual(result_a["summary"], result_b["summary"])
        # Result A references Diabetes in the context
        self.assertIn("Diabetes", result_a["summary"] + result_a.get("what_this_may_mean", ""))

    @patch("api.report_insight_engine.GeminiProvider")
    def test_no_history_user_still_gets_valid_insight(self, MockProvider):
        mock = MockProvider.return_value
        mock.is_available = True
        mock.complete.return_value = LLM_RESPONSE_NO_HISTORY

        result = generate_combined_report_insights(
            report_data={"file_name": "cbc.pdf", "extracted_text": SAMPLE_REPORT_TEXT,
                         "tests": [], "abnormal_findings": []},
            user_context={"age": 30, "gender": "M", "past_history": [],
                          "other_notes": None, "past_triages": [], "prior_report_findings": []},
        )
        self.assertTrue(result["success"])
        self.assertFalse(result["degraded"])
        self.assertGreater(len(result["summary"]), 0)


# ---------------------------------------------------------------------------
# Part 6: pending report → 202
# ---------------------------------------------------------------------------

class ReportPendingStatusTest(TestCase):
    def setUp(self):
        self.user, _ = _make_user("pending@example.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("api.report_insight_engine.GeminiProvider")
    def test_pending_report_is_analyzed_not_blocked(self, MockProvider):
        """'pending' is the default status for every freshly uploaded report —
        it must be analyzed synchronously by this same request, not treated as
        a blocking in-progress state. Regression test: this guard used to also
        catch 'pending', and since nothing else ever moves a report off
        'pending', every fresh upload was permanently stuck returning 202."""
        mock = MockProvider.return_value
        mock.is_available = True
        mock.complete.return_value = LLM_RESPONSE_NO_HISTORY

        report = _fake_report(self.user, extracted_text=SAMPLE_REPORT_TEXT, status_val="pending")
        resp = self.client.post(
            "/api/reports/analyze-local/",
            {"report_id": report.id},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        report.refresh_from_db()
        self.assertEqual(report.status, "completed")

    def test_processing_report_returns_202(self):
        report = _fake_report(self.user, status_val="processing")
        resp = self.client.post(
            "/api/reports/analyze-local/",
            {"report_id": report.id},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)


# ---------------------------------------------------------------------------
# Part 7: provider failure → degraded fallback
# ---------------------------------------------------------------------------

class ProviderFailureDegradedTest(TestCase):
    @patch("api.report_insight_engine.OpenRouterProvider")
    @patch("api.report_insight_engine.GeminiProvider")
    def test_provider_unavailable_returns_degraded(self, MockProvider, MockOpenRouter):
        # Both disabled: insights now fail over to OpenRouter, so the fallback
        # must be stubbed out or this asserts the wrong path and hits the network.
        MockOpenRouter.return_value.is_available = False
        mock = MockProvider.return_value
        mock.is_available = False

        result = generate_combined_report_insights(
            report_data={"file_name": "cbc.pdf", "extracted_text": SAMPLE_REPORT_TEXT,
                         "tests": [], "abnormal_findings": []},
            user_context={"age": 30, "gender": "M", "past_history": [],
                          "other_notes": None, "past_triages": [], "prior_report_findings": []},
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["degraded"])
        self.assertIn("not configured", result["structuring_error"])

    @patch("api.report_insight_engine.GeminiProvider")
    def test_garbage_llm_response_returns_degraded(self, MockProvider):
        mock = MockProvider.return_value
        mock.is_available = True
        mock.complete.return_value = "This is not valid JSON, just prose."

        result = generate_combined_report_insights(
            report_data={"file_name": "cbc.pdf", "extracted_text": SAMPLE_REPORT_TEXT,
                         "tests": [], "abnormal_findings": []},
            user_context={"age": 30, "gender": "M", "past_history": [],
                          "other_notes": None, "past_triages": [], "prior_report_findings": []},
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["degraded"])

    @patch("api.report_insight_engine.GeminiProvider")
    def test_no_report_content_returns_degraded(self, MockProvider):
        """Report with no text and no tests → degraded, not a crash."""
        result = generate_combined_report_insights(
            report_data={"file_name": "empty.pdf", "extracted_text": "",
                         "tests": [], "abnormal_findings": []},
            user_context={"age": 30, "gender": "M", "past_history": [],
                          "other_notes": None, "past_triages": [], "prior_report_findings": []},
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["degraded"])
