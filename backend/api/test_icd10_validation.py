"""Fix B: two-pass condition validation (curated list, then ICD-10-CM).

The curated list stays as a fast first-pass filter. ICD-10-CM is consulted
only for names it misses, before anything is flagged for human review.
"""
from django.test import SimpleTestCase

from . import icd10
from .assessment_quality import classify_condition_name, validate_conditions
from .condition_reference import COMMON_CONDITIONS
from .triage_engine_v2 import TriageEngineV2

# The three fabrications carried forward from the earlier curated-only tests.
FABRICATIONS = [
    'Sparkle Fever Extreme',
    'Purple Monday Syndrome Variant',
    'Quantum Bone Disorder Type 7',
]

# Real conditions absent from condition_reference.py's curated entries.
UNCURATED_REAL = [
    'Sarcoidosis',
    'Osteomyelitis',
    'Thrombocytopenia',
    'Dermatomyositis',
    'Achalasia',
    'Myasthenia Gravis',
    'Rhabdomyolysis',
]


class DatasetTests(SimpleTestCase):
    def test_dataset_is_present_and_loads(self):
        self.assertTrue(icd10.is_available(), 'vendored ICD-10-CM dataset failed to load')

    def test_dataset_has_expected_scale(self):
        index = icd10.get_index()
        self.assertGreater(len(index['terms']), 50000)
        self.assertGreater(len(index['codes']), 40000)

    def test_index_is_built_once_per_process(self):
        self.assertIs(icd10.get_index(), icd10.get_index())


class IcdLookupTests(SimpleTestCase):
    def test_uncurated_real_conditions_resolve(self):
        for name in UNCURATED_REAL:
            with self.subTest(name=name):
                match = icd10.lookup(name)
                self.assertIsNotNone(match, f'{name} did not resolve against ICD-10-CM')
                code, description, _how = match
                self.assertTrue(code)
                self.assertTrue(description)

    def test_fabrications_do_not_resolve(self):
        for name in FABRICATIONS + ['wibble wobble flurb', 'Glorptastic Bone Fizz']:
            with self.subTest(name=name):
                self.assertIsNone(icd10.lookup(name), f'{name} wrongly matched ICD-10-CM')

    def test_single_generic_token_cannot_carry_a_match(self):
        # "Q fever" reduces to {fever}; a fabricated name sharing only that
        # must not inherit its code.
        self.assertIsNone(icd10.lookup('Sparkle Fever Extreme'))

    def test_short_and_empty_names_are_rejected(self):
        for name in ['', '   ', 'ab', None]:
            with self.subTest(name=name):
                self.assertIsNone(icd10.lookup(name))


class TwoPassClassificationTests(SimpleTestCase):
    """The headline requirement: uncurated-but-real now resolves via ICD-10
    instead of being flagged for review."""

    def test_uncurated_real_conditions_are_known_via_icd10(self):
        for name in UNCURATED_REAL:
            with self.subTest(name=name):
                self.assertNotIn(name.lower(), COMMON_CONDITIONS,
                                 f'{name} is curated; pick a genuinely uncurated term')
                status, reason, source, code = classify_condition_name(name)
                self.assertEqual(status, 'known', f'{name}: {reason}')
                self.assertEqual(source, 'icd10', f'{name} did not come from the ICD-10 pass')
                self.assertTrue(code)
                self.assertIn('ICD-10-CM', reason)

    def test_curated_names_still_take_the_fast_path(self):
        for name in ['Migraine', 'Appendicitis', 'Asthma', 'Acute Viral Gastroenteritis']:
            with self.subTest(name=name):
                status, _reason, source, _code = classify_condition_name(name)
                self.assertEqual(status, 'known')
                self.assertEqual(source, 'curated', 'curated list should have matched first')

    def test_all_three_fabrications_still_reject(self):
        for name in FABRICATIONS:
            with self.subTest(name=name):
                status, _reason, source, _code = classify_condition_name(name)
                self.assertNotEqual(status, 'known', f'{name} wrongly accepted as known')
                self.assertNotEqual(source, 'icd10', f'{name} wrongly matched ICD-10-CM')

    def test_curated_flag_stays_narrow(self):
        # 'curated' must mean our vetted list specifically - an ICD-10 match
        # is recognised but is not the same assurance level.
        _s, _r, curated_source, _c = classify_condition_name('Migraine')
        _s2, _r2, icd_source, _c2 = classify_condition_name('Sarcoidosis')
        self.assertEqual(curated_source, 'curated')
        self.assertEqual(icd_source, 'icd10')


