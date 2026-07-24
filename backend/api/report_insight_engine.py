"""
Report Insight Engine — LLM-powered structuring and interpretation of OCR text.

Mirrors the architecture of triage_engine_v2.py:
  - _build_report_insight_prompt() builds the per-report structuring prompt
  - _build_combined_report_prompt() builds the history-aware "Analyze report" prompt
  - _extract_json() parses JSON from LLM response
  - generate_report_insights() is the main entry point (OCR → structured data)
  - build_report_insight_context() assembles full patient context for the Analyze view
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from django.conf import settings
from dotenv import load_dotenv

from .lab_reference import (
    build_grounded_facts_block,
    ground_tests,
    overall_status,
    select_lab_relevant_text,
)
from .llm_providers import GeminiProvider, ModelProviderError, OpenRouterProvider
from .llm_providers.base import provider_request_context

load_dotenv()

logger = logging.getLogger(__name__)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _max_report_chars() -> int:
    """
    How much OCR text may be sent to the model.

    Gemini 2.5 Flash carries a very large context window, so the old 3,000-char
    cap was throwing away the entire body of any multi-page report for no
    benefit. Configurable via settings.REPORT_INSIGHT_MAX_CHARS.
    """
    return int(getattr(settings, "REPORT_INSIGHT_MAX_CHARS", 60000))

def _build_report_insight_prompt(ocr_text: str, user_context: Optional[Dict] = None) -> str:
    """
    Build the LLM prompt for structuring OCR text into medical test results
    and generating plain-language insights.

    Mirrors _build_assessment_prompt in triage_engine_v2.py.
    """
    ctx = user_context or {}
    age = ctx.get("age", "Unknown")
    gender = ctx.get("gender", "Unknown")
    history = ctx.get("past_history", [])
    history_str = ", ".join(
        c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in history
    ) if history else "None reported"

    other_notes = (ctx.get("other_notes") or "").strip()
    other_notes_line = f"\n**Additional info from patient:** {other_notes}" if other_notes else ""

    # Drop cover/disclaimer pages so a long report's actual results survive.
    ocr_text = select_lab_relevant_text(ocr_text, _max_report_chars())

    return f"""You are a medical report analysis assistant. Your job is to extract structured test results from OCR text of a medical report and provide a clear, accurate interpretation.

**Patient context:** Age {age}, Gender {gender}
**Medical history:** {history_str}{other_notes_line}

**OCR Text from the report:**
---
{ocr_text}
---

Analyze the OCR text above and respond with ONLY valid JSON in this exact structure:

{{
    "tests": [
        {{
            "test_name": "Hemoglobin",
            "value": "12.5",
            "unit": "g/dL",
            "reference_range": "12.0 - 16.0",
            "status": "normal"
        }}
    ],
    "summary": "A plain-language 2-3 sentence summary of what this report shows overall.",
    "abnormal_findings": [
        {{
            "test_name": "WBC Count",
            "value": "15000",
            "status": "high",
            "explanation": "White blood cell count is elevated, which may indicate an infection or inflammatory response."
        }}
    ],
    "what_this_may_mean": "A 2-4 sentence explanation connecting the abnormal findings to possible clinical significance, written for a patient to understand.",
    "consult_note": "Please consult your doctor for a complete interpretation of these results. This analysis is informational and not a diagnosis."
}}

**Critical rules:**
1. Extract EVERY test result visible in the OCR text. Do not skip tests.
2. Use the EXACT values from the OCR text. Do NOT fabricate or round values.
3. If the OCR text is garbled or a value is unclear, include it with the value as-is and add "(OCR unclear)" to the test_name.
4. Status must be one of: "normal", "high", "low", "critical", "unknown".
5. If no reference range is visible in the report, write "Not specified".
6. If there are no abnormal findings, return an empty array for "abnormal_findings".
7. The "what_this_may_mean" should be cautious and factual, not alarmist.
8. Always end with the consult_note — this is NOT a diagnosis.

