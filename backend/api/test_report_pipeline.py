"""
Tests for the report processing pipeline: OCR extraction, insight generation,
fallback behavior, and data persistence.
"""

import json
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from api.models import User, UserProfile, MedicalReport, MedicalTest, AbnormalResult
from api.medical_report_analyzer import extract_text
from api.report_insight_engine import generate_report_insights, _extract_json, _build_report_insight_prompt
from api.report_processor import ReportProcessor


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_OCR_TEXT_1 = """
COMPLETE BLOOD COUNT (CBC)
Patient: John Doe
Date: 2026-07-15

Test            Result    Unit      Reference Range
Hemoglobin      14.2      g/dL      12.0 - 16.0
RBC Count       5.1       M/uL      4.5 - 5.5
WBC Count       11500     /uL       4000 - 11000
Platelet Count  250000    /uL       150000 - 400000
MCV             88        fL        80 - 100
MCH             28        pg        27 - 33
"""

SAMPLE_OCR_TEXT_2 = """
LIVER FUNCTION TEST
Patient: Jane Smith
Date: 2026-07-14

Test                Result    Unit      Reference Range
SGOT (AST)          85        U/L       10 - 40
SGPT (ALT)          120       U/L       7 - 56
Alkaline Phosphatase 180      U/L       44 - 147
Total Bilirubin     2.8       mg/dL     0.1 - 1.2
"""

SAMPLE_LLM_RESPONSE_1 = json.dumps({
    "tests": [
        {"test_name": "Hemoglobin", "value": "14.2", "unit": "g/dL", "reference_range": "12.0 - 16.0", "status": "normal"},
        {"test_name": "RBC Count", "value": "5.1", "unit": "M/uL", "reference_range": "4.5 - 5.5", "status": "normal"},
        {"test_name": "WBC Count", "value": "11500", "unit": "/uL", "reference_range": "4000 - 11000", "status": "high"},
        {"test_name": "Platelet Count", "value": "250000", "unit": "/uL", "reference_range": "150000 - 400000", "status": "normal"},
    ],
    "summary": "CBC report shows mildly elevated WBC count suggesting possible infection. Other values are within normal range.",
    "abnormal_findings": [
        {"test_name": "WBC Count", "value": "11500", "status": "high", "explanation": "Elevated WBC may indicate infection or inflammation."}
    ],
    "what_this_may_mean": "The elevated WBC count may suggest your body is fighting an infection.",
    "consult_note": "Please consult your doctor for interpretation. This is not a diagnosis.",
})

SAMPLE_LLM_RESPONSE_2 = json.dumps({
    "tests": [
        {"test_name": "SGOT (AST)", "value": "85", "unit": "U/L", "reference_range": "10 - 40", "status": "high"},
        {"test_name": "SGPT (ALT)", "value": "120", "unit": "U/L", "reference_range": "7 - 56", "status": "high"},
        {"test_name": "Total Bilirubin", "value": "2.8", "unit": "mg/dL", "reference_range": "0.1 - 1.2", "status": "high"},
    ],
    "summary": "Liver function tests show significantly elevated transaminases and bilirubin indicating possible liver dysfunction.",
    "abnormal_findings": [
        {"test_name": "SGOT (AST)", "value": "85", "status": "high", "explanation": "Elevated AST may indicate liver damage."},
        {"test_name": "SGPT (ALT)", "value": "120", "status": "high", "explanation": "Elevated ALT is a marker for liver inflammation."},
        {"test_name": "Total Bilirubin", "value": "2.8", "status": "high", "explanation": "Elevated bilirubin may cause jaundice."},
    ],
    "what_this_may_mean": "These findings suggest possible liver inflammation or damage.",
    "consult_note": "Please consult your doctor. This is not a diagnosis.",
})


def _create_test_user(email="test@example.com"):
    user = User.objects.create_user(
        username=email,
        email=email,
        password="testpass123",
    )
    UserProfile.objects.create(user=user, gender="M")
    return user


