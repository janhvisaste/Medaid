"""Shared contract for V2 triage LLM providers."""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, List


_request_context: ContextVar[dict] = ContextVar("medaid_llm_request_context", default={})


@contextmanager
def provider_request_context(**context):
    """Make request metadata available to provider logs without logging PHI."""
    token = _request_context.set({key: value for key, value in context.items() if value is not None})
    try:
        yield
    finally:
        _request_context.reset(token)


def provider_log_context() -> dict:
    return dict(_request_context.get())


class ModelProviderError(Exception):
    """Raised when a selected provider cannot complete the request."""

    def __init__(self, message: str, *, status_code: int | None = None, user_message: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.user_message = user_message or "Selected AI model is temporarily unavailable. Please try another model."


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: List[Dict[str, str]], model_id: str, temperature: float) -> str:
        """Return raw provider text for a non-streaming chat completion."""
