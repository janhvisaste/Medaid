"""
Medical Report Analyzer — 3-tier OCR extraction with fallback chain.

OCR path priority:
  1. Apple Vision OCR service (macOS microservice at OCR_SERVICE_URL)
  2. Tesseract (pytesseract, cross-platform fallback)
  3. NVIDIA Vision model (image-to-markdown, lowest fidelity for structuring)

Each path logs which strategy served the request.
"""

import base64
import io
import logging
import os
import tempfile
import time
from typing import Dict, Optional

import requests
from django.conf import settings
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier 1: Apple Vision OCR service
# ---------------------------------------------------------------------------

def _ocr_apple_vision(file_bytes: bytes, content_type: str) -> Optional[Dict]:
    """Call the standalone Apple Vision OCR service over HTTP."""
    ocr_url = getattr(settings, 'OCR_SERVICE_URL', 'http://127.0.0.1:5050')
    ocr_key = getattr(settings, 'OCR_SERVICE_KEY', '')
    timeout = getattr(settings, 'OCR_SERVICE_TIMEOUT', 20)

    try:
        headers = {}
        if ocr_key:
            headers['X-OCR-Key'] = ocr_key

        resp = requests.post(
            f"{ocr_url.rstrip('/')}/ocr",
            files={'file': ('report', file_bytes, content_type)},
            headers=headers,
            timeout=timeout,
        )

        if resp.status_code >= 400:
            logger.warning(
                "ocr.apple_vision_error",
                extra={"status_code": resp.status_code, "body": resp.text[:500]},
            )
            return None

        data = resp.json()
        logger.info(
            "ocr.apple_vision_success",
            extra={
                "confidence": data.get("confidence"),
                "blocks": len(data.get("blocks", [])),
                "pages": data.get("pages", 1),
                "text_length": len(data.get("text", "")),
            },
        )
        return {
            "text": data.get("text", ""),
            "confidence": data.get("confidence", 0.0),
            "blocks": data.get("blocks", []),
            "pages": data.get("pages", 1),
            "ocr_path": "apple_vision",
        }

    except requests.Timeout:
        logger.warning("ocr.apple_vision_timeout", extra={"timeout": timeout})
        return None
    except requests.ConnectionError:
        logger.warning("ocr.apple_vision_unreachable", extra={"url": ocr_url})
        return None
    except Exception as e:
        logger.warning("ocr.apple_vision_unexpected", extra={"error": str(e)})
        return None


# ---------------------------------------------------------------------------
# Tier 2: Tesseract (pytesseract)
# ---------------------------------------------------------------------------

def _ocr_tesseract(file_bytes: bytes, content_type: str) -> Optional[Dict]:
    """Cross-platform OCR fallback using Tesseract."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        logger.warning("ocr.tesseract_not_installed")
        return None

    try:
        pages_text = []

        if 'pdf' in content_type.lower():
            # Use PyMuPDF (fitz) for PDF rasterization — already in requirements
            try:
                import fitz  # PyMuPDF
            except ImportError:
                logger.warning("ocr.tesseract_pdf_no_fitz")
                return None

            pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page_num in range(len(pdf_doc)):
                page = pdf_doc[page_num]
                # Render at 300 DPI
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                page_text = pytesseract.image_to_string(img)
                pages_text.append(page_text.strip())
            pdf_doc.close()
        else:
            # Single image
            img = Image.open(io.BytesIO(file_bytes))
            page_text = pytesseract.image_to_string(img)
            pages_text.append(page_text.strip())

        full_text = "\n--- PAGE BREAK ---\n".join(pages_text)

        if not full_text.strip():
            logger.warning("ocr.tesseract_empty_result")
            return None

        logger.info(
            "ocr.tesseract_success",
            extra={"pages": len(pages_text), "text_length": len(full_text)},
        )
        return {
            "text": full_text,
            "confidence": 0.0,  # Tesseract basic mode doesn't return confidence easily
            "blocks": [],
            "pages": len(pages_text),
            "ocr_path": "tesseract",
        }

    except Exception as e:
        logger.warning("ocr.tesseract_failed", extra={"error": str(e)})
        return None


# ---------------------------------------------------------------------------
# Tier 3: NVIDIA Vision model (image-to-markdown, no structured extraction)
# ---------------------------------------------------------------------------

UPLOAD_INSIGHTS_PROMPT = """You are a clinical report explanation assistant.
Analyze the uploaded medical document (CBC/lab report) and return output in EXACTLY this structure and order.

