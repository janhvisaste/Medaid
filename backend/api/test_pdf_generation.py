"""Regression tests for assessment PDF generation.

Covers two previously-unguarded things:
  1. generate_assessment_pdf with a real UserProfile used to crash on a
     nonexistent user_profile.phone attribute (phone lives on User as
     phone_number). Nothing tested PDF generation with a profile.
  2. A degraded assessment must render its prominent "requires clinician
     review" notice on the PDF itself, with no silent-blank conditions section.
"""

from django.test import TestCase

import pymupdf

from .models import User, UserProfile, TriageRecord, PossibleCondition
from .report_generator import generate_assessment_pdf


def _pdf_text(pdf_bytes):
    return "\n".join(page.get_text() for page in pymupdf.open(stream=pdf_bytes, filetype="pdf"))


class AssessmentPdfTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pdf@x.com", email="pdf@x.com", password="pw12345678",
            first_name="Pat", last_name="Doe", phone_number="+919812345678",
        )

    def _record(self, **kw):
        fields = dict(
            user=self.user, current_symptoms="fever", risk_level="medium",
            reasoning="r", confidence=0.4,
        )
        fields.update(kw)   # allow callers to override any default (e.g. confidence)
        return TriageRecord.objects.create(**fields)

    def test_generation_with_profile_does_not_crash_and_renders_phone(self):
        profile = UserProfile.objects.create(user=self.user, gender="F")
        rec = self._record(assessment_source="ai_v2")
        text = _pdf_text(generate_assessment_pdf(rec, self.user, profile))
        # The bug: user_profile.phone AttributeError. Phone must render from
        # the User's phone_number instead.
        self.assertIn("+919812345678", text)

    def test_degraded_assessment_renders_prominent_notice(self):
        profile = UserProfile.objects.create(user=self.user, gender="F")
        rec = self._record(assessment_source="llm_fallback", requires_human_review=True,
                           similar_cases={"is_degraded": True, "degraded": True})
        text = _pdf_text(generate_assessment_pdf(rec, self.user, profile))
        self.assertIn("REQUIRES CLINICIAN REVIEW", text)
        self.assertIn("No condition differential was generated", text)
        self.assertIn("POSSIBLE CONDITIONS", text)   # section present, not silent

    def test_normal_assessment_has_no_degraded_notice(self):
        rec = self._record(assessment_source="ai_v2", confidence=0.8,
                           similar_cases={"is_degraded": False})
        PossibleCondition.objects.create(triage_record=rec, disease_name="Viral pharyngitis", confidence=0.3)
        text = _pdf_text(generate_assessment_pdf(rec, self.user, None))
        self.assertNotIn("REQUIRES CLINICIAN REVIEW", text)
        self.assertIn("Viral pharyngitis", text)     # real differential renders
