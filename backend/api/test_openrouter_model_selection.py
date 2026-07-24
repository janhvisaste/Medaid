import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from api.llm_providers.base import ModelProviderError
from api.llm_providers.openrouter_client import OpenRouterProvider
from api.triage_engine_v2 import TriageEngineV2
from api.views import assess_symptoms, available_models


class FakeProvider:
    def __init__(self, response_text=None, error=None, is_available=True):
        self.response_text = response_text or json.dumps({
            "risk_level": "low",
            "risk_probability": 0.2,
            "confidence": 0.8,
            "reasoning": "Likely mild viral illness.",
            "possible_conditions": [
                {
                    "disease": "Viral Upper Respiratory Infection",
                    "confidence": 0.35,
                    "supporting_evidence": ["Cough and fever"],
                }
            ],
            "recommendations": ["Rest and hydrate"],
            "when_to_seek_care": "If symptoms worsen",
        })
        self.error = error
        self.is_available = is_available
        self.calls = []

    def complete(self, messages, model_id, temperature):
        self.calls.append({
            "messages": messages,
            "model_id": model_id,
            "temperature": temperature,
        })
        if self.error:
            raise self.error
        return self.response_text


@override_settings(
    ALLOWED_OPENROUTER_MODELS=["google/gemini-2.5-flash", "openai/gpt-4o-mini"],
    DEFAULT_TRIAGE_MODEL="gemini-3.1-flash-lite",
    TRIAGE_MODEL_TEMPERATURE=0.4,
)
class TriageEngineModelSelectionTests(SimpleTestCase):
    def test_valid_model_id_routes_through_openrouter(self):
        default_provider = FakeProvider()
        openrouter_provider = FakeProvider()
        engine = TriageEngineV2(default_provider=default_provider, openrouter_provider=openrouter_provider)

        result = engine.assess(
            "fever and cough",
            {"age": 30, "gender": "F", "past_history": []},
            model_id="openai/gpt-4o-mini",
        )

        self.assertEqual(result["model_provider"], "openrouter")
        self.assertEqual(result["model_id"], "openai/gpt-4o-mini")
        self.assertEqual(openrouter_provider.calls[0]["model_id"], "openai/gpt-4o-mini")
        self.assertEqual(default_provider.calls, [])

    def test_omitted_model_id_uses_default_gemini_provider(self):
        default_provider = FakeProvider()
        openrouter_provider = FakeProvider()
        engine = TriageEngineV2(default_provider=default_provider, openrouter_provider=openrouter_provider)

        result = engine.assess("fever", {"age": 30, "gender": "F", "past_history": []})

        self.assertEqual(result["model_provider"], "gemini")
        self.assertEqual(result["model_id"], "gemini-3.1-flash-lite")
        self.assertEqual(default_provider.calls[0]["model_id"], "gemini-3.1-flash-lite")
        self.assertEqual(openrouter_provider.calls, [])

    def test_invalid_model_id_maps_to_default_provider(self):
        default_provider = FakeProvider()
        openrouter_provider = FakeProvider()
        engine = TriageEngineV2(default_provider=default_provider, openrouter_provider=openrouter_provider)

        with patch("api.llm_providers.catalog.get_free_openrouter_models", return_value=[]):
            result = engine.assess(
                "fever",
                {"age": 30, "gender": "F", "past_history": []},
                model_id="not/allowed-expensive-model",
            )

        self.assertEqual(result["model_provider"], "gemini")
        self.assertEqual(default_provider.calls[0]["model_id"], "gemini-3.1-flash-lite")
        self.assertEqual(openrouter_provider.calls, [])

    def test_free_model_id_routes_through_openrouter(self):
        default_provider = FakeProvider()
        openrouter_provider = FakeProvider()
        engine = TriageEngineV2(default_provider=default_provider, openrouter_provider=openrouter_provider)

        with patch("api.llm_providers.catalog.get_free_openrouter_models", return_value=[{
            "id": "meta-llama/llama-3.3-8b-instruct:free",
            "name": "Llama 3.3 8B Instruct Free",
            "pricing": {"prompt": "0", "completion": "0"},
            "is_free": True,
        }]):
            result = engine.assess(
                "fever",
                {"age": 30, "gender": "F", "past_history": []},
                model_id="meta-llama/llama-3.3-8b-instruct:free",
            )

        self.assertEqual(result["model_provider"], "openrouter")
        self.assertEqual(openrouter_provider.calls[0]["model_id"], "meta-llama/llama-3.3-8b-instruct:free")

    def test_openrouter_model_error_returns_graceful_model_error_shape(self):
        default_provider = FakeProvider(is_available=False)
        openrouter_provider = FakeProvider(error=ModelProviderError(
            "OpenRouter 503",
            status_code=503,
            user_message="This model is temporarily unavailable. Please try another model.",
        ))
        engine = TriageEngineV2(default_provider=default_provider, openrouter_provider=openrouter_provider)

        result = engine.assess(
            "fever",
            {"age": 30, "gender": "F", "past_history": []},
            model_id="openai/gpt-4o-mini",
        )

        self.assertEqual(result["model_provider"], "openrouter")
        self.assertEqual(result["model_error_status"], 503)
        self.assertTrue(result["degraded"])
        self.assertEqual(result["assessment_source"], "llm_fallback")
        # Fix 3: degraded responses must not default to 'low' risk - that
        # looked like reassurance instead of an unknown/unconfirmed result.
        self.assertEqual(result["risk_level"], "medium")
        self.assertTrue(result["requires_human_review"])
        self.assertIn("try another model", result["model_error"].lower())

    def test_malformed_json_uses_marked_degraded_fallback_shape(self):
        default_provider = FakeProvider(response_text="this is not json")
        engine = TriageEngineV2(default_provider=default_provider, openrouter_provider=FakeProvider())

        result = engine.assess("fever", {"age": 30, "gender": "F", "past_history": []})

        self.assertEqual(result["risk_level"], "medium")
        self.assertTrue(result["requires_human_review"])
        self.assertTrue(result["degraded"])
        # App-wide programmatic flag, same field/shape as the rate-limited 429.
        self.assertTrue(result["is_degraded"])
        self.assertEqual(result["assessment_source"], "llm_fallback")
        # A degraded response must NOT return a fabricated differential that
        # reads like a real assessment (Phase 1 finding): conditions are empty.
        self.assertEqual(result["possible_conditions"], [])
        self.assertIn("couldn't complete a full AI analysis", result["reasoning"])

    def test_successful_assessment_is_not_degraded(self):
        default_provider = FakeProvider(response_text=(
            '{"risk_level":"low","confidence":0.6,"possible_conditions":'
            '[{"disease":"Viral pharyngitis","confidence":0.3}]}'
        ))
        engine = TriageEngineV2(default_provider=default_provider, openrouter_provider=FakeProvider())
        result = engine.assess("sore throat 2 days", {"age": 30, "gender": "F", "past_history": []})
        # is_degraded must be present and False on the normal path, so a client
        # can always trust the flag rather than treating "absent" as "fine".
        self.assertIn("is_degraded", result)
        self.assertFalse(result["is_degraded"])


