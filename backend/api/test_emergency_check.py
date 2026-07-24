"""Regression tests for Fix 1: emergency keyword check on all symptom-entry paths.

Covers:
  - contains_emergency_keyword() keyword coverage + negation handling
  - Parity across the three entry points: assess_symptoms, start_consultation /
    submit_consultation_step, and chat_send_message
  - TriageEngineV2.assess() short-circuiting before any provider call
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import ConsultationSession, TriageRecord
from .safety.emergency_check import contains_emergency_keyword
from .triage_engine_v2 import TriageEngineV2

User = get_user_model()

EMERGENCY_TEXT = "I have severe chest pain and can't breathe"


class ContainsEmergencyKeywordTests(TestCase):
    """Unit tests for the shared keyword + negation matcher."""

    def test_expanded_keywords_detected(self):
        positive_cases = [
            "sudden facial drooping on one side",
            "I think this is a heart attack",
            "signs of anaphylaxis after the bee sting",
            "possible overdose on pills",
            "feeling suicidal tonight",
            "accidental poisoning from cleaning fluid",
            "vomiting blood since this morning",
            "sudden numbness down my left arm",
            "severe abdominal pain that won't go away",
            "infant high fever and won't wake up",
            "pregnant and bleeding heavily",
        ]
        for text in positive_cases:
            with self.subTest(text=text):
                self.assertTrue(contains_emergency_keyword(text), text)

    def test_negated_phrasing_does_not_trigger(self):
        negative_cases = [
            "no chest pain",
            "denies difficulty breathing",
            "ruling out seizure",
            "patient has no history of seizure",
        ]
        for text in negative_cases:
            with self.subTest(text=text):
                self.assertFalse(contains_emergency_keyword(text), text)

    def test_forward_negated_phrasing_does_not_trigger(self):
        # Answers to a yes/no follow-up often echo the symptom BEFORE the
        # negation ("chest pain: no") rather than after ("no chest pain") -
        # especially when the assistant's own question named the symptom
        # first. Regression for a real false-positive: a patient answering
        # "5, chest pain no, no bluish tint" to a severity/chest-pain/cyanosis
        # follow-up was incorrectly routed to a full emergency response.
        negative_cases = [
            "5, chest pain no, no bluish tint",
            "chest pain: no",
            "chest pain no.",
            "chest pain no,",
            "chest pain - no",
        ]
        for text in negative_cases:
            with self.subTest(text=text):
                self.assertFalse(contains_emergency_keyword(text), text)

    def test_forward_negation_does_not_swallow_a_real_emergency(self):
        # The forward-negation check must stay narrow: if "no" is followed by
        # more words rather than punctuation/end, it's modifying something
        # else in the sentence, not negating the symptom - this must still
        # trigger the emergency path.
        positive_cases = [
            "chest pain, no relief for two hours",
            "chest pain no matter what I do",
            "severe chest pain no one else is home",
        ]
        for text in positive_cases:
            with self.subTest(text=text):
                self.assertTrue(contains_emergency_keyword(text), text)

    def test_unrelated_text_does_not_trigger(self):
        self.assertFalse(contains_emergency_keyword("mild headache and tiredness"))

    def test_empty_text_does_not_trigger(self):
        self.assertFalse(contains_emergency_keyword(""))
        self.assertFalse(contains_emergency_keyword(None))


class EmergencyEntryPointParityTests(TestCase):
    """All three symptom-entry paths must agree on the same input text."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='emergency_user', password='password123', email='emergency@example.com'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _latest_triage_record(self):
        return TriageRecord.objects.filter(user=self.user).order_by('-created_at').first()

    def test_assess_symptoms_triggers_emergency(self):
        response = self.client.post(
            reverse('assess_symptoms'), {'current_symptoms': EMERGENCY_TEXT}, format='json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['risk_level'], 'emergency')
        record = self._latest_triage_record()
        self.assertIsNotNone(record)
        self.assertEqual(record.risk_level, 'emergency')
        self.assertEqual(record.assessment_source, 'emergency_rule')

    def test_start_consultation_triggers_emergency(self):
        response = self.client.post(
            reverse('start_consultation'), {'symptoms': EMERGENCY_TEXT}, format='json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['risk_level'], 'emergency')
        record = self._latest_triage_record()
        self.assertIsNotNone(record)
        self.assertEqual(record.risk_level, 'emergency')
        self.assertEqual(record.assessment_source, 'emergency_rule')

    def test_submit_consultation_step_symptoms_stage_triggers_emergency(self):
        # A session with no initial symptoms stays on the 'symptoms' stage,
        # exercising the check inserted at the top of that branch directly.
        session = ConsultationSession.objects.create(user=self.user, stage='symptoms', is_active=True)
        response = self.client.post(
            reverse('submit_consultation_step', args=[session.id]),
            {'symptoms': EMERGENCY_TEXT},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['risk_level'], 'emergency')
        record = self._latest_triage_record()
        self.assertIsNotNone(record)
        self.assertEqual(record.risk_level, 'emergency')
        self.assertEqual(record.assessment_source, 'emergency_rule')

    def test_chat_send_message_triggers_emergency(self):
        create_resp = self.client.post(reverse('chat_conversations_list'), {}, format='json')
        self.assertEqual(create_resp.status_code, 201)
        conversation_id = create_resp.data['conversation']['id']

        response = self.client.post(
            reverse('chat_send_message', args=[conversation_id]),
            {'content': EMERGENCY_TEXT},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['risk_level'], 'emergency')
        record = self._latest_triage_record()
        self.assertIsNotNone(record)
        self.assertEqual(record.risk_level, 'emergency')
        self.assertEqual(record.assessment_source, 'emergency_rule')

    def test_negated_phrasing_does_not_trigger_emergency(self):
        # Negated text must NOT short-circuit: the session proceeds normally
        # and no emergency TriageRecord is created.
        response = self.client.post(
            reverse('start_consultation'), {'symptoms': 'no chest pain, just tired'}, format='json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('risk_level', response.data)
        self.assertEqual(response.data['session']['stage'], 'history')
        self.assertIsNone(self._latest_triage_record())


class TriageEngineEmergencyShortCircuitTests(TestCase):
    """The engine itself must short-circuit before any provider call."""

    def test_assess_short_circuits_on_emergency_text_without_provider(self):
        engine = TriageEngineV2()
        # Force no configured Gemini client so a normal (non-short-circuited)
        # call would raise RuntimeError instead of silently succeeding.
        engine.client = None
        result = engine.assess(symptoms_text=EMERGENCY_TEXT, user_data={})
        self.assertEqual(result['risk_level'], 'emergency')
        self.assertEqual(result['assessment_source'], 'emergency_rule')

    def test_assess_does_not_short_circuit_on_negated_text(self):
        # Negated text must fall through to the normal (provider) path rather
        # than being treated as an emergency. With no provider configured,
        # assess() catches the resulting RuntimeError internally and returns
        # its degraded fallback shape instead of the emergency shape.
        engine = TriageEngineV2()
        engine.client = None
        result = engine.assess(symptoms_text="no chest pain, just tired", user_data={})
        self.assertNotEqual(result['risk_level'], 'emergency')
        self.assertNotEqual(result.get('assessment_source'), 'emergency_rule')

    def test_skip_emergency_recheck_bypasses_the_scan_entirely(self):
        # A clarifying question routinely names the symptom it's asking about
        # ("Are you experiencing chest pain?"), so text merging a question
        # with the patient's answer can contain an emergency keyword that has
        # nothing to do with what the patient actually reported. Callers that
        # already checked the patient's raw message before merging must be
        # able to opt out of the internal re-scan entirely.
        engine = TriageEngineV2()
        engine.client = None
        merged_text = (
            "Q: Are you experiencing any chest pain or pressure when you breathe?\n"
            "A: No, none of that."
        )
        # Without the flag: the merged text still contains an unnegated
        # "chest pain" (from the question, followed by "or pressure..." - not
        # a forward-negation match), so it short-circuits to emergency.
        without_skip = engine.assess(symptoms_text=merged_text, user_data={})
        self.assertEqual(without_skip['risk_level'], 'emergency')

        # With the flag: no scan happens at all, so it falls through to the
        # normal path (degraded fallback here, since no provider is configured).
        with_skip = engine.assess(symptoms_text=merged_text, user_data={}, skip_emergency_recheck=True)
        self.assertNotEqual(with_skip['risk_level'], 'emergency')
        self.assertNotEqual(with_skip.get('assessment_source'), 'emergency_rule')


class ChatClarifyingQuestionDoesNotSelfTriggerEmergencyTests(TestCase):
    """Regression: a clarifying question naming a symptom (e.g. "chest pain")
    must not turn the patient's own (possibly negated) answer into a false
    emergency on the next chat turn, once its text is folded into the
    conversation transcript that TriageEngineV2.assess() re-processes.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='chatneg@example.com', email='chatneg@example.com', password='pw'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        from .models import ChatConversation
        self.conversation = ChatConversation.objects.create(user=self.user, title='c')

    def test_negated_answer_to_a_symptom_naming_question_is_not_emergency(self):
        from unittest.mock import patch
        import json as _json

        # Turn 1: a vague report triggers the clarifying-question gate. The
        # generated question names "chest pain" - entirely plausible for a
        # cough/breathing complaint.
        with patch('api.views.get_triage_engine_v2') as mocked_engine:
            mocked_engine.return_value.generate_clarifying_questions.return_value = [
                {'question': 'Are you experiencing any chest pain or pressure when you breathe?', 'type': 'yes_no'},
            ]
            first = self.client.post(
                reverse('chat_send_message', args=[self.conversation.id]),
                {'content': 'I have had a cough for a few days'},
                format='json',
            )
        self.assertEqual(first.status_code, 201)
        self.assertTrue(first.data['needs_clarification'])

        # Turn 2: the patient answers "No" - not an emergency. This must
        # exercise the REAL TriageEngineV2.assess() logic (including the
        # skip_emergency_recheck fix), not a fully-mocked engine that would
        # bypass the very code path under test - so we patch chat_service's
        # TriageEngineV2 to build a real engine around a scripted provider
        # instead of stubbing assess() outright.
        class ScriptedProvider:
            is_available = True

            def complete(self, messages, model_id, temperature):
                return _json.dumps({
                    'risk_level': 'low',
                    'risk_probability': 0.1,
                    'confidence': 0.5,
                    'reasoning': 'Consistent with a mild viral cough, no red flags reported.',
                    'possible_conditions': [{'disease': 'Common cold', 'confidence': 0.3}],
                    'recommendations': ['Rest', 'Fluids'],
                    'when_to_seek_care': 'If symptoms worsen',
                    'disclaimer': 'test',
                })

        from .triage_engine_v2 import TriageEngineV2 as RealEngine
        provider = ScriptedProvider()
        real_engine = RealEngine(default_provider=provider, openrouter_provider=provider)

        with patch('api.chat_service.TriageEngineV2', return_value=real_engine):
            second = self.client.post(
                reverse('chat_send_message', args=[self.conversation.id]),
                {'content': '5, chest pain no, no bluish tint'},
                format='json',
            )
        self.assertEqual(second.status_code, 201)
        metadata = second.data['assistant_message']['metadata']
        # The engine's own risk-floor logic (critical_findings.py) may still
        # adjust the LLM's self-reported 'low' upward on other signals - that
        # is unrelated to this regression. What must never happen is the rule-
        # based emergency short-circuit firing on the assistant's own question
        # wording ("chest pain") re-scanned from the merged conversation text.
        self.assertNotEqual(metadata.get('risk_level'), 'emergency')
        self.assertNotEqual(metadata.get('assessment_source'), 'emergency_rule')