Formatting rules (strict):
- Use plain markdown only.
- Keep section titles, emojis, and numbering exactly as below.
- Use tables where shown.
- Mention exact values and ranges from the document.
- If a value/range is missing, write "Not available".
- Do NOT wrap output in code fences.

OUTPUT TEMPLATE:

[2-3 sentence overview in simple language, similar to: "This is a CBC report …"]

Below is a clear explanation of the important results.

🧾 1. Red Blood Cells (Oxygen-carrying cells)
| Test | Your Result | Normal Range | Meaning |
|---|---|---|---|
[Include key RBC parameters present in report: Hemoglobin, RBC Count, Hematocrit/PCV, MCV, MCH, MCHC, RDW, etc.]

📌 Interpretation:
[2-4 bullets explaining the RBC pattern and likely meaning]

🦠 2. White Blood Cells (Infection fighters)
| Test | Result | Normal | Meaning |
|---|---|---|---|
[Include total WBC and differential data if present]

Differential Count
| Cell Type | Result | Meaning |
|---|---|---|
[Neutrophils, Lymphocytes, Eosinophils, Monocytes, Basophils if present]

📌 Interpretation:
[2-4 bullets about infection/inflammation pattern]

🩸 3. Platelets (Clotting cells)
| Test | Result | Normal |
|---|---|---|
[Platelet count/MPV/IPF if present]

[One-line conclusion, e.g., "✅ Platelets are completely normal." or state abnormality clearly]

📊 4. Absolute White Cell Counts
| Cell | Result | Interpretation |
|---|---|---|
[Include absolute counts if present, otherwise write "Not available"]

🔎 Overall Medical Interpretation
[Summarize the top 2-4 clinical takeaways in simple language]

⚠️ When to see a doctor urgently
[Bullet list: red-flag symptoms relevant to current abnormalities]

🥗 Typical treatment doctors recommend
[Bullet list: general/non-prescription-safe guidance + "consult doctor"]

✅ Simple summary:
- [Point 1]
- [Point 2]
- [Point 3]