class ValidateConditionsTwoPassTests(SimpleTestCase):
    def test_icd10_match_is_recognised_but_not_marked_curated(self):
        result = validate_conditions([
            {'disease': 'Migraine', 'confidence': 0.4},
            {'disease': 'Sarcoidosis', 'confidence': 0.3},
        ])
        curated, icd = result['conditions']

        self.assertTrue(curated['recognized'])
        self.assertTrue(curated['curated'])
        self.assertIsNone(curated['icd10_code'])

        self.assertTrue(icd['recognized'])
        self.assertFalse(icd['curated'])
        self.assertEqual(icd['match_source'], 'icd10')
        self.assertTrue(icd['icd10_code'])

        self.assertEqual(result['icd10_matched_count'], 1)
        self.assertEqual(result['unrecognized_count'], 0)

    def test_fabrication_alongside_icd10_match_is_still_flagged(self):
        result = validate_conditions([
            {'disease': 'Sarcoidosis', 'confidence': 0.4},
            {'disease': 'Quantum Bone Disorder Type 7', 'confidence': 0.3},
        ])
        good, bad = result['conditions']

        self.assertEqual(good['match_source'], 'icd10')
        self.assertNotEqual(bad['match_source'], 'icd10')
        self.assertFalse(bad['curated'])


class UncuratedRealConditionNoLongerForcesReviewTests(SimpleTestCase):
    """End-to-end: a differential of real-but-uncurated conditions must not
    be routed to a human as if it were hallucinated."""

    def setUp(self):
        self.engine = TriageEngineV2()
        self.detailed = (
            'Persistent dry cough and shortness of breath for three weeks, '
            'moderate severity, worse on exertion and with swollen lymph nodes.'
        )

    def _structure(self, diseases):
        return self.engine._structure_assessment(
            {
                'risk_level': 'medium',
                'confidence': 0.7,
                'reasoning': 'r',
                'possible_conditions': [{'disease': d, 'confidence': 0.3} for d in diseases],
                'recommendations': ['See a clinician'],
            },
            self.detailed,
        )

    def test_uncurated_real_differential_is_not_flagged_for_review(self):
        structured = self._structure(['Sarcoidosis', 'Osteomyelitis'])

        self.assertFalse(structured['has_unrecognized_conditions'])
        self.assertEqual(structured['unrecognized_condition_count'], 0)
        self.assertEqual(structured['icd10_matched_condition_count'], 2)
        self.assertNotIn('unrecognized_conditions', structured['review_reasons'])

    def test_fabricated_differential_still_forces_review(self):
        structured = self._structure(FABRICATIONS)

        self.assertTrue(structured['requires_human_review'])
        self.assertEqual(structured['icd10_matched_condition_count'], 0)
        self.assertEqual(structured['authoritative_condition_count'], 0)
        # Two of these three look medical enough to pass morphology, so the
        # trigger is "nothing resolved against a real terminology" rather
        # than "everything was gibberish".
        self.assertTrue(
            {'unrecognized_conditions', 'no_authoritative_condition_match'}
            & set(structured['review_reasons']),
            f"expected a review reason, got {structured['review_reasons']}",
        )

    def test_morphology_only_differential_forces_review(self):
        # Names that merely look medical - none resolve against the curated
        # list or ICD-10-CM - must not pass through unreviewed.
        structured = self._structure(['Zorbulitis Prime', 'Quantum Bone Disorder Type 7'])

        self.assertEqual(structured['authoritative_condition_count'], 0)
        self.assertTrue(structured['requires_human_review'])
        self.assertIn('no_authoritative_condition_match', structured['review_reasons'])

    def test_one_authoritative_match_is_enough_to_avoid_the_blanket_flag(self):
        structured = self._structure(['Sarcoidosis', 'Zorbulitis Prime'])

        self.assertEqual(structured['authoritative_condition_count'], 1)
        self.assertNotIn('no_authoritative_condition_match', structured['review_reasons'])

    def test_mixed_differential_flags_only_the_fabrication(self):
        structured = self._structure(['Sarcoidosis', 'Glorptastic Bone Fizz'])

        self.assertTrue(structured['has_unrecognized_conditions'])
        self.assertEqual(structured['unrecognized_condition_count'], 1)
        by_name = {c['disease']: c for c in structured['possible_conditions']}
        self.assertTrue(by_name['Sarcoidosis']['recognized'])
        self.assertFalse(by_name['Glorptastic Bone Fizz']['recognized'])