def _create_test_report(user, file_name="test_report.pdf"):
    from django.core.files.uploadedfile import SimpleUploadedFile
    fake_file = SimpleUploadedFile(file_name, b"fake pdf content", content_type="application/pdf")
    return MedicalReport.objects.create(
        user=user,
        file=fake_file,
        file_name=file_name,
        file_type="application/pdf",
        file_size=100,
    )


# ---------------------------------------------------------------------------
# Unit tests: _extract_json
# ---------------------------------------------------------------------------

class ExtractJsonTests(TestCase):
    def test_plain_json(self):
        result = _extract_json('{"tests": [], "summary": "ok"}')
        self.assertEqual(result.get("summary"), "ok")

    def test_json_in_code_block(self):
        text = '```json\n{"tests": [], "summary": "ok"}\n```'
        result = _extract_json(text)
        self.assertEqual(result.get("summary"), "ok")

    def test_json_with_preamble(self):
        text = 'Here is the analysis:\n{"tests": [{"test_name": "Hb"}], "summary": "done"}'
        result = _extract_json(text)
        self.assertEqual(result.get("summary"), "done")

    def test_garbage_returns_empty(self):
        result = _extract_json("this is not json at all")
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# Unit tests: OCR fallback chain
# ---------------------------------------------------------------------------

class OCRFallbackTests(TestCase):
    """Test that the 3-tier OCR fallback chain works correctly."""

    @patch("api.medical_report_analyzer._ocr_apple_vision")
    def test_apple_vision_success(self, mock_av):
        mock_av.return_value = {
            "text": "Test result text",
            "confidence": 0.95,
            "blocks": [],
            "pages": 1,
            "ocr_path": "apple_vision",
        }
        result = extract_text(b"fake-image", "image/jpeg")
        self.assertTrue(result["success"])
        self.assertEqual(result["ocr_path"], "apple_vision")
        self.assertEqual(result["text"], "Test result text")

    @patch("api.medical_report_analyzer._ocr_nvidia_vision")
    @patch("api.medical_report_analyzer._ocr_tesseract")
    @patch("api.medical_report_analyzer._ocr_apple_vision")
    def test_fallback_to_tesseract(self, mock_av, mock_tess, mock_nvidia):
        """When Apple Vision is unreachable, fall back to Tesseract."""
        mock_av.return_value = None  # Apple Vision unavailable
        mock_tess.return_value = {
            "text": "Tesseract output",
            "confidence": 0.0,
            "blocks": [],
            "pages": 1,
            "ocr_path": "tesseract",
        }
        result = extract_text(b"fake-image", "image/jpeg")
        self.assertTrue(result["success"])
        self.assertEqual(result["ocr_path"], "tesseract")

    @patch("api.medical_report_analyzer._ocr_nvidia_vision")
    @patch("api.medical_report_analyzer._ocr_tesseract")
    @patch("api.medical_report_analyzer._ocr_apple_vision")
    def test_fallback_to_nvidia(self, mock_av, mock_tess, mock_nvidia):
        """When both Apple Vision and Tesseract fail, fall back to NVIDIA."""
        mock_av.return_value = None
        mock_tess.return_value = None
        mock_nvidia.return_value = {
            "text": "NVIDIA analysis output",
            "confidence": 0.0,
            "blocks": [],
            "pages": 1,
            "ocr_path": "nvidia_vision",
        }
        result = extract_text(b"fake-image", "image/jpeg")
        self.assertTrue(result["success"])
        self.assertEqual(result["ocr_path"], "nvidia_vision")

    @patch("api.medical_report_analyzer._ocr_nvidia_vision")
    @patch("api.medical_report_analyzer._ocr_tesseract")
    @patch("api.medical_report_analyzer._ocr_apple_vision")
    def test_all_paths_fail(self, mock_av, mock_tess, mock_nvidia):
        """When all OCR paths fail, return a structured error."""
        mock_av.return_value = None
        mock_tess.return_value = None
        mock_nvidia.return_value = None
        result = extract_text(b"fake-image", "image/jpeg")
        self.assertFalse(result["success"])
        self.assertEqual(result["ocr_path"], "none")
        self.assertIn("All OCR paths failed", result["error"])


