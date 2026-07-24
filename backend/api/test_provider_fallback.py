"""Regression tests for Fix 8: real cross-provider LLM failover.

When the selected provider raises ModelProviderError, the engine must try the
other configured provider once before returning a degraded response.
"""
import json

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from unittest.mock import patch

from .llm_providers.base import ModelProviderError
from .triage_engine_v2 import TriageEngineV2

VALID_RESPONSE = json.dumps({
    "risk_level": "low",
    "risk_probability": 0.2,
    "confidence": 0.8,
    "reasoning": "Likely mild viral illness.",
    "possible_conditions": [{"disease": "Viral Upper Respiratory Infection", "confidence": 0.35}],
    "recommendations": ["Rest and hydrate"],
    "when_to_seek_care": "If symptoms worsen",
})

USER_DATA = {"age": 30, "gender": "F", "past_history": []}


class RecordingProvider:
    def __init__(self, response_text=None, error=None, is_available=True):
        self.response_text = response_text
        self.error = error
        self.is_available = is_available
        self.calls = []

    def complete(self, messages, model_id, temperature):
        self.calls.append(model_id)
        if self.error:
            raise self.error
        return self.response_text


@override_settings(
    ALLOWED_OPENROUTER_MODELS=["openai/gpt-4o-mini"],
    TRIAGE_FALLBACK_OPENROUTER_MODEL="google/gemini-2.5-flash",
    DEFAULT_TRIAGE_MODEL="gemini-3.1-flash-lite",
)
class CrossProviderFailoverTests(SimpleTestCase):
    def setUp(self):
        # Fix 5 made the failover target resolve from OpenRouter's live
        # catalog. These tests are about failover behaviour, not model
        # resolution, so pin the catalog to empty (forcing the configured
        # default) and clear the hourly cache between tests. Without this
        # they make real network calls and flake on whatever OpenRouter
        # happens to be offering.
        cache.clear()
        self.addCleanup(cache.clear)
        patcher = patch('api.llm_providers.catalog.get_free_openrouter_models', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_provider_failure_fails_over_to_openrouter(self):
        gemini = RecordingProvider(error=ModelProviderError("gemini down", status_code=503))
        openrouter = RecordingProvider(response_text=VALID_RESPONSE)
        engine = TriageEngineV2(default_provider=gemini, openrouter_provider=openrouter)

        result = engine.assess("cough and fever", USER_DATA)

        # Secondary provider was actually attempted...
        self.assertEqual(openrouter.calls, ["google/gemini-2.5-flash"])
        # ...and its result was used instead of a degraded response.
        self.assertNotIn("degraded", result)
        self.assertEqual(result["model_provider"], "openrouter")
        self.assertTrue(result["used_fallback_provider"])
        self.assertEqual(result["risk_level"], "low")

    def test_selected_openrouter_model_failure_fails_over_to_default(self):
        gemini = RecordingProvider(response_text=VALID_RESPONSE)
        openrouter = RecordingProvider(error=ModelProviderError("model down", status_code=503))
        engine = TriageEngineV2(default_provider=gemini, openrouter_provider=openrouter)

        result = engine.assess("cough and fever", USER_DATA, model_id="openai/gpt-4o-mini")

        self.assertEqual(openrouter.calls, ["openai/gpt-4o-mini"])
        self.assertEqual(gemini.calls, ["gemini-3.1-flash-lite"])
        self.assertNotIn("degraded", result)
        self.assertEqual(result["model_provider"], "gemini")
        self.assertTrue(result["used_fallback_provider"])

    def test_both_providers_failing_returns_degraded_response(self):
        gemini = RecordingProvider(error=ModelProviderError("gemini down", status_code=503))
        openrouter = RecordingProvider(error=ModelProviderError("openrouter down", status_code=502))
        engine = TriageEngineV2(default_provider=gemini, openrouter_provider=openrouter)

        result = engine.assess("cough and fever", USER_DATA)

        self.assertEqual(len(gemini.calls), 1)
        self.assertEqual(len(openrouter.calls), 1)
        self.assertTrue(result["degraded"])
        # Fix 3 contract still holds on the all-providers-down path.
        self.assertEqual(result["risk_level"], "medium")
        self.assertTrue(result["requires_human_review"])

    def test_successful_primary_does_not_call_secondary(self):
        gemini = RecordingProvider(response_text=VALID_RESPONSE)
        openrouter = RecordingProvider(response_text=VALID_RESPONSE)
        engine = TriageEngineV2(default_provider=gemini, openrouter_provider=openrouter)

        result = engine.assess("cough and fever", USER_DATA)

        self.assertEqual(len(gemini.calls), 1)
        self.assertEqual(openrouter.calls, [], 'secondary provider must not be called on success')
        self.assertFalse(result["used_fallback_provider"])

    def test_only_one_failover_attempt_is_made(self):
        gemini = RecordingProvider(error=ModelProviderError("gemini down"))
        openrouter = RecordingProvider(error=ModelProviderError("openrouter down"))
        engine = TriageEngineV2(default_provider=gemini, openrouter_provider=openrouter)

        engine.assess("cough and fever", USER_DATA)

        # Exactly one attempt each - no retry storms against a failing provider.
        self.assertEqual(len(gemini.calls), 1)
        self.assertEqual(len(openrouter.calls), 1)

    def test_no_failover_when_secondary_unavailable(self):
        gemini = RecordingProvider(error=ModelProviderError("gemini down", status_code=503))
        openrouter = RecordingProvider(response_text=VALID_RESPONSE, is_available=False)
        engine = TriageEngineV2(default_provider=gemini, openrouter_provider=openrouter)

        result = engine.assess("cough and fever", USER_DATA)

        self.assertEqual(openrouter.calls, [], 'unconfigured provider must not be called')
        self.assertTrue(result["degraded"])

    @override_settings(TRIAGE_FALLBACK_OPENROUTER_MODEL="")
    def test_failover_disabled_by_empty_setting(self):
        gemini = RecordingProvider(error=ModelProviderError("gemini down", status_code=503))
        openrouter = RecordingProvider(response_text=VALID_RESPONSE)
        engine = TriageEngineV2(default_provider=gemini, openrouter_provider=openrouter)

        result = engine.assess("cough and fever", USER_DATA)

        self.assertEqual(openrouter.calls, [])
        self.assertTrue(result["degraded"])
