"""Fix 5: the OpenRouter failover model is resolved from the live catalog.

The hardcoded TRIAGE_FALLBACK_OPENROUTER_MODEL is now only a last resort, so a
retired model cannot silently break cross-provider failover.

Fix A moved the live query out of the request path: resolution/ranking now
happens in refresh_fallback_openrouter_model() (background), while
resolve_fallback_openrouter_model() is a pure cache-or-default read. These
tests exercise the ranking logic where it actually lives.
"""
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from unittest.mock import patch

from .llm_providers.catalog import (
    FALLBACK_MODEL_CACHE_KEY,
    refresh_fallback_openrouter_model,
    resolve_fallback_openrouter_model,
)
from .triage_engine_v2 import TriageEngineV2

HARDCODED = 'google/gemini-2.5-flash'
LIVE_FREE = 'meta-llama/llama-3.3-8b-instruct:free'


def free_model(model_id, context_length=8192):
    return {
        'id': model_id,
        'name': model_id,
        'context_length': context_length,
        'pricing': {'prompt': '0', 'completion': '0'},
        'is_free': True,
    }


@override_settings(
    TRIAGE_FALLBACK_OPENROUTER_MODEL=HARDCODED,
    ALLOWED_OPENROUTER_MODELS=[],
)
class FallbackModelResolutionTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_uses_live_free_model_over_hardcoded_default(self):
        with patch('api.llm_providers.catalog.get_free_openrouter_models',
                   return_value=[free_model(LIVE_FREE)]):
            resolved = refresh_fallback_openrouter_model()

        self.assertEqual(resolved, LIVE_FREE)
        self.assertNotEqual(resolved, HARDCODED)

    def test_falls_back_to_hardcoded_when_live_query_returns_nothing(self):
        with patch('api.llm_providers.catalog.get_free_openrouter_models', return_value=[]):
            resolved = refresh_fallback_openrouter_model()

        self.assertEqual(resolved, HARDCODED)

    def test_falls_back_to_hardcoded_when_live_query_raises(self):
        with patch('api.llm_providers.catalog.get_free_openrouter_models',
                   side_effect=RuntimeError('openrouter unreachable')):
            resolved = refresh_fallback_openrouter_model()

        self.assertEqual(resolved, HARDCODED)

    def test_refresh_writes_cache_and_resolver_then_reads_it_without_querying(self):
        # The refresher always re-queries - that is its job. The saving is
        # that readers never query at all once it has run.
        with patch('api.llm_providers.catalog.get_free_openrouter_models',
                   return_value=[free_model(LIVE_FREE)]) as lookup:
            refresh_fallback_openrouter_model()
            self.assertEqual(lookup.call_count, 1)
            self.assertEqual(cache.get(FALLBACK_MODEL_CACHE_KEY), LIVE_FREE)

            # Many reads, still exactly one catalog query.
            for _ in range(5):
                self.assertEqual(resolve_fallback_openrouter_model(), LIVE_FREE)
            self.assertEqual(lookup.call_count, 1, 'a read path queried the catalog')

    def test_cached_value_is_used_without_any_lookup(self):
        cache.set(FALLBACK_MODEL_CACHE_KEY, 'cached/model', 3600)

        with patch('api.llm_providers.catalog.get_free_openrouter_models') as lookup:
            resolved = resolve_fallback_openrouter_model()

        self.assertEqual(resolved, 'cached/model')
        lookup.assert_not_called()

    def test_prefers_larger_context_window_among_free_models(self):
        with patch('api.llm_providers.catalog.get_free_openrouter_models', return_value=[
            free_model('small/model:free', context_length=4096),
            free_model('big/model:free', context_length=131072),
        ]):
            self.assertEqual(refresh_fallback_openrouter_model(), 'big/model:free')

    def test_selection_is_stable_across_calls(self):
        models = [
            free_model('b/model:free', context_length=8192),
            free_model('a/model:free', context_length=8192),
        ]
        with patch('api.llm_providers.catalog.get_free_openrouter_models', return_value=models):
            first = refresh_fallback_openrouter_model()
        cache.clear()
        with patch('api.llm_providers.catalog.get_free_openrouter_models',
                   return_value=list(reversed(models))):
            second = refresh_fallback_openrouter_model()

        self.assertEqual(first, second, 'tie-break is not deterministic')

    @override_settings(ALLOWED_OPENROUTER_MODELS=['allowed/model:free'])
    def test_prefers_an_allow_listed_free_model(self):
        with patch('api.llm_providers.catalog.get_free_openrouter_models', return_value=[
            free_model('other/model:free', context_length=131072),
            free_model('allowed/model:free', context_length=4096),
        ]):
            self.assertEqual(refresh_fallback_openrouter_model(), 'allowed/model:free')

    @override_settings(TRIAGE_FALLBACK_OPENROUTER_MODEL='')
    def test_empty_setting_disables_failover_without_a_lookup(self):
        with patch('api.llm_providers.catalog.get_free_openrouter_models') as lookup:
            resolved = resolve_fallback_openrouter_model()

        self.assertEqual(resolved, '')
        lookup.assert_not_called()


@override_settings(
    TRIAGE_FALLBACK_OPENROUTER_MODEL=HARDCODED,
    ALLOWED_OPENROUTER_MODELS=[],
)
class EngineUsesResolvedFallbackModelTests(SimpleTestCase):
    """The resolved model must be the one the engine actually calls."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_engine_fails_over_to_the_live_resolved_model(self):
        from .llm_providers.base import ModelProviderError

        class Recorder:
            is_available = True

            def __init__(self, error=None, text=None):
                self.error, self.text, self.calls = error, text, []

            def complete(self, messages, model_id, temperature):
                self.calls.append(model_id)
                if self.error:
                    raise self.error
                return self.text

        import json
        gemini = Recorder(error=ModelProviderError('down', status_code=503))
        openrouter = Recorder(text=json.dumps({
            'risk_level': 'low', 'confidence': 0.5, 'reasoning': 'ok',
            'possible_conditions': [{'disease': 'Migraine', 'confidence': 0.3}],
            'recommendations': ['Rest'],
        }))
        engine = TriageEngineV2(default_provider=gemini, openrouter_provider=openrouter)

        # Real production flow: the beat task warms the cache out-of-band,
        # then assess() reads it. assess() itself never queries the catalog.
        with patch('api.llm_providers.catalog.get_free_openrouter_models',
                   return_value=[free_model(LIVE_FREE)]):
            refresh_fallback_openrouter_model()

        with patch('api.llm_providers.catalog.get_free_openrouter_models') as lookup:
            engine.assess('cough and fever for three days, mild', {})
        lookup.assert_not_called()

        self.assertEqual(
            openrouter.calls, [LIVE_FREE],
            'engine did not fail over to the live-resolved free model',
        )
