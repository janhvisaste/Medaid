"""Reference JSON parsing and integration fallback contracts."""

import json
from typing import Any, Dict, Optional


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON using the reference direct-then-braced strategy."""
    # Source: backend_processing.py::extract_json_from_text, active definition.
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_text = text[start:end + 1]
                json_text = json_text.replace("'", '"')
                json_text = json_text.replace("\n", "").replace("\r", "")
                json_text = json_text.replace(", }", "}")
                json_text = json_text.replace(", ]", "]")
                return json.loads(json_text)
        except Exception:
            pass
    return None


def get_fallback_response(message: str = "LLM unavailable") -> Dict[str, Any]:
    """Return the Medium/Unknown object produced by reference integration.

    Source: backend_processing.py::integrate_report_and_run_assessment converts
    llm_predict_assessment errors to this exact shape.
    """
    return {
        "possible_conditions": [{"disease": "Unknown", "confidence": 0.3}],
        "risk_level": "Medium",
        "risk_proba": 0.3,
        "reason": message,
        "recommendations": [
            "Consult physician",
            "Monitor symptoms",
            "Visit PHC if worsens",
        ],
    }


def normalize_llm_assessment(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Apply reference defaults, confidence clamping, and risk validation."""
    parsed = dict(parsed or {})
    parsed.setdefault("possible_conditions", [])
    parsed.setdefault("risk_level", "Medium")
    parsed.setdefault("risk_proba", 0.0)
    parsed.setdefault("reason", "")
    parsed.setdefault("recommendations", [])

    conditions = []
    for item in parsed.get("possible_conditions", []):
        if isinstance(item, dict):
            name = item.get("disease", "")
            confidence = item.get("confidence", 0.0)
        else:
            name = str(item)
            confidence = 0.0
        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.0
        conditions.append({
            "disease": str(name),
            "confidence": max(0.0, min(1.0, confidence)),
        })
    parsed["possible_conditions"] = conditions

    try:
        risk_proba = float(parsed.get("risk_proba", 0.0))
    except Exception:
        risk_proba = 0.0
    parsed["risk_proba"] = max(0.0, min(1.0, risk_proba))

    if parsed.get("risk_level") not in ["Low", "Medium", "High", "Emergency"]:
        parsed["risk_level"] = "Medium"
    return parsed
