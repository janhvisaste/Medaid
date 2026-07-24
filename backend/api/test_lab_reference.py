"""
Tests for the deterministic lab-value grounding engine.

This layer decides whether a value is normal / low / high / critical, which is
the most safety-critical output of the report pipeline. It must be arithmetic
and reproducible — never dependent on what a language model guessed.
"""

import json
from unittest.mock import patch

from django.test import TestCase

from api.lab_reference import (
    build_grounded_facts_block,
    classify_value,
    get_explanation,
    get_reference_range,
    ground_tests,
    load_knowledge_base,
    normalize_test_name,
    overall_status,
    parse_numeric,
    score_lab_relevance,
    select_lab_relevant_text,
)
from api.report_insight_engine import generate_combined_report_insights


class KnowledgeBaseLoadTest(TestCase):
    def test_kb_loads_with_expected_sections(self):
        kb = load_knowledge_base()
        self.assertGreater(len(kb["reference_ranges"]), 30)
        self.assertGreater(len(kb["explanations"]), 50)
        self.assertGreater(len(kb["test_name_aliases"]), 50)


class TestNameNormalizationTest(TestCase):
    def test_common_aliases_resolve(self):
        self.assertEqual(normalize_test_name("Hemoglobin"), "hemoglobin")
        self.assertEqual(normalize_test_name("HB"), "hemoglobin")
        self.assertEqual(normalize_test_name("Haemoglobin"), "hemoglobin")

    def test_punctuation_and_parentheses_are_handled(self):
        """Real OCR output is messy — 'R.B.C. Count' and 'SGOT (AST)' must resolve."""
        self.assertEqual(normalize_test_name("R.B.C. Count"), "rbc")
        self.assertEqual(normalize_test_name("SGOT (AST)"), "sgot")
        self.assertEqual(normalize_test_name("Platelet Count"), "platelet_count")

    def test_unknown_test_returns_none_rather_than_guessing(self):
        self.assertIsNone(normalize_test_name("Vitamin D"))
        self.assertIsNone(normalize_test_name(""))


class NumericParsingTest(TestCase):
    def test_parses_common_formats(self):
        self.assertEqual(parse_numeric("14.2"), 14.2)
        self.assertEqual(parse_numeric("11,500"), 11500.0)
        self.assertEqual(parse_numeric("2.8 mg/dL"), 2.8)
        self.assertEqual(parse_numeric(15000), 15000.0)

    def test_censored_values_use_their_boundary(self):
        self.assertEqual(parse_numeric("<0.1"), 0.1)
        self.assertEqual(parse_numeric("> 100"), 100.0)

    def test_comma_decimal_locale(self):
        self.assertEqual(parse_numeric("12,5"), 12.5)

    def test_unparseable_returns_none(self):
        """No number means no guess — callers must not fabricate a value."""
        self.assertIsNone(parse_numeric("abc"))
        self.assertIsNone(parse_numeric(""))
        self.assertIsNone(parse_numeric(None))


class GenderSpecificRangeTest(TestCase):
    def test_hemoglobin_range_differs_by_gender(self):
        male = get_reference_range("hemoglobin", "M")
        female = get_reference_range("hemoglobin", "F")
        self.assertEqual(male["_key"], "hemoglobin_male")
        self.assertEqual(female["_key"], "hemoglobin_female")
        self.assertNotEqual(male["low"], female["low"])

    def test_same_value_classifies_differently_by_gender(self):
        """Hb 12.5 is low for a male but normal for a female — the exact nuance
        an ungrounded model gets wrong."""
        self.assertEqual(classify_value(12.5, get_reference_range("hemoglobin", "M")), "low")
        self.assertEqual(classify_value(12.5, get_reference_range("hemoglobin", "F")), "normal")


class ClassificationTest(TestCase):
    def test_all_bands(self):
        ref = {"low": 10.0, "high": 20.0, "critical_low": 5.0, "critical_high": 30.0}
        self.assertEqual(classify_value(15.0, ref), "normal")
        self.assertEqual(classify_value(8.0, ref), "low")
        self.assertEqual(classify_value(25.0, ref), "high")
        self.assertEqual(classify_value(4.0, ref), "critical_low")
        self.assertEqual(classify_value(35.0, ref), "critical_high")

    def test_boundaries_are_inclusive_of_normal(self):
        ref = {"low": 10.0, "high": 20.0, "critical_low": 5.0, "critical_high": 30.0}
        self.assertEqual(classify_value(10.0, ref), "normal")
        self.assertEqual(classify_value(20.0, ref), "normal")


