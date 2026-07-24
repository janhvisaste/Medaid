import json
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .models import DietaryAdvice, MedicalReport, User, UserProfile
from .triage_engine_v2 import TriageEngineV2


class KnownGoodProvider:
    is_available = True

    def __init__(self):
        self.calls = []

    def complete(self, messages, model_id, temperature):
        self.calls.append({'messages': messages, 'model_id': model_id, 'temperature': temperature})
        return json.dumps({
            'risk_level': 'medium',
            'risk_probability': 0.55,
            'confidence': 0.88,
            'reasoning': 'The symptom pattern needs routine clinical evaluation.',
            'possible_conditions': [{
                'disease': 'Viral Upper Respiratory Infection',
                'confidence': 0.35,
                'supporting_evidence': ['Cough and fatigue'],
            }],
            'recommendations': ['Rest, hydrate, and arrange a clinical review if symptoms persist.'],
            'when_to_seek_care': 'Seek urgent care if breathing becomes difficult or symptoms worsen quickly.',
        })


class DietaryKnownGoodProvider:
    def complete(self, messages, model_id, temperature):
        return json.dumps({
            'summary': 'A simple, flexible starting point based on the information you shared.',
            'cards': [{
                'category': 'Balanced option',
                'name': 'Lentil and vegetable bowl',
                'rationale': 'A practical source of plant protein and fibre for a balanced meal.',
                'nutrient_highlights': [{'label': 'Plant protein', 'value': 'Lentils'}],
            }],
            'daily_pattern': ['Choose a varied mix of foods that fits your routine.'],
            'next_step': 'Discuss condition-specific changes with a clinician when relevant.',
        })


class ConsultationFlowIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='flow@example.com',
            email='flow@example.com',
            password='password-123',
        )
        UserProfile.objects.create(user=self.user, gender='F')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_report_only_consultation_also_enters_history_stage(self):
        response = self.client.post(
            reverse('start_consultation'),
            {'symptoms': '', 'has_report': True},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['session']['stage'], 'history')

    @patch('api.views.get_report_processor')
    def test_uploaded_report_can_be_analyzed_by_returned_id(self, get_processor):
        class FakeReportProcessor:
            def extract_and_analyze(self, file_bytes, file_name, content_type='', user_context=None,
                                    request_id=None, user_id=None):
                return {
                    'success': True,
                    'extracted_text': 'Hemoglobin is within the supplied reference range.',
                    'ocr_path': 'tesseract',
                    'ocr_confidence': 0.0,
                    'structured_data': {
                        'tests': [{
                            'test_name': 'Hemoglobin',
                            'value': '13.2',
                            'unit': 'g/dL',
                            'reference_range': '12.0 - 16.0',
                            'status': 'normal',
                        }],
                        'summary': 'Report processed.',
                        'abnormal_findings': [],
                        'what_this_may_mean': '',
                        'consult_note': 'Consult your doctor.',
                        'degraded': False,
                    },
                    'insights_text': 'Hemoglobin is within the supplied reference range.',
                    'error': None,
                }

        get_processor.return_value = FakeReportProcessor()
        upload = self.client.post(
            reverse('medical-report-list'),
            {'file': SimpleUploadedFile('report.pdf', b'%PDF-test', content_type='application/pdf')},
            format='multipart',
        )
        self.assertEqual(upload.status_code, 201)
        report_id = upload.data['id']

        analyzed = self.client.post(
            reverse('analyze_report'),
            {'report_id': report_id},
            format='json',
        )

        self.assertEqual(analyzed.status_code, 201)
        self.assertEqual(analyzed.data['report_id'], report_id)
        self.assertEqual(analyzed.data['status'], 'completed')
        self.assertEqual(MedicalReport.objects.get(id=report_id).extracted_text, 'Hemoglobin is within the supplied reference range.')
        self.assertEqual(MedicalReport.objects.get(id=report_id).status, 'completed')

    @patch('api.views.get_triage_engine_v2')
    def test_consultation_request_to_persisted_triage_result(self, get_engine):
        provider = KnownGoodProvider()
        get_engine.return_value = TriageEngineV2(
            default_provider=provider,
            openrouter_provider=provider,
        )

        started = self.client.post(
            reverse('start_consultation'),
            {'symptoms': 'cough and fatigue for two days'},
            format='json',
        )
        self.assertEqual(started.status_code, 201)
        self.assertEqual(started.data['session']['stage'], 'history')
        session_id = started.data['session']['id']

        history = self.client.post(
            reverse('submit_consultation_step', args=[session_id]),
            {'medical_history': {'conditions': []}},
            format='json',
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data['session']['stage'], 'questions')

        questions = self.client.get(reverse('get_clarifying_questions', args=[session_id]))
        self.assertEqual(questions.status_code, 200)
        self.assertTrue(questions.data['questions'])

        answers = self.client.post(
            reverse('submit_consultation_step', args=[session_id]),
            {'answers': [{'question': questions.data['questions'][0]['question'], 'answer': 'Two days'}]},
            format='json',
        )
        self.assertEqual(answers.status_code, 200)
        self.assertEqual(answers.data['session']['stage'], 'assessment')

        completed = self.client.post(
            reverse('submit_consultation_step', args=[session_id]),
            {},
            format='json',
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data['session']['stage'], 'completed')
        self.assertIsNotNone(completed.data['session']['triage_id'])
        # Two provider calls: clarifying-question generation, then the
        # assessment. Question generation used to be stubbed out and made no
        # call at all, which is what this previously asserted.
        self.assertEqual(len(provider.calls), 2)

        history_response = self.client.get(reverse('triage_history'))
        self.assertEqual(history_response.status_code, 200)
        # triage_history is now paginated: {count, next, previous, results}.
        record = history_response.data['results'][0]
        self.assertEqual(record['risk_level'], 'medium')
        self.assertFalse(record['degraded'])
        self.assertIn('Viral Upper Respiratory Infection', record['possible_conditions'])


@override_settings(
    DIETARY_DEFAULT_FREE_MODEL='test/free-model',
    DIETARY_THROTTLE_SECONDS=0,
    DIETARY_GLOBAL_RPM_LIMIT=10,
    DIETARY_GLOBAL_DAILY_LIMIT=10,
    DIETARY_GLOBAL_ACTIVE_LIMIT=2,
)
class DietaryFlowIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(
            username='dietary-flow@example.com',
            email='dietary-flow@example.com',
            password='password-123',
        )
        UserProfile.objects.create(user=self.user, past_history={'conditions': [{'name': 'Hypertension'}]})
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('api.dietary_service.OpenRouterProvider', return_value=DietaryKnownGoodProvider())
    @patch(
        'api.dietary_service.get_free_openrouter_models',
        return_value=[{'id': 'test/free-model', 'name': 'Test Free Model', 'context_length': 32768, 'is_free': True}],
    )
    def test_dietary_request_to_provider_persistence_and_response(self, _models, _provider):
        response = self.client.post(
            reverse('dietary_recommendations'),
            {'risk_level': 'medium', 'symptoms': 'I want balanced meals'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['model_id'], 'test/free-model')
        self.assertTrue(response.data['cards'])
        self.assertEqual(DietaryAdvice.objects.filter(user=self.user).count(), 1)
        self.assertEqual(response.data['context_used']['profile'], True)
