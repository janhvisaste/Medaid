import logging
from typing import Dict, Optional
from .medical_report_analyzer import get_medical_report_analyzer

logger = logging.getLogger(__name__)

def analyze_medical_report_local(
    file_bytes: bytes,
    file_type: str,
    gender: str = "male",
    mode: str = "ocr"
) -> Dict:
    """Analyze medical report using the Gemini adapter directly."""
    try:
        analyzer = get_medical_report_analyzer()
        # By passing file_bytes directly, we bypass any pipeline/OCR steps
        result = analyzer.analyze_report(file_bytes=file_bytes, file_type=file_type)
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Analysis failed"),
                "summary": {
                    "total_tests": 0,
                    "abnormal": 0,
                    "normal": 0,
                    "unknown": 0,
                    "critical_flags": 0,
                },
                "findings": [],
                "text_report": result.get("clinical_insights", ""),
                "clinical_insights": result.get("clinical_insights", ""),
            }

        text_result = result.get("clinical_insights") or result.get("markdown_report", "")
        return {
            "success": True,
            "error": None,
            "summary": {
                "total_tests": 0,
                "abnormal": 0,
                "normal": 0,
                "unknown": 0,
                "critical_flags": 0,
            },
            "findings": [],
            "text_report": text_result,
            "clinical_insights": text_result,
            "markdown_report": result.get("markdown_report", text_result),
            "json_data": result.get("json_data", {}),
            "extraction_summary": result.get("extraction_summary", {}),
        }
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        return {
            "success": False,
            "error": str(e),
            "summary": {"total_tests": 0, "abnormal": 0, "normal": 0,
                        "unknown": 0, "critical_flags": 0},
            "findings": [],
            "text_report": f"Analysis failed: {e}",
            "clinical_insights": f"Analysis failed: {e}"
        }

def analyze_extracted_values(
    values: Dict[str, float],
    units: Optional[Dict[str, str]] = None,
    gender: str = "male"
) -> Dict:
    """Fallback if someone analyzes extracted values manually."""
    return {
        "success": False,
        "error": "Extracted value analysis is unneeded now that Gemini handles it natively.",
        "summary": {"total_tests": 0, "abnormal": 0, "normal": 0,
                    "unknown": 0, "critical_flags": 0},
        "findings": [],
        "text_report": "Values submitted directly, but Gemini pipeline is currently used for document parsing."
    }
