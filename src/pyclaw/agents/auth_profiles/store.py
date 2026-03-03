"""Auth profile store — load, save, lock-protected updates."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from pyclaw.agents.auth_profiles.types import AuthProfileStore
from pyclaw.config.paths import resolve_state_dir


def resolve_auth_store_path(agent_dir: Path | None = None) -> Path:
    """Return path to ``auth-profiles.json`` for the given agent dir."""
    if agent_dir:
        return agent_dir / "auth-profiles.json"
    return resolve_state_dir() / "auth-profiles.json"


def load_auth_profile_store(agent_dir: Path | None = None) -> AuthProfileStore:
    """Load the auth profile store from disk, falling back to empty store."""
    path = resolve_auth_store_path(agent_dir)
    if not path.is_file():
        # Try legacy auth.json
        legacy = path.parent / "auth.json"
        if legacy.is_file():
            return _load_and_migrate_legacy(legacy)
        return AuthProfileStore()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AuthProfileStore.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return AuthProfileStore()


def _load_and_migrate_legacy(legacy_path: Path) -> AuthProfileStore:
    """Migrate legacy auth.json format to AuthProfileStore."""
    try:
        data = json.loads(legacy_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return AuthProfileStore()

    store = AuthProfileStore()
    # Legacy format may have provider keys with api_key values
    if isinstance(data, dict):
        for provider, value in data.items():
            if isinstance(value, str) and value.strip():
                from pyclaw.agents.auth_profiles.types import ApiKeyCredential

                pid = f"{provider}-default"
                store.profiles[pid] = ApiKeyCredential(provider=provider, key=value.strip())
            elif isinstance(value, dict):
                # Already structured
                parsed = AuthProfileStore.from_dict(
                    {"profiles": {provider: value}}
                )
                cred = parsed.profiles.get(provider) or store.profiles.get(provider)
                if cred is not None:
                    store.profiles[provider] = cred
    return store


def save_auth_profile_store(
    store: AuthProfileStore,
    agent_dir: Path | None = None,
) -> None:
    """Persist the auth profile store atomically."""
    path = resolve_auth_store_path(agent_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(store.to_dict(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def ensure_auth_profile_store(agent_dir: Path | None = None) -> AuthProfileStore:
    """Load or create the auth profile store, persisting if newly created."""
    store = load_auth_profile_store(agent_dir)
    path = resolve_auth_store_path(agent_dir)
    if not path.is_file():
        save_auth_profile_store(store, agent_dir)
    return store


_LOCK_SUFFIX = ".lock"


@contextmanager
def _file_lock(path: Path) -> Generator[None, None, None]:
    lock = path.with_suffix(path.suffix + _LOCK_SUFFIX)
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        yield
    except FileExistsError:
        # Stale lock — remove and retry once
        try:
            lock.unlink(missing_ok=True)
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            yield
        except FileExistsError:
            yield  # fallback: proceed without lock
    finally:
        if fd is not None:
            os.close(fd)
        lock.unlink(missing_ok=True)


def update_auth_profile_store_with_lock(
    updater: Callable[[AuthProfileStore], AuthProfileStore | None],
    *,
    agent_dir: Path | None = None,
) -> AuthProfileStore:
    """Load, update, and save the store under an exclusive file lock."""
    path = resolve_auth_store_path(agent_dir)
    with _file_lock(path):
        store = load_auth_profile_store(agent_dir)
        result = updater(store)
        updated = result if result is not None else store
        save_auth_profile_store(updated, agent_dir)
        return updated
