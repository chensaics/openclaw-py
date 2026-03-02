"""WebSocket protocol frame definitions.

Compatible with the TypeScript gateway protocol v3:
  req  → { type: "req",   id, method, params? }
  res  → { type: "res",   id, ok, payload?, error? }
  event→ { type: "event", event, payload?, seq?, stateVersion? }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION = 3


@dataclass
class ErrorShape:
    code: str
    message: str
    details: Any | None = None
    retryable: bool | None = None
    retry_after_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            d["details"] = self.details
        if self.retryable is not None:
            d["retryable"] = self.retryable
        if self.retry_after_ms is not None:
            d["retryAfterMs"] = self.retry_after_ms
        return d


@dataclass
class RequestFrame:
    id: str
    method: str
    params: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RequestFrame | None:
        if data.get("type") != "req":
            return None
        frame_id = data.get("id")
        method = data.get("method")
        if not frame_id or not method:
            return None
        return cls(id=frame_id, method=method, params=data.get("params"))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": "req", "id": self.id, "method": self.method}
        if self.params is not None:
            d["params"] = self.params
        return d


@dataclass
class ResponseFrame:
    id: str
    ok: bool
    payload: Any | None = None
    error: ErrorShape | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": "res", "id": self.id, "ok": self.ok}
        if self.payload is not None:
            d["payload"] = self.payload
        if self.error is not None:
            d["error"] = self.error.to_dict()
        return d

    @classmethod
    def ok_response(cls, frame_id: str, payload: Any = None) -> ResponseFrame:
        return cls(id=frame_id, ok=True, payload=payload)

    @classmethod
    def error_response(
        cls, frame_id: str, code: str, message: str, **kwargs: Any
    ) -> ResponseFrame:
        return cls(
            id=frame_id,
            ok=False,
            error=ErrorShape(code=code, message=message, **kwargs),
        )


@dataclass
class EventFrame:
    event: str
    payload: Any | None = None
    seq: int | None = None
    state_version: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": "event", "event": self.event}
        if self.payload is not None:
            d["payload"] = self.payload
        if self.seq is not None:
            d["seq"] = self.seq
        if self.state_version is not None:
            d["stateVersion"] = self.state_version
        return d
