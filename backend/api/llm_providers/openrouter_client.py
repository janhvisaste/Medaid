"""OpenRouter implementation of the V2 triage provider contract."""

import logging
import time
from typing import Dict, List

import requests
from django.conf import settings

from .base import LLMProvider, ModelProviderError, provider_log_context


logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, session: requests.Session | None = None):
        self.api_key = api_key if api_key is not None else getattr(settings, "OPENROUTER_API_KEY", "")
        self.base_url = getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
        self.session = session or requests.Session()

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def complete(self, messages: List[Dict[str, str]], model_id: str, temperature: float) -> str:
        if not self.is_available:
            logger.warning("openrouter.provider_unconfigured", extra=provider_log_context())
            raise ModelProviderError(
                "OPENROUTER_API_KEY is not configured",
                user_message="Selected AI model provider is not configured. Please use the default model.",
            )

        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": getattr(settings, "OPENROUTER_HTTP_REFERER", "http://localhost:3000"),
            "X-OpenRouter-Title": getattr(settings, "OPENROUTER_APP_TITLE", "MedAid"),
            "X-Title": getattr(settings, "OPENROUTER_APP_TITLE", "MedAid"),
        }

        last_error = None
        for attempt in range(2):
            try:
                response = self.session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=30,
                )
            except requests.Timeout as error:
                last_error = error
                logger.warning("openrouter.request_timeout", extra={**provider_log_context(), "model_id": model_id, "attempt": attempt + 1})
                if attempt == 0:
                    time.sleep(0.25)
                    continue
                raise ModelProviderError("OpenRouter request timed out", user_message="This model is taking too long to respond. Please try another model.") from error
            except requests.RequestException as error:
                logger.warning("openrouter.request_failed", extra={**provider_log_context(), "model_id": model_id, "error_type": type(error).__name__})
                raise ModelProviderError("OpenRouter request failed", user_message="This model is temporarily unavailable. Please try another model.") from error

            if 500 <= response.status_code < 600:
                last_error = response
                logger.warning("openrouter.upstream_server_error", extra={**provider_log_context(), "model_id": model_id, "status_code": response.status_code, "attempt": attempt + 1})
                if attempt == 0:
                    time.sleep(0.25)
                    continue
                raise ModelProviderError(
                    f"OpenRouter server error: {response.status_code}",
                    status_code=response.status_code,
                    user_message="This model is temporarily unavailable. Please try another model.",
                )

            if response.status_code in (402, 403):
                logger.warning("openrouter.authorization_failed", extra={**provider_log_context(), "model_id": model_id, "status_code": response.status_code})
                raise ModelProviderError(
                    f"OpenRouter account or authorization error: {response.status_code}",
                    status_code=response.status_code,
                    user_message="Selected AI model is unavailable. Please use the default model or try another model.",
                )

            if 400 <= response.status_code < 500:
                logger.warning("openrouter.model_request_rejected", extra={**provider_log_context(), "model_id": model_id, "status_code": response.status_code})
                raise ModelProviderError(
                    f"OpenRouter client error: {response.status_code}",
                    status_code=response.status_code,
                    user_message="Selected AI model could not be used. Please try another model.",
                )

            try:
                data = response.json()
            except ValueError as error:
                logger.warning("openrouter.invalid_json_response", extra={**provider_log_context(), "model_id": model_id})
                raise ModelProviderError("OpenRouter response was not valid JSON") from error
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as error:
                logger.warning("openrouter.response_missing_content", extra={**provider_log_context(), "model_id": model_id})
                raise ModelProviderError("OpenRouter response did not include message content") from error

        raise ModelProviderError(f"OpenRouter request failed: {last_error}")
