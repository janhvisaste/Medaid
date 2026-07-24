"""Assemble prior-assessment context for a patient's triage prompt.

TriageRecord rows already capture every previous assessment for a user. This
module turns the recent ones into a compact, bounded summary the LLM can
actually reason over ("this is the third headache episode this month, and the
last one was assessed high risk") instead of each assessment starting cold.

Everything here is bounded on purpose: a triage prompt that grows with a
patient's history would eventually blow the context window and silently start
truncating the *current* symptoms, which is the one thing that must survive.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Bounds for what we feed the model.
DEFAULT_MAX_RECORDS = 5
DEFAULT_WITHIN_DAYS = 365
MAX_SYMPTOM_CHARS = 160
MAX_CONDITIONS_PER_RECORD = 3


def _truncate(text: Optional[str], limit: int) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def get_prior_assessments(
    user,
    *,
    max_records: int = DEFAULT_MAX_RECORDS,
    within_days: int = DEFAULT_WITHIN_DAYS,
    exclude_record_id: Optional[int] = None,
) -> List[Dict]:
    """Return the patient's most recent prior assessments, newest first.

    Uses prefetch_related so rendering conditions stays a fixed number of
    queries regardless of how many records come back.
    """
    from datetime import timedelta

    from django.utils import timezone

    from .models import TriageRecord

    if user is None or not getattr(user, "pk", None):
        return []

    cutoff = timezone.now() - timedelta(days=within_days)
    queryset = (
        TriageRecord.objects.filter(user=user, created_at__gte=cutoff)
        .prefetch_related("possible_conditions")
        .order_by("-created_at")
    )
    if exclude_record_id:
        queryset = queryset.exclude(pk=exclude_record_id)

    prior = []
    for record in queryset[:max_records]:
        conditions = [
            condition.disease_name
            for condition in sorted(
                record.possible_conditions.all(),
                key=lambda c: c.confidence or 0,
                reverse=True,
            )[:MAX_CONDITIONS_PER_RECORD]
        ]
        prior.append({
            "date": record.created_at.date().isoformat(),
            "risk_level": record.risk_level,
            "symptoms": _truncate(record.current_symptoms, MAX_SYMPTOM_CHARS),
            "conditions": conditions,
            "assessment_source": record.assessment_source,
        })
    return prior


def format_prior_assessments(prior: List[Dict]) -> str:
    """Render prior assessments as compact prompt text."""
    if not prior:
        return ""

    lines = []
    for entry in prior:
        conditions = ", ".join(entry["conditions"]) if entry["conditions"] else "no specific conditions recorded"
        lines.append(
            f"- {entry['date']} | assessed {entry['risk_level']} risk | "
            f"reported: {entry['symptoms'] or 'not recorded'} | considered: {conditions}"
        )
    return "\n".join(lines)


def build_patient_history_context(
    user,
    *,
    max_records: int = DEFAULT_MAX_RECORDS,
    within_days: int = DEFAULT_WITHIN_DAYS,
    exclude_record_id: Optional[int] = None,
) -> Dict:
    """Return {'prior_assessments': [...], 'prior_assessments_text': str}.

    Never raises: a history lookup failure must degrade the prompt, not fail
    the patient's assessment.
    """
    try:
        prior = get_prior_assessments(
            user,
            max_records=max_records,
            within_days=within_days,
            exclude_record_id=exclude_record_id,
        )
    except Exception as error:
        logger.warning(
            "triage.prior_assessment_lookup_failed",
            extra={"user_id": getattr(user, "pk", None), "error_type": type(error).__name__},
        )
        return {"prior_assessments": [], "prior_assessments_text": ""}

    return {
        "prior_assessments": prior,
        "prior_assessments_text": format_prior_assessments(prior),
    }