Return ONLY the JSON object, no markdown fences, no commentary."""


def _build_combined_report_prompt(report_data: Dict, user_context: Dict) -> str:
    """
    Build the combined history-aware prompt for the "Analyze report" view.

    Labels report findings and patient history distinctly so the model can
    tell which is which — never concatenated ambiguously.
    """
    # --- Report section ---
    file_name = report_data.get("file_name", "Medical Report")
    extracted_text = (report_data.get("extracted_text") or "").strip()
    tests = report_data.get("tests", [])
    abnormal_findings = report_data.get("abnormal_findings", [])

    if tests:
        tests_str = "\n".join(
            f"  - {t.get('test_name', '')}: {t.get('value', '')} {t.get('unit', '')} "
            f"[ref: {t.get('reference_range', 'N/A')}] — {t.get('status', 'unknown')}"
            for t in tests[:40]
        )
        report_section = f"Extracted test results:\n{tests_str}"
    elif extracted_text:
        # Multi-page reports open with branding/disclaimer/contents pages. A flat
        # head-truncation spends the whole budget there and shows the model no
        # results at all, so filter to the pages that actually carry values.
        report_section = f"Extracted text (raw OCR):\n{select_lab_relevant_text(extracted_text, _max_report_chars())}"
    else:
        report_section = "No extracted text available — analysis based on filename only."

    if abnormal_findings:
        abnormals_str = "\n".join(
            f"  - {f.get('test_name', '')}: {f.get('status', '')} — {f.get('explanation', '')}"
            for f in abnormal_findings[:20]
        )
        report_section += f"\n\nAlready identified abnormal findings:\n{abnormals_str}"

    # --- Patient history section ---
    age = user_context.get("age", "Unknown")
    gender = user_context.get("gender", "Unknown")

    conditions = user_context.get("past_history", [])
    conditions_str = ", ".join(
        c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in conditions
    ) if conditions else "None reported"

    other_notes = (user_context.get("other_notes") or "").strip()
    other_notes_line = f"\n**Additional notes from patient:** {other_notes}" if other_notes else ""

    past_triages = user_context.get("past_triages", [])
    triage_str = ""
    if past_triages:
        triage_lines = []
        for tr in past_triages[:3]:
            conditions_found = ", ".join(tr.get("conditions", [])[:5]) or "None"
            triage_lines.append(
                f"  - {tr.get('date', 'Unknown date')}: {tr.get('risk_level', '')} risk, "
                f"symptoms: {tr.get('symptoms', '')[:120]}, flagged: {conditions_found}"
            )
        triage_str = f"\n**Past triage assessments:**\n" + "\n".join(triage_lines)

    prior_reports = user_context.get("prior_report_findings", [])
    prior_str = ""
    if prior_reports:
        prior_lines = []
        for pr in prior_reports[:3]:
            abnormals = ", ".join(pr.get("abnormal_tests", [])[:5]) or "none"
            prior_lines.append(
                f"  - {pr.get('file_name', 'Report')} ({pr.get('date', '')}): {pr.get('summary', '')[:200]} Abnormals: {abnormals}"
            )
        prior_str = f"\n**Previous report findings:**\n" + "\n".join(prior_lines)

    return f"""You are a clinical AI assistant analyzing a patient's medical report in the context of their full health history.

**Report:** {file_name}
**Report findings:**
{report_section}

---

**Patient profile:** Age {age}, {gender}
**Known conditions:** {conditions_str}{other_notes_line}{triage_str}{prior_str}

---

Analyze this report in the context of the patient's full history above.
Where relevant, explicitly connect report findings to known conditions or past assessments.
For example: "Given your history of Diabetes, the elevated HbA1c finding is significant because..."

Respond with ONLY valid JSON:
{{
    "tests": [
        {{
            "test_name": "Hemoglobin",
            "value": "12.5",
            "unit": "g/dL",
            "reference_range": "12.0 - 16.0",
            "status": "normal"
        }}
    ],
    "summary": "2-3 sentence plain-language summary referencing the patient's history where relevant.",
    "abnormal_findings": [
        {{
            "test_name": "WBC Count",
            "value": "15000",
            "status": "high",
            "explanation": "Explanation connecting this to the patient's history where applicable."
        }}
    ],
    "what_this_may_mean": "2-4 sentence explanation written for the patient, explicitly connecting report findings to their known conditions or past assessments where relevant.",
    "consult_note": "Please consult your doctor for a complete interpretation. This is not a diagnosis."
}}

