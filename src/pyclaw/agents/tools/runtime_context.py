"""Runtime context — channel/session context injected into tool execution.

Provides a ``RuntimeContext`` that flows through the agent runner into
tool executions, giving tools access to the current channel, chat ID,
session key, and workspace directory without global state.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Any

_current_ctx: contextvars.ContextVar["RuntimeContext | None"] = contextvars.ContextVar(
    "runtime_context", default=None,
)


@dataclass
class RuntimeContext:
    """Execution context available to all tools during an agent run."""

    channel: str = ""
    chat_id: str = ""
    session_key: str = ""
    agent_id: str = "main"
    workspace_dir: str = ""
    parent_session_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_channel_bound(self) -> bool:
        return bool(self.channel and self.chat_id)


def set_runtime_context(ctx: RuntimeContext) -> contextvars.Token[RuntimeContext | None]:
    """Set the runtime context for the current async task."""
    return _current_ctx.set(ctx)


def get_runtime_context() -> RuntimeContext | None:
    """Retrieve the runtime context for the current async task."""
    return _current_ctx.get()


def get_runtime_context_or_default() -> RuntimeContext:
    """Retrieve the runtime context, or a blank default."""
    return _current_ctx.get() or RuntimeContext()


def reset_runtime_context(token: contextvars.Token[RuntimeContext | None]) -> None:
    """Reset the runtime context using a previously obtained token."""
    _current_ctx.reset(token)
