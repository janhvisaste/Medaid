"""Tests for feeding prior TriageRecord history into the assessment prompt.

The data already existed per-user; these cover that it is actually fetched,
bounded, and reaches the prompt the model sees.
"""
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from rest_framework.test import APIClient

from .models import PossibleCondition, TriageRecord, UserProfile
from .patient_context import (
    DEFAULT_MAX_RECORDS,
    build_patient_history_context,
    format_prior_assessments,
    get_prior_assessments,
)
from .triage_engine_v2 import TriageEngineV2

User = get_user_model()


class CapturingProvider:
    """Records the prompt it was given and returns a valid assessment."""

    is_available = True

    def __init__(self):
        self.calls = []

    def complete(self, messages, model_id, temperature):
        self.calls.append(messages)
        return json.dumps({
            'risk_level': 'medium',
            'risk_probability': 0.5,
            'confidence': 0.7,
            'reasoning': 'Needs evaluation.',
            'possible_conditions': [{'disease': 'Migraine', 'confidence': 0.3}],
            'recommendations': ['Rest'],
            'when_to_seek_care': 'If worse',
        })

    @property
    def last_prompt(self):
        return self.calls[-1][0]['content']


class PriorAssessmentRetrievalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='hist_user', password='password123', email='hist@example.com'
        )

    def _make_record(self, symptoms, risk_level, days_ago=0, conditions=()):
        record = TriageRecord.objects.create(
            user=self.user, current_symptoms=symptoms, risk_level=risk_level, reasoning='r'
        )
        if days_ago:
            TriageRecord.objects.filter(pk=record.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago)
            )
            record.refresh_from_db()
        for name, confidence in conditions:
            PossibleCondition.objects.create(
                triage_record=record, disease_name=name, confidence=confidence
            )
        return record

    def test_returns_empty_for_user_with_no_history(self):
        self.assertEqual(get_prior_assessments(self.user), [])

    def test_returns_records_newest_first(self):
        self._make_record('oldest headache', 'low', days_ago=10)
        self._make_record('middle headache', 'medium', days_ago=5)
        self._make_record('newest headache', 'high', days_ago=1)

        prior = get_prior_assessments(self.user)

        self.assertEqual([p['risk_level'] for p in prior], ['high', 'medium', 'low'])

    def test_caps_number_of_records(self):
        for i in range(DEFAULT_MAX_RECORDS + 4):
            self._make_record(f'episode {i}', 'low', days_ago=i + 1)

        self.assertEqual(len(get_prior_assessments(self.user)), DEFAULT_MAX_RECORDS)

    def test_excludes_records_outside_the_time_window(self):
        self._make_record('ancient', 'low', days_ago=400)
        self._make_record('recent', 'low', days_ago=2)

        prior = get_prior_assessments(self.user, within_days=365)

        self.assertEqual(len(prior), 1)
        self.assertEqual(prior[0]['symptoms'], 'recent')

    def test_excludes_other_users_history(self):
        other = User.objects.create_user(
            username='other_hist', password='password123', email='other_hist@example.com'
        )
        TriageRecord.objects.create(
            user=other, current_symptoms='not mine', risk_level='high', reasoning='r'
        )
        self._make_record('mine', 'low', days_ago=1)

        prior = get_prior_assessments(self.user)

        self.assertEqual(len(prior), 1)
        self.assertEqual(prior[0]['symptoms'], 'mine')

    def test_includes_top_conditions_by_confidence(self):
        self._make_record(
            'headache', 'medium', days_ago=1,
            conditions=[('Migraine', 0.4), ('Tension Headache', 0.2), ('Sinusitis', 0.35)],
        )

        prior = get_prior_assessments(self.user)

        self.assertEqual(prior[0]['conditions'], ['Migraine', 'Sinusitis', 'Tension Headache'])

    def test_can_exclude_a_specific_record(self):
        keep = self._make_record('keep me', 'low', days_ago=2)
        drop = self._make_record('drop me', 'low', days_ago=1)

        prior = get_prior_assessments(self.user, exclude_record_id=drop.pk)

        self.assertEqual([p['symptoms'] for p in prior], ['keep me'])
        self.assertTrue(keep.pk)

    def test_long_symptom_text_is_truncated(self):
        self._make_record('x' * 500, 'low', days_ago=1)
        prior = get_prior_assessments(self.user)
        self.assertLessEqual(len(prior[0]['symptoms']), 161)

    def test_query_count_is_bounded_regardless_of_record_count(self):
        for i in range(DEFAULT_MAX_RECORDS):
            self._make_record(f'episode {i}', 'low', days_ago=i + 1,
                              conditions=[('Migraine', 0.3), ('Sinusitis', 0.2)])

        # prefetch_related keeps this at a fixed 2 queries (records + conditions)
        # rather than growing with the number of records.
        with self.assertNumQueries(2):
            get_prior_assessments(self.user)

    def test_build_context_never_raises_on_lookup_failure(self):
        with patch('api.patient_context.get_prior_assessments', side_effect=RuntimeError('db down')):
            context = build_patient_history_context(self.user)
        self.assertEqual(context['prior_assessments'], [])
        self.assertEqual(context['prior_assessments_text'], '')

    def test_format_is_empty_for_no_history(self):
        self.assertEqual(format_prior_assessments([]), '')


class PriorHistoryReachesThePromptTests(TestCase):
    """The whole point: prior assessments must appear in the model's prompt."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='prompt_hist', password='password123', email='prompt_hist@example.com'
        )
        UserProfile.objects.create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_prompt_includes_prior_assessments(self):
        past = TriageRecord.objects.create(
            user=self.user,
            current_symptoms='recurring migraine with aura',
            risk_level='high',
            reasoning='prior',
        )
        PossibleCondition.objects.create(
            triage_record=past, disease_name='Migraine', confidence=0.4
        )

        provider = CapturingProvider()
        engine = TriageEngineV2(default_provider=provider, openrouter_provider=provider)

        with patch('api.views.get_triage_engine_v2', return_value=engine):
            response = self.client.post(
                reverse('assess_symptoms'),
                {'current_symptoms': 'headache again today', 'skip_clarification': True},
                format='json',
            )

        self.assertEqual(response.status_code, 201)
        prompt = provider.last_prompt
        self.assertIn('Previous assessments', prompt)
        self.assertIn('recurring migraine with aura', prompt)
        self.assertIn('Migraine', prompt)
        self.assertEqual(response.data['used_prior_assessments'], 1)

    def test_prompt_omits_history_block_for_first_time_patient(self):
        provider = CapturingProvider()
        engine = TriageEngineV2(default_provider=provider, openrouter_provider=provider)

        with patch('api.views.get_triage_engine_v2', return_value=engine):
            response = self.client.post(
                reverse('assess_symptoms'),
                {'current_symptoms': 'headache today', 'skip_clarification': True},
                format='json',
            )

        self.assertEqual(response.status_code, 201)
        self.assertNotIn('Previous assessments', provider.last_prompt)
        self.assertEqual(response.data['used_prior_assessments'], 0)

    def test_report_summary_and_location_reach_the_prompt(self):
        # These were accepted by _build_assessment_prompt and then dropped.
        engine = TriageEngineV2()
        prompt = engine._build_assessment_prompt(
            'cough',
            {'age': 30, 'gender': 'F'},
            'Hemoglobin 8.1 g/dL (low)',
            'Pune, Pincode: 411046',
        )
        self.assertIn('Hemoglobin 8.1 g/dL (low)', prompt)
        self.assertIn('411046', prompt)