Rules:
- Extract all test results from the report section.
- Status: "normal", "high", "low", "critical", or "unknown".
- The summary and what_this_may_mean MUST reference the patient's history when it is relevant — do not describe the report in isolation.
- If history is empty, a report-only analysis is fine.
- Return ONLY the JSON object."""


def _build_consultation_prompt(
    grounding: Dict,
    user_context: Dict,
    report_data: Optional[Dict] = None,
) -> str:
    """
    Stage 3 prompt: turn VERIFIED findings into a doctor-to-patient consultation.

    The model receives findings whose status was decided arithmetically and
    whose clinical meaning came from the curated knowledge base. Its only job
    is to explain them like a good clinician would — it is explicitly forbidden
    from re-judging whether a value is high or low, because that decision has
    already been made correctly upstream.
    """
    report_data = report_data or {}
    counts = grounding.get("counts", {})
    posture = overall_status(counts)

    age = user_context.get("age", "Unknown")
    gender = user_context.get("gender", "Unknown")

    conditions = user_context.get("past_history", [])
    conditions_str = ", ".join(
        c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in conditions
    ) if conditions else "None reported"

    other_notes = (user_context.get("other_notes") or "").strip()
    other_notes_line = f"\n**Patient also told us:** {other_notes}" if other_notes else ""

    # Prior reports let us speak to trajectory rather than a single snapshot.
    prior = user_context.get("prior_report_findings", []) or []
    prior_str = ""
    if prior:
        prior_lines = [
            f"  - {p.get('file_name', 'Report')} ({p.get('date', '')}): "
            f"abnormal then: {', '.join(p.get('abnormal_tests', [])[:6]) or 'none'}"
            for p in prior[:3]
        ]
        prior_str = "\n**Their previous reports:**\n" + "\n".join(prior_lines)

    triages = user_context.get("past_triages", []) or []
    triage_str = ""
    if triages:
        triage_lines = [
            f"  - {t.get('date', '')}: {t.get('risk_level', '')} risk — {t.get('symptoms', '')[:100]}"
            for t in triages[:3]
        ]
        triage_str = "\n**Recent symptom check-ins:**\n" + "\n".join(triage_lines)

    facts = build_grounded_facts_block(grounding)

    urgency_instruction = {
        "urgent": (
            "At least one value is at a CRITICAL threshold. Open by saying clearly and calmly "
            "that something here needs prompt medical attention, and put the urgent action first. "
            "Do not bury it. Do not cause panic — be direct and steady."
        ),
        "attention_needed": (
            "Some values are outside the normal range but none are critical. Be reassuring about "
            "what is fine, clear about what needs follow-up, and specific about the timeframe."
        ),
        "reassuring": (
            "Everything verified came back normal. Lead with genuine reassurance, then briefly note "
            "anything worth routine monitoring. Do not manufacture concern."
        ),
        "unclear": (
            "Little could be verified against reference data. Be honest that this report could not be "
            "fully interpreted automatically, and steer them to their doctor with the raw values."
        ),
    }[posture]

    return f"""You are an experienced physician sitting with your patient, going through their lab
report together. Speak to them directly ("you", "your"), warmly and plainly — the way a good doctor
explains results in clinic. No jargon without immediately explaining it. Never lecture.

**Patient:** Age {age}, {gender}
**Known conditions:** {conditions_str}{other_notes_line}{triage_str}{prior_str}

**Report:** {report_data.get('file_name', 'Lab report')}

**VERIFIED FINDINGS** — these statuses were computed arithmetically against validated
reference ranges and are already correct. Treat every line here as established fact:
{facts}

Result counts: {counts.get('normal', 0)} normal, {counts.get('abnormal', 0)} outside range,
{counts.get('critical', 0)} at critical levels, {counts.get('unverified', 0)} not verifiable.

