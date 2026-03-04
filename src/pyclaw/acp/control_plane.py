"""ACP control plane — session manager, runtime cache, and spawn logic.

Ported from ``src/acp/control-plane/``.
Manages ACP session lifecycle across multiple runtimes.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AcpSessionMode(str, Enum):
    PERSISTENT = "persistent"
    ONESHOT = "oneshot"


@dataclass
class AcpSessionResolution:
    """Result of resolving/creating an ACP session."""

    session_key: str
    backend: str
    runtime_session_name: str
    cwd: str
    agent_id: str = ""
    acpx_record_id: str | None = None
    backend_session_id: str | None = None
    agent_session_id: str | None = None


@dataclass
class AcpSessionStatus:
    """Status of a single ACP session."""

    session_key: str
    backend: str
    mode: str = "persistent"
    is_active: bool = False
    last_activity: float = 0.0
    run_count: int = 0


@dataclass
class AcpRunTurnInput:
    """Input for running a single turn on an ACP session."""

    session_key: str
    prompt: str
    handle: AcpSessionResolution
    abort_event: asyncio.Event | None = None


@dataclass
class AcpRuntimeEvent:
    """Event yielded during an ACP runtime turn."""

    type: str  # "text", "tool_start", "tool_end", "done", "error"
    text: str = ""
    name: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class AcpRuntimeProtocol:
    """Protocol for ACP runtime backends (acpx, built-in, etc.)."""

    async def ensure_session(
        self,
        session_key: str,
        agent: str,
        cwd: str,
        mode: str = "persistent",
        sandbox_config: dict[str, Any] | None = None,
    ) -> AcpSessionResolution:
        raise NotImplementedError

    async def run_turn(self, input: AcpRunTurnInput) -> AsyncIterator[AcpRuntimeEvent]:
        raise NotImplementedError
        yield

    async def get_status(self, handle: AcpSessionResolution) -> AcpSessionStatus:
        raise NotImplementedError

    async def cancel(self, handle: AcpSessionResolution) -> None:
        raise NotImplementedError

    async def close(self, handle: AcpSessionResolution) -> None:
        raise NotImplementedError

    def is_healthy(self) -> bool:
        return False


@dataclass
class _RuntimeCacheEntry:
    backend: str
    runtime: AcpRuntimeProtocol
    last_used: float = 0.0


class AcpSessionManager:
    """Manages ACP sessions across multiple runtime backends.

    Singleton pattern — use ``get_acp_session_manager()`` to get the instance.
    """

    def __init__(self, *, default_sandbox_config: dict[str, Any] | None = None) -> None:
        self._runtimes: dict[str, AcpRuntimeProtocol] = {}
        self._sessions: dict[str, AcpSessionResolution] = {}
        self._session_status: dict[str, AcpSessionStatus] = {}
        self._default_backend: str = "builtin"
        self._default_sandbox_config: dict[str, Any] | None = default_sandbox_config

    def register_runtime(self, backend_id: str, runtime: AcpRuntimeProtocol) -> None:
        self._runtimes[backend_id] = runtime
        logger.info("Registered ACP runtime: %s", backend_id)

    def get_runtime(self, backend_id: str) -> AcpRuntimeProtocol | None:
        return self._runtimes.get(backend_id)

    async def initialize_session(
        self,
        session_key: str,
        agent: str,
        cwd: str,
        *,
        backend: str | None = None,
        mode: str = "persistent",
        sandbox: dict[str, Any] | None = None,
    ) -> AcpSessionResolution:
        """Initialize or resume a session on the specified backend."""
        backend_id = backend or self._default_backend
        runtime = self._runtimes.get(backend_id)
        if not runtime:
            raise ValueError(f"ACP runtime not found: {backend_id}")

        sandbox_config = sandbox if sandbox is not None else self._default_sandbox_config
        resolution = await runtime.ensure_session(session_key, agent, cwd, mode, sandbox_config=sandbox_config)
        self._sessions[session_key] = resolution
        self._session_status[session_key] = AcpSessionStatus(
            session_key=session_key,
            backend=backend_id,
            mode=mode,
            is_active=True,
            last_activity=time.time(),
        )
        return resolution

    async def run_turn(
        self, session_key: str, prompt: str, *, abort_event: asyncio.Event | None = None
    ) -> AsyncIterator[AcpRuntimeEvent]:
        """Run a single agent turn on an existing session."""
        resolution = self._sessions.get(session_key)
        if not resolution:
            raise ValueError(f"ACP session not found: {session_key}")

        runtime = self._runtimes.get(resolution.backend)
        if not runtime:
            raise ValueError(f"ACP runtime not found: {resolution.backend}")

        status = self._session_status.get(session_key)
        if status:
            status.last_activity = time.time()
            status.run_count += 1

        turn_input = AcpRunTurnInput(
            session_key=session_key,
            prompt=prompt,
            handle=resolution,
            abort_event=abort_event,
        )
        async for event in runtime.run_turn(turn_input):
            yield event

    async def close_session(self, session_key: str) -> None:
        resolution = self._sessions.pop(session_key, None)
        self._session_status.pop(session_key, None)
        if resolution:
            runtime = self._runtimes.get(resolution.backend)
            if runtime:
                await runtime.close(resolution)

    async def cancel_session(self, session_key: str) -> None:
        resolution = self._sessions.get(session_key)
        if resolution:
            runtime = self._runtimes.get(resolution.backend)
            if runtime:
                await runtime.cancel(resolution)

    def list_sessions(self) -> list[AcpSessionStatus]:
        return list(self._session_status.values())

    def get_session(self, session_key: str) -> AcpSessionResolution | None:
        return self._sessions.get(session_key)

    def observability_snapshot(self) -> dict[str, Any]:
        return {
            "runtimes": list(self._runtimes.keys()),
            "sessions": len(self._sessions),
            "default_backend": self._default_backend,
        }


_SINGLETON: AcpSessionManager | None = None


def get_acp_session_manager() -> AcpSessionManager:
    global _SINGLETON  # noqa: PLW0603
    if _SINGLETON is None:
        _SINGLETON = AcpSessionManager()
    return _SINGLETON
