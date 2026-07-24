"""
Tests for user-initiated deletion of their own records.

The load-bearing case is the assessment guard: PatientAssignment cascades off
TriageRecord and ClinicianAlert cascades off that, so an unguarded delete would
let a patient silently erase a clinician's pending review work.
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from api.models import (
    ChatConversation, ClinicianAlert, MedicalReport, PatientAssignment,
    TriageRecord, User,
)


def _patient(email="patient@example.com"):
    return User.objects.create_user(username=email, email=email, password="testpass123", role="patient")


def _clinician(email="doc@example.com"):
    return User.objects.create_user(username=email, email=email, password="testpass123", role="clinician")


def _triage(user, risk="medium"):
    return TriageRecord.objects.create(
        user=user, current_symptoms="headache", risk_level=risk,
        risk_probability=0.4, confidence=0.7,
    )


class ConversationDeletionTest(TestCase):
    def setUp(self):
        self.user = _patient()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_user_can_delete_own_conversation(self):
        convo = ChatConversation.objects.create(user=self.user, title="Chest pain")
        resp = self.client.delete(f"/api/chat/conversations/{convo.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(ChatConversation.objects.filter(id=convo.id).exists())

    def test_cannot_delete_another_users_conversation(self):
        other = _patient("other@example.com")
        convo = ChatConversation.objects.create(user=other, title="Not yours")
        resp = self.client.delete(f"/api/chat/conversations/{convo.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ChatConversation.objects.filter(id=convo.id).exists())


class MedicalReportDeletionTest(TestCase):
    def setUp(self):
        self.user = _patient()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _report(self, user):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return MedicalReport.objects.create(
            user=user,
            file=SimpleUploadedFile("r.pdf", b"%PDF-x", content_type="application/pdf"),
            file_name="r.pdf", file_type="application/pdf", file_size=6,
        )

    def test_user_can_delete_own_report(self):
        report = self._report(self.user)
        resp = self.client.delete(f"/api/medical-reports/{report.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(MedicalReport.objects.filter(id=report.id).exists())

    def test_cannot_delete_another_users_report(self):
        report = self._report(_patient("other@example.com"))
        resp = self.client.delete(f"/api/medical-reports/{report.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(MedicalReport.objects.filter(id=report.id).exists())


class AssessmentDeletionTest(TestCase):
    def setUp(self):
        self.user = _patient()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_user_can_delete_unassigned_assessment(self):
        record = _triage(self.user)
        resp = self.client.delete(f"/api/triage/{record.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(TriageRecord.objects.filter(id=record.id).exists())

    def test_cannot_delete_another_users_assessment(self):
        record = _triage(_patient("other@example.com"))
        resp = self.client.delete(f"/api/triage/{record.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(TriageRecord.objects.filter(id=record.id).exists())

    def test_assessment_under_active_clinician_review_is_refused(self):
        """The core guard: deleting would cascade away the clinician's assignment."""
        record = _triage(self.user, risk="high")
        PatientAssignment.objects.create(
            patient=self.user, clinician=_clinician(), triage_record=record, status="active",
        )

        resp = self.client.delete(f"/api/triage/{record.id}/")

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["reason"], "under_clinician_review")
        self.assertTrue(TriageRecord.objects.filter(id=record.id).exists())

    def test_unacknowledged_alert_survives_the_refusal(self):
        """Regression: an unguarded delete would take the alert with it."""
        record = _triage(self.user, risk="emergency")
        assignment = PatientAssignment.objects.create(
            patient=self.user, clinician=_clinician(), triage_record=record, status="active",
        )
        alert = ClinicianAlert.objects.create(
            clinician=assignment.clinician, patient=self.user, assignment=assignment,
            alert_type="high_risk", message="Critical value", is_read=False,
        )

        self.client.delete(f"/api/triage/{record.id}/")

        self.assertTrue(ClinicianAlert.objects.filter(id=alert.id).exists())
        self.assertTrue(PatientAssignment.objects.filter(id=assignment.id).exists())

    def test_resolved_assignment_no_longer_blocks_deletion(self):
        record = _triage(self.user)
        PatientAssignment.objects.create(
            patient=self.user, clinician=_clinician(), triage_record=record, status="resolved",
        )
        resp = self.client.delete(f"/api/triage/{record.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(TriageRecord.objects.filter(id=record.id).exists())

    def test_missing_assessment_returns_404(self):
        resp = self.client.delete("/api/triage/999999/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class DeletionRequiresAuthTest(TestCase):
    def test_anonymous_cannot_delete(self):
        user = _patient()
        record = _triage(user)
        convo = ChatConversation.objects.create(user=user, title="x")
        anon = APIClient()

        self.assertIn(anon.delete(f"/api/triage/{record.id}/").status_code, (401, 403))
        self.assertIn(anon.delete(f"/api/chat/conversations/{convo.id}/").status_code, (401, 403))
        self.assertTrue(TriageRecord.objects.filter(id=record.id).exists())
        self.assertTrue(ChatConversation.objects.filter(id=convo.id).exists())
