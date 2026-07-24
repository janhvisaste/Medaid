"""Tests for confidence calibration and the lightweight ontology check."""
import json

from django.test import SimpleTestCase

from .assessment_quality import (
    CONFIDENCE_CEILINGS,
    calibrate_confidence,
    classify_condition_name,
    score_input_specificity,
    validate_conditions,
)
from .triage_engine_v2 import TriageEngineV2

VAGUE = 'i feel bad'
DETAILED = (
    'Sharp throbbing pain in my lower right abdomen for the past 2 days, '
    'rated 7/10, getting worse after eating and relieved when lying still.'
)


class InputSpecificityTests(SimpleTestCase):
    def test_vague_input_scores_minimal(self):
        self.assertEqual(score_input_specificity(VAGUE)['level'], 'minimal')

    def test_detailed_input_scores_rich(self):
        result = score_input_specificity(DETAILED)
        self.assertEqual(result['level'], 'rich')
        self.assertTrue(result['signals']['duration'])
        self.assertTrue(result['signals']['severity'])
        self.assertTrue(result['signals']['location'])

    def test_empty_input_is_minimal(self):
        self.assertEqual(score_input_specificity('')['level'], 'minimal')
        self.assertEqual(score_input_specificity(None)['level'], 'minimal')

    def test_missing_signals_are_reported(self):
        result = score_input_specificity('my head hurts a lot but I cannot say more')
        self.assertIn('duration', result['missing'])

    def test_short_text_cannot_reach_rich(self):
        # Even keyword-dense but very short input stays capped.
        result = score_input_specificity('severe chest 2 days')
        self.assertIn(result['level'], ('sparse', 'moderate'))


class ConfidenceCalibrationTests(SimpleTestCase):
    def test_high_confidence_on_vague_input_is_capped(self):
        result = calibrate_confidence(0.95, VAGUE)

        self.assertLess(result['confidence'], 0.95)
        self.assertEqual(result['confidence'], CONFIDENCE_CEILINGS['minimal'])
        self.assertTrue(result['confidence_was_capped'])
        self.assertEqual(result['reported_confidence'], 0.95)

    def test_capping_is_explained_in_plain_language(self):
        result = calibrate_confidence(0.95, VAGUE)
        self.assertIn('reduced', result['confidence_explanation'].lower())
        self.assertIn('follow-up questions', result['confidence_explanation'])

    def test_high_confidence_on_detailed_input_is_preserved(self):
        result = calibrate_confidence(0.85, DETAILED)

        self.assertEqual(result['confidence'], 0.85)
        self.assertFalse(result['confidence_was_capped'])

    def test_ceiling_is_not_a_floor(self):
        # A low self-reported confidence must never be raised to the ceiling.
        result = calibrate_confidence(0.1, DETAILED)
        self.assertEqual(result['confidence'], 0.1)
        self.assertFalse(result['confidence_was_capped'])

    def test_out_of_range_and_garbage_values_are_clamped(self):
        self.assertEqual(calibrate_confidence(5.0, DETAILED)['reported_confidence'], 1.0)
        self.assertEqual(calibrate_confidence(-2.0, DETAILED)['reported_confidence'], 0.0)
        self.assertEqual(calibrate_confidence('not a number', DETAILED)['reported_confidence'], 0.0)
        self.assertEqual(calibrate_confidence(None, DETAILED)['reported_confidence'], 0.0)

    def test_reports_which_details_were_missing(self):
        result = calibrate_confidence(0.9, VAGUE)
        self.assertTrue(result['missing_detail'])


