"""Fix 4: LLM condition names are validated against a curated reference list.

Nonsense names must be flagged - never silently passed through at face value,
and never silently dropped either.
"""
from django.test import SimpleTestCase

from .assessment_quality import classify_condition_name, validate_conditions
from .condition_reference import COMMON_CONDITIONS
from .triage_engine_v2 import TriageEngineV2


class ReferenceListTests(SimpleTestCase):
    def test_list_covers_a_few_hundred_presentations(self):
        self.assertGreaterEqual(len(COMMON_CONDITIONS), 250)

    def test_list_entries_are_lowercase_and_stripped(self):
        for name in COMMON_CONDITIONS:
            self.assertEqual(name, name.lower().strip(), name)


class FuzzyMatchingTests(SimpleTestCase):
    def test_exact_curated_names_match(self):
        for name in ['Migraine', 'Appendicitis', 'Hypertension', 'Asthma']:
            with self.subTest(name=name):
                self.assertEqual(classify_condition_name(name)[0], 'known')

    def test_qualifiers_and_inflections_still_match(self):
        for name in ['Acute Viral Gastroenteritis', 'Severe Tension Headache',
                     'Chronic Lower Back Pain', 'Type 2 Diabetes Mellitus']:
            with self.subTest(name=name):
                self.assertEqual(classify_condition_name(name)[0], 'known')

    def test_minor_misspellings_still_match(self):
        for name, expected in [('migrane', 'migraine'), ('asthama', 'asthma')]:
            with self.subTest(name=name):
                status, reason, _source, _code = classify_condition_name(name)
                self.assertEqual(status, 'known', f'{name}: {reason}')
                self.assertIn(expected, reason)

    def test_match_reason_names_the_reference_entry(self):
        _status, reason, _source, _code = classify_condition_name('Acute Viral Gastroenteritis')
        self.assertIn('gastroenteritis', reason)

    def test_generic_shared_word_does_not_launder_a_fabrication(self):
        # "hay fever" and "dry eye syndrome" reduce to one generic token;
        # sharing only that must not count as a curated match.
        for name in ['Sparkle Fever Extreme', 'Purple Monday Syndrome Variant']:
            with self.subTest(name=name):
                self.assertNotEqual(classify_condition_name(name)[0], 'known', name)

    def test_pure_nonsense_is_unrecognized(self):
        for name in ['wibble wobble flurb', 'Blue Cloud Thing', 'Sparkle Fever Extreme']:
            with self.subTest(name=name):
                self.assertEqual(classify_condition_name(name)[0], 'unrecognized', name)


class NonsenseConditionIsFlaggedTests(SimpleTestCase):
    """The headline requirement: a nonsense name must be flagged, not passed
    through with the same authority as a validated term."""

    def test_nonsense_condition_is_flagged_not_dropped(self):
        result = validate_conditions([
            {'disease': 'Migraine', 'confidence': 0.4},
            {'disease': 'Flibbertigibbet Cranial Wobble', 'confidence': 0.35},
        ])

        # Still present - dropping would hide the failure from a reviewer.
        self.assertEqual(len(result['conditions']), 2)

        good, bad = result['conditions']
        self.assertTrue(good['recognized'])
        self.assertTrue(good['curated'])

        self.assertFalse(bad['recognized'])
        self.assertFalse(bad['curated'])
        self.assertEqual(bad['name_status'], 'unrecognized')
        self.assertTrue(bad['name_status_reason'])
        self.assertEqual(result['unrecognized_count'], 1)
        self.assertTrue(result['any_unrecognized'])

    def test_nonsense_does_not_carry_the_same_authority_as_validated_terms(self):
        result = validate_conditions([
            {'disease': 'Influenza', 'confidence': 0.4},
            {'disease': 'Glorptastic Bone Fizz', 'confidence': 0.4},
        ])
        good, bad = result['conditions']
        # Same model-reported confidence, different assurance markers.
        self.assertEqual(good['confidence'], bad['confidence'])
        self.assertNotEqual(good['recognized'], bad['recognized'])
        self.assertNotEqual(good['curated'], bad['curated'])


class NonsenseFlaggedThroughTheEngineTests(SimpleTestCase):
    """A mocked LLM differential containing nonsense is flagged end-to-end."""

    def setUp(self):
        self.engine = TriageEngineV2()
        self.detailed = (
            'Sharp pain in my lower right abdomen for two days, rated 7/10, '
            'worse after eating and better when lying still.'
        )

    def test_mocked_nonsense_condition_is_flagged_in_structured_output(self):
        structured = self.engine._structure_assessment(
            {
                'risk_level': 'low',
                'confidence': 0.8,
                'reasoning': 'r',
                'possible_conditions': [
                    {'disease': 'Appendicitis', 'confidence': 0.4},
                    {'disease': 'Flibbertigibbet Cranial Wobble', 'confidence': 0.3},
                ],
                'recommendations': ['Rest'],
            },
            self.detailed,
        )

        self.assertTrue(structured['has_unrecognized_conditions'])
        self.assertEqual(structured['unrecognized_condition_count'], 1)

        by_name = {c['disease']: c for c in structured['possible_conditions']}
        self.assertTrue(by_name['Appendicitis']['recognized'])
        self.assertFalse(by_name['Flibbertigibbet Cranial Wobble']['recognized'])

    def test_all_nonsense_differential_forces_human_review(self):
        structured = self.engine._structure_assessment(
            {
                'risk_level': 'low',
                'confidence': 0.9,
                'reasoning': 'r',
                'possible_conditions': [
                    {'disease': 'Flibbertigibbet Cranial Wobble', 'confidence': 0.4},
                    {'disease': 'Glorptastic Bone Fizz', 'confidence': 0.3},
                ],
                'recommendations': ['Rest'],
            },
            self.detailed,
        )

        self.assertTrue(structured['requires_human_review'])
        self.assertIn('unrecognized_conditions', structured['review_reasons'])

    def test_valid_differential_is_not_flagged(self):
        structured = self.engine._structure_assessment(
            {
                'risk_level': 'low',
                'confidence': 0.8,
                'reasoning': 'r',
                'possible_conditions': [
                    {'disease': 'Appendicitis', 'confidence': 0.4},
                    {'disease': 'Acute Gastroenteritis', 'confidence': 0.3},
                ],
                'recommendations': ['Rest'],
            },
            self.detailed,
        )

        self.assertFalse(structured['has_unrecognized_conditions'])
        self.assertEqual(structured['unrecognized_condition_count'], 0)
        self.assertEqual(structured['non_curated_condition_count'], 0)
