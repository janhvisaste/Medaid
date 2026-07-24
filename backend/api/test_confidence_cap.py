"""Fix 3: short, unclarified symptom reports cannot yield confident assessments.

Covers both halves of the fix: the explicit prompt instruction, and the
post-parse hard cap that holds regardless of what the model returns.
"""
import json

from django.test import SimpleTestCase

from .assessment_quality import (
    SHORT_INPUT_CONFIDENCE_CAP,
    SHORT_INPUT_WORD_THRESHOLD,
    calibrate_confidence,
)
from .triage_engine_v2 import TriageEngineV2

VAGUE = 'I feel bad'
LONG_DETAILED = (
    'Sharp throbbing pain in my lower right abdomen for the past two days, '
    'rated about seven out of ten, noticeably worse after eating and somewhat '
    'relieved when I lie completely still on my side.'
)


class OverconfidentProvider:
    """Returns a maximally confident assessment no matter what it is asked."""

    is_available = True

    def __init__(self):
        self.calls = []

    def complete(self, messages, model_id, temperature):
        self.calls.append(messages)
        return json.dumps({
            'risk_level': 'low',
            'risk_probability': 0.1,
            'confidence': 0.99,
            'reasoning': 'Totally sure about this.',
            'possible_conditions': [{'disease': 'Migraine', 'confidence': 0.35}],
            'recommendations': ['Rest'],
            'when_to_seek_care': 'If worse',
        })


class PromptInstructsOnConfidenceTests(SimpleTestCase):
    def test_prompt_tells_model_to_lower_confidence_for_vague_input(self):
        engine = TriageEngineV2()
        prompt = engine._build_assessment_prompt(VAGUE, {'age': 30, 'gender': 'F'}, '', '')

        lowered = prompt.lower()
        self.assertIn('confidence', lowered)
        self.assertIn('vague', lowered)
        self.assertIn('duration', lowered)
        # Must also ask the model to say so in its reasoning.
        self.assertIn('reasoning', lowered)
        self.assertIn('missing', lowered)


class ShortInputConfidenceCapTests(SimpleTestCase):
    def test_vague_one_liner_cannot_exceed_cap(self):
        result = calibrate_confidence(0.99, VAGUE)

        self.assertLessEqual(result['confidence'], SHORT_INPUT_CONFIDENCE_CAP)
        self.assertTrue(result['confidence_was_capped'])
        self.assertEqual(result['reported_confidence'], 0.99)

    def test_cap_applies_just_below_word_threshold(self):
        text = ' '.join(['word'] * (SHORT_INPUT_WORD_THRESHOLD - 1))
        result = calibrate_confidence(0.99, text)

        self.assertLessEqual(result['confidence'], SHORT_INPUT_CONFIDENCE_CAP)
        self.assertTrue(result['short_input_cap_applied'])

    def test_cap_does_not_apply_at_or_above_word_threshold(self):
        result = calibrate_confidence(0.99, LONG_DETAILED)

        self.assertGreaterEqual(len(LONG_DETAILED.split()), SHORT_INPUT_WORD_THRESHOLD)
        self.assertFalse(result['short_input_cap_applied'])
        self.assertGreater(result['confidence'], SHORT_INPUT_CONFIDENCE_CAP)

    def test_clarifying_round_lifts_the_short_input_cap(self):
        without = calibrate_confidence(0.99, 'headache for 2 days, severe', had_clarifying_round=False)
        with_round = calibrate_confidence(0.99, 'headache for 2 days, severe', had_clarifying_round=True)

        self.assertTrue(without['short_input_cap_applied'])
        self.assertFalse(with_round['short_input_cap_applied'])
        self.assertGreater(with_round['confidence'], without['confidence'])

    def test_cap_reason_is_explained_to_the_patient(self):
        result = calibrate_confidence(0.99, VAGUE)
        explanation = result['confidence_explanation'].lower()
        self.assertIn('follow-up questions', explanation)
        self.assertIn('words', explanation)

    def test_cap_never_raises_a_low_confidence(self):
        result = calibrate_confidence(0.1, VAGUE)
        self.assertEqual(result['confidence'], 0.1)
        self.assertFalse(result['confidence_was_capped'])


class CapSurvivesOverconfidentModelTests(SimpleTestCase):
    """The cap must hold end-to-end, not just in the helper."""

    def test_structured_output_caps_an_overconfident_model(self):
        engine = TriageEngineV2()
        structured = engine._structure_assessment(
            {
                'risk_level': 'low',
                'confidence': 0.99,
                'reasoning': 'Totally sure.',
                'possible_conditions': [{'disease': 'Migraine', 'confidence': 0.35}],
                'recommendations': ['Rest'],
            },
            VAGUE,
        )

        self.assertLessEqual(structured['confidence'], SHORT_INPUT_CONFIDENCE_CAP)
        self.assertEqual(structured['reported_confidence'], 0.99)
        self.assertTrue(structured['confidence_was_capped'])

    def test_assess_caps_an_overconfident_model_for_vague_input(self):
        provider = OverconfidentProvider()
        engine = TriageEngineV2(default_provider=provider, openrouter_provider=provider)

        result = engine.assess(VAGUE, {'age': 30, 'gender': 'F', 'past_history': []})

        self.assertEqual(result['reported_confidence'], 0.99)
        self.assertLessEqual(
            result['confidence'], SHORT_INPUT_CONFIDENCE_CAP,
            'a vague one-liner produced a confidence above the cap',
        )

    def test_assess_does_not_cap_detailed_input(self):
        provider = OverconfidentProvider()
        engine = TriageEngineV2(default_provider=provider, openrouter_provider=provider)

        result = engine.assess(LONG_DETAILED, {'age': 30, 'gender': 'F', 'past_history': []})

        self.assertGreater(result['confidence'], SHORT_INPUT_CONFIDENCE_CAP)

    def test_assess_respects_clarifying_round_flag(self):
        provider = OverconfidentProvider()
        engine = TriageEngineV2(default_provider=provider, openrouter_provider=provider)
        short_text = 'headache for 2 days, severe'

        without = engine.assess(short_text, {}, had_clarifying_round=False)
        with_round = engine.assess(short_text, {}, had_clarifying_round=True)

        self.assertLessEqual(without['confidence'], SHORT_INPUT_CONFIDENCE_CAP)
        self.assertGreater(with_round['confidence'], without['confidence'])
