"""Per-process quota guards for the LLM call sites (triage, chat, report insight).

Mirrors the reserve-then-check counter pattern already used for dietary advice
(see get_dietary_recommendations_view): increment a windowed cache counter, then
compare it to the ceiling, releasing the increment if it put us over. Doing the
increment first closes the race where several concurrent requests each read an
under-limit value and all admit themselves past the cap.

Two ceilings per endpoint:
  * a GLOBAL ceiling protecting the shared, app-wide free-tier quota, and
  * a PER-USER ceiling so a single user or session cannot exhaust the shared
    quota for everyone else.

The per-user ceiling is checked FIRST: a single abuser then trips their own
ceiling and is rejected before consuming any of the shared global quota.

IMPORTANT - per-process limitation (NOT fixed here):
    These counters live in Django's cache. With no REDIS_URL configured the
    cache is LocMemCache, which is PER PROCESS - so with N gunicorn/uwsgi
    workers every ceiling below is effectively enforced N times over, exactly
    as settings.py already warns for the dietary quotas. Set REDIS_URL to
    enforce these across workers. This module does not attempt to change that.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Windowed-counter timeouts. The minute counter only needs to outlive its
# minute; the day counter is given a little over a day so it never expires
# mid-day. Matches the dietary guard's own timeouts.
_MINUTE_TIMEOUT = 90
_DAY_TIMEOUT = 60 * 60 * 26

# endpoint name -> settings constant prefix. Every endpoint reads
# {PREFIX}_GLOBAL_RPM_LIMIT / _GLOBAL_DAILY_LIMIT / _USER_RPM_LIMIT /
# _USER_DAILY_LIMIT from settings, so the limits are configurable per endpoint.
_ENDPOINT_PREFIX = {
    "triage": "TRIAGE",
    "chat": "CHAT",
    "report_insight": "REPORT_INSIGHT",
}


class LLMQuotaExceeded(Exception):
    """Raised by check_llm_quota when a ceiling is hit.

    Carries enough for the caller to build a distinct, honest 429 response:
    which ceiling (`scope`), which window (`period`), and how long to wait
    (`retry_after`, seconds).
    """

    def __init__(self, scope: str, period: str, retry_after: int):
        self.scope = scope        # 'user' | 'global'
        self.period = period      # 'minute' | 'day'
        self.retry_after = max(1, int(retry_after))
        super().__init__(f"{scope} {period} LLM quota exceeded")


def _cache_reserve(key, timeout):
    """Atomically increment a counter, creating it at 1 if absent.

    Returns the post-increment value. Callers compare that value against the
    limit (reserve-then-check) rather than reading the counter and then
    incrementing, which would let concurrent requests all observe an
    under-limit value before any of them increments.
    """
    try:
        return cache.incr(key)
    except ValueError:
        # Key is absent or expired. cache.add is atomic, so exactly one racing
        # caller wins and seeds the counter; the rest fall through to incr.
        if cache.add(key, 1, timeout=timeout):
            return 1
        try:
            return cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=timeout)
            return 1


def _cache_release(key, timeout):
    """Give back a reservation taken by _cache_reserve, never going negative."""
    try:
        if cache.decr(key) < 0:
            cache.set(key, 0, timeout=timeout)
    except ValueError:
        cache.set(key, 0, timeout=timeout)


def _minute_bucket() -> str:
    return timezone.now().strftime("%Y%m%d%H%M")


def _day_bucket() -> str:
    return timezone.now().strftime("%Y%m%d")


def _seconds_to_utc_midnight() -> int:
    now = timezone.now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


def _limits_for(endpoint: str) -> dict:
    prefix = _ENDPOINT_PREFIX.get(endpoint)
    if not prefix:
        raise ValueError(f"Unknown LLM quota endpoint: {endpoint!r}")
    return {
        "global_rpm": max(1, getattr(settings, f"{prefix}_GLOBAL_RPM_LIMIT", 18)),
        "global_daily": max(1, getattr(settings, f"{prefix}_GLOBAL_DAILY_LIMIT", 45)),
        "user_rpm": max(1, getattr(settings, f"{prefix}_USER_RPM_LIMIT", 5)),
        "user_daily": max(1, getattr(settings, f"{prefix}_USER_DAILY_LIMIT", 15)),
    }


def check_llm_quota(endpoint: str, user_id) -> None:
    """Reserve one request against the endpoint's ceilings, or raise.

    Per-user ceilings are checked before global ones so a single heavy user
    trips their own limit without first draining the shared quota. On any
    breach, every reservation taken in this call - including the breaching one -
    is released, so a rejected request consumes no quota, and LLMQuotaExceeded
    is raised for the caller to translate into a distinct 429.

    MUST be called only AFTER emergency screening for patient-facing paths:
    this gates the LLM call, never the safety check.
    """
    limits = _limits_for(endpoint)
    reserved: list[tuple[str, int]] = []

    def reserve(key, timeout, limit, scope, period, retry_after):
        if _cache_reserve(key, timeout) > limit:
            _cache_release(key, timeout)                 # release the breacher
            for k, t in reserved:                        # roll back earlier holds
                _cache_release(k, t)
            logger.warning(
                "llm_quota.exceeded",
                extra={"endpoint": endpoint, "scope": scope, "period": period},
            )
            raise LLMQuotaExceeded(scope, period, retry_after)
        reserved.append((key, timeout))

    minute, day = _minute_bucket(), _day_bucket()
    daily_retry = _seconds_to_utc_midnight()

    if user_id is not None:
        reserve(f"llmq:{endpoint}:user:{user_id}:rpm:{minute}", _MINUTE_TIMEOUT,
                limits["user_rpm"], "user", "minute", 60)
        reserve(f"llmq:{endpoint}:user:{user_id}:day:{day}", _DAY_TIMEOUT,
                limits["user_daily"], "user", "day", daily_retry)

    reserve(f"llmq:{endpoint}:global:rpm:{minute}", _MINUTE_TIMEOUT,
            limits["global_rpm"], "global", "minute", 60)
    reserve(f"llmq:{endpoint}:global:day:{day}", _DAY_TIMEOUT,
            limits["global_daily"], "global", "day", daily_retry)


def note_global_usage(endpoint: str) -> None:
    """Count one call against ONLY the endpoint's global counters, never raising.

    For piggyback LLM calls that must consume shared quota so they are not a
    quota-free loophole, but should not carry their own gate - specifically
    chat title generation (see chat_send_message). It increments the same
    global minute/day counters check_llm_quota reads, so title usage pushes the
    shared ceiling closer and can cause the NEXT gated call to be rejected, but
    a title call itself is never blocked.
    """
    if endpoint not in _ENDPOINT_PREFIX:
        raise ValueError(f"Unknown LLM quota endpoint: {endpoint!r}")
    _cache_reserve(f"llmq:{endpoint}:global:rpm:{_minute_bucket()}", _MINUTE_TIMEOUT)
    _cache_reserve(f"llmq:{endpoint}:global:day:{_day_bucket()}", _DAY_TIMEOUT)
