"""Tests for the shared vague-input clarifying-question gate.

The trigger (`should_request_clarification`) is defined once in
assessment_quality and reused by /triage/assess/ and the chat endpoint, so a
thin/vague symptom report is met with a clarifying follow-up before a
low-confidence assessment is returned. These tests lock in that both entry
points honour the shared gate and its bypass paths.
"""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .assessment_quality import should_request_clarification
from .models import User, UserProfile, ChatConversation, ChatMessage, TriageRecord


FAKE_ASSESSMENT = {
    'risk_level': 'low',
    'risk_probability': 0.2,
    'reasoning': 'Mild symptoms.',
    'confidence': 0.5,
    'possible_conditions': [],
    'recommendations': ['Rest'],
    'when_to_seek_care': 'If it worsens',
    'disclaimer': 'Consult a professional.',
}

FAKE_QUESTIONS = [
    {'question': 'How long have you had this?', 'type': 'text'},
    {'question': 'Rate the severity.', 'type': 'scale'},
]


class ShouldRequestClarificationTests(TestCase):
    def test_short_input_is_vague(self):
        self.assertTrue(should_request_clarification('mild cough'))

    def test_low_signal_longer_input_is_vague(self):
        # Enough words but no duration/severity/location/modifier signals.
        self.assertTrue(
            should_request_clarification('i really do not feel very good at all right now honestly')
        )

    def test_rich_detailed_input_is_not_vague(self):
        text = (
            'I have had a sharp throbbing headache on the left side of my head for '
            'the past three days and it gets worse every evening'
        )
        self.assertFalse(should_request_clarification(text))

    def test_clarifying_round_disables_the_gate(self):
        self.assertFalse(
            should_request_clarification('mild cough', had_clarifying_round=True)
        )

    def test_empty_input_is_not_gated(self):
        self.assertFalse(should_request_clarification(''))


class AssessClarificationGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='vague@example.com', email='vague@example.com', password='pw'
        )
        UserProfile.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch('api.views.get_triage_engine_v2')
    def test_vague_input_returns_clarifying_questions_without_saving(self, mocked_engine):
        mocked_engine.return_value.generate_clarifying_questions.return_value = FAKE_QUESTIONS

        response = self.client.post(
            reverse('assess_symptoms'), {'current_symptoms': 'headache'}, format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['needs_clarification'])
        self.assertEqual(response.data['clarifying_questions'], FAKE_QUESTIONS)
        # No assessment ran and nothing was persisted.
        mocked_engine.return_value.assess.assert_not_called()
        self.assertEqual(TriageRecord.objects.filter(user=self.user).count(), 0)

    @patch('api.views.get_triage_engine_v2')
    def test_skip_clarification_bypasses_the_gate(self, mocked_engine):
        mocked_engine.return_value.assess.return_value = dict(FAKE_ASSESSMENT)

        response = self.client.post(
            reverse('assess_symptoms'),
            {'current_symptoms': 'headache', 'skip_clarification': True},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        mocked_engine.return_value.generate_clarifying_questions.assert_not_called()
        mocked_engine.return_value.assess.assert_called_once()

    @patch('api.views.get_triage_engine_v2')
    def test_clarifying_answers_proceed_to_assessment_and_lift_cap(self, mocked_engine):
        mocked_engine.return_value.assess.return_value = dict(FAKE_ASSESSMENT)

        response = self.client.post(
            reverse('assess_symptoms'),
            {
                'current_symptoms': 'headache',
                'clarifying_answers': [
                    {'question': 'How long?', 'answer': 'Three days'},
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        mocked_engine.return_value.generate_clarifying_questions.assert_not_called()
        call = mocked_engine.return_value.assess.call_args
        # had_clarifying_round is forwarded so the short-input cap is lifted,
        # and the answer text is folded into the symptoms the model sees.
        self.assertTrue(call.kwargs['had_clarifying_round'])
        self.assertIn('Three days', call.args[0])


class ChatClarificationGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='chat@example.com', email='chat@example.com', password='pw'
        )
        UserProfile.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.conversation = ChatConversation.objects.create(user=self.user, title='c')

    @patch('api.views.get_triage_engine_v2')
    def test_vague_first_message_gets_clarifying_questions(self, mocked_engine):
        mocked_engine.return_value.generate_clarifying_questions.return_value = FAKE_QUESTIONS

        response = self.client.post(
            reverse('chat_send_message', args=[self.conversation.id]),
            {'content': 'headache'},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['needs_clarification'])
        assistant = response.data['assistant_message']
        self.assertIn('How long have you had this?', assistant['content'])
        self.assertTrue(assistant['metadata']['clarification_requested'])

    @patch('api.views.get_chat_service')
    @patch('api.views.get_triage_engine_v2')
    def test_does_not_ask_again_when_prior_turn_already_asked(self, mocked_engine, mocked_chat):
        # Previous assistant turn already requested clarification.
        ChatMessage.objects.create(
            conversation=self.conversation, role='user', content='headache'
        )
        ChatMessage.objects.create(
            conversation=self.conversation, role='assistant',
            content='A few quick questions...',
            metadata={'clarification_requested': True},
        )
        mocked_chat.return_value.estimate_tokens.return_value = 3
        mocked_chat.return_value.generate_ai_response.return_value = {
            'content': 'Here is your guidance.', 'tokens_used': 5,
        }
        mocked_chat.return_value.should_suggest_new_chat.return_value = False

        response = self.client.post(
            reverse('chat_send_message', args=[self.conversation.id]),
            {'content': 'three days, throbbing'},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        # The user is answering our questions, so we proceed to a real response.
        mocked_engine.return_value.generate_clarifying_questions.assert_not_called()
        mocked_chat.return_value.generate_ai_response.assert_called_once()
