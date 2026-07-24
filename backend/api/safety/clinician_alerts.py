"""Clinician notification logic for high-risk / emergency triage records.

This module is the single place responsible for making sure a high-risk or
emergency TriageRecord always results in a ClinicianAlert. It also handles
auto-assigning a clinician (simple round-robin/least-loaded pick among active
clinicians) when the patient doesn't already have one, so no high-risk
patient is ever left without a clinician to alert.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Which TriageRecord.risk_level values require a clinician to be notified,
# and which ClinicianAlert.alert_type each maps to.
ALERT_TYPE_BY_RISK = {
    "emergency": "new_emergency",
    "high": "high_risk",
}


def _alert_type_for(triage_record) -> Optional[str]:
    """Decide whether (and how) a TriageRecord should notify a clinician.

    Risk tier takes priority. A record that isn't high/emergency but is
    flagged requires_human_review (e.g. a degraded/failed AI assessment)
    still gets a 'follow_up' alert - it must never be silently indistinguishable
    from a normal low/medium-risk result.
    """
    alert_type = ALERT_TYPE_BY_RISK.get(triage_record.risk_level)
    if alert_type:
        return alert_type
    if getattr(triage_record, "requires_human_review", False):
        return "follow_up"
    return None


def _pick_clinician_round_robin():
    """Pick an active clinician, preferring whoever currently has the fewest
    patient assignments (a simple round-robin/load-balance, not a full
    pool/queue system)."""
    from django.db.models import Count

    from ..models import PatientAssignment, User

    clinicians = list(User.objects.filter(role="clinician", is_active=True).order_by("id"))
    if not clinicians:
        return None

    counts = {clinician.id: 0 for clinician in clinicians}
    assignment_counts = (
        PatientAssignment.objects.filter(clinician__in=clinicians)
        .values("clinician_id")
        .annotate(n=Count("id"))
    )
    for row in assignment_counts:
        counts[row["clinician_id"]] = row["n"]

    return min(clinicians, key=lambda clinician: (counts[clinician.id], clinician.id))


def pick_clinician_for_patient(patient):
    """Pick the clinician who should hear about this patient.

    Prefers continuity of care - the patient's most recent clinician - and
    falls back to a least-loaded round-robin pick. Shared by the triage alert
    path and the critical-report-finding path (see safety.critical_findings)
    so both route to the same clinician for the same patient.

    Returns None when there is no active clinician at all.
    """
    from ..models import PatientAssignment

    existing_assignment = (
        PatientAssignment.objects.filter(patient=patient).order_by("-assigned_at").first()
    )
    if existing_assignment:
        return existing_assignment.clinician
    return _pick_clinician_round_robin()


def ensure_clinician_assignment(patient, triage_record):
    """Return a PatientAssignment linking patient -> a clinician for this
    triage_record, creating one (with auto-assignment) if needed.

    Returns None if there is no active clinician available at all.
    """
    from ..models import PatientAssignment

    existing_for_record = PatientAssignment.objects.filter(
        patient=patient, triage_record=triage_record
    ).first()
    if existing_for_record:
        return existing_for_record

    clinician = pick_clinician_for_patient(patient)
    if not clinician:
        return None

    return PatientAssignment.objects.create(
        patient=patient,
        clinician=clinician,
        triage_record=triage_record,
        status="active",
        priority=1 if triage_record.risk_level == "emergency" else 2,
    )


def create_alert_for_triage_record(triage_record) -> Optional[object]:
    """Ensure a clinician is alerted for a high-risk/emergency TriageRecord,
    or one flagged requires_human_review (e.g. a degraded AI assessment).

    No-op (returns None) if none of those apply. Returns the created
    ClinicianAlert, or None if no clinician could be found/assigned.
    """
    from ..models import ClinicianAlert

    alert_type = _alert_type_for(triage_record)
    if not alert_type:
        return None

    assignment = ensure_clinician_assignment(triage_record.user, triage_record)
    if not assignment:
        logger.error(
            "clinician_alert.no_clinician_available",
            extra={"triage_record_id": triage_record.pk, "risk_level": triage_record.risk_level},
        )
        return None

    if triage_record.risk_level == "emergency":
        label = "Emergency"
    elif triage_record.risk_level == "high":
        label = "High-risk"
    else:
        label = "Needs review (degraded/low-confidence)"
    reasoning_preview = (triage_record.reasoning or "")[:200]
    message = f"{label} assessment for {triage_record.user.email}: {reasoning_preview}"

    alert = ClinicianAlert.objects.create(
        clinician=assignment.clinician,
        patient=triage_record.user,
        assignment=assignment,
        alert_type=alert_type,
        message=message,
    )
    logger.info(
        "clinician_alert.created",
        extra={
            "triage_record_id": triage_record.pk,
            "clinician_id": assignment.clinician_id,
            "alert_type": alert_type,
        },
    )
    return alert