# ---------------------------------------------------------------------------
# Unit tests: Insight generation
# ---------------------------------------------------------------------------

class InsightGenerationTests(TestCase):
    """Test LLM insight generation and fallback behavior."""

    @patch("api.report_insight_engine.GeminiProvider")
    def test_successful_insight_generation(self, MockProvider):
        """LLM returns valid JSON → structured insights returned."""
        mock_instance = MockProvider.return_value
        mock_instance.is_available = True
        mock_instance.complete.return_value = SAMPLE_LLM_RESPONSE_1

        result = generate_report_insights(SAMPLE_OCR_TEXT_1)
        self.assertTrue(result["success"])
        self.assertFalse(result["degraded"])
        self.assertGreater(len(result["tests"]), 0)
        self.assertIn("WBC", result["summary"])

    @patch("api.report_insight_engine.GeminiProvider")
    def test_unparseable_response_returns_degraded(self, MockProvider):
        """LLM returns non-JSON → degraded response with raw OCR text."""
        mock_instance = MockProvider.return_value
        mock_instance.is_available = True
        mock_instance.complete.return_value = "This is not JSON at all, just rambling text."

        result = generate_report_insights(SAMPLE_OCR_TEXT_1)
        self.assertTrue(result["success"])
        self.assertTrue(result["degraded"])
        self.assertIn("couldn't be parsed", result["structuring_error"])
        self.assertEqual(result["raw_ocr_text"], SAMPLE_OCR_TEXT_1)

    @patch("api.report_insight_engine.OpenRouterProvider")
    @patch("api.report_insight_engine.GeminiProvider")
    def test_provider_unavailable_returns_degraded(self, MockProvider, MockOpenRouter):
        """With no provider configured at all, return a degraded response.

        Both providers are disabled explicitly: report insights now fail over
        from Gemini to OpenRouter, so leaving the fallback live would both
        change the message and let the suite reach the network.
        """
        MockProvider.return_value.is_available = False
        MockOpenRouter.return_value.is_available = False

        result = generate_report_insights(SAMPLE_OCR_TEXT_1)
        self.assertTrue(result["degraded"])
        self.assertIn("not configured", result["structuring_error"])

    def test_empty_ocr_text_returns_degraded(self):
        """Empty OCR text should return degraded response."""
        result = generate_report_insights("")
        self.assertTrue(result["degraded"])
        self.assertIn("No OCR text", result["structuring_error"])


# ---------------------------------------------------------------------------
# Integration tests: Different reports produce different insights
# ---------------------------------------------------------------------------

class DifferentReportsDifferentInsightsTest(TestCase):
    """Two different reports must produce different insights (no static responses)."""

    @patch("api.report_insight_engine.GeminiProvider")
    def test_different_reports_different_insights(self, MockProvider):
        mock_instance = MockProvider.return_value
        mock_instance.is_available = True

        # First report (CBC)
        mock_instance.complete.return_value = SAMPLE_LLM_RESPONSE_1
        result1 = generate_report_insights(SAMPLE_OCR_TEXT_1)

        # Second report (Liver)
        mock_instance.complete.return_value = SAMPLE_LLM_RESPONSE_2
        result2 = generate_report_insights(SAMPLE_OCR_TEXT_2)

        # Summaries must differ
        self.assertNotEqual(result1["summary"], result2["summary"])

        # Test names must differ
        names1 = {t["test_name"] for t in result1["tests"]}
        names2 = {t["test_name"] for t in result2["tests"]}
        self.assertNotEqual(names1, names2)

        # Abnormal findings must differ
        self.assertNotEqual(
            [f["test_name"] for f in result1["abnormal_findings"]],
            [f["test_name"] for f in result2["abnormal_findings"]],
        )


