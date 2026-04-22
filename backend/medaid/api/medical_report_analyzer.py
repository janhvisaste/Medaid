import logging
import base64
import os
from typing import Dict
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


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

[2-3 sentence overview in simple language, similar to: “This is a CBC report …”]

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

[One-line conclusion, e.g., “✅ Platelets are completely normal.” or state abnormality clearly]

📊 4. Absolute White Cell Counts
| Cell | Result | Interpretation |
|---|---|---|
[Include absolute counts if present, otherwise write “Not available”]

🔎 Overall Medical Interpretation
[Summarize the top 2-4 clinical takeaways in simple language]

⚠️ When to see a doctor urgently
[Bullet list: red-flag symptoms relevant to current abnormalities]

🥗 Typical treatment doctors recommend
[Bullet list: general/non-prescription-safe guidance + “consult doctor”]

✅ Simple summary:
- [Point 1]
- [Point 2]
- [Point 3]

Important safety rule:
Add one final line: “This is for informational purposes only and not a diagnosis.”
"""

class MedicalReportAnalyzerAdapter:
    """
    NVIDIA API integration for Medical Document Analysis.
    """
    def __init__(self):
        self.nvidia_api_key = os.getenv("NVIDIA_API_KEY")
        self.nvidia_base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self.nvidia_vision_model = os.getenv("NVIDIA_VISION_MODEL", "meta/llama-3.2-90b-vision-instruct")

    def _resolve_mime_type(self, file_type: str, file_name: str) -> str:
        raw_type = (file_type or "").strip().lower()
        normalized_name = (file_name or "").strip().lower()

        if raw_type in {"application/pdf", "pdf"}:
            return "application/pdf"

        if raw_type in {"image", "img"}:
            if normalized_name.endswith(".png"):
                return "image/png"
            if normalized_name.endswith(".webp"):
                return "image/webp"
            return "image/jpeg"

        if raw_type in {"jpg", "jpeg", "image/jpg", "image/jpeg"}:
            return "image/jpeg"
        if raw_type in {"png", "image/png"}:
            return "image/png"
        if raw_type in {"webp", "image/webp"}:
            return "image/webp"

        if "/" in raw_type:
            return raw_type

        if normalized_name.endswith(".pdf"):
            return "application/pdf"
        if normalized_name.endswith(".png"):
            return "image/png"
        if normalized_name.endswith(".webp"):
            return "image/webp"
        if normalized_name.endswith((".jpg", ".jpeg")):
            return "image/jpeg"

        return "application/pdf"

    def analyze_report(self, file_bytes: bytes, file_type: str, file_name: str = "report") -> Dict:
        if not self.nvidia_api_key:
            return {
                "success": False,
                "error": "NVIDIA_API_KEY is not configured",
                "markdown_report": "",
                "json_data": {},
                "clinical_insights": "NVIDIA API key is missing. Please set NVIDIA_API_KEY for document/image analysis.",
                "extraction_summary": {}
            }

        try:
            mime = self._resolve_mime_type(file_type=file_type, file_name=file_name)
            encoded_content = base64.b64encode(file_bytes).decode("utf-8")
            data_uri = f"data:{mime};base64,{encoded_content}"

            payload = {
                "model": self.nvidia_vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": UPLOAD_INSIGHTS_PROMPT},
                            {"type": "image_url", "image_url": {"url": data_uri}}
                        ]
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 1800
            }

            response = requests.post(
                f"{self.nvidia_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.nvidia_api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=90
            )

            if response.status_code >= 400:
                error_text = response.text
                logger.error(f"NVIDIA analysis failed: HTTP {response.status_code} - {error_text}")
                return {
                    "success": False,
                    "error": f"NVIDIA API error ({response.status_code}): {error_text}",
                    "markdown_report": "",
                    "json_data": {},
                    "clinical_insights": f"Analysis failed: NVIDIA API error ({response.status_code}).",
                    "extraction_summary": {}
                }

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
                message_content = "\n".join([part for part in text_parts if part])

            text_result = (message_content or "").strip()
            if not text_result:
                text_result = "Unable to generate insights from the uploaded report."
            
            return {
                "success": True,
                "markdown_report": text_result,
                "json_data": {},
                "clinical_insights": text_result,
                "extraction_summary": {}
            }
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "markdown_report": "",
                "json_data": {},
                "clinical_insights": f"Analysis failed: {str(e)}",
                "extraction_summary": {}
            }


_analyzer_instance = None

def get_medical_report_analyzer():
    """Singleton accessor for the analyzer adapter."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = MedicalReportAnalyzerAdapter()
    return _analyzer_instance
