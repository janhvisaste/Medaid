"""Synchronous Gemini client configured to match the reference."""

import os
from typing import Optional

from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

load_dotenv()

REFERENCE_MODEL = "gemini-1.5-flash"
REFERENCE_TEMPERATURE = 0.0


class LLMClient:
    """Small adapter for the reference single LangChain call."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else os.getenv("GOOGLE_API_KEY")
        self.client = None
        if self.api_key and genai is not None:
            self.client = genai.Client(api_key=self.api_key)

    def is_available(self) -> bool:
        return self.client is not None

    def call(
        self,
        prompt: str,
        system: str = "Return ONLY a single JSON object with no additional text or formatting.",
    ) -> str:
        """Make one synchronous, non-streaming model call.

        Source behavior: backend_processing.py::LLMClient.call_chat uses one
        LangChain invocation with temperature 0.0 and no application retry.
        """
        if not self.client:
            raise RuntimeError(
                "Gemini backend not initialized (check GOOGLE_API_KEY and google-genai)."
            )

        contents = f"{system}\n\n{prompt}" if system else prompt
        config = types.GenerateContentConfig(
            temperature=REFERENCE_TEMPERATURE,
            max_output_tokens=800,
        )
        response = self.client.models.generate_content(
            model=REFERENCE_MODEL,
            contents=contents,
            config=config,
        )

        text = getattr(response, "text", None)
        if text:
            return text
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    return part_text
        raise RuntimeError("No text content found in Gemini response")
