"""Regression tests for Fix 5: medical report upload type/size validation
and attachment-only file serving.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import MedicalReport

User = get_user_model()


class MedicalReportUploadValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='upload_user', password='password123', email='upload_user@example.com'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.upload_url = reverse('medical-report-list')

    def test_disallowed_extension_rejected_with_400(self):
        malicious_file = SimpleUploadedFile(
            'not_a_report.exe', b'MZ-fake-binary-content', content_type='application/octet-stream'
        )
        response = self.client.post(self.upload_url, {'file': malicious_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MedicalReport.objects.count(), 0)

    def test_disallowed_extension_html_rejected_with_400(self):
        # The stored-XSS-relevant case: an uploaded .html must never be accepted.
        html_file = SimpleUploadedFile(
            'evil.html', b'<script>alert(1)</script>', content_type='text/html'
        )
        response = self.client.post(self.upload_url, {'file': html_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MedicalReport.objects.count(), 0)

    def test_oversized_pdf_rejected_with_400(self):
        oversized_content = b'%PDF-1.4\n' + (b'0' * (10 * 1024 * 1024 + 1))
        oversized_file = SimpleUploadedFile('big_report.pdf', oversized_content, content_type='application/pdf')

        response = self.client.post(self.upload_url, {'file': oversized_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MedicalReport.objects.count(), 0)

    def test_allowed_pdf_within_size_limit_accepted(self):
        good_file = SimpleUploadedFile('report.pdf', b'%PDF-1.4\nreal content', content_type='application/pdf')

        response = self.client.post(self.upload_url, {'file': good_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MedicalReport.objects.count(), 1)


class MedicalReportFileUrlServingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='serve_user', password='password123', email='serve_user@example.com'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_file_url_points_to_attachment_download_endpoint(self):
        good_file = SimpleUploadedFile('report.pdf', b'%PDF-1.4\nreal content', content_type='application/pdf')
        upload = self.client.post(reverse('medical-report-list'), {'file': good_file}, format='multipart')
        self.assertEqual(upload.status_code, status.HTTP_201_CREATED)

        report_id = upload.data['id']
        expected_path = reverse('medical-report-download', kwargs={'pk': report_id})
        self.assertIn(expected_path, upload.data['file_url'])

        download_response = self.client.get(expected_path)
        self.assertEqual(download_response.status_code, status.HTTP_200_OK)
        self.assertIn('attachment', download_response['Content-Disposition'])
