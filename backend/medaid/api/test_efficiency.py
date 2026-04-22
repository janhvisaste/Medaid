from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.urls import reverse
from .models import UserProfile, TriageRecord, PossibleCondition, MedicalReport, MedicalTest, AbnormalResult

User = get_user_model()

class HealthPassportEfficiencyTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='efficiency_user', password='password123', email='eff@example.com')
        self.profile = UserProfile.objects.create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create 5 TriageRecords with conditions
        for i in range(5):
            t_record = TriageRecord.objects.create(user=self.user, current_symptoms=f'Symptom {i}', risk_level='medium', reasoning='')
            PossibleCondition.objects.create(triage_record=t_record, disease_name=f'Disease {i}A', confidence=0.8)
            PossibleCondition.objects.create(triage_record=t_record, disease_name=f'Disease {i}B', confidence=0.5)

        # Create 5 MedicalReports with tests
        for i in range(5):
            report = MedicalReport.objects.create(user=self.user, file_name=f'Report {i}', file_size=100)
            test1 = MedicalTest.objects.create(medical_report=report, test_name=f'Test {i}A', test_value=1.0, test_unit='units')
            test2 = MedicalTest.objects.create(medical_report=report, test_name=f'Test {i}B', test_value=2.0, test_unit='units', is_abnormal=True)
            AbnormalResult.objects.create(medical_test=test2, status='High', concern_level='High', interpretation='High value')

    def test_get_health_passport_queries(self):
        """
        Tests that get_health_passport uses prefetch_related and runs in a constant number of queries.
        Usually it is around 4-6 queries: Session/Auth + UserProfile + TriageRecords + Conditions + MedicalReports + MedicalTests + AbnormalResults.
        Without prefetch, it would be 4 + 2 * (number of records/reports), which is N+1.
        We expect 6 queries or less for fetching this data.
        """
        # User auth, UserProfile, TriageRecord, PossibleCondition, MedicalReport, MedicalTest/AbnormalResult
        url = reverse('health_passport')
        with self.assertNumQueries(6):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(len(data['triage_history']), 5)
        self.assertEqual(len(data['medical_reports']), 5)
        self.assertEqual(data['medical_reports'][0]['abnormal_count'], 1)
