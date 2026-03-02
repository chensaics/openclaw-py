"""Subagent manager — lifecycle management for child agent sessions."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Any

from pyclaw.agents.subagents.types import (
    SubagentConfig,
    SubagentMeta,
    SubagentResult,
    SubagentState,
)


class SubagentManager:
    """Manages spawning, tracking, and killing subagent sessions."""

    MAX_CONCURRENT = 4
    MAX_DEPTH = 5

    def __init__(self) -> None:
        self._active: dict[str, _SubagentEntry] = {}
        self._completed: list[dict[str, Any]] = []
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        self._on_event: Callable[..., Any] | None = None
        self._on_parent_notify: Callable[..., Any] | None = None

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def active_ids(self) -> list[str]:
        return list(self._active.keys())

    def set_event_handler(self, handler: Callable[..., Any]) -> None:
        self._on_event = handler

    def set_parent_notify_handler(self, handler: Callable[..., Any]) -> None:
        """Set the callback for notifying parent sessions on completion."""
        self._on_parent_notify = handler

    async def spawn(
        self,
        config: SubagentConfig,
        *,
        runner: Callable[..., AsyncGenerator[Any, None]] | None = None,
    ) -> SubagentResult:
        """Spawn a subagent and wait for completion."""
        if config.current_depth >= self.MAX_DEPTH:
            return SubagentResult(
                state=SubagentState.FAILED,
                error=f"Max subagent depth ({self.MAX_DEPTH}) exceeded",
            )

        session_id = config.session_id or str(uuid.uuid4())
        config.session_id = session_id

        entry = _SubagentEntry(
            session_id=session_id,
            config=config,
            state=SubagentState.PENDING,
        )
        self._active[session_id] = entry

        try:
            async with self._semaphore:
                entry.state = SubagentState.RUNNING
                self._emit("subagent.started", session_id=session_id, config=config)

                if runner:
                    result = await self._run_with_runner(entry, runner)
                else:
                    result = await self._run_default(entry)

                entry.state = result.state
                self._emit("subagent.completed", session_id=session_id, result=result)

                self._completed.append({
                    "session_id": session_id,
                    "state": result.state.value,
                    "label": config.label,
                    "output_preview": (result.output or "")[:200],
                })
                if len(self._completed) > 100:
                    self._completed = self._completed[-100:]

                if config.notify_parent and config.parent_session_id:
                    self._notify_parent(config, result)

                return result

        except asyncio.CancelledError:
            entry.state = SubagentState.ABORTED
            return SubagentResult(state=SubagentState.ABORTED, error="Cancelled")
        except Exception as e:
            entry.state = SubagentState.FAILED
            return SubagentResult(state=SubagentState.FAILED, error=str(e))
        finally:
            self._active.pop(session_id, None)

    def _notify_parent(self, config: SubagentConfig, result: SubagentResult) -> None:
        """Notify the parent session that a subagent has completed."""
        if self._on_parent_notify:
            try:
                self._on_parent_notify(
                    parent_session_id=config.parent_session_id,
                    child_session_id=config.session_id,
                    label=config.label,
                    state=result.state.value,
                    output=result.output,
                )
            except Exception:
                pass
        self._emit(
            "subagent.parent_notified",
            parent_session_id=config.parent_session_id,
            child_session_id=config.session_id,
        )

    async def kill(self, session_id: str) -> bool:
        """Abort a running subagent."""
        entry = self._active.get(session_id)
        if not entry:
            return False

        if entry.cancel_event:
            entry.cancel_event.set()
        entry.state = SubagentState.ABORTED
        self._emit("subagent.killed", session_id=session_id)
        return True

    async def steer(self, session_id: str, instruction: str) -> bool:
        """Send a steering instruction to a running subagent."""
        entry = self._active.get(session_id)
        if not entry or entry.state != SubagentState.RUNNING:
            return False

        entry.steering_instructions.append(instruction)
        self._emit("subagent.steered", session_id=session_id, instruction=instruction)
        return True

    def list_active(self) -> list[dict[str, Any]]:
        """Return info about all active subagents."""
        return [
            {
                "session_id": e.session_id,
                "agent_id": e.config.agent_id,
                "state": e.state.value,
                "depth": e.config.current_depth,
                "label": e.config.label,
                "prompt_preview": e.config.prompt[:100],
            }
            for e in self._active.values()
        ]

    def list_running(self) -> list[dict[str, Any]]:
        """Return info about currently running subagents only."""
        return [
            info for info in self.list_active()
            if info["state"] == SubagentState.RUNNING.value
        ]

    def list_completed(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """Return recently completed subagent info."""
        return list(reversed(self._completed[-limit:]))

    async def _run_default(self, entry: _SubagentEntry) -> SubagentResult:
        """Default subagent runner using the standard agent loop."""
        from pyclaw.agents.runner import run_agent
        from pyclaw.agents.session import SessionManager
        from pyclaw.agents.types import ModelConfig

        config = entry.config
        entry.cancel_event = asyncio.Event()

        model_config = ModelConfig(
            provider=config.provider or "openai",
            model_id=config.model or "gpt-4o",
        )

        session = SessionManager.in_memory()

        output_parts: list[str] = []
        async for event in run_agent(
            prompt=config.prompt,
            session=session,
            model=model_config,
            tools=[],
            system_prompt=f"You are a subagent (depth={config.current_depth}). Complete the task concisely.",
            abort_event=entry.cancel_event,
        ):
            if entry.cancel_event.is_set():
                return SubagentResult(state=SubagentState.ABORTED, error="Killed by parent")

            if event.type == "message_update" and event.delta:
                output_parts.append(event.delta)
            elif event.type == "error":
                return SubagentResult(
                    state=SubagentState.FAILED,
                    error=event.error or "Unknown error",
                )

        return SubagentResult(
            state=SubagentState.COMPLETED,
            output="".join(output_parts),
            meta=SubagentMeta(
                session_id=entry.session_id,
                agent_id=config.agent_id,
                depth=config.current_depth,
            ),
        )

    async def _run_with_runner(
        self, entry: _SubagentEntry, runner: Callable[..., AsyncGenerator[Any, None]]
    ) -> SubagentResult:
        """Run subagent with a custom runner function."""
        entry.cancel_event = asyncio.Event()
        output_parts: list[str] = []

        async for event in runner(entry.config):
            if entry.cancel_event and entry.cancel_event.is_set():
                return SubagentResult(state=SubagentState.ABORTED, error="Killed")
            if hasattr(event, "delta") and event.delta:
                output_parts.append(event.delta)

        return SubagentResult(
            state=SubagentState.COMPLETED,
            output="".join(output_parts),
            meta=SubagentMeta(
                session_id=entry.session_id,
                agent_id=entry.config.agent_id,
                depth=entry.config.current_depth,
            ),
        )

    def _emit(self, event: str, **kwargs: Any) -> None:
        if self._on_event:
            try:
                self._on_event(event, **kwargs)
            except Exception:
                pass


class _SubagentEntry:
    __slots__ = ("session_id", "config", "state", "cancel_event", "steering_instructions")

    def __init__(self, session_id: str, config: SubagentConfig, state: SubagentState) -> None:
        self.session_id = session_id
        self.config = config
        self.state = state
        self.cancel_event: asyncio.Event | None = None
        self.steering_instructions: list[str] = []