**Guidance for this particular report:** {urgency_instruction}

Respond with ONLY valid JSON:
{{
  "headline": "One clear sentence a worried patient can grasp instantly.",
  "opening": "2-3 warm sentences orienting them to what this report covers and the overall picture.",
  "whats_working_well": "What came back normal and why that is genuinely good news. 1-3 sentences. If nothing was verified normal, say so honestly.",
  "needs_attention": [
    {{
      "test_name": "WBC Count",
      "plain_meaning": "What this test measures, in one everyday sentence.",
      "why_it_matters_for_you": "Why THIS patient specifically should care, referencing their age, conditions, or history where it genuinely applies.",
      "urgency": "routine | soon | urgent"
    }}
  ],
  "connection_to_your_history": "Explicitly tie findings to their known conditions or past reports. If there is no meaningful connection, say that plainly rather than inventing one.",
  "trend_vs_previous": "How this compares to their earlier reports. Empty string if there are no priors to compare.",
  "next_steps": ["Concrete, doable actions — tests to ask for, habits to change, things to monitor."],
  "follow_up": "When they should next see a doctor about this, and with what urgency.",
  "questions_for_your_doctor": ["Specific questions this patient should actually ask at their next visit."],
  "red_flags": ["Symptoms that mean seek care immediately, tailored to these findings."],
  "closing": "One steadying, human closing line."
}}

Hard rules:
1. NEVER contradict a VERIFIED status. If it says HIGH, it is high. Do not re-evaluate the numbers.
2. Only discuss tests listed above. Do not invent results, values, or diagnoses.
3. Do not name a specific disease as their diagnosis — describe possibilities and what to rule out.
4. For anything marked NOT independently verified, describe it tentatively and defer to their doctor.
5. Everyday language. "Your liver enzymes are raised" not "transaminitis is present".
6. Empty arrays/strings are fine when a section genuinely does not apply. Never pad.

