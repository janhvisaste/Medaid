from django.test import TestCase
from api.models import User, ClinicianAlert, TriageRecord, PatientAssignment
from api.safety.critical_findings import (
    is_critical_status, select_critical_findings, escalate_critical_findings)
from api.serializers import ClinicianAlertSerializer

class CriticalFindings(TestCase):
    def setUp(self):
        self.pat = User.objects.create_user(username='p@x.com', email='p@x.com', password='pw12345678', role='patient')
        self.doc = User.objects.create_user(username='d@x.com', email='d@x.com', password='pw12345678', role='clinician')

    def test_casing_normalised_both_pipelines(self):
        for s in ['critical','CRITICAL','CRITICAL_HIGH','Critical_Low',' critical ']:
            self.assertTrue(is_critical_status(s), s)
        for s in ['normal','NORMAL','high','low','unknown',None,'']:
            self.assertFalse(is_critical_status(s), repr(s))
        items=[{'status':'critical','test_name':'Hb'},{'status':'CRITICAL_HIGH','test_name':'K'},{'status':'high','test_name':'WBC'}]
        self.assertEqual([f['test_name'] for f in select_critical_findings(items)], ['Hb','K'])

    def test_escalates_alert_only_no_triage_record(self):
        a = escalate_critical_findings(user=self.pat, report_id=7, file_name='cbc.pdf',
              critical_findings=[{'test_name':'Hemoglobin','status':'critical'}])
        self.assertIsNotNone(a)
        self.assertEqual(a.clinician, self.doc)
        self.assertIsNone(a.assignment)
        self.assertIn('Hemoglobin', a.message)
        # alert-only: nothing fabricated
        self.assertEqual(TriageRecord.objects.count(), 0)
        self.assertEqual(PatientAssignment.objects.count(), 0)
        # orphan alert still renders a real risk tier
        self.assertEqual(ClinicianAlertSerializer(a).data['risk_level'], 'high')

    def test_idempotent_per_report(self):
        f=[{'test_name':'Hb','status':'critical'}]
        escalate_critical_findings(user=self.pat, report_id=9, file_name='r.pdf', critical_findings=f)
        escalate_critical_findings(user=self.pat, report_id=9, file_name='r.pdf', critical_findings=f)
        self.assertEqual(ClinicianAlert.objects.count(), 1)
        escalate_critical_findings(user=self.pat, report_id=10, file_name='r2.pdf', critical_findings=f)
        self.assertEqual(ClinicianAlert.objects.count(), 2)

    def test_upload_dedupes_on_content_not_filename(self):
        """Same bytes => same document => suppress. New bytes => new alert.

        Filename is deliberately held CONSTANT across both uploads: keying on
        filename would wrongly suppress the second, genuinely-new critical result.
        """
        from api.safety.critical_findings import content_key_for
        f = [{'test_name': 'Hb', 'status': 'critical'}]
        same = b'%PDF-1.4 cbc original'
        for _ in range(2):
            escalate_critical_findings(user=self.pat, report_id=None, file_name='report.pdf',
                                       critical_findings=f, content_key=content_key_for(same))
        self.assertEqual(ClinicianAlert.objects.count(), 1, 'identical bytes must dedupe')

        # Follow-up report, SAME filename, different contents -> must alert.
        escalate_critical_findings(user=self.pat, report_id=None, file_name='report.pdf',
                                   critical_findings=f,
                                   content_key=content_key_for(b'%PDF-1.4 cbc follow-up'))
        self.assertEqual(ClinicianAlert.objects.count(), 2, 'new contents must not be suppressed')

    def test_upload_dedupe_is_scoped_per_patient(self):
        from api.safety.critical_findings import content_key_for
        other = User.objects.create_user(username='o@x.com', email='o@x.com',
                                         password='pw12345678', role='patient')
        f = [{'test_name': 'Hb', 'status': 'critical'}]
        key = content_key_for(b'shared bytes')
        escalate_critical_findings(user=self.pat, report_id=None, file_name='r.pdf',
                                   critical_findings=f, content_key=key)
        escalate_critical_findings(user=other, report_id=None, file_name='r.pdf',
                                   critical_findings=f, content_key=key)
        self.assertEqual(ClinicianAlert.objects.count(), 2)

    def test_no_key_still_alerts_rather_than_dropping(self):
        f = [{'test_name': 'Hb', 'status': 'critical'}]
        for _ in range(2):
            escalate_critical_findings(user=self.pat, report_id=None, file_name='r.pdf',
                                       critical_findings=f, content_key=None)
        # Duplicates are acceptable; a dropped critical result is not.
        self.assertEqual(ClinicianAlert.objects.count(), 2)

    def test_noop_when_nothing_critical(self):
        self.assertIsNone(escalate_critical_findings(user=self.pat, report_id=1, file_name='x', critical_findings=[]))
        self.assertEqual(ClinicianAlert.objects.count(), 0)

    def test_no_clinician_available_returns_none(self):
        self.doc.delete()
        self.assertIsNone(escalate_critical_findings(user=self.pat, report_id=2, file_name='x',
              critical_findings=[{'test_name':'Hb','status':'critical'}]))
