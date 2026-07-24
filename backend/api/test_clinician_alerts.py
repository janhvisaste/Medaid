"""Regression tests for Fix 2: ClinicianAlert creation + auto-assignment.

Covers:
  - A ClinicianAlert is created whenever a TriageRecord is saved with
    risk_level 'high' or 'emergency'.
  - Auto round-robin assignment kicks in for a patient with no prior
    clinician, so no high-risk patient is ever left alert-less.
  - No alert (and no crash) when there is no active clinician at all.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import ClinicianAlert, PatientAssignment, TriageRecord
from .safety.clinician_alerts import create_alert_for_triage_record

User = get_user_model()


class ClinicianAlertCreationTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='patient1', password='password123', email='patient1@example.com', role='patient'
        )

    def _make_triage_record(self, risk_level):
        return TriageRecord.objects.create(
            user=self.patient,
            current_symptoms='some symptoms',
            risk_level=risk_level,
            reasoning='test reasoning',
        )

    def test_no_alert_for_low_or_medium_risk(self):
        for risk_level in ('low', 'medium'):
            with self.subTest(risk_level=risk_level):
                record = self._make_triage_record(risk_level)
                alert = create_alert_for_triage_record(record)
                self.assertIsNone(alert)
                self.assertEqual(ClinicianAlert.objects.filter(patient=self.patient).count(), 0)

    def test_alert_created_for_high_risk_with_no_prior_clinician(self):
        clinician = User.objects.create_user(
            username='clin1', password='password123', email='clin1@example.com', role='clinician'
        )
        record = self._make_triage_record('high')

        alert = create_alert_for_triage_record(record)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, 'high_risk')
        self.assertEqual(alert.clinician, clinician)
        self.assertEqual(alert.patient, self.patient)
        self.assertEqual(ClinicianAlert.objects.filter(patient=self.patient).count(), 1)
        # Auto-assignment must have happened too.
        self.assertTrue(
            PatientAssignment.objects.filter(patient=self.patient, clinician=clinician).exists()
        )

    def test_alert_created_for_emergency_risk(self):
        User.objects.create_user(
            username='clin2', password='password123', email='clin2@example.com', role='clinician'
        )
        record = self._make_triage_record('emergency')

        alert = create_alert_for_triage_record(record)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, 'new_emergency')

    def test_round_robin_picks_least_loaded_clinician(self):
        busy_clinician = User.objects.create_user(
            username='busy_clin', password='password123', email='busy@example.com', role='clinician'
        )
        idle_clinician = User.objects.create_user(
            username='idle_clin', password='password123', email='idle@example.com', role='clinician'
        )

        # Load up the "busy" clinician with existing assignments for other patients.
        for i in range(3):
            other_patient = User.objects.create_user(
                username=f'other_patient_{i}', password='password123',
                email=f'other{i}@example.com', role='patient'
            )
            other_record = TriageRecord.objects.create(
                user=other_patient, current_symptoms='x', risk_level='high', reasoning=''
            )
            PatientAssignment.objects.create(
                patient=other_patient, clinician=busy_clinician, triage_record=other_record, status='active'
            )

        record = self._make_triage_record('high')
        alert = create_alert_for_triage_record(record)

        self.assertEqual(alert.clinician, idle_clinician)

    def test_reuses_existing_clinician_for_continuity(self):
        first_clinician = User.objects.create_user(
            username='clin_a', password='password123', email='clin_a@example.com', role='clinician'
        )
        User.objects.create_user(
            username='clin_b', password='password123', email='clin_b@example.com', role='clinician'
        )

        first_record = self._make_triage_record('high')
        first_alert = create_alert_for_triage_record(first_record)
        self.assertEqual(first_alert.clinician, first_clinician)

        second_record = self._make_triage_record('emergency')
        second_alert = create_alert_for_triage_record(second_record)

        # Continuity of care: same clinician should be alerted again rather
        # than round-robining to clin_b, since the patient already has one.
        self.assertEqual(second_alert.clinician, first_clinician)

    def test_no_clinician_available_does_not_crash(self):
        # No clinician users exist at all.
        record = self._make_triage_record('emergency')
        alert = create_alert_for_triage_record(record)
        self.assertIsNone(alert)
        self.assertEqual(ClinicianAlert.objects.filter(patient=self.patient).count(), 0)


class ClinicianAlertWiredIntoEmergencyPathTests(TestCase):
    """End-to-end: the emergency short-circuit path (Fix 1) must also create
    a ClinicianAlert (Fix 2), not just a TriageRecord."""

    def setUp(self):
        self.patient = User.objects.create_user(
            username='patient2', password='password123', email='patient2@example.com', role='patient'
        )
        self.clinician = User.objects.create_user(
            username='clin3', password='password123', email='clin3@example.com', role='clinician'
        )

    def test_create_emergency_triage_record_creates_alert(self):
        from .safety.emergency_check import create_emergency_triage_record

        triage_record, _assessment = create_emergency_triage_record(
            user=self.patient,
            symptoms_text="I have severe chest pain and can't breathe",
            input_mode='text',
        )

        self.assertEqual(triage_record.risk_level, 'emergency')
        alert = ClinicianAlert.objects.filter(patient=self.patient).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, 'new_emergency')
        self.assertEqual(alert.clinician, self.clinician)