class ExplanationLookupTest(TestCase):
    def test_returns_curated_explanation(self):
        exp = get_explanation("hemoglobin", "low")
        self.assertIn("simple", exp)
        self.assertIn("possible_causes", exp)
        self.assertIn("action", exp)

    def test_critical_prefers_critical_specific_copy(self):
        exp = get_explanation("hemoglobin", "critical_low")
        self.assertEqual(exp["_source_key"], "hemoglobin_critical_low")

    def test_falls_back_to_default_for_unknown_test(self):
        exp = get_explanation("some_unmapped_test", "high")
        self.assertEqual(exp["_source_key"], "default_high")


class GroundingOverridesModelTest(TestCase):
    """The whole point: arithmetic wins over whatever the LLM claimed."""

    def test_model_status_is_overridden_when_wrong(self):
        tests = [
            # Model wrongly calls an elevated WBC "normal"
            {"test_name": "WBC Count", "value": "13500", "unit": "/uL", "status": "normal"},
            # Model understates a critically low platelet count as merely "low"
            {"test_name": "Platelet Count", "value": "45000", "unit": "/uL", "status": "low"},
        ]
        result = ground_tests(tests, gender="M")
        by_name = {g["test_name"]: g for g in result["grounded"]}

        self.assertEqual(by_name["WBC Count"]["status"], "high")
        self.assertEqual(by_name["Platelet Count"]["status"], "critical_low")
        # The original claim is retained for auditability
        self.assertEqual(by_name["WBC Count"]["model_suggested_status"], "normal")

    def test_critical_value_is_surfaced(self):
        result = ground_tests(
            [{"test_name": "Platelet Count", "value": "45000", "status": "normal"}], gender="M"
        )
        self.assertEqual(result["counts"]["critical"], 1)
        self.assertEqual(overall_status(result["counts"]), "urgent")

    def test_unknown_test_is_kept_but_marked_unverified(self):
        """Out-of-scope analytes must never be silently dropped or guessed."""
        result = ground_tests([{"test_name": "Vitamin D", "value": "18", "status": "low"}])
        item = result["grounded"][0]
        self.assertFalse(item["verified"])
        self.assertEqual(item["status"], "unknown")
        self.assertEqual(result["counts"]["unverified"], 1)
        # An unverified test must not be counted as abnormal or critical
        self.assertEqual(result["counts"]["abnormal"], 0)
        self.assertEqual(result["counts"]["critical"], 0)

    def test_unparseable_value_is_not_classified(self):
        result = ground_tests([{"test_name": "Hemoglobin", "value": "see note", "status": "low"}])
        self.assertFalse(result["grounded"][0]["verified"])
        self.assertEqual(result["grounded"][0]["status"], "unknown")

    def test_abnormals_sorted_worst_first(self):
        tests = [
            {"test_name": "WBC Count", "value": "13500"},
            {"test_name": "Platelet Count", "value": "45000"},
        ]
        result = ground_tests(tests, gender="M")
        self.assertEqual(result["abnormal"][0]["test_name"], "Platelet Count")

    def test_all_normal_reads_as_reassuring(self):
        result = ground_tests([{"test_name": "Hemoglobin", "value": "15.0"}], gender="M")
        self.assertEqual(result["counts"]["abnormal"], 0)
        self.assertEqual(overall_status(result["counts"]), "reassuring")


class GroundedFactsBlockTest(TestCase):
    def test_block_contains_verified_marker_and_curated_causes(self):
        result = ground_tests([{"test_name": "Hemoglobin", "value": "9.0"}], gender="M")
        block = build_grounded_facts_block(result)
        self.assertIn("VERIFIED LOW", block)
        self.assertIn("Iron deficiency", block)

    def test_unverified_tests_are_flagged_for_cautious_language(self):
        result = ground_tests([{"test_name": "Vitamin D", "value": "18"}])
        block = build_grounded_facts_block(result)
        self.assertIn("NOT independently verified", block)


COVER_PAGE = """
VIJAYA PH DIAGNOSTIC CENTRE
A Unit Of Vijaya Diagnostic Centre Limited
SMART REPORT — Navigate Your Health with Clarity and Actionable Insights
Prepared for : Mr. Pramod Saste
Registration ID : 266160001360
Package : VIJAYA PH DIAMOND PACKAGE
Date of test : 08-06-2026
Report released on: 08-06-2026
Disclaimer: The smart report depicts an overall summary of the investigations and
prepared by a third party using the excerpts from the lab test reports and as such is
vulnerable to errors and omissions. Accordingly, Vijaya PH Diagnostic Centre shall not
assume liability in any manner whatsoever, directly or indirectly.
Report Walkthrough — Glance at Imp. Parameters — Pg- 04
"""

