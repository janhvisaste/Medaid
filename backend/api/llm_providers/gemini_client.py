"""Gemini implementation of the V2 triage provider contract."""

import logging
import os
from typing import Dict, List

from .base import LLMProvider, ModelProviderError


logger = logging.getLogger(__name__)

# Wall-clock timeout for a Gemini completion, consistent with the sibling
# OpenRouter LLM call (30s). Without it the google-genai SDK can hang a request
# worker indefinitely on a stalled upstream. The SDK takes the value in
# milliseconds via HttpOptions.
GEMINI_TIMEOUT_SECONDS = 30

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key and genai is not None else None

    @property
    def is_available(self) -> bool:
        return self.client is not None and types is not None

    def complete(self, messages: List[Dict[str, str]], model_id: str, temperature: float) -> str:
        if not self.is_available:
            logger.warning("gemini.provider_unconfigured")
            raise ModelProviderError(
                "Gemini client not initialized",
                user_message="Default AI model is not configured. Please try again later.",
            )

        prompt = "\n\n".join(message.get("content", "") for message in messages if message.get("content"))
        try:
            response = self.client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=4096,
                    http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_SECONDS * 1000),
                ),
            )
        except Exception as error:
            # A timeout (or any other request failure) is converted to a
            # ModelProviderError here, which the triage engine catches and
            # routes to its failover / degraded-response path - it never
            # propagates as an unhandled 500.
            logger.warning("gemini.request_failed", extra={"model_id": model_id, "error_type": type(error).__name__})
            raise ModelProviderError("Gemini request failed", user_message="The default AI model is temporarily unavailable. Please try another model.") from error

        if response and response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, "text") and part.text:
                            return part.text

        logger.warning("gemini.response_missing_content", extra={"model_id": model_id})
        raise ModelProviderError("No text content found in Gemini response")