class OpenRouterProviderRetryTests(SimpleTestCase):
    @override_settings(
        OPENROUTER_API_KEY="test-secret-key",
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        OPENROUTER_HTTP_REFERER="https://medaid.example",
        OPENROUTER_APP_TITLE="MedAid",
    )
    @patch("api.llm_providers.openrouter_client.time.sleep")
    def test_5xx_is_retried_once_then_raises_provider_error(self, _sleep):
        response = Mock()
        response.status_code = 503
        session = Mock()
        session.post.return_value = response
        provider = OpenRouterProvider(session=session)

        with self.assertRaises(ModelProviderError):
            provider.complete([{"role": "user", "content": "prompt"}], "openai/gpt-4o-mini", 0.4)

        self.assertEqual(session.post.call_count, 2)

    @override_settings(OPENROUTER_API_KEY="test-secret-key")
    def test_4xx_is_not_retried(self):
        response = Mock()
        response.status_code = 400
        session = Mock()
        session.post.return_value = response
        provider = OpenRouterProvider(session=session)

        with self.assertRaises(ModelProviderError):
            provider.complete([{"role": "user", "content": "prompt"}], "openai/gpt-4o-mini", 0.4)

        self.assertEqual(session.post.call_count, 1)


@override_settings(
    ALLOWED_OPENROUTER_MODELS=["openai/gpt-4o-mini"],
    OPENROUTER_API_KEY="super-secret-openrouter-key",
)
class ModelEndpointSafetyTests(SimpleTestCase):
    # assess_symptoms now wraps its TriageRecord + child-object creation in
    # transaction.atomic() (Fix 6), which needs a real DB connection even
    # though every ORM call in these tests is mocked out.
    databases = {'default'}

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = Mock()
        self.user.is_authenticated = True
        self.user.profile = Mock()

    @patch("api.views.get_available_model_catalog")
    def test_models_endpoint_does_not_expose_openrouter_api_key(self, mocked_catalog):
        mocked_catalog.return_value = [{
            "id": "openai/gpt-4o-mini",
            "name": "GPT-4o mini",
            "context_length": 128000,
            "pricing": {"prompt": "0.00000015", "completion": "0.00000060"},
            "description": "Small structured-output model.",
        }]

        request = self.factory.get("/api/models/available")
        force_authenticate(request, user=self.user)
        response = available_models(request)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("super-secret-openrouter-key", str(response.data))

    @patch("api.views.create_alert_for_triage_record")
    @patch("api.views.Recommendation.objects.create")
    @patch("api.views.PossibleCondition.objects.create")
    @patch("api.views.TriageRecord.objects.create")
    @patch("api.views.UserProfile.objects.filter")
    @patch("api.views.get_triage_engine_v2")
    def test_assess_response_does_not_expose_openrouter_api_key(
        self,
        mocked_engine,
        mocked_profile_filter,
        mocked_triage_create,
        _mocked_condition_create,
        _mocked_recommendation_create,
        _mocked_create_alert,
    ):
        # Clinician-alert creation touches the DB directly (see
        # test_clinician_alerts.py); it's out of scope for this test, which
        # only cares that the API key never leaks into the response body.
        mocked_profile_filter.return_value.first.return_value = None
        mocked_triage_create.return_value = Mock(id=123, created_at="2026-07-16T00:00:00Z")
        mocked_engine.return_value.assess.return_value = {
            "risk_level": "low",
            "risk_probability": 0.2,
            "confidence": 0.8,
            "reasoning": "Mild symptoms.",
            "possible_conditions": [],
            "recommendations": ["Rest"],
            "when_to_seek_care": "If symptoms worsen",
            "disclaimer": "Consult a professional.",
            "model_id": "openai/gpt-4o-mini",
            "model_provider": "openrouter",
        }

        request = self.factory.post(
            "/api/triage/assess/",
            {"current_symptoms": "fever", "model_id": "openai/gpt-4o-mini", "skip_clarification": True},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = assess_symptoms(request)

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("super-secret-openrouter-key", str(response.data))