Return ONLY the JSON object, no markdown fences."""


# ---------------------------------------------------------------------------
# Context builder for the Analyze Report view
# ---------------------------------------------------------------------------

def build_report_insight_context(user: Any, report: Any) -> Dict:
    """
    Assemble the full patient context for the combined report insight prompt.

    Pulls from:
    - UserProfile: age, gender, past_history.conditions, other_notes
    - TriageRecord: last 3 records (risk_level, possible_conditions, symptoms)
    - MedicalReport: last 3 prior reports (excluding current) — insights_text, abnormal tests
    - Current report: extracted_text, structured_data (tests, abnormal_findings), file_name

    Returns a dict safe to pass to _build_combined_report_prompt().
    """
    # Lazy imports to avoid circular issues at module level
    from datetime import date as _date
    from .models import UserProfile, TriageRecord, MedicalReport

    # --- Profile ---
    profile = None
    try:
        profile = user.profile
    except Exception:
        pass

    age = "Unknown"
    gender = "Unknown"
    past_history_conditions = []
    other_notes = None

    if profile:
        if getattr(profile, "date_of_birth", None):
            today = _date.today()
            dob = profile.date_of_birth
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        gender = getattr(profile, "gender", "Unknown") or "Unknown"
        ph = getattr(profile, "past_history", {}) or {}
        past_history_conditions = ph.get("conditions", []) if isinstance(ph, dict) else []
        other_notes = getattr(profile, "other_notes", None) or None

    # --- Past triages ---
    past_triages = []
    try:
        for tr in TriageRecord.objects.filter(user=user).prefetch_related(
            "possible_conditions"
        ).order_by("-created_at")[:3]:
            conditions_found = [
                getattr(pc, "disease_name", "") for pc in tr.possible_conditions.all()[:5]
            ]
            past_triages.append({
                "date": tr.created_at.date().isoformat() if tr.created_at else "Unknown",
                "risk_level": tr.risk_level or "",
                "symptoms": (tr.current_symptoms or "")[:200],
                "conditions": [c for c in conditions_found if c],
            })
    except Exception:
        logger.debug("build_report_insight_context: triage fetch failed", exc_info=True)

    # --- Prior reports (excluding current) ---
    prior_report_findings = []
    try:
        exclude_id = getattr(report, "id", None)
        qs = MedicalReport.objects.filter(user=user)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        for pr in qs.prefetch_related("tests").order_by("-created_at")[:3]:
            abnormal_tests = [
                getattr(t, "test_name", "") for t in pr.tests.filter(is_abnormal=True)[:10]
            ]
            prior_report_findings.append({
                "file_name": pr.file_name or "Report",
                "date": pr.created_at.date().isoformat() if pr.created_at else "",
                "summary": (pr.insights_text or "")[:250],
                "abnormal_tests": [t for t in abnormal_tests if t],
            })
    except Exception:
        logger.debug("build_report_insight_context: prior report fetch failed", exc_info=True)

    # --- Current report data ---
    sd = getattr(report, "structured_data", {}) or {}
    report_data = {
        "file_name": getattr(report, "file_name", "Medical Report") or "Medical Report",
        "extracted_text": getattr(report, "extracted_text", "") or "",
        "tests": sd.get("tests", []),
        "abnormal_findings": sd.get("abnormal_findings", []),
    }

    user_context = {
        "age": age,
        "gender": gender,
        "past_history": past_history_conditions,
        "other_notes": other_notes,
        "past_triages": past_triages,
        "prior_report_findings": prior_report_findings,
    }

    return {"report_data": report_data, "user_context": user_context}


# ---------------------------------------------------------------------------
# JSON extraction (mirrors triage_engine_v2._extract_json)
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Dict:
    """Extract JSON from LLM response text."""
    try:
        # Try to find JSON in code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_str = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            json_str = text[start:end].strip()
        else:
            # Try to find JSON object directly
            start = text.find("{")
            end = text.rfind("}") + 1
            json_str = text[start:end].strip()

        return json.loads(json_str)
    except Exception:
        # Try parsing the whole text
        try:
            return json.loads(text)
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# Response structuring and validation
# ---------------------------------------------------------------------------

def _structure_insight_response(parsed: Dict, ocr_text: str) -> Dict:
    """Validate and normalize the parsed LLM response."""
    tests = parsed.get("tests", [])
    validated_tests = []

    for test in tests:
        if not isinstance(test, dict):
            continue
        validated_tests.append({
            "test_name": str(test.get("test_name", "Unknown Test")),
            "value": str(test.get("value", "")),
            "unit": str(test.get("unit", "")),
            "reference_range": str(test.get("reference_range", "Not specified")),
            "status": str(test.get("status", "unknown")).lower(),
        })

    abnormal = parsed.get("abnormal_findings", [])
    validated_abnormal = []
    for finding in abnormal:
        if not isinstance(finding, dict):
            continue
        validated_abnormal.append({
            "test_name": str(finding.get("test_name", "")),
            "value": str(finding.get("value", "")),
            "status": str(finding.get("status", "unknown")).lower(),
            "explanation": str(finding.get("explanation", "")),
        })

    summary = parsed.get("summary", "")
    if not summary:
        summary = "Report analysis completed. Please review the extracted test values."

    what_this_may_mean = parsed.get("what_this_may_mean", "")
    consult_note = parsed.get(
        "consult_note",
        "Please consult your doctor for a complete interpretation. This is not a diagnosis.",
    )

    return {
        "success": True,
        "degraded": False,
        "tests": validated_tests,
        "summary": summary,
        "abnormal_findings": validated_abnormal,
        "what_this_may_mean": what_this_may_mean,
        "consult_note": consult_note,
        # Raw parsed payload, kept so the stage-3 consultation call can read its
        # own (differently-shaped) JSON without a second parse. Stripped before
        # the response leaves the engine.
        "_raw_parsed": parsed,
    }


def _degraded_response(ocr_text: str, error_msg: str) -> Dict:
    """
    Return a clearly-marked degraded response when LLM structuring fails.

    Per the standing rule: never a dead end, always a real degraded path.
    """
    return {
        "success": True,
        "degraded": True,
        "tests": [],
        "summary": "We extracted the text from your report but couldn't fully structure it into individual test results. The raw text is provided below for your reference.",
        "abnormal_findings": [],
        "what_this_may_mean": "",
        "consult_note": "Please consult your doctor for a complete interpretation of these results. This is not a diagnosis.",
        "raw_ocr_text": ocr_text,
        "structuring_error": error_msg,
    }


# ---------------------------------------------------------------------------
# LLM call helper (shared by both entry points)
# ---------------------------------------------------------------------------

def _call_llm(prompt: str, *, request_id: str | None, user_id: int | None, ocr_text: str) -> Dict:
    """
    Call GeminiProvider with the given prompt, parse JSON, and return a
    structured or degraded response. Never raises.
    """
    log_ctx = {"request_id": request_id, "user_id": user_id}
    model_id = getattr(settings, "REPORT_INSIGHT_MODEL", "gemini-2.5-flash")
    temperature = getattr(settings, "REPORT_INSIGHT_TEMPERATURE", 0.2)

    gemini = GeminiProvider(api_key=GOOGLE_API_KEY)

    # Failover chain, mirroring triage_engine_v2._build_provider_attempts. Gemini
    # alone means a single 429 (free-tier quota is easy to exhaust) degrades every
    # report to "couldn't structure into test results" — indistinguishable to the
    # user from a genuinely unreadable document.
    attempts: List[tuple] = []
    if gemini.is_available:
        attempts.append((gemini, model_id, "gemini"))
    try:
        from .llm_providers.catalog import resolve_fallback_openrouter_model
        openrouter = OpenRouterProvider()
        fallback_model = resolve_fallback_openrouter_model()
        if fallback_model and getattr(openrouter, "is_available", False):
            attempts.append((openrouter, fallback_model, "openrouter"))
    except Exception:
        logger.debug("insight.openrouter_fallback_unavailable", exc_info=True)

    if not attempts:
        logger.warning("insight.gemini_unavailable", extra=log_ctx)
        return _degraded_response(
            ocr_text,
            "AI model not configured (GOOGLE_API_KEY missing). Raw OCR text is provided.",
        )

    messages = [{"role": "user", "content": prompt}]
    result_text = None
    last_error: Optional[ModelProviderError] = None

    for index, (provider, candidate_model, provider_name) in enumerate(attempts):
        try:
            with provider_request_context(request_id=request_id, user_id=user_id):
                result_text = provider.complete(messages, candidate_model, temperature)
            logger.info(
                "insight.llm_completed",
                extra={**log_ctx, "model_id": candidate_model, "provider": provider_name,
                       "used_fallback": index > 0, "response_length": len(result_text)},
            )
            break
        except ModelProviderError as e:
            last_error = e
            logger.warning(
                "insight.provider_failed",
                extra={**log_ctx, "provider": provider_name, "model_id": candidate_model,
                       "status_code": getattr(e, "status_code", None),
                       "will_failover": index < len(attempts) - 1},
            )
        except Exception:
            logger.exception("insight.llm_unexpected", extra={**log_ctx, "provider": provider_name})
            return _degraded_response(ocr_text, "Unexpected error during analysis.")

    if result_text is None:
        message = getattr(last_error, "user_message", None) or "AI analysis is temporarily unavailable."
        logger.warning("insight.llm_failed", extra={**log_ctx, "error": str(last_error)})
        return _degraded_response(ocr_text, f"AI analysis failed: {message}")

    parsed = _extract_json(result_text)
    if not parsed:
        logger.warning(
            "insight.json_parse_failed",
            extra={**log_ctx, "response_preview": result_text[:300]},
        )
        return _degraded_response(
            ocr_text,
            "AI returned a response but it couldn't be parsed into structured data.",
        )

    tests = parsed.get("tests", [])
    if not tests:
        logger.warning("insight.no_tests_extracted", extra=log_ctx)
        result = _structure_insight_response(parsed, ocr_text)
        if not result.get("summary"):
            return _degraded_response(ocr_text, "AI could not extract any test results from the OCR text.")
        return result

    structured = _structure_insight_response(parsed, ocr_text)
    logger.info(
        "insight.generation_complete",
        extra={
            **log_ctx,
            "tests_count": len(structured["tests"]),
            "abnormal_count": len(structured["abnormal_findings"]),
            "degraded": structured["degraded"],
        },
    )
    return structured


# ---------------------------------------------------------------------------
# Stage 2 + 3: ground the extraction, then narrate it
# ---------------------------------------------------------------------------

def _apply_grounding_and_consultation(
    base: Dict,
    user_context: Optional[Dict],
    report_data: Optional[Dict],
    *,
    request_id: str | None,
    user_id: int | None,
    ocr_text: str,
) -> Dict:
    """
    Take a stage-1 extraction result and upgrade it:

      Stage 2 — verify every value arithmetically against the knowledge base,
                overriding whatever status the model guessed.
      Stage 3 — ask the model for a doctor-to-patient consultation built only
                from those verified facts.

    Legacy keys (tests/summary/abnormal_findings/what_this_may_mean/consult_note)
    are preserved so existing callers and the PDF generator keep working.
    """
    ctx = user_context or {}
    log_ctx = {"request_id": request_id, "user_id": user_id}

    grounding = ground_tests(base.get("tests", []), gender=ctx.get("gender"))
    counts = grounding["counts"]
    posture = overall_status(counts)

    logger.info("insight.grounded", extra={**log_ctx, **counts, "overall": posture})

    # Verified findings replace the model's own status calls.
    base["tests"] = [
        {
            "test_name": g["test_name"],
            "value": g["value"],
            "unit": g.get("canonical_unit") or g.get("unit", ""),
            "reference_range": g.get("reference_range", "Not specified"),
            "status": g["status"],
            "verified": g["verified"],
            # Numeric bounds let the UI plot the value against its normal band
            # rather than only printing the range as a string.
            "numeric_value": g.get("numeric_value"),
            "reference_low": g.get("reference_low"),
            "reference_high": g.get("reference_high"),
        }
        for g in grounding["grounded"]
    ]

    base["abnormal_findings"] = [
        {
            "test_name": g["test_name"],
            "value": g["value"],
            "status": g["status"],
            "explanation": (g.get("explanation") or {}).get("simple", "")
            or (g.get("explanation") or {}).get("technical", ""),
            "possible_causes": (g.get("explanation") or {}).get("possible_causes", []),
            "action": (g.get("explanation") or {}).get("action", ""),
            "reference_range": g.get("reference_range", ""),
        }
        for g in grounding["abnormal"]
    ]

    base["verification"] = {**counts, "overall_status": posture}

    # Nothing verified and nothing extracted → leave the stage-1 text as-is.
    if counts["total"] == 0:
        base.pop("_raw_parsed", None)
        return base

    consultation = _fetch_consultation(
        grounding, ctx, report_data, request_id=request_id, user_id=user_id, ocr_text=ocr_text
    )
    if consultation:
        base["consultation"] = consultation
        # Surface the consultation through the legacy narrative fields too, so
        # older consumers (PDF export, chat cards) immediately read better.
        headline = consultation.get("headline", "")
        opening = consultation.get("opening", "")
        merged_summary = " ".join(p for p in (headline, opening) if p).strip()
        if merged_summary:
            base["summary"] = merged_summary

        narrative_parts = [
            consultation.get("whats_working_well", ""),
            consultation.get("connection_to_your_history", ""),
            consultation.get("trend_vs_previous", ""),
        ]
        steps = consultation.get("next_steps") or []
        if steps:
            narrative_parts.append("What to do next: " + "; ".join(str(s) for s in steps[:5]))
        if consultation.get("follow_up"):
            narrative_parts.append(str(consultation["follow_up"]))
        merged_narrative = " ".join(p for p in narrative_parts if p).strip()
        if merged_narrative:
            base["what_this_may_mean"] = merged_narrative

    base.pop("_raw_parsed", None)
    return base


def _fetch_consultation(
    grounding: Dict,
    user_context: Dict,
    report_data: Optional[Dict],
    *,
    request_id: str | None,
    user_id: int | None,
    ocr_text: str,
) -> Optional[Dict]:
    """
    Run the stage-3 narrative call. Returns None if it fails — a missing
    consultation degrades the output's warmth, never its correctness, because
    the verified findings already stand on their own.
    """
    prompt = _build_consultation_prompt(grounding, user_context, report_data)
    result = _call_llm(prompt, request_id=request_id, user_id=user_id, ocr_text=ocr_text)

    if result.get("degraded"):
        logger.info("insight.consultation_unavailable", extra={"request_id": request_id})
        return None

    raw = result.get("_raw_parsed") or {}
    # Only accept it if it actually looks like a consultation, not a re-run of
    # the extraction schema (which is what a stubbed provider would return).
    if not any(k in raw for k in ("headline", "opening", "next_steps", "needs_attention")):
        return None

    def _as_list(key: str) -> List[str]:
        val = raw.get(key) or []
        return [str(v) for v in val if str(v).strip()] if isinstance(val, list) else []

    needs_attention = []
    for item in raw.get("needs_attention") or []:
        if isinstance(item, dict):
            needs_attention.append({
                "test_name": str(item.get("test_name", "")),
                "plain_meaning": str(item.get("plain_meaning", "")),
                "why_it_matters_for_you": str(item.get("why_it_matters_for_you", "")),
                "urgency": str(item.get("urgency", "routine")).lower(),
            })

    return {
        "headline": str(raw.get("headline", "")),
        "opening": str(raw.get("opening", "")),
        "whats_working_well": str(raw.get("whats_working_well", "")),
        "needs_attention": needs_attention,
        "connection_to_your_history": str(raw.get("connection_to_your_history", "")),
        "trend_vs_previous": str(raw.get("trend_vs_previous", "")),
        "next_steps": _as_list("next_steps"),
        "follow_up": str(raw.get("follow_up", "")),
        "questions_for_your_doctor": _as_list("questions_for_your_doctor"),
        "red_flags": _as_list("red_flags"),
        "closing": str(raw.get("closing", "")),
    }


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

def generate_report_insights(
    ocr_text: str,
    user_context: Optional[Dict] = None,
    *,
    request_id: str | None = None,
    user_id: int | None = None,
) -> Dict:
    """
    Generate verified test results and a doctor-voice consultation from OCR text.
    Used by the report upload/analyze pipeline (report_processor.py).

    Pipeline: LLM extraction → arithmetic verification → LLM consultation.
    Falls back gracefully at every stage.
    """
    if not ocr_text or not ocr_text.strip():
        logger.warning("insight.empty_ocr_text", extra={"request_id": request_id, "user_id": user_id})
        return _degraded_response("", "No OCR text to analyze")

    prompt = _build_report_insight_prompt(ocr_text, user_context)
    base = _call_llm(prompt, request_id=request_id, user_id=user_id, ocr_text=ocr_text)
    if base.get("degraded"):
        return base

    return _apply_grounding_and_consultation(
        base, user_context, None,
        request_id=request_id, user_id=user_id, ocr_text=ocr_text,
    )


def generate_combined_report_insights(
    report_data: Dict,
    user_context: Dict,
    *,
    request_id: str | None = None,
    user_id: int | None = None,
) -> Dict:
    """
    Generate history-aware, verified insights for the "Analyze report" view.

    Args:
        report_data: {file_name, extracted_text, tests[], abnormal_findings[]}
        user_context: {age, gender, past_history[], other_notes, past_triages[], prior_report_findings[]}
    """
    ocr_text = report_data.get("extracted_text", "")
    if not ocr_text and not report_data.get("tests"):
        logger.warning("insight.combined.no_content", extra={"request_id": request_id})
        return _degraded_response("", "No report content to analyze")

    prompt = _build_combined_report_prompt(report_data, user_context)
    base = _call_llm(prompt, request_id=request_id, user_id=user_id, ocr_text=ocr_text)
    if base.get("degraded"):
        return base

    return _apply_grounding_and_consultation(
        base, user_context, report_data,
        request_id=request_id, user_id=user_id, ocr_text=ocr_text,
    )
