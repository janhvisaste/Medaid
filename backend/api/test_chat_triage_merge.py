"""Tests for merging chat and the guided assessment flow into one pipeline.

chat_service.generate_ai_response() has always run a full TriageEngineV2.assess()
call under the hood - it just discarded the structured result and kept only the
formatted text. This merge persists that same result as a TriageRecord (via the
shared _persist_triage_assessment helper also used by /triage/assess/) and
surfaces it in the assistant message's metadata, so a chat conversation and a
guided assessment are the same underlying record: it shows up in Assessment
history and can generate a PDF either way.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import ChatConversation, TriageRecord

User = get_user_model()

FAKE_ASSESSMENT = {
    "risk_level": "medium",
    "risk_probability": 0.5,
    "confidence": 0.6,
    "reasoning": "Consistent with a viral upper respiratory infection.",
    "possible_conditions": [{"disease": "Common cold", "confidence": 0.4}],
    "recommendations": ["Rest", "Fluids"],
    "when_to_seek_care": "If fever persists beyond 3 days",
    "disclaimer": "test disclaimer",
    "model_id": "test-model",
    "model_provider": "gemini",
    "degraded": False,
    "requires_human_review": False,
}


class ChatPersistsTriageRecordTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='chatmerge@example.com', email='chatmerge@example.com', password='pw'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.conversation = ChatConversation.objects.create(user=self.user, title='c')

    @patch('api.chat_service.TriageEngineV2')
    def test_completed_assessment_creates_a_triage_record(self, mocked_engine_cls):
        mocked_engine_cls.return_value.assess.return_value = dict(FAKE_ASSESSMENT)

        response = self.client.post(
            reverse('chat_send_message', args=[self.conversation.id]),
            {'content': 'I have had a persistent mild cough and a sore throat for the last four days, and it seems to be getting slightly worse each evening'},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(TriageRecord.objects.filter(user=self.user).count(), 1)
        record = TriageRecord.objects.get(user=self.user)
        self.assertEqual(record.risk_level, 'medium')
        self.assertEqual(record.input_mode, 'chat')

        metadata = response.data['assistant_message']['metadata']
        self.assertEqual(metadata['triage_id'], record.pk)
        self.assertEqual(metadata['risk_level'], 'medium')
        self.assertEqual(metadata['confidence'], 0.6)
        self.assertEqual(metadata['recommendations'], ['Rest', 'Fluids'])
        self.assertEqual(
            metadata['possible_conditions'], [{'disease': 'Common cold', 'confidence': 0.4}]
        )

    @patch('api.chat_service.TriageEngineV2')
    def test_pdf_can_be_generated_from_a_chat_originated_record(self, mocked_engine_cls):
        mocked_engine_cls.return_value.assess.return_value = dict(FAKE_ASSESSMENT)

        send = self.client.post(
            reverse('chat_send_message', args=[self.conversation.id]),
            {'content': 'I have had a persistent mild cough and a sore throat for the last four days, and it seems to be getting slightly worse each evening'},
            format='json',
        )
        triage_id = send.data['assistant_message']['metadata']['triage_id']

        pdf_response = self.client.get(reverse('download_assessment_pdf', args=[triage_id]))
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response['Content-Type'], 'application/pdf')

    @patch('api.chat_service.TriageEngineV2')
    def test_exception_fallback_does_not_create_a_triage_record(self, mocked_engine_cls):
        # generate_ai_response's outer except returns a dict with no
        # 'risk_level' key at all - that must NOT be persisted as a TriageRecord.
        mocked_engine_cls.return_value.assess.side_effect = RuntimeError('provider exploded')
        response = self.client.post(
            reverse('chat_send_message', args=[self.conversation.id]),
            {'content': 'I have had a persistent mild cough and a sore throat for the last four days, and it seems to be getting slightly worse each evening'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(TriageRecord.objects.filter(user=self.user).count(), 0)
        self.assertIsNone(response.data['assistant_message']['metadata'].get('triage_id'))