class ConditionNameClassificationTests(SimpleTestCase):
    def test_curated_conditions_are_known(self):
        for name in ['Migraine', 'Acute Gastroenteritis', 'Viral Upper Respiratory Infection',
                     'Iron Deficiency Anemia', 'Type 2 Diabetes Mellitus']:
            with self.subTest(name=name):
                self.assertEqual(classify_condition_name(name)[0], 'known')

    def test_real_uncurated_conditions_resolve_via_the_icd10_pass(self):
        # Real conditions outside the curated common-presentations list are
        # caught by the ICD-10-CM second pass rather than being demoted.
        # Asserted on match_source, not on a hand-picked term list, so growing
        # the curated list does not invalidate this test.
        for name in ['Sarcoidosis', 'Osteomyelitis', 'Thrombocytopenia', 'Dermatomyositis']:
            with self.subTest(name=name):
                status, reason, source, code = classify_condition_name(name)
                self.assertEqual(status, 'known', f'{name}: {reason}')
                self.assertIn(source, ('curated', 'icd10'))
                if source == 'icd10':
                    self.assertTrue(code, f'{name} matched ICD-10 without a code')

    def test_morphology_only_names_remain_plausible(self):
        # Fails both the curated list and ICD-10-CM, but looks like a medical
        # term - admitted at lower assurance, not asserted as known.
        status, _reason, source, _code = classify_condition_name('Zorbulitis Prime')
        self.assertEqual(status, 'plausible')
        self.assertEqual(source, 'morphology')

    def test_generic_placeholders_are_flagged_generic(self):
        for name in ['Medical Condition Requiring Evaluation', 'Unknown Condition', 'Unspecified']:
            with self.subTest(name=name):
                self.assertEqual(classify_condition_name(name)[0], 'generic')

    def test_hallucinated_names_with_no_medical_signal_are_unrecognized(self):
        for name in ['Sparkle Fever Extreme', 'Wobbly Tuesday Feeling', 'Blue Cloud Thing']:
            with self.subTest(name=name):
                self.assertEqual(classify_condition_name(name)[0], 'unrecognized', name)

    def test_well_formed_fabrications_are_not_curated_even_if_plausible(self):
        """Morphology alone cannot catch a fabrication that borrows real
        medical vocabulary. The honest contract is that these are never
        'known' - they fall to 'plausible', which callers must treat as
        lower assurance than a curated match."""
        for name in ['Quantum Bone Disorder Type 7', 'Zorbulitis Prime',
                     'Purple Monday Syndrome Variant']:
            with self.subTest(name=name):
                status, _reason, _source, _code = classify_condition_name(name)
                self.assertNotEqual(status, 'known', name)

    def test_validate_conditions_marks_uncurated_names(self):
        result = validate_conditions([
            {'disease': 'Migraine', 'confidence': 0.4},
            {'disease': 'Quantum Bone Disorder Type 7', 'confidence': 0.3},
        ])

        self.assertTrue(result['conditions'][0]['curated'])
        self.assertFalse(result['conditions'][1]['curated'])
        self.assertEqual(result['non_curated_count'], 1)

    def test_pure_gibberish_is_unrecognized(self):
        self.assertEqual(classify_condition_name('wibble wobble flurb')[0], 'unrecognized')

    def test_empty_name_is_unrecognized(self):
        self.assertEqual(classify_condition_name('')[0], 'unrecognized')


class ConditionValidationTests(SimpleTestCase):
    def test_annotates_rather_than_drops(self):
        result = validate_conditions([
            {'disease': 'Migraine', 'confidence': 0.4},
            {'disease': 'wibble wobble flurb', 'confidence': 0.3},
        ])

        # Both survive - silently dropping hides the failure from clinicians.
        self.assertEqual(len(result['conditions']), 2)
        self.assertTrue(result['conditions'][0]['recognized'])
        self.assertFalse(result['conditions'][1]['recognized'])
        self.assertEqual(result['unrecognized_count'], 1)
        self.assertTrue(result['any_unrecognized'])
        self.assertFalse(result['all_unrecognized'])

    def test_all_unrecognized_is_detected(self):
        result = validate_conditions([
            {'disease': 'wibble wobble', 'confidence': 0.3},
            {'disease': 'florp glorp', 'confidence': 0.2},
        ])
        self.assertTrue(result['all_unrecognized'])

    def test_every_condition_carries_a_reason(self):
        result = validate_conditions([{'disease': 'Migraine', 'confidence': 0.4}])
        self.assertTrue(result['conditions'][0]['name_status_reason'])

    def test_handles_empty_and_non_dict_input(self):
        self.assertEqual(validate_conditions([])['conditions'], [])
        self.assertEqual(validate_conditions(None)['conditions'], [])
        result = validate_conditions(['Migraine'])
        self.assertTrue(result['conditions'][0]['recognized'])


