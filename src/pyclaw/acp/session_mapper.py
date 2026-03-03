"""ACP session mapper — resolve session keys and labels via gateway.

Ported from ``src/acp/session-mapper.ts``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass
class AcpSessionMetaHints:
    """Hints extracted from ACP request _meta for session resolution."""

    session_key: str | None = None
    session_label: str | None = None
    reset_session: bool = False
    require_existing: bool = False
    prefix_cwd: bool = False
    cwd: str | None = None


def parse_session_meta(meta: dict[str, Any] | None) -> AcpSessionMetaHints:
    """Parse _meta from ACP request into session hints."""
    if not meta or not isinstance(meta, dict):
        return AcpSessionMetaHints()

    def _str(keys: list[str]) -> str | None:
        for k in keys:
            v = meta.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    def _bool(keys: list[str]) -> bool:
        for k in keys:
            v = meta.get(k)
            if isinstance(v, bool):
                return v
        return False

    return AcpSessionMetaHints(
        session_key=_str(["sessionKey", "session", "key"]),
        session_label=_str(["sessionLabel", "label"]),
        reset_session=_bool(["resetSession", "reset"]),
        require_existing=_bool(["requireExistingSession", "requireExisting"]),
        prefix_cwd=_bool(["prefixCwd"]),
        cwd=_str(["cwd", "workingDirectory"]),
    )


async def resolve_session_key(
    *,
    meta: AcpSessionMetaHints,
    fallback_key: str,
    gateway_request: Any,
    default_session_key: str | None = None,
    default_session_label: str | None = None,
    require_existing_session: bool = False,
) -> str:
    """Resolve the session key from meta hints, gateway labels, or defaults.

    ``gateway_request`` should be an async callable: ``async (method, params) -> dict``.
    """
    requested_label = meta.session_label or default_session_label
    requested_key = meta.session_key or default_session_key
    require = meta.require_existing or require_existing_session

    if meta.session_label:
        resolved = await gateway_request("sessions.resolve", {"label": meta.session_label})
        key = resolved.get("key") if isinstance(resolved, dict) else None
        if not key:
            raise ValueError(f"Unable to resolve session label: {meta.session_label}")
        return cast(str, key)

    if meta.session_key:
        if not require:
            return meta.session_key
        resolved = await gateway_request("sessions.resolve", {"key": meta.session_key})
        key = resolved.get("key") if isinstance(resolved, dict) else None
        if not key:
            raise ValueError(f"Session key not found: {meta.session_key}")
        return cast(str, key)

    if requested_label:
        resolved = await gateway_request("sessions.resolve", {"label": requested_label})
        key = resolved.get("key") if isinstance(resolved, dict) else None
        if not key:
            raise ValueError(f"Unable to resolve session label: {requested_label}")
        return cast(str, key)

    if requested_key:
        if not require:
            return requested_key
        resolved = await gateway_request("sessions.resolve", {"key": requested_key})
        key = resolved.get("key") if isinstance(resolved, dict) else None
        if not key:
            raise ValueError(f"Session key not found: {requested_key}")
        return cast(str, key)

    return fallback_key


async def reset_session_if_needed(
    *,
    meta: AcpSessionMetaHints,
    session_key: str,
    gateway_request: Any,
    reset_session_default: bool = False,
) -> None:
    """Reset the session via gateway if requested."""
    should_reset = meta.reset_session or reset_session_default
    if not should_reset:
        return
    await gateway_request("sessions.reset", {"key": session_key})


class SessionLabelMap:
    """Persist ACP session-id/key/label mapping in state directory."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def resolve_label(self, label: str) -> str | None:
        data = self._load()
        labels = data.get("labels", {})
        value = labels.get(label)
        return value if isinstance(value, str) and value else None

    def resolve_session(self, session_id: str) -> str | None:
        data = self._load()
        sessions = data.get("sessions", {})
        value = sessions.get(session_id)
        return value if isinstance(value, str) and value else None

    def bind(self, *, session_id: str, session_key: str, session_label: str | None = None) -> None:
        data = self._load()
        sessions = data.setdefault("sessions", {})
        labels = data.setdefault("labels", {})
        sessions[session_id] = session_key
        if session_label:
            labels[session_label] = session_key
        self._save(data)

    def is_known_key(self, key: str) -> bool:
        data = self._load()
        sessions = data.get("sessions", {})
        labels = data.get("labels", {})
        return key in sessions.values() or key in labels.values()

    def reset_session(self, session_id: str) -> None:
        data = self._load()
        sessions = data.get("sessions", {})
        if session_id in sessions:
            del sessions[session_id]
            self._save(data)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"sessions": {}, "labels": {}}
        try:
            result: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
            return result
        except Exception:
            return {"sessions": {}, "labels": {}}

    def _save(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
