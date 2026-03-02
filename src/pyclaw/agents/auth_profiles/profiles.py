"""Profile CRUD — list, upsert, order, mark good."""

from __future__ import annotations

from pathlib import Path

from pyclaw.agents.auth_profiles.store import (
    update_auth_profile_store_with_lock,
)
from pyclaw.agents.auth_profiles.types import (
    ApiKeyCredential,
    AuthProfileCredential,
    AuthProfileStore,
)


def list_profiles_for_provider(
    store: AuthProfileStore,
    provider: str,
) -> list[tuple[str, AuthProfileCredential]]:
    """Return ``(profile_id, credential)`` pairs for the given provider."""
    ordered_ids = store.order.get(provider, [])
    seen: set[str] = set()
    result: list[tuple[str, AuthProfileCredential]] = []

    # Ordered profiles first
    for pid in ordered_ids:
        if pid in store.profiles and pid not in seen:
            cred = store.profiles[pid]
            if cred.provider == provider:
                result.append((pid, cred))
                seen.add(pid)

    # Remaining unordered profiles
    for pid, cred in store.profiles.items():
        if cred.provider == provider and pid not in seen:
            result.append((pid, cred))
            seen.add(pid)

    return result


def upsert_auth_profile(
    store: AuthProfileStore,
    profile_id: str,
    credential: AuthProfileCredential,
) -> None:
    """Insert or update a profile in the store (in-memory only)."""
    store.profiles[profile_id] = credential


def upsert_auth_profile_with_lock(
    profile_id: str,
    credential: AuthProfileCredential,
    *,
    agent_dir: Path | None = None,
) -> AuthProfileStore:
    """Upsert a profile and persist under lock."""

    def _updater(store: AuthProfileStore) -> AuthProfileStore:
        upsert_auth_profile(store, profile_id, credential)
        return store

    return update_auth_profile_store_with_lock(_updater, agent_dir=agent_dir)


def set_auth_profile_order(
    *,
    agent_dir: Path | None = None,
    provider: str,
    order: list[str],
) -> AuthProfileStore:
    """Persist a new profile evaluation order for a provider."""

    def _updater(store: AuthProfileStore) -> AuthProfileStore:
        store.order[provider] = _dedupe_ids(order)
        return store

    return update_auth_profile_store_with_lock(_updater, agent_dir=agent_dir)


def mark_auth_profile_good(
    *,
    store: AuthProfileStore,
    provider: str,
    profile_id: str,
    agent_dir: Path | None = None,
) -> None:
    """Record that a profile was used successfully."""
    store.last_good[provider] = profile_id


def resolve_auth_profile_display_label(
    profile_id: str,
    cred: AuthProfileCredential,
) -> str:
    """Human-readable label for a profile."""
    if cred.label:
        return cred.label
    if cred.email:
        return cred.email
    if isinstance(cred, ApiKeyCredential) and cred.key:
        masked = cred.key[:4] + "..." + cred.key[-4:] if len(cred.key) > 12 else "***"
        return f"API Key ({masked})"
    return profile_id


def _dedupe_ids(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for pid in ids:
        if pid not in seen:
            result.append(pid)
            seen.add(pid)
    return result
