"""OpenRouter model catalog helpers for V2 triage."""

import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

MODEL_CACHE_KEY = "openrouter:model-catalog:v2"
FALLBACK_MODEL_CACHE_KEY = "openrouter:fallback-model:v1"
FALLBACK_MODEL_CACHE_SECONDS = 60 * 60  # 1 hour


def get_allowed_openrouter_models() -> list[str]:
    return list(getattr(settings, "ALLOWED_OPENROUTER_MODELS", []))


def is_allowed_openrouter_model(model_id: str | None) -> bool:
    if not model_id:
        return False
    if model_id in set(get_allowed_openrouter_models()):
        return True
    return any(model["id"] == model_id for model in get_free_openrouter_models())


def trim_first_sentence(description: str | None) -> str:
    if not description:
        return ""
    first_sentence = description.split(". ")[0].strip()
    return f"{first_sentence}." if first_sentence and not first_sentence.endswith(".") else first_sentence


def _fallback_model_rows() -> list[dict]:
    fallback = getattr(settings, "OPENROUTER_MODEL_FALLBACK_CATALOG", {})
    rows = []
    for model_id in get_allowed_openrouter_models():
        metadata = fallback.get(model_id, {})
        rows.append({
            "id": model_id,
            "name": metadata.get("name", model_id),
            "context_length": metadata.get("context_length"),
            "pricing": metadata.get("pricing", {"prompt": None, "completion": None}),
            "description": trim_first_sentence(metadata.get("description", "")),
            "is_free": _is_free_pricing(metadata.get("pricing", {}), model_id),
        })
    return rows


def _price_as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_free_pricing(pricing: dict | None, model_id: str = "") -> bool:
    pricing = pricing or {}
    # OpenRouter's live catalog is the source of truth for free models. Accept
    # its string or numeric zero representation, but do not infer free access
    # from a model suffix when pricing is missing.
    prompt = _price_as_float(pricing.get("prompt"))
    completion = _price_as_float(pricing.get("completion"))
    return prompt == 0 and completion == 0


def _model_to_row(model: dict) -> dict:
    pricing = model.get("pricing") or {}
    model_id = model.get("id")
    return {
        "id": model_id,
        "name": model.get("name") or model_id,
        "context_length": model.get("context_length"),
        "pricing": {
            "prompt": pricing.get("prompt"),
            "completion": pricing.get("completion"),
        },
        "description": trim_first_sentence(model.get("description", "")),
        "is_free": _is_free_pricing(pricing, model_id or ""),
    }


def _extract_model_list(payload: dict) -> list[dict]:
    data = payload.get("data", [])
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"]
    return []


def get_openrouter_model_catalog() -> list[dict]:
    cached = cache.get(MODEL_CACHE_KEY)
    if cached is not None:
        return cached

    rows_by_id = {row["id"]: row for row in _fallback_model_rows()}
    try:
        response = requests.get(
            f"{getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/')}/models",
            timeout=15,
        )
        response.raise_for_status()
        for model in _extract_model_list(response.json()):
            model_id = model.get("id")
            if model_id:
                rows_by_id[model_id] = _model_to_row(model)
    except requests.RequestException as error:
        logger.warning(
            "openrouter.catalog_fetch_failed",
            extra={"error_type": type(error).__name__},
        )

    catalog = sorted(rows_by_id.values(), key=lambda row: (not row.get("is_free"), row.get("name") or row["id"]))
    cache.set(MODEL_CACHE_KEY, catalog, getattr(settings, "OPENROUTER_MODEL_CACHE_SECONDS", 60 * 60 * 4))
    return catalog


def get_free_openrouter_models() -> list[dict]:
    return [model for model in get_openrouter_model_catalog() if model.get("is_free")]


def _score_fallback_candidate(model: dict) -> tuple:
    """Rank free models for use as the cross-provider failover target.

    Prefers an explicitly allow-listed model, then the largest context window
    (triage prompts now carry prior-assessment history), then id for a stable
    tie-break so the choice does not flap between calls.
    """
    allowed = set(get_allowed_openrouter_models())
    model_id = model.get("id") or ""
    context_length = model.get("context_length") or 0
    try:
        context_length = int(context_length)
    except (TypeError, ValueError):
        context_length = 0
    return (0 if model_id in allowed else 1, -context_length, model_id)


def resolve_fallback_openrouter_model() -> str:
    """Return the OpenRouter model id to fail over to. NEVER makes an HTTP call.

    This runs on the live triage path, so it is strictly a cache-or-default
    read. A cold cache resolves immediately to the configured last-known-good
    default rather than blocking a patient's assessment on OpenRouter's
    /models endpoint. The cache is warmed out-of-band by
    refresh_fallback_openrouter_model() (see api.tasks).
    """
    configured_default = getattr(settings, "TRIAGE_FALLBACK_OPENROUTER_MODEL", "")

    # An explicitly empty setting is an opt-out from OpenRouter failover
    # entirely. Honour it without any lookup, so disabling failover cannot be
    # undone by whatever the live catalog happens to return.
    if not configured_default:
        return ""

    cached = cache.get(FALLBACK_MODEL_CACHE_KEY)
    if cached is not None:
        return cached

    # Cold cache (fresh deploy, cache flush, or a stalled refresh worker).
    # Fall through immediately - correctness here is "don't block triage".
    logger.info(
        "openrouter.fallback_model_cache_cold",
        extra={"model_id": configured_default},
    )
    return configured_default


def refresh_fallback_openrouter_model() -> str:
    """Query OpenRouter's live catalog and warm the fallback-model cache.

    BACKGROUND USE ONLY - this makes a blocking HTTP request and must never be
    called from a request/response path. Returns the resolved model id.
    """
    configured_default = getattr(settings, "TRIAGE_FALLBACK_OPENROUTER_MODEL", "")
    if not configured_default:
        # Failover is disabled; nothing to warm.
        return ""

    resolved = configured_default
    try:
        free_models = get_free_openrouter_models()
    except Exception as error:  # catalog helper already swallows RequestException
        logger.warning(
            "openrouter.fallback_model_lookup_failed",
            extra={"error_type": type(error).__name__},
        )
        free_models = []

    if free_models:
        best = sorted(free_models, key=_score_fallback_candidate)[0]
        resolved = best.get("id") or configured_default
        logger.info(
            "openrouter.fallback_model_resolved",
            extra={"model_id": resolved, "free_model_count": len(free_models)},
        )
    else:
        logger.warning(
            "openrouter.fallback_model_using_configured_default",
            extra={"model_id": configured_default},
        )

    cache.set(FALLBACK_MODEL_CACHE_KEY, resolved, FALLBACK_MODEL_CACHE_SECONDS)
    return resolved


def get_available_model_catalog() -> list[dict]:
    allowed = set(get_allowed_openrouter_models())
    catalog = get_openrouter_model_catalog()
    available = [
        model for model in catalog
        if model.get("is_free") or model["id"] in allowed
    ]
    return sorted(available, key=lambda row: (not row.get("is_free"), row.get("name") or row["id"]))
