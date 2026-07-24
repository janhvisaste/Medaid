"""Tests for per-endpoint LLM quota guards (api/llm_quota.py) and the 429
responses at the triage, chat, and report-insight call sites."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .llm_quota import LLMQuotaExceeded, check_llm_quota, note_global_usage
from .models import ChatConversation, User


class QuotaUnitTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(TRIAGE_USER_RPM_LIMIT=2, TRIAGE_USER_DAILY_LIMIT=99,
                       TRIAGE_GLOBAL_RPM_LIMIT=99, TRIAGE_GLOBAL_DAILY_LIMIT=99)
    def test_per_user_rpm_trips_and_is_scoped(self):
        check_llm_quota('triage', user_id=1)
        check_llm_quota('triage', user_id=1)
        with self.assertRaises(LLMQuotaExceeded) as ctx:
            check_llm_quota('triage', user_id=1)
        self.assertEqual(ctx.exception.scope, 'user')
        self.assertEqual(ctx.exception.period, 'minute')
        # A different user is unaffected by user 1's ceiling.
        check_llm_quota('triage', user_id=2)

    @override_settings(TRIAGE_USER_RPM_LIMIT=99, TRIAGE_USER_DAILY_LIMIT=99,
                       TRIAGE_GLOBAL_RPM_LIMIT=2, TRIAGE_GLOBAL_DAILY_LIMIT=99)
    def test_global_rpm_trips_across_users(self):
        check_llm_quota('triage', user_id=1)
        check_llm_quota('triage', user_id=2)
        with self.assertRaises(LLMQuotaExceeded) as ctx:
            check_llm_quota('triage', user_id=3)
        self.assertEqual(ctx.exception.scope, 'global')

    @override_settings(TRIAGE_USER_RPM_LIMIT=99, TRIAGE_USER_DAILY_LIMIT=99,
                       TRIAGE_GLOBAL_RPM_LIMIT=1, TRIAGE_GLOBAL_DAILY_LIMIT=99)
    def test_rejected_request_consumes_no_quota(self):
        check_llm_quota('triage', user_id=1)          # global rpm now at 1/1
        with self.assertRaises(LLMQuotaExceeded):
            check_llm_quota('triage', user_id=2)      # rejected
        # The rejected call rolled back its user reservations too, so user 2's
        # own counter shows no net consumption (released back to 0).
        from django.utils import timezone
        key = 'llmq:triage:user:2:rpm:' + timezone.now().strftime('%Y%m%d%H%M')
        self.assertIn(cache.get(key), (0, None))

    @override_settings(CHAT_GLOBAL_RPM_LIMIT=1, CHAT_GLOBAL_DAILY_LIMIT=99,
                       CHAT_USER_RPM_LIMIT=99, CHAT_USER_DAILY_LIMIT=99)
    def test_note_global_usage_consumes_shared_quota_without_gating(self):
        # A title-generation-style global note never raises...
        note_global_usage('chat')
        # ...but it consumed the shared minute quota, so the next gated call trips.
        with self.assertRaises(LLMQuotaExceeded) as ctx:
            check_llm_quota('chat', user_id=1)
        self.assertEqual(ctx.exception.scope, 'global')

    @override_settings(REPORT_INSIGHT_GLOBAL_RPM_LIMIT=1, REPORT_INSIGHT_GLOBAL_DAILY_LIMIT=99,
                       REPORT_INSIGHT_USER_RPM_LIMIT=99, REPORT_INSIGHT_USER_DAILY_LIMIT=99)
    def test_background_task_success_counts_against_report_insight_global(self):
        """The async report task's internal Gemini call is not a quota-free
        loophole: on the success branch it notes global report_insight usage,
        so an interactive report-insight call then trips the shared ceiling."""
        from unittest.mock import MagicMock, patch
        from . import tasks

        report = MagicMock(pk=1, file_type='application/pdf', file_name='x.pdf', user_id=1)
        report.file.read.return_value = b'bytes'
        pipeline_result = {'success': True, 'extracted_text': 't',
                           'structured_data': {'tests': []}, 'insights_text': 'i',
                           'ocr_path': 'tesseract'}

        with patch('api.tasks.MedicalReport.objects.get', return_value=report), \
                patch('api.tasks.get_report_processor') as mock_proc:
            mock_proc.return_value.extract_and_analyze.return_value = pipeline_result
            tasks.process_medical_report_task(1)

        # The task's Gemini call was counted, so the shared ceiling (1) is now hit.
        with self.assertRaises(LLMQuotaExceeded) as ctx:
            check_llm_quota('report_insight', user_id=1)
        self.assertEqual(ctx.exception.scope, 'global')

    @override_settings(REPORT_INSIGHT_GLOBAL_RPM_LIMIT=1, REPORT_INSIGHT_GLOBAL_DAILY_LIMIT=99,
                       REPORT_INSIGHT_USER_RPM_LIMIT=99, REPORT_INSIGHT_USER_DAILY_LIMIT=99)
    def test_background_task_ocr_failure_does_not_count(self):
        """OCR-total-failure returns before the Gemini call, so nothing is
        counted - the interactive ceiling stays available."""
        from unittest.mock import MagicMock, patch
        from . import tasks

        report = MagicMock(pk=2, file_type='application/pdf', file_name='x.pdf', user_id=1)
        report.file.read.return_value = b'bytes'

        with patch('api.tasks.MedicalReport.objects.get', return_value=report), \
                patch('api.tasks.get_report_processor') as mock_proc:
            mock_proc.return_value.extract_and_analyze.return_value = {
                'success': False, 'error': 'All OCR paths failed'}
            tasks.process_medical_report_task(2)

        # No usage counted: the ceiling of 1 is still free.
        check_llm_quota('report_insight', user_id=1)  # must not raise


@override_settings(TRIAGE_USER_RPM_LIMIT=1, TRIAGE_USER_DAILY_LIMIT=99,
                   TRIAGE_GLOBAL_RPM_LIMIT=99, TRIAGE_GLOBAL_DAILY_LIMIT=99)
class TriageGateResponseTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='p@x.com', email='p@x.com',
                                              password='pw12345678', role='patient')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('api.views.get_triage_engine_v2')
    def test_second_call_is_429_with_safe_labeled_body(self, mock_engine):
        # A benign assessment for the first (allowed) call.
        mock_engine.return_value.assess.return_value = {
            'risk_level': 'low', 'reasoning': 'ok', 'confidence': 0.5,
            'possible_conditions': [], 'recommendations': [],
        }
        url = reverse('assess_symptoms')
        # skip_clarification keeps this focused on quota behaviour rather than
        # the vague-input clarifying-question gate, which is tested separately.
        first = self.client.post(url, {'current_symptoms': 'mild sore throat for 2 days', 'skip_clarification': True}, format='json')
        self.assertIn(first.status_code, (200, 201))

        second = self.client.post(url, {'current_symptoms': 'mild sore throat for 2 days', 'skip_clarification': True}, format='json')
        self.assertEqual(second.status_code, 429)
        self.assertTrue(second.data['rate_limited'])
        self.assertEqual(second.data['quota_scope'], 'user')
        self.assertTrue(second.data['requires_human_review'])
        self.assertEqual(second.data['possible_conditions'], [])   # no fabricated differential
        self.assertIn('Retry-After', second)

    @patch('api.views.create_emergency_triage_record')
    def test_emergency_is_never_rate_limited(self, mock_emergency):
        # Exhaust the user's triage quota first.
        check_llm_quota('triage', self.user.pk)
        mock_emergency.return_value = (
            type('T', (), {'pk': 1, 'created_at': __import__('django').utils.timezone.now()})(),
            {'reasoning': 'r', 'confidence': 1.0, 'recommendations': [], 'when_to_seek_care': 'now'},
        )
        url = reverse('assess_symptoms')
        # An emergency keyword must bypass the (now-exhausted) quota entirely.
        resp = self.client.post(url, {'current_symptoms': 'severe chest pain and cannot breathe'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['risk_level'], 'emergency')
        mock_emergency.assert_called_once()