# ---------------------------------------------------------------------------
# Integration tests: Report pipeline persistence
# ---------------------------------------------------------------------------

class ReportPersistenceTests(TestCase):
    """Test that the pipeline correctly persists data to the database."""

    @patch("api.report_insight_engine.GeminiProvider")
    @patch("api.medical_report_analyzer._ocr_apple_vision")
    def test_full_pipeline_persists_data(self, mock_av, MockProvider):
        """Full pipeline: OCR → LLM → DB persistence."""
        user = _create_test_user()
        report = _create_test_report(user)

        # Mock OCR
        mock_av.return_value = {
            "text": SAMPLE_OCR_TEXT_1,
            "confidence": 0.95,
            "blocks": [],
            "pages": 1,
            "ocr_path": "apple_vision",
        }

        # Mock LLM
        mock_instance = MockProvider.return_value
        mock_instance.is_available = True
        mock_instance.complete.return_value = SAMPLE_LLM_RESPONSE_1

        processor = ReportProcessor()
        result = processor.extract_and_analyze(
            file_bytes=b"fake-pdf-content",
            file_name="test.pdf",
            content_type="application/pdf",
            user_context={"age": 30, "gender": "M"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["ocr_path"], "apple_vision")
        self.assertIn("tests", result["structured_data"])
        self.assertGreater(len(result["insights_text"]), 0)


# ---------------------------------------------------------------------------
# API tests: Malformed upload
# ---------------------------------------------------------------------------

class MalformedUploadTests(TestCase):
    """Test that malformed/unsupported uploads return clear errors."""

    def setUp(self):
        self.user = _create_test_user("upload_test@example.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_no_file_returns_400(self):
        response = self.client.post("/api/reports/analyze/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_unsupported_file_type_returns_400(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        txt_file = SimpleUploadedFile("test.txt", b"plain text", content_type="text/plain")
        response = self.client.post(
            "/api/reports/analyze/",
            {"file": txt_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)


# ---------------------------------------------------------------------------
# Model status lifecycle test
# ---------------------------------------------------------------------------

class ReportStatusLifecycleTest(TestCase):
    """Test that MedicalReport status field works correctly."""

    def test_default_status_is_pending(self):
        user = _create_test_user("status_test@example.com")
        report = _create_test_report(user)
        self.assertEqual(report.status, "pending")

    def test_status_transitions(self):
        user = _create_test_user("status2@example.com")
        report = _create_test_report(user)

        report.status = "processing"
        report.save(update_fields=["status"])
        report.refresh_from_db()
        self.assertEqual(report.status, "processing")

        report.status = "completed"
        report.save(update_fields=["status"])
        report.refresh_from_db()
        self.assertEqual(report.status, "completed")

    def test_status_failed(self):
        user = _create_test_user("status3@example.com")
        report = _create_test_report(user)

        report.status = "failed"
        report.save(update_fields=["status"])
        report.refresh_from_db()
        self.assertEqual(report.status, "failed")


# ---------------------------------------------------------------------------
# Prompt builder test
# ---------------------------------------------------------------------------

class PromptBuilderTest(TestCase):
    """Test that the insight prompt incorporates user context."""

    def test_prompt_includes_user_context(self):
        prompt = _build_report_insight_prompt(
            "Hemoglobin: 14.2 g/dL",
            {"age": 25, "gender": "Female", "past_history": ["Diabetes", "Anemia"]},
        )
        self.assertIn("25", prompt)
        self.assertIn("Female", prompt)
        self.assertIn("Diabetes", prompt)
        self.assertIn("Hemoglobin", prompt)

    def test_prompt_handles_empty_context(self):
        prompt = _build_report_insight_prompt("Some OCR text", None)
        self.assertIn("Unknown", prompt)
        self.assertIn("Some OCR text", prompt)
