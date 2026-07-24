"""
Deterministic lab-value grounding.

Reference ranges, status classification, and baseline explanations come from
medical_knowledge_base.json — NOT from the language model.

Why this module exists
----------------------
The Lab-AI study (arXiv:2409.18986) measured unaugmented LLMs answering lab
reference-range questions at 38.4% accuracy, rising to 99.3% when the same
model was grounded in retrieved source data. Asking a model to decide whether
a value is "high" or "low" is therefore the single least reliable thing we
could do with it — and it is also the most safety-critical field we produce.

So the split is:
  - Arithmetic  (this module) decides normal / low / high / critical.
  - The LLM     only writes prose, and only about findings we already verified.

medical_knowledge_base.json shipped with the repo but nothing ever imported it;
this module is what finally puts it to work.
"""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medical_knowledge_base.json")

# Statuses that mean "this needs to be looked at", in escalating order.
ABNORMAL_STATUSES = ("low", "high", "critical_low", "critical_high")
CRITICAL_STATUSES = ("critical_low", "critical_high")

_SEVERITY_RANK = {
    "normal": 0,
    "unknown": 1,
    "low": 2,
    "high": 2,
    "critical_low": 3,
    "critical_high": 3,
}


@lru_cache(maxsize=1)
def load_knowledge_base() -> Dict[str, Any]:
    """Load and cache the knowledge base. Returns empty scaffolding on failure."""
    try:
        with open(_KB_PATH, "r", encoding="utf-8") as fh:
            kb = json.load(fh)
        logger.info(
            "lab_reference.kb_loaded",
            extra={
                "ranges": len(kb.get("reference_ranges", {})),
                "explanations": len(kb.get("explanations", {})),
                "aliases": len(kb.get("test_name_aliases", {})),
            },
        )
        return kb
    except Exception:
        logger.exception("lab_reference.kb_load_failed", extra={"path": _KB_PATH})
        return {"reference_ranges": {}, "explanations": {}, "test_name_aliases": {}}


def _normalize_gender(gender: Optional[str]) -> Optional[str]:
    """Map assorted gender representations onto the KB's male/female suffixes."""
    if not gender:
        return None
    g = str(gender).strip().lower()
    if g in ("m", "male"):
        return "male"
    if g in ("f", "female"):
        return "female"
    return None


def normalize_test_name(raw_name: str) -> Optional[str]:
    """
    Resolve an OCR'd test label to a canonical KB key.

    Handles the noise real reports carry: case, punctuation, embedded
    abbreviations ("SGOT (AST)"), and the alias table.
    Returns None when the test isn't in the knowledge base.
    """
    if not raw_name:
        return None

    kb = load_knowledge_base()
    aliases = kb.get("test_name_aliases", {})
    ranges = kb.get("reference_ranges", {})

    cleaned = str(raw_name).strip().lower()
    # Drop OCR-quality markers we add ourselves upstream.
    cleaned = cleaned.replace("(ocr unclear)", "").strip()
    # Collapse whitespace.
    cleaned = re.sub(r"\s+", " ", cleaned)

    candidates = [cleaned]

    # "SGOT (AST)" → also try "sgot" and "ast"
    paren = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", cleaned)
    if paren:
        candidates.append(paren.group(1).strip())
        candidates.append(paren.group(2).strip())

    # Strip punctuation entirely ("r.b.c. count" → "rbc count")
    candidates.append(re.sub(r"[.\-_/]", "", cleaned))
    candidates.append(re.sub(r"[^a-z0-9 ]", "", cleaned).strip())
    # Underscore form, matching KB key style ("platelet count" → "platelet_count")
    candidates.append(re.sub(r"\s+", "_", re.sub(r"[^a-z0-9 ]", "", cleaned).strip()))

    for cand in candidates:
        if not cand:
            continue
        if cand in aliases:
            return aliases[cand]
        if cand in ranges:
            return cand

    return None


