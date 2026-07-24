"""Tests for the Gemini request timeout (Phase 1 item 5).

A stalled Gemini upstream must not hang a request worker forever, and a
timeout must degrade gracefully - it is converted to a ModelProviderError and
routed to the triage engine's degraded-response path, never propagated as an
unhandled 500.
"""

from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from . import llm_providers
from .llm_providers import gemini_client
from .llm_providers.base import ModelProviderError
from .triage_engine_v2 import TriageEngineV2


class _UnavailableProvider:
    """OpenRouter stand-in that is not configured, so no failover happens."""
    is_available = False

    def complete(self, messages, model_id, temperature):  # pragma: no cover
        raise AssertionError("failover provider should not be called")


def _gemini_provider_raising(exc):
    """A real GeminiProvider whose underlying SDK client raises `exc`.

    Built with __new__ to skip the real genai.Client construction; the mock
    client stands in for the SDK.
    """
    provider = gemini_client.GeminiProvider.__new__(gemini_client.GeminiProvider)
    provider.api_key = "test-key"
    client = MagicMock()
    client.models.generate_content.side_effect = exc
    provider.client = client
    return provider, client


class GeminiTimeoutUnitTests(SimpleTestCase):
    def test_configured_timeout_is_passed_to_the_sdk(self):
        provider, client = _gemini_provider_raising(TimeoutError("deadline exceeded"))
        with self.assertRaises(ModelProviderError):
            provider.complete([{"role": "user", "content": "hi"}], "gemini-x", 0.4)
        # Prove the timeout actually reached the SDK call (in milliseconds),
        # not just that exceptions are caught.
        _, kwargs = client.models.generate_content.call_args
        self.assertEqual(
            kwargs["config"].http_options.timeout,
            gemini_client.GEMINI_TIMEOUT_SECONDS * 1000,
        )

    def test_timeout_is_converted_to_model_provider_error(self):
        # Whatever timeout type the SDK surfaces, it becomes a ModelProviderError.
        for exc in (TimeoutError("deadline"), Exception("read timed out")):
            provider, _ = _gemini_provider_raising(exc)
            with self.assertRaises(ModelProviderError):
                provider.complete([{"role": "user", "content": "hi"}], "gemini-x", 0.4)


class GeminiTimeoutEngineTests(SimpleTestCase):
    @override_settings(TRIAGE_FALLBACK_OPENROUTER_MODEL="")  # disable OR failover
    def test_engine_degrades_on_timeout_instead_of_crashing(self):
        provider, _ = _gemini_provider_raising(TimeoutError("deadline exceeded"))
        engine = TriageEngineV2(default_provider=provider,
                                openrouter_provider=_UnavailableProvider())

        # Non-emergency symptoms so nothing short-circuits before the LLM call.
        result = engine.assess(
            "mild sore throat for two days",
            {"age": 30, "gender": "F", "past_history": []},
        )

        # Degraded, safe, flagged for review - and it returned a dict, not a raise.
        self.assertTrue(result["degraded"])
        self.assertTrue(result["is_degraded"])
        self.assertTrue(result["requires_human_review"])
        self.assertEqual(result["risk_level"], "medium")
        self.assertEqual(result["possible_conditions"], [])


# Sanity: the provider export surface still imports cleanly.
assert hasattr(llm_providers, "GeminiProvider")
