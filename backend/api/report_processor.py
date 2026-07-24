"""
Report Processor — orchestrates OCR extraction and insight generation.

Delegates to:
  - medical_report_analyzer.extract_text() for OCR (3-tier fallback)
  - report_insight_engine.generate_report_insights() for LLM structuring
"""

import logging
from typing import Dict, Optional

from .medical_report_analyzer import extract_text
from .report_insight_engine import generate_report_insights

logger = logging.getLogger(__name__)


class ReportProcessor:
    """Orchestrates OCR text extraction and LLM insight generation."""

    def extract_and_analyze(
        self,
        file_bytes: bytes,
        file_name: str,
        content_type: str = "",
        user_context: Optional[Dict] = None,
        *,
        request_id: str | None = None,
        user_id: int | None = None,
    ) -> Dict:
        """
        Full pipeline: OCR extract → LLM structure → return results.

        Args:
            file_bytes: Raw file content
            file_name: Original filename (used for type inference)
            content_type: MIME type (e.g., "application/pdf", "image/jpeg")
            user_context: Optional dict with age, gender, past_history
            request_id: For log correlation
            user_id: For log correlation

        Returns:
            {
                "success": bool,
                "extracted_text": str,           # Raw OCR text
                "ocr_path": str,                 # Which OCR path served
                "ocr_confidence": float,
                "structured_data": dict,         # LLM-structured tests + insights
                "insights_text": str,            # Narrative summary
                "error": str | None,
            }
        """
        # Resolve content type if not provided
        if not content_type:
            content_type = self._infer_content_type(file_name)

        # Step 1: OCR extraction
        ocr_result = extract_text(file_bytes, content_type, file_name)

        if not ocr_result.get("success"):
            logger.warning(
                "report_processor.ocr_failed",
                extra={"request_id": request_id, "error": ocr_result.get("error")},
            )
            return {
                "success": False,
                "extracted_text": "",
                "ocr_path": ocr_result.get("ocr_path", "none"),
                "ocr_confidence": 0.0,
                "structured_data": {},
                "insights_text": "",
                "error": ocr_result.get("error", "OCR extraction failed"),
            }

        raw_text = ocr_result.get("text", "")
        ocr_path = ocr_result.get("ocr_path", "unknown")
        ocr_confidence = ocr_result.get("confidence", 0.0)

        logger.info(
            "report_processor.ocr_complete",
            extra={
                "request_id": request_id,
                "ocr_path": ocr_path,
                "text_length": len(raw_text),
                "confidence": ocr_confidence,
            },
        )

        # Step 2: LLM insight generation
        insight_result = generate_report_insights(
            raw_text,
            user_context,
            request_id=request_id,
            user_id=user_id,
        )

        # Build narrative insights text
        insights_text = self._build_insights_narrative(insight_result)

        return {
            "success": True,
            "extracted_text": raw_text,
            "ocr_path": ocr_path,
            "ocr_confidence": ocr_confidence,
            "structured_data": insight_result,
            "insights_text": insights_text,
            "error": None,
        }

    def _build_insights_narrative(self, insight_result: Dict) -> str:
        """Build a human-readable narrative from structured insights."""
        parts = []

        summary = insight_result.get("summary", "")
        if summary:
            parts.append(summary)

        abnormal = insight_result.get("abnormal_findings", [])
        if abnormal:
            parts.append("\n**Abnormal Findings:**")
            for finding in abnormal:
                name = finding.get("test_name", "")
                value = finding.get("value", "")
                status = finding.get("status", "")
                explanation = finding.get("explanation", "")
                parts.append(f"- {name}: {value} ({status}) — {explanation}")

        meaning = insight_result.get("what_this_may_mean", "")
        if meaning:
            parts.append(f"\n**What this may mean:**\n{meaning}")

        consult = insight_result.get("consult_note", "")
        if consult:
            parts.append(f"\n{consult}")

        if insight_result.get("degraded"):
            parts.append(
                "\n⚠️ Note: Full structured analysis was not possible. "
                "The raw OCR text has been preserved for manual review."
            )

        return "\n".join(parts) if parts else "Report processed successfully."

    def _infer_content_type(self, file_name: str) -> str:
        """Infer MIME type from file extension."""
        name = (file_name or "").lower()
        if name.endswith(".pdf"):
            return "application/pdf"
        if name.endswith(".png"):
            return "image/png"
        if name.endswith(".webp"):
            return "image/webp"
        if name.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        if name.endswith((".tiff", ".tif")):
            return "image/tiff"
        return "image/jpeg"  # default


def get_report_processor():
    """Get a ReportProcessor instance."""
    return ReportProcessor()