RESULTS_PAGE = """
COMPLETE BLOOD COUNT
Test              Result   Unit         Reference Range
Hemoglobin        11.2     g/dL         13.0 - 17.0
WBC Count         12800    cells/cumm   4000 - 11000
Platelet Count    190000   cells/cumm   150000 - 450000
"""


class LabRelevanceScoringTest(TestCase):
    def test_results_page_far_outscores_cover_page(self):
        self.assertGreater(score_lab_relevance(RESULTS_PAGE), score_lab_relevance(COVER_PAGE) * 3)

    def test_dates_are_not_counted_as_reference_ranges(self):
        """Cover pages are dense with dates; those must not look like lab ranges."""
        dates_only = "Date of test : 08-06-2026\nReport released on: 08-06-2026\nDOB 12/04/1975"
        self.assertEqual(score_lab_relevance(dates_only), 0)

    def test_empty_text_scores_zero(self):
        self.assertEqual(score_lab_relevance(""), 0)
        self.assertEqual(score_lab_relevance("   \n  "), 0)


class LabTextSelectionTest(TestCase):
    """Regression: a real multi-page report reported 'couldn't structure into
    test results' because a flat 3000-char truncation spent the entire budget on
    branding and disclaimer pages, so the model never saw a single value."""

    def _bloated_report(self, cover_pages: int = 6) -> str:
        pages = [COVER_PAGE] * cover_pages + [RESULTS_PAGE]
        return "\n--- PAGE BREAK ---\n".join(pages)

    def test_flat_truncation_would_have_lost_all_values(self):
        report = self._bloated_report()
        self.assertNotIn("Hemoglobin", report[:3000])

    def test_selection_recovers_the_results_page(self):
        selected = select_lab_relevant_text(self._bloated_report(), 60000)
        self.assertIn("Hemoglobin", selected)
        self.assertIn("Platelet Count", selected)

    def test_tight_budget_drops_cover_pages_first(self):
        selected = select_lab_relevant_text(self._bloated_report(), 1200)
        self.assertIn("Hemoglobin", selected)
        self.assertNotIn("shall not assume liability", selected)

    def test_short_single_page_text_is_returned_untouched(self):
        self.assertEqual(select_lab_relevant_text(RESULTS_PAGE, 60000), RESULTS_PAGE)

    def test_empty_input(self):
        self.assertEqual(select_lab_relevant_text("", 100), "")

    def test_all_pages_irrelevant_falls_back_to_head(self):
        """Never return nothing — degrade to previous behaviour instead."""
        junk = "\n--- PAGE BREAK ---\n".join(["lorem ipsum dolor sit amet"] * 5)
        selected = select_lab_relevant_text(junk, 40)
        self.assertTrue(selected)
        self.assertLessEqual(len(selected), 40)

    def test_document_order_is_preserved(self):
        report = "\n--- PAGE BREAK ---\n".join([RESULTS_PAGE, COVER_PAGE, "SGPT (ALT) 88 IU/L 0 - 49"])
        selected = select_lab_relevant_text(report, 60000)
        self.assertLess(selected.index("Hemoglobin"), selected.index("SGPT"))


