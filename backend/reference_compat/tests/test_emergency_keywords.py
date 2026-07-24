import unittest

from reference_compat.keywords import EMERGENCY_KEYWORDS, contains_emergency_keyword


class EmergencyKeywordTests(unittest.TestCase):
    def test_each_reference_keyword_triggers(self):
        for keyword in EMERGENCY_KEYWORDS:
            with self.subTest(keyword=keyword):
                self.assertTrue(contains_emergency_keyword(keyword))

    def test_local_v2_only_keywords_do_not_trigger(self):
        self.assertFalse(contains_emergency_keyword("chest pain"))
        self.assertFalse(contains_emergency_keyword("difficulty breathing"))
        self.assertFalse(contains_emergency_keyword("passed out"))
        self.assertFalse(contains_emergency_keyword("behosh"))