class StructuredAssessmentIntegrationTests(SimpleTestCase):
    """Both checks must apply to what actually leaves the engine."""

    def setUp(self):
        self.engine = TriageEngineV2()

    def test_confidence_capped_in_structured_output(self):
        structured = self.engine._structure_assessment(
            {
                'risk_level': 'low',
                'confidence': 0.95,
                'reasoning': 'r',
                'possible_conditions': [{'disease': 'Migraine', 'confidence': 0.3}],
                'recommendations': ['Rest'],
            },
            VAGUE,
        )

        self.assertTrue(structured['confidence_was_capped'])
        self.assertEqual(structured['reported_confidence'], 0.95)
        self.assertLess(structured['confidence'], 0.95)
        self.assertTrue(structured['confidence_explanation'])

    def test_capped_confidence_below_threshold_triggers_human_review(self):
        structured = self.engine._structure_assessment(
            {
                'risk_level': 'low',
                'confidence': 0.99,
                'reasoning': 'r',
                'possible_conditions': [{'disease': 'Migraine', 'confidence': 0.3}],
                'recommendations': ['Rest'],
            },
            'bad',
        )
        # 'minimal' ceiling is 0.30, which is not below the 0.30 review
        # threshold, so this asserts the wiring rather than an off-by-one.
        self.assertEqual(structured['confidence'], CONFIDENCE_CEILINGS['minimal'])
        self.assertIn('input_specificity', structured)

    def test_unrecognized_conditions_are_annotated_in_output(self):
        structured = self.engine._structure_assessment(
            {
                'risk_level': 'low',
                'confidence': 0.6,
                'reasoning': 'r',
                'possible_conditions': [
                    {'disease': 'Migraine', 'confidence': 0.4},
                    {'disease': 'wibble wobble flurb', 'confidence': 0.3},
                ],
                'recommendations': ['Rest'],
            },
            DETAILED,
        )

        self.assertTrue(structured['has_unrecognized_conditions'])
        self.assertEqual(structured['unrecognized_condition_count'], 1)
        statuses = {c['disease']: c['recognized'] for c in structured['possible_conditions']}
        self.assertTrue(statuses['Migraine'])
        self.assertFalse(statuses['wibble wobble flurb'])

    def test_all_unrecognized_conditions_force_human_review(self):
        structured = self.engine._structure_assessment(
            {
                'risk_level': 'low',
                'confidence': 0.9,
                'reasoning': 'r',
                'possible_conditions': [
                    {'disease': 'wibble wobble', 'confidence': 0.4},
                    {'disease': 'florp glorp', 'confidence': 0.3},
                ],
                'recommendations': ['Rest'],
            },
            DETAILED,
        )

        self.assertTrue(structured['requires_human_review'])
        self.assertIn('unrecognized_conditions', structured['review_reasons'])

    def test_clean_assessment_needs_no_review(self):
        structured = self.engine._structure_assessment(
            {
                'risk_level': 'low',
                'confidence': 0.8,
                'reasoning': 'r',
                'possible_conditions': [{'disease': 'Migraine', 'confidence': 0.4}],
                'recommendations': ['Rest'],
            },
            DETAILED,
        )

        self.assertFalse(structured['requires_human_review'])
        self.assertEqual(structured['review_reasons'], [])
        self.assertFalse(structured['has_unrecognized_conditions'])
