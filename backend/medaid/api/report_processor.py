import logging
from typing import Dict, List, Tuple, Optional
from .medical_report_analyzer import get_medical_report_analyzer

logger = logging.getLogger(__name__)

class ReportProcessor:
    def __init__(self):
        pass

    def extract_and_analyze(self, file_bytes: bytes, file_name: str) -> Dict:
        """Process medical report via Gemini."""
        analyzer = get_medical_report_analyzer()
        result = analyzer.analyze_report(file_bytes=file_bytes, file_type=None, file_name=file_name)
        
        return {
            "success": result.get("success", False),
            "text": result.get("markdown_report", "No text extracted"),
            "structured_data": result.get("json_data", {}),
            "error": result.get("error")
        }

def get_report_processor():
    return ReportProcessor()

def summarize_medical_report_with_llm(text: str) -> Dict:
    """Fallback LLM text summary. We can invoke Gemini here too."""
    import os
    try:
        from google import genai
    except ImportError:
        return {"summary": "Gemini SDK missing.", "key_findings": []}
        
    try:
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        prompt = f"Summarize the key medical findings from this text:\n{text}\n\nProvide a short summary paragraph and a list of key_findings."
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return {"summary": response.text.strip(), "key_findings": []}
    except Exception as e:
        return {"summary": f"Failed: {str(e)}", "key_findings": []}
