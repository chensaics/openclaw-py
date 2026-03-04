"""Profile usage tracking — cooldowns, failure counts, rotation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from pyclaw.agents.auth_profiles.types import (
    AuthProfileStore,
    FailureReason,
    ProfileUsageStats,
)

# Cooldown escalation: first failure = 30s, doubles up to 5 min
_BASE_COOLDOWN_MS = 30_000
_MAX_COOLDOWN_MS = 300_000
_PERMANENT_REASONS: set[str] = {"auth_permanent", "billing"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_stats(store: AuthProfileStore, profile_id: str) -> ProfileUsageStats:
    if profile_id not in store.usage_stats:
        store.usage_stats[profile_id] = ProfileUsageStats()
    return store.usage_stats[profile_id]


def is_profile_in_cooldown(store: AuthProfileStore, profile_id: str) -> bool:
    """Check if a profile is currently in cooldown."""
    stats = store.usage_stats.get(profile_id)
    if not stats or not stats.cooldown_until:
        return False
    try:
        cooldown_end = datetime.fromisoformat(stats.cooldown_until)
        return datetime.now(UTC) < cooldown_end
    except ValueError:
        return False


def mark_auth_profile_used(store: AuthProfileStore, profile_id: str) -> None:
    """Record successful usage of a profile."""
    stats = _ensure_stats(store, profile_id)
    stats.last_used = _now_iso()


def mark_auth_profile_failure(
    store: AuthProfileStore,
    profile_id: str,
    reason: FailureReason = "unknown",
) -> None:
    """Record a failure and increment error counts."""
    stats = _ensure_stats(store, profile_id)
    stats.error_count += 1
    stats.failure_counts[reason] = stats.failure_counts.get(reason, 0) + 1
    stats.last_failure_at = _now_iso()

    if reason in _PERMANENT_REASONS:
        stats.disabled_reason = reason
        stats.disabled_until = "permanent"


def mark_auth_profile_cooldown(
    store: AuthProfileStore,
    profile_id: str,
    *,
    duration_ms: int | None = None,
) -> None:
    """Put a profile into cooldown."""
    stats = _ensure_stats(store, profile_id)
    if duration_ms is None:
        duration_ms = calculate_auth_profile_cooldown_ms(stats)
    cooldown_end = datetime.now(UTC).timestamp() + duration_ms / 1000
    stats.cooldown_until = datetime.fromtimestamp(cooldown_end, tz=UTC).isoformat()


def calculate_auth_profile_cooldown_ms(stats: ProfileUsageStats) -> int:
    """Exponential backoff cooldown based on consecutive errors."""
    consecutive = stats.error_count
    ms = _BASE_COOLDOWN_MS * (2 ** min(consecutive, 10))
    return cast(int, min(ms, _MAX_COOLDOWN_MS))


def clear_auth_profile_cooldown(
    store: AuthProfileStore,
    profile_id: str,
) -> None:
    """Remove cooldown from a profile."""
    stats = store.usage_stats.get(profile_id)
    if stats:
        stats.cooldown_until = ""
        stats.error_count = 0


def clear_expired_cooldowns(store: AuthProfileStore) -> int:
    """Clear all expired cooldowns, return count cleared."""
    now = datetime.now(UTC)
    cleared = 0
    for _pid, stats in store.usage_stats.items():
        if stats.cooldown_until and stats.cooldown_until != "permanent":
            try:
                end = datetime.fromisoformat(stats.cooldown_until)
                if now >= end:
                    stats.cooldown_until = ""
                    stats.error_count = 0
                    cleared += 1
            except ValueError:
                stats.cooldown_until = ""
                cleared += 1
    return cleared


def get_soonest_cooldown_expiry(store: AuthProfileStore) -> str | None:
    """Return the earliest cooldown expiry ISO string, or None."""
    soonest: str | None = None
    for stats in store.usage_stats.values():
        if stats.cooldown_until and stats.cooldown_until != "permanent":
            if soonest is None or stats.cooldown_until < soonest:
                soonest = stats.cooldown_until
    return soonest


def resolve_profiles_unavailable_reason(
    store: AuthProfileStore,
    provider: str,
) -> str | None:
    """If all profiles for a provider are unavailable, return a reason."""
    from pyclaw.agents.auth_profiles.profiles import list_profiles_for_provider

    profiles = list_profiles_for_provider(store, provider)
    if not profiles:
        return "no_profiles"

    all_cooldown = all(is_profile_in_cooldown(store, pid) for pid, _ in profiles)
    if all_cooldown:
        return "all_in_cooldown"

    all_disabled = all(
        store.usage_stats.get(pid, ProfileUsageStats()).disabled_until == "permanent" for pid, _ in profiles
    )
    if all_disabled:
        return "all_disabled"

    return None
