"""Escalation for critical values found in an uploaded medical report.

The report pipeline already classifies each extracted test as
normal/high/low/critical (see report_insight_engine). Until now that
classification terminated in a display string: a report showing a critically
low haemoglobin was rendered to the patient, persisted, and no clinician was
ever told. This module closes that gap.

Deliberately NOT keyword-based. Running the symptom emergency-keyword screen
(safety.emergency_check) over OCR'd report text misfires badly - clinical prose
mentions "chest pain", "seizure" and "overdose" routinely in history,
indication and negated-finding sections - so it would fire on resolved or
family-history events while staying silent on the abnormal number that
actually matters. Critical-value status is the signal that matches lab-report
semantics.

Scope: `critical` is now assigned by lab_reference.classify_value(), which
compares the parsed value arithmetically against gender-aware thresholds in
medical_knowledge_base.json — not by the LLM. (It previously was LLM-assigned,
which was unreliable; see lab_reference for the evidence.)

Residual caveat: coverage is bounded by the knowledge base. A test with no
reference data on file classifies as `unknown`, never `critical`, so a missed
critical value is still possible for out-of-scope analytes. This raises the
floor substantially; it is still not a guarantee, and should not be described
to clinicians as a complete safety net.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Alert type used for a critical report finding. Reuses the existing
# ClinicianAlert.ALERT_TYPES vocabulary rather than adding a new one.
CRITICAL_ALERT_TYPE = "high_risk"

# Cap on how many test names get named in the alert message.
MAX_NAMED_TESTS = 5


def is_critical_status(status) -> bool:
    """True if a test status denotes a critical value, in any casing.

    The two report paths historically disagreed: the local pipeline compared
    `status == 'critical'` (lower) while the detailed formatter matched
    `'CRITICAL' in status` (upper, to catch CRITICAL_HIGH / CRITICAL_LOW).
    Normalising in one place stops the two from drifting apart again.
    """
    return "critical" in str(status or "").lower()


def select_critical_findings(items) -> List[dict]:
    """Filter a list of test/finding dicts down to the critical ones.

    Accepts either report shape - both carry a 'status' key - so callers do
    not need to know which pipeline produced the list.
    """
    return [
        item
        for item in (items or [])
        if isinstance(item, dict) and is_critical_status(item.get("status"))
    ]


def _finding_name(finding: dict) -> str:
    return str(finding.get("test_name") or finding.get("test") or "unnamed test").strip()


def content_key_for(file_bytes) -> str:
    """Stable per-document key for uploads that were never persisted.

    Content-addressed on purpose. Filename alone would be actively unsafe:
    the same name with new contents (a follow-up CBC saved as 'report.pdf')
    would dedupe against the previous upload and silently suppress a genuine
    new critical result. Identical bytes really are the same document, so
    suppressing those is correct; a follow-up report hashes differently and
    alerts as it should.
    """
    import hashlib

    return hashlib.sha256(file_bytes or b"").hexdigest()[:16]


def _dedupe_marker(report_id, content_key) -> Optional[str]:
    """Stable marker embedded in the alert message for idempotency.

    ClinicianAlert has no FK to MedicalReport, so re-analysing the same report
    would otherwise raise a duplicate alert every time. A FK plus a
    unique-together would be the cleaner fix; this keeps the change
    migration-free at the cost of a string match.

    Persisted reports key on report_id; direct uploads (which have no row to
    point at) key on a hash of the file contents. Returns None when neither is
    available, in which case the caller alerts without deduping - a duplicate
    alert is a far better failure than a dropped critical result.
    """
    if report_id is not None:
        return f"[report:{report_id}]"
    if content_key:
        return f"[upload:{content_key}]"
    return None


def escalate_critical_findings(
    *, user, report_id, file_name, critical_findings, content_key=None
) -> Optional[object]:
    """Raise ONE ClinicianAlert when a report contains critical values.

    Alert-only by design: no TriageRecord is created. The patient uploaded a
    document, they did not request a triage assessment, and fabricating one
    would pollute both their assessment history and the prior-assessment
    context fed into future triage prompts.

    Because no TriageRecord exists there is no PatientAssignment to attach
    (PatientAssignment.triage_record is non-nullable), so the alert is created
    with assignment=None. ClinicianAlertSerializer resolves risk_level for such
    alerts from alert_type.

    No-op (returns None) when there are no critical findings, when an alert for
    this report already exists, or when no clinician is available.
    """
    from ..models import ClinicianAlert
    from .clinician_alerts import pick_clinician_for_patient

    if not critical_findings:
        return None

    marker = _dedupe_marker(report_id, content_key)
    if marker and ClinicianAlert.objects.filter(
        patient=user, alert_type=CRITICAL_ALERT_TYPE, message__contains=marker
    ).exists():
        logger.info(
            "critical_findings.alert_already_exists",
            extra={"report_id": report_id, "user_id": user.pk, "marker": marker},
        )
        return None
    if not marker:
        logger.warning(
            "critical_findings.no_dedupe_key",
            extra={"user_id": user.pk, "file_name": file_name},
        )

    clinician = pick_clinician_for_patient(user)
    if not clinician:
        # Same failure mode as clinician_alerts: log loudly. A critical result
        # with nobody to route it to is worse than a missing feature.
        logger.error(
            "critical_findings.no_clinician_available",
            extra={"report_id": report_id, "user_id": user.pk, "count": len(critical_findings)},
        )
        return None

    names = [_finding_name(f) for f in critical_findings[:MAX_NAMED_TESTS]]
    remainder = len(critical_findings) - len(names)
    named = ", ".join(names) + (f" (+{remainder} more)" if remainder > 0 else "")
    message = (
        f"Critical result(s) in uploaded report '{file_name}' for {user.email}: "
        f"{named}. Review the report. {marker or ''}"
    ).strip()

    alert = ClinicianAlert.objects.create(
        clinician=clinician,
        patient=user,
        assignment=None,
        alert_type=CRITICAL_ALERT_TYPE,
        message=message,
    )
    logger.warning(
        "critical_findings.alert_created",
        extra={
            "report_id": report_id,
            "user_id": user.pk,
            "clinician_id": clinician.pk,
            "count": len(critical_findings),
        },
    )
    return alert
