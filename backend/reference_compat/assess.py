"""Reference-compatible pure triage orchestration.

This ports Shivanikinagi/Medaid/backend_processing.py::
integrate_report_and_run_assessment in seven observable stages:

1. Read symptoms, city, and pincode.
2. Apply the reference emergency-keyword override.
3. Scan at most 50 report tests for strict SpO2/Hb emergency thresholds.
4. Summarize at most 10 report tests.
5. Read past history, build the reference prompt, and call Gemini once.
6. Parse/normalize the response or return the Medium/Unknown fallback.
7. Catch unexpected errors and return the same fallback without raising.

The function has no persistence, facility, or database side effects. The
reference caller performs persistence after this function returns.
"""

from typing import Any, Dict, Optional

from .keywords import contains_emergency_keyword
from .llm_client import LLMClient
from .normalize import (
    extract_json_from_text,
    get_fallback_response,
    normalize_llm_assessment,
)
from .prompt import _build_triage_prompt
from .thresholds import find_report_emergency


def _emergency_assessment(reason: str, recommendations):
    return {
        "possible_conditions": [],
        "risk_level": "Emergency",
        "risk_proba": 1.0,
        "reason": reason,
        "recommendations": list(recommendations),
    }


def _summarize_report(report_data: Optional[Dict[str, Any]]) -> str:
    tests = report_data.get("medical_tests", []) if isinstance(report_data, dict) else []
    if not isinstance(tests, list):
        return ""
    parts = []
    for test in tests[:10]:
        if not isinstance(test, dict):
            continue
        value = test.get("value", "")
        status = f" ({test.get('status')})" if test.get("status") else ""
        parts.append(f"{test.get('test_name', '')}: {value}{status}")
    return "; ".join(parts)


def integrate_report_and_run_assessment(
    report_data: Optional[Dict[str, Any]],
    user_inputs: Dict[str, Any],
    user_profile: Optional[Dict[str, Any]],
    llm_client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    """Run the reference assessment sequence and never raise an exception."""
    try:
        user_inputs = user_inputs or {}
        symptoms_text = user_inputs.get("symptoms_text", "") or ""
        city = user_inputs.get("city", "") or ""
        pincode = user_inputs.get("pincode", "") or ""

        # Reference step 2: keyword check must precede report checks.
        if contains_emergency_keyword(symptoms_text):
            return {
                "status": "ok",
                "assessment": _emergency_assessment(
                    "Emergency keyword detected in symptoms. Seek immediate care.",
                    ["Call emergency services immediately", "Go to nearest hospital"],
                ),
            }

        # Reference step 3: strict threshold checks, capped at 50 tests.
        report_reason = find_report_emergency(report_data)
        if report_reason:
            return {
                "status": "ok",
                "assessment": _emergency_assessment(
                    report_reason,
                    ["Seek emergency medical care"],
                ),
            }

        report_summary = _summarize_report(report_data)
        location_info = ""
        if city and pincode:
            location_info = f"{city}, {pincode}"
        elif city:
            location_info = city
        elif pincode:
            location_info = f"Pincode: {pincode}"

        past_history = user_profile.get("past_history", {}) if user_profile else {}
        prompt = _build_triage_prompt(
            symptoms_text,
            report_summary,
            past_history=past_history,
            location=location_info,
        )

        client = llm_client or LLMClient()
        if not client.is_available():
            return {
                "status": "ok",
                "assessment": get_fallback_response(
                    "Gemini backend not initialized (check GOOGLE_API_KEY and langchain_google_genai)."
                ),
            }

        try:
            raw_text = client.call(prompt)
            cleaned = (raw_text or "").replace(chr(96) * 3 + "json", "").replace(chr(96) * 3, "").strip()
            parsed = extract_json_from_text(cleaned)
            if parsed is None:
                return {
                    "status": "ok",
                    "assessment": get_fallback_response("LLM returned unparsable JSON"),
                }
            return {
                "status": "ok",
                "assessment": normalize_llm_assessment(parsed),
            }
        except Exception as error:
            return {
                "status": "ok",
                "assessment": get_fallback_response(str(error)),
            }
    except Exception as error:
        return {
            "status": "ok",
            "assessment": get_fallback_response(str(error)),
        }
