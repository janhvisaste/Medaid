"""Fix A: the triage path must never issue an HTTP request to resolve the
OpenRouter failover model, even on a cold cache.

A slow /models endpoint used to be able to add up to 15s to a patient's
assessment. The catalog is now warmed out-of-band by a Celery beat task.
"""
import json

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from unittest.mock import patch

import api.llm_providers.catalog as catalog_module
from .llm_providers.base import ModelProviderError
from .llm_providers.catalog import (
    FALLBACK_MODEL_CACHE_KEY,
    refresh_fallback_openrouter_model,
    resolve_fallback_openrouter_model,
)
from .triage_engine_v2 import TriageEngineV2

HARDCODED = 'google/gemini-2.5-flash'
LIVE_FREE = 'meta-llama/llama-3.3-8b-instruct:free'

VALID_RESPONSE = json.dumps({
    'risk_level': 'low',
    'confidence': 0.5,
    'reasoning': 'ok',
    'possible_conditions': [{'disease': 'Migraine', 'confidence': 0.3}],
    'recommendations': ['Rest'],
})


def free_model(model_id, context_length=8192):
    return {
        'id': model_id,
        'name': model_id,
        'context_length': context_length,
        'pricing': {'prompt': '0', 'completion': '0'},
        'is_free': True,
    }


class Recorder:
    is_available = True

    def __init__(self, error=None, text=None):
        self.error, self.text, self.calls = error, text, []

    def complete(self, messages, model_id, temperature):
        self.calls.append(model_id)
        if self.error:
            raise self.error
        return self.text


@override_settings(
    TRIAGE_FALLBACK_OPENROUTER_MODEL=HARDCODED,
    ALLOWED_OPENROUTER_MODELS=[],
)
class ResolverNeverBlocksTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_cold_cache_returns_default_without_http(self):
        with patch.object(catalog_module.requests, 'get') as http:
            resolved = resolve_fallback_openrouter_model()

        self.assertEqual(resolved, HARDCODED)
        http.assert_not_called()

    def test_cold_cache_does_not_populate_cache(self):
        # The hot path must stay a pure read - no write-through, or a cold
        # start would pin the default for a whole TTL and block the refresher.
        resolve_fallback_openrouter_model()
        self.assertIsNone(cache.get(FALLBACK_MODEL_CACHE_KEY))

    def test_warm_cache_is_used_without_http(self):
        cache.set(FALLBACK_MODEL_CACHE_KEY, LIVE_FREE, 3600)

        with patch.object(catalog_module.requests, 'get') as http:
            resolved = resolve_fallback_openrouter_model()

        self.assertEqual(resolved, LIVE_FREE)
        http.assert_not_called()


@override_settings(
    TRIAGE_FALLBACK_OPENROUTER_MODEL=HARDCODED,
    ALLOWED_OPENROUTER_MODELS=[],
)
class AssessIssuesNoHttpTests(SimpleTestCase):
    """The headline assertion: assess() itself makes no HTTP request."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _assess_with_failover(self):
        gemini = Recorder(error=ModelProviderError('down', status_code=503))
        openrouter = Recorder(text=VALID_RESPONSE)
        engine = TriageEngineV2(default_provider=gemini, openrouter_provider=openrouter)
        result = engine.assess('cough and fever for three days, mild', {})
        return result, openrouter

    def test_assess_makes_no_http_call_on_cold_cache(self):
        with patch.object(catalog_module.requests, 'get') as http:
            result, openrouter = self._assess_with_failover()

        http.assert_not_called()
        # Failover still happened - just against the last-known-good default.
        self.assertEqual(openrouter.calls, [HARDCODED])
        self.assertEqual(result['model_provider'], 'openrouter')

    def test_assess_makes_no_http_call_on_warm_cache(self):
        cache.set(FALLBACK_MODEL_CACHE_KEY, LIVE_FREE, 3600)

        with patch.object(catalog_module.requests, 'get') as http:
            _, openrouter = self._assess_with_failover()

        http.assert_not_called()
        self.assertEqual(openrouter.calls, [LIVE_FREE])

    def test_assess_makes_no_http_call_on_the_happy_path(self):
        engine = TriageEngineV2(
            default_provider=Recorder(text=VALID_RESPONSE),
            openrouter_provider=Recorder(text=VALID_RESPONSE),
        )
        with patch.object(catalog_module.requests, 'get') as http:
            engine.assess('cough and fever for three days, mild', {})

        http.assert_not_called()


@override_settings(
    TRIAGE_FALLBACK_OPENROUTER_MODEL=HARDCODED,
    ALLOWED_OPENROUTER_MODELS=[],
)
class BackgroundRefreshWarmsCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_refresh_populates_cache_from_live_catalog(self):
        with patch('api.llm_providers.catalog.get_free_openrouter_models',
                   return_value=[free_model(LIVE_FREE)]):
            resolved = refresh_fallback_openrouter_model()

        self.assertEqual(resolved, LIVE_FREE)
        self.assertEqual(cache.get(FALLBACK_MODEL_CACHE_KEY), LIVE_FREE)

    def test_resolver_serves_what_the_refresher_wrote(self):
        with patch('api.llm_providers.catalog.get_free_openrouter_models',
                   return_value=[free_model(LIVE_FREE)]):
            refresh_fallback_openrouter_model()

        with patch.object(catalog_module.requests, 'get') as http:
            self.assertEqual(resolve_fallback_openrouter_model(), LIVE_FREE)
        http.assert_not_called()

    def test_refresh_falls_back_to_default_when_catalog_fails(self):
        with patch('api.llm_providers.catalog.get_free_openrouter_models',
                   side_effect=RuntimeError('unreachable')):
            resolved = refresh_fallback_openrouter_model()

        self.assertEqual(resolved, HARDCODED)

    def test_celery_task_swallows_errors(self):
        from .tasks import refresh_openrouter_fallback_model_task

        with patch('api.llm_providers.catalog.refresh_fallback_openrouter_model',
                   side_effect=RuntimeError('boom')):
            # Must not raise - a failed refresh degrades to the default, it
            # does not take down the worker.
            self.assertIsNone(refresh_openrouter_fallback_model_task())

    def test_celery_task_returns_resolved_model(self):
        from .tasks import refresh_openrouter_fallback_model_task

        with patch('api.llm_providers.catalog.get_free_openrouter_models',
                   return_value=[free_model(LIVE_FREE)]):
            self.assertEqual(refresh_openrouter_fallback_model_task(), LIVE_FREE)


class BeatScheduleTests(SimpleTestCase):
    def test_refresh_task_is_scheduled(self):
        from django.conf import settings

        schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        entry = schedule.get('refresh-openrouter-fallback-model')
        self.assertIsNotNone(entry, 'refresh task is not scheduled')
        self.assertEqual(entry['task'], 'api.tasks.refresh_openrouter_fallback_model_task')

    def test_schedule_interval_is_below_cache_ttl(self):
        from django.conf import settings

        from .llm_providers.catalog import FALLBACK_MODEL_CACHE_SECONDS

        interval = settings.CELERY_BEAT_SCHEDULE['refresh-openrouter-fallback-model']['schedule']
        # A single missed run must not let the cache expire.
        self.assertLessEqual(interval * 2, FALLBACK_MODEL_CACHE_SECONDS)