Important safety rule:
Add one final line: "This is for informational purposes only and not a diagnosis."
"""


def _ocr_nvidia_vision(file_bytes: bytes, content_type: str, file_name: str = "report") -> Optional[Dict]:
    """NVIDIA vision model fallback — sends image to NVIDIA API for markdown analysis."""
    nvidia_api_key = os.getenv("NVIDIA_API_KEY")
    if not nvidia_api_key:
        logger.warning("ocr.nvidia_not_configured")
        return None

    nvidia_base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    nvidia_model = os.getenv("NVIDIA_VISION_MODEL", "meta/llama-3.2-90b-vision-instruct")

    try:
        # Resolve MIME type
        if 'pdf' in content_type.lower():
            mime = "application/pdf"
        elif 'png' in content_type.lower():
            mime = "image/png"
        elif 'webp' in content_type.lower():
            mime = "image/webp"
        else:
            mime = "image/jpeg"

        encoded_content = base64.b64encode(file_bytes).decode("utf-8")
        data_uri = f"data:{mime};base64,{encoded_content}"

        payload = {
            "model": nvidia_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": UPLOAD_INSIGHTS_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
            "temperature": 0.2,
            "max_tokens": 1800,
        }

        response = requests.post(
            f"{nvidia_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {nvidia_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )

        if response.status_code >= 400:
            logger.warning(
                "ocr.nvidia_api_error",
                extra={"status_code": response.status_code, "body": response.text[:500]},
            )
            return None

        body = response.json()
        choices = body.get("choices") or []
        message_content = ""
        if choices:
            message_content = ((choices[0] or {}).get("message") or {}).get("content", "")

        if isinstance(message_content, list):
            text_parts = []
            for part in message_content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif isinstance(part, str):
                    text_parts.append(part)
            message_content = "\n".join([p for p in text_parts if p])

        text_result = (message_content or "").strip()
        if not text_result:
            logger.warning("ocr.nvidia_empty_response")
            return None

        logger.info(
            "ocr.nvidia_success",
            extra={"text_length": len(text_result)},
        )
        return {
            "text": text_result,
            "confidence": 0.0,
            "blocks": [],
            "pages": 1,
            "ocr_path": "nvidia_vision",
        }

    except Exception as e:
        logger.warning("ocr.nvidia_failed", extra={"error": str(e)})
        return None


# ---------------------------------------------------------------------------
# Public API: extract_text — 3-tier OCR with fallback
# ---------------------------------------------------------------------------

def extract_text(file_bytes: bytes, content_type: str, file_name: str = "report") -> Dict:
    """
    Extract text from a medical report using a 3-tier OCR fallback chain.

    Returns:
        {
            "success": bool,
            "text": str,
            "confidence": float,
            "blocks": list,
            "pages": int,
            "ocr_path": "apple_vision" | "tesseract" | "nvidia_vision" | "none",
            "error": str | None,
        }
    """
    start = time.time()

    # Tier 1: Apple Vision
    result = _ocr_apple_vision(file_bytes, content_type)
    if result and result.get("text", "").strip():
        result["success"] = True
        result["error"] = None
        logger.info("ocr.path_selected", extra={"path": "apple_vision", "elapsed_ms": int((time.time() - start) * 1000)})
        return result

    # Tier 2: Tesseract
    result = _ocr_tesseract(file_bytes, content_type)
    if result and result.get("text", "").strip():
        result["success"] = True
        result["error"] = None
        logger.info("ocr.path_selected", extra={"path": "tesseract", "elapsed_ms": int((time.time() - start) * 1000)})
        return result

    # Tier 3: NVIDIA Vision
    result = _ocr_nvidia_vision(file_bytes, content_type, file_name)
    if result and result.get("text", "").strip():
        result["success"] = True
        result["error"] = None
        logger.info("ocr.path_selected", extra={"path": "nvidia_vision", "elapsed_ms": int((time.time() - start) * 1000)})
        return result

    # All tiers failed
    logger.error("ocr.all_paths_failed", extra={"elapsed_ms": int((time.time() - start) * 1000)})
    return {
        "success": False,
        "text": "",
        "confidence": 0.0,
        "blocks": [],
        "pages": 0,
        "ocr_path": "none",
        "error": "All OCR paths failed. Ensure the Apple Vision OCR service is running, or Tesseract is installed, or NVIDIA_API_KEY is configured.",
    }


# ---------------------------------------------------------------------------
# Legacy compatibility: MedicalReportAnalyzerAdapter
# ---------------------------------------------------------------------------

class MedicalReportAnalyzerAdapter:
    """
    Legacy adapter preserved for compatibility with chat_send_message and other
    call sites that use analyzer.analyze_report(). Now delegates to extract_text.
    """

    def analyze_report(self, file_bytes: bytes, file_type: str, file_name: str = "report") -> Dict:
        """Analyze a report — returns legacy-shaped dict for backward compat."""
        content_type = self._resolve_content_type(file_type, file_name)
        ocr_result = extract_text(file_bytes, content_type, file_name)

        if not ocr_result.get("success"):
            return {
                "success": False,
                "error": ocr_result.get("error", "OCR extraction failed"),
                "markdown_report": "",
                "json_data": {},
                "clinical_insights": ocr_result.get("error", "OCR extraction failed"),
                "extraction_summary": {},
            }

        text = ocr_result.get("text", "")
        return {
            "success": True,
            "markdown_report": text,
            "json_data": {},
            "clinical_insights": text,
            "extraction_summary": {},
            "ocr_path": ocr_result.get("ocr_path", "unknown"),
        }

    def _resolve_content_type(self, file_type: str, file_name: str) -> str:
        raw_type = (file_type or "").strip().lower()
        normalized_name = (file_name or "").strip().lower()

        if raw_type in {"application/pdf", "pdf"} or normalized_name.endswith(".pdf"):
            return "application/pdf"
        if raw_type in {"image/png", "png"} or normalized_name.endswith(".png"):
            return "image/png"
        if raw_type in {"image/webp", "webp"} or normalized_name.endswith(".webp"):
            return "image/webp"
        if "/" in raw_type:
            return raw_type
        return "image/jpeg"


_analyzer_instance = None


def get_medical_report_analyzer():
    """Singleton accessor for the analyzer adapter."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = MedicalReportAnalyzerAdapter()
    return _analyzer_instance