def parse_numeric(raw_value: Any) -> Optional[float]:
    """
    Pull a comparable number out of an OCR'd result cell.

    Tolerates thousands separators, embedded units, and censored values
    ("<0.1", "> 100") which are treated as their boundary. Returns None when
    there is no usable number — callers must not guess.
    """
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    text = str(raw_value).strip()
    if not text:
        return None

    # Remove thousands separators only when they sit between digits (1,200)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    # Some locales use comma as the decimal mark (12,5) — only if no dot present
    if "." not in text:
        text = re.sub(r"(?<=\d),(?=\d{1,2}\b)", ".", text)

    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def get_reference_range(canonical_name: str, gender: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Look up the reference range, preferring a gender-specific variant.

    e.g. hemoglobin + female → 'hemoglobin_female' if present, else 'hemoglobin'.
    """
    kb = load_knowledge_base()
    ranges = kb.get("reference_ranges", {})

    g = _normalize_gender(gender)
    if g:
        gendered = f"{canonical_name}_{g}"
        if gendered in ranges:
            return {**ranges[gendered], "_key": gendered, "_gender_specific": True}

    if canonical_name in ranges:
        return {**ranges[canonical_name], "_key": canonical_name, "_gender_specific": False}
    return None


def classify_value(value: float, ref: Dict[str, Any]) -> str:
    """Pure arithmetic classification. No model involved."""
    crit_low = ref.get("critical_low")
    crit_high = ref.get("critical_high")
    low = ref.get("low")
    high = ref.get("high")

    if crit_low is not None and value < crit_low:
        return "critical_low"
    if crit_high is not None and value > crit_high:
        return "critical_high"
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "normal"


def get_explanation(canonical_name: str, status: str) -> Dict[str, Any]:
    """
    Fetch the curated explanation for a test+status.

    Falls back: critical-specific → plain direction → generic default.
    Always returns a dict (possibly empty-ish) so callers need no None checks.
    """
    kb = load_knowledge_base()
    explanations = kb.get("explanations", {})

    keys: List[str] = []
    if status in CRITICAL_STATUSES:
        direction = "low" if status == "critical_low" else "high"
        keys.append(f"{canonical_name}_critical_{direction}")
        keys.append(f"{canonical_name}_{direction}")
        keys.append(f"default_{direction}")
    elif status in ("low", "high"):
        keys.append(f"{canonical_name}_{status}")
        keys.append(f"default_{status}")
    elif status == "normal":
        keys.append(f"{canonical_name}_normal")
        keys.append("default_normal")

    for key in keys:
        if key in explanations:
            return {**explanations[key], "_source_key": key}
    return {}


def format_range(ref: Dict[str, Any]) -> str:
    """Human-readable canonical range, e.g. '13.0 - 17.0 g/dL'."""
    low, high, unit = ref.get("low"), ref.get("high"), ref.get("unit", "")
    if low is None or high is None:
        return "Not specified"
    return f"{low} - {high}{(' ' + unit) if unit else ''}"


def ground_tests(
    tests: List[Dict[str, Any]],
    gender: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Verify a list of extracted tests against the knowledge base.

    Input items look like {test_name, value, unit, reference_range, status?}.
    The incoming `status` is treated as untrusted and replaced whenever we can
    classify the value ourselves.

    Returns:
        {
          "grounded":   [ ...every test, annotated... ],
          "abnormal":   [ ...subset needing attention, worst-first... ],
          "critical":   [ ...subset at critical thresholds... ],
          "counts":     {total, verified, normal, abnormal, critical, unverified},
        }
    """
    grounded: List[Dict[str, Any]] = []

    for test in tests or []:
        if not isinstance(test, dict):
            continue

        raw_name = str(test.get("test_name", "")).strip()
        raw_value = test.get("value", "")
        canonical = normalize_test_name(raw_name)
        numeric = parse_numeric(raw_value)

        item: Dict[str, Any] = {
            "test_name": raw_name or "Unknown Test",
            "canonical_name": canonical,
            "value": str(raw_value),
            "numeric_value": numeric,
            "unit": str(test.get("unit", "") or ""),
            # What the lab itself printed on the page, if anything.
            "printed_reference_range": str(test.get("reference_range", "") or "Not specified"),
            "model_suggested_status": str(test.get("status", "") or "unknown").lower(),
            "verified": False,
            "status": "unknown",
            "explanation": {},
        }

        ref = get_reference_range(canonical, gender) if canonical else None

        if ref is not None and numeric is not None:
            status = classify_value(numeric, ref)
            item.update({
                "verified": True,
                "status": status,
                "reference_range": format_range(ref),
                "reference_low": ref.get("low"),
                "reference_high": ref.get("high"),
                "canonical_unit": ref.get("unit", ""),
                "gender_specific_range": ref.get("_gender_specific", False),
                "explanation": get_explanation(canonical, status),
            })
            # Visibility into model-vs-arithmetic disagreement; the arithmetic wins.
            if item["model_suggested_status"] not in ("", "unknown", status):
                logger.info(
                    "lab_reference.status_corrected",
                    extra={
                        "test": canonical,
                        "model_said": item["model_suggested_status"],
                        "verified_as": status,
                    },
                )
        else:
            # Not in the KB, or unparseable value: keep it, mark it unverified,
            # and fall back to the printed range. Never silently drop a result.
            item["reference_range"] = item["printed_reference_range"]
            item["status"] = "unknown"

        grounded.append(item)

    abnormal = [g for g in grounded if g["status"] in ABNORMAL_STATUSES]
    abnormal.sort(key=lambda g: _SEVERITY_RANK.get(g["status"], 0), reverse=True)
    critical = [g for g in grounded if g["status"] in CRITICAL_STATUSES]

    counts = {
        "total": len(grounded),
        "verified": sum(1 for g in grounded if g["verified"]),
        "normal": sum(1 for g in grounded if g["status"] == "normal"),
        "abnormal": len(abnormal),
        "critical": len(critical),
        "unverified": sum(1 for g in grounded if not g["verified"]),
    }

    return {
        "grounded": grounded,
        "abnormal": abnormal,
        "critical": critical,
        "counts": counts,
    }


def overall_status(counts: Dict[str, int]) -> str:
    """Headline posture for the report: urgent / attention / reassuring."""
    if counts.get("critical", 0) > 0:
        return "urgent"
    if counts.get("abnormal", 0) > 0:
        return "attention_needed"
    if counts.get("verified", 0) > 0:
        return "reassuring"
    return "unclear"


# ---------------------------------------------------------------------------
# OCR text triage
# ---------------------------------------------------------------------------

# A number followed by a recognised lab unit — the strongest signal that a line
# carries an actual result rather than prose.
_VALUE_UNIT_RE = re.compile(
    r"\d+\.?\d*\s*(?:mg/d[lL]|g/d[lL]|µg/d[lL]|ug/d[lL]|ng/m[lL]|pg/m[lL]|"
    r"m?IU/[lL]|U/[lL]|mmol/[lL]|µmol/[lL]|mEq/[lL]|cells?/cumm|mill/cmm|"
    r"lakhs?/cumm|/u[lL]|/µ[lL]|fL|pg\b|%)",
    re.IGNORECASE,
)
# A printed reference interval, e.g. "12.0 - 16.0" or "70 – 100".
_REF_RANGE_RE = re.compile(r"\d+\.?\d*\s*[-–—]\s*\d+\.?\d*")
# Dates (08-06-2026, 8/6/26) otherwise read as reference intervals and inflate
# the score of cover pages, which are dense with dates and nothing else.
_DATE_RE = re.compile(r"\b\d{1,4}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{2,4}\b")


def score_lab_relevance(page_text: str) -> int:
    """
    Heuristic score for how likely a page contains actual lab results.

    Marketing covers, disclaimers and tables of contents score ~0; pages of
    values score high. Deliberately cheap and dependency-free — this runs
    before any model call.
    """
    if not page_text or not page_text.strip():
        return 0

    kb = load_knowledge_base()
    # Strip dates first so they can't be counted as reference intervals.
    cleaned = _DATE_RE.sub(" ", page_text)
    lowered = cleaned.lower()

    score = 0
    score += 3 * len(_VALUE_UNIT_RE.findall(cleaned))
    score += 2 * len(_REF_RANGE_RE.findall(cleaned))

    # Known test names carry real weight; only count each name once so a
    # glossary page listing every test doesn't outrank a page of results.
    for name in kb.get("reference_ranges", {}):
        if name.replace("_", " ") in lowered:
            score += 3
    for alias in kb.get("test_name_aliases", {}):
        if len(alias) > 2 and alias in lowered:
            score += 2

    return score


def select_lab_relevant_text(ocr_text: str, max_chars: int = 60000) -> str:
    """
    Reduce multi-page OCR output to the parts that actually contain results.

    Real lab PDFs (especially "smart report" packages) open with several pages
    of branding, disclaimers and a table of contents. Naively truncating the
    text to fit a prompt therefore spends the entire budget on cover pages and
    shows the model zero results — which is exactly how a full report ends up
    reported as "couldn't structure into test results".

    Pages are scored, zero-signal pages dropped, and the rest kept in their
    original order up to `max_chars`. If nothing scores, the head of the text
    is returned unchanged so behaviour never gets worse than before.
    """
    if not ocr_text:
        return ""
    if len(ocr_text) <= max_chars and "--- PAGE BREAK ---" not in ocr_text:
        return ocr_text

    pages = ocr_text.split("--- PAGE BREAK ---")
    scored = [(index, page, score_lab_relevance(page)) for index, page in enumerate(pages)]
    relevant = [item for item in scored if item[2] > 0]

    if not relevant:
        logger.info("lab_reference.no_relevant_pages", extra={"pages": len(pages)})
        return ocr_text[:max_chars]

    # Keep document order; drop the lowest-scoring pages first only if we must.
    kept: List[tuple] = []
    budget = max_chars
    for item in sorted(relevant, key=lambda i: i[2], reverse=True):
        chunk = item[1]
        if len(chunk) <= budget:
            kept.append(item)
            budget -= len(chunk)
    if not kept:
        kept = [max(relevant, key=lambda i: i[2])]

    kept.sort(key=lambda i: i[0])
    dropped = len(pages) - len(kept)
    logger.info(
        "lab_reference.pages_filtered",
        extra={"total_pages": len(pages), "kept": len(kept), "dropped": dropped},
    )
    return "\n--- PAGE BREAK ---\n".join(item[1].strip() for item in kept)


def build_grounded_facts_block(result: Dict[str, Any]) -> str:
    """
    Render verified findings as a compact factual block for the narrative prompt.

    The model is given these as established facts to explain — it is never asked
    to decide them.
    """
    lines: List[str] = []

    for item in result.get("abnormal", []):
        exp = item.get("explanation") or {}
        causes = ", ".join((exp.get("possible_causes") or [])[:5])
        lines.append(
            f"- {item['test_name']}: {item['value']} {item.get('canonical_unit') or item.get('unit', '')} "
            f"(normal {item.get('reference_range', 'n/a')}) → VERIFIED {item['status'].upper()}"
        )
        if exp.get("simple"):
            lines.append(f"    Established meaning: {exp['simple']}")
        if causes:
            lines.append(f"    Known possible causes: {causes}")
        if exp.get("action"):
            lines.append(f"    Standard advice: {exp['action']}")

    normals = [g for g in result.get("grounded", []) if g["status"] == "normal"]
    if normals:
        lines.append(
            "- Verified NORMAL: " + ", ".join(f"{n['test_name']} ({n['value']})" for n in normals[:15])
        )

    unverified = [g for g in result.get("grounded", []) if not g["verified"]]
    if unverified:
        lines.append(
            "- NOT independently verified (no reference data on file, describe cautiously): "
            + ", ".join(f"{u['test_name']} ({u['value']})" for u in unverified[:15])
        )

    return "\n".join(lines) if lines else "No test values could be verified."