class ConsultationPipelineTest(TestCase):
    """End-to-end: extraction → grounding → doctor-voice consultation."""

    EXTRACTION = json.dumps({
        "tests": [
            {"test_name": "Hemoglobin", "value": "10.1", "unit": "g/dL", "status": "normal"},
            {"test_name": "Platelet Count", "value": "220000", "unit": "/uL", "status": "normal"},
        ],
        "summary": "thin",
        "abnormal_findings": [],
        "what_this_may_mean": "",
        "consult_note": "x",
    })

    CONSULT = json.dumps({
        "headline": "Your haemoglobin is low, which is worth following up.",
        "opening": "This was a blood count. Most of it looks steady.",
        "whats_working_well": "Your platelets are normal.",
        "needs_attention": [{
            "test_name": "Hemoglobin",
            "plain_meaning": "Hemoglobin carries oxygen.",
            "why_it_matters_for_you": "Yours is low, which fits the tiredness you described.",
            "urgency": "soon",
        }],
        "connection_to_your_history": "Relevant given your reported fatigue.",
        "trend_vs_previous": "",
        "next_steps": ["Ask your doctor for iron studies"],
        "follow_up": "Within 2 weeks.",
        "questions_for_your_doctor": ["Do I need iron supplements?"],
        "red_flags": ["Fainting or severe breathlessness"],
        "closing": "This is manageable.",
    })

    @patch("api.report_insight_engine.GeminiProvider")
    def test_consultation_is_produced_and_status_verified(self, MockProvider):
        mock = MockProvider.return_value
        mock.is_available = True
        mock.complete.side_effect = [self.EXTRACTION, self.CONSULT]

        result = generate_combined_report_insights(
            report_data={"file_name": "cbc.pdf", "extracted_text": "raw", "tests": [], "abnormal_findings": []},
            user_context={"age": 52, "gender": "M", "past_history": [],
                          "other_notes": None, "past_triages": [], "prior_report_findings": []},
        )

        # Arithmetic corrected the model's "normal" claim on a low haemoglobin
        by_name = {t["test_name"]: t for t in result["tests"]}
        self.assertEqual(by_name["Hemoglobin"]["status"], "low")
        self.assertEqual(by_name["Platelet Count"]["status"], "normal")

        consultation = result["consultation"]
        self.assertIn("haemoglobin", consultation["headline"].lower())
        self.assertEqual(consultation["next_steps"], ["Ask your doctor for iron studies"])
        self.assertEqual(consultation["red_flags"], ["Fainting or severe breathlessness"])

        self.assertEqual(result["verification"]["overall_status"], "attention_needed")
        # Internal plumbing must not leak to API consumers
        self.assertNotIn("_raw_parsed", result)

    @patch("api.report_insight_engine.GeminiProvider")
    def test_narrative_failure_still_returns_verified_findings(self, MockProvider):
        """If the consultation call returns junk, correctness must survive."""
        mock = MockProvider.return_value
        mock.is_available = True
        mock.complete.side_effect = [self.EXTRACTION, "not json at all"]

        result = generate_combined_report_insights(
            report_data={"file_name": "cbc.pdf", "extracted_text": "raw", "tests": [], "abnormal_findings": []},
            user_context={"age": 52, "gender": "M", "past_history": [],
                          "other_notes": None, "past_triages": [], "prior_report_findings": []},
        )

        self.assertTrue(result["success"])
        self.assertIsNone(result.get("consultation"))
        by_name = {t["test_name"]: t for t in result["tests"]}
        self.assertEqual(by_name["Hemoglobin"]["status"], "low")
        self.assertNotIn("_raw_parsed", result)

    @patch("api.report_insight_engine.resolve_fallback_openrouter_model", create=True)
    @patch("api.report_insight_engine.OpenRouterProvider")
    @patch("api.report_insight_engine.GeminiProvider")
    def test_gemini_quota_error_fails_over_to_openrouter(self, MockGemini, MockOpenRouter, _mock_resolve):
        """A Gemini 429 must not degrade the whole report — free-tier quota is
        easy to exhaust and produces the same message as an unreadable scan."""
        from api.llm_providers import ModelProviderError

        MockGemini.return_value.is_available = True
        MockGemini.return_value.complete.side_effect = ModelProviderError("Gemini request failed")

        MockOpenRouter.return_value.is_available = True
        MockOpenRouter.return_value.complete.side_effect = [self.EXTRACTION, self.CONSULT]

        with patch("api.llm_providers.catalog.resolve_fallback_openrouter_model", return_value="free/model"):
            result = generate_combined_report_insights(
                report_data={"file_name": "cbc.pdf", "extracted_text": "raw", "tests": [], "abnormal_findings": []},
                user_context={"age": 52, "gender": "M", "past_history": [],
                              "other_notes": None, "past_triages": [], "prior_report_findings": []},
            )

        self.assertFalse(result.get("degraded"))
        by_name = {t["test_name"]: t for t in result["tests"]}
        self.assertEqual(by_name["Hemoglobin"]["status"], "low")

    @patch("api.report_insight_engine.GeminiProvider")
    def test_abnormal_findings_carry_knowledge_base_detail(self, MockProvider):
        mock = MockProvider.return_value
        mock.is_available = True
        mock.complete.side_effect = [self.EXTRACTION, self.CONSULT]

        result = generate_combined_report_insights(
            report_data={"file_name": "cbc.pdf", "extracted_text": "raw", "tests": [], "abnormal_findings": []},
            user_context={"age": 52, "gender": "M", "past_history": [],
                          "other_notes": None, "past_triages": [], "prior_report_findings": []},
        )
        hb = result["abnormal_findings"][0]
        self.assertEqual(hb["test_name"], "Hemoglobin")
        self.assertTrue(hb["explanation"])
        self.assertTrue(hb["possible_causes"])
        self.assertTrue(hb["action"])
