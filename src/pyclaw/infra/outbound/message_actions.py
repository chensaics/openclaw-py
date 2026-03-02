"""Message actions — post-delivery action execution (buttons, reactions).

Ported from ``src/infra/outbound/message-action-runner.ts``.

Provides:
- Action definitions (button, reaction, pin, delete)
- Action parameter specs
- Action runner with retry
- Action result tracking
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    REACTION = "reaction"
    BUTTON = "button"
    PIN = "pin"
    UNPIN = "unpin"
    DELETE = "delete"
    EDIT = "edit"
    FORWARD = "forward"


@dataclass
class ActionSpec:
    """Specification for a post-delivery action."""
    type: ActionType
    message_id: str
    channel_id: str
    params: dict[str, Any] = field(default_factory=dict)
    delay_ms: int = 0
    retry_count: int = 0
    max_retries: int = 2


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    action_type: ActionType
    message_id: str = ""
    error: str = ""
    executed_at: float = 0.0

    def __post_init__(self) -> None:
        if self.executed_at == 0.0 and self.success:
            self.executed_at = time.time()


ActionExecutor = Callable[[ActionSpec], Coroutine[Any, Any, ActionResult]]


class MessageActionRunner:
    """Execute post-delivery actions with retry."""

    def __init__(self) -> None:
        self._executors: dict[str, dict[ActionType, ActionExecutor]] = {}
        self._results: list[ActionResult] = []
        self._pending: list[ActionSpec] = []

    def register_executor(
        self,
        channel_id: str,
        action_type: ActionType,
        executor: ActionExecutor,
    ) -> None:
        if channel_id not in self._executors:
            self._executors[channel_id] = {}
        self._executors[channel_id][action_type] = executor

    def queue_action(self, spec: ActionSpec) -> None:
        self._pending.append(spec)

    async def execute(self, spec: ActionSpec) -> ActionResult:
        """Execute a single action with retry."""
        executors = self._executors.get(spec.channel_id, {})
        executor = executors.get(spec.type)

        if not executor:
            result = ActionResult(
                success=False,
                action_type=spec.type,
                message_id=spec.message_id,
                error=f"No executor for {spec.type} on {spec.channel_id}",
            )
            self._results.append(result)
            return result

        last_error = ""
        for attempt in range(spec.max_retries + 1):
            try:
                result = await executor(spec)
                self._results.append(result)
                return result
            except Exception as e:
                last_error = str(e)
                if attempt < spec.max_retries:
                    logger.debug("Action retry %d for %s: %s", attempt + 1, spec.type, e)

        result = ActionResult(
            success=False,
            action_type=spec.type,
            message_id=spec.message_id,
            error=last_error,
        )
        self._results.append(result)
        return result

    async def run_pending(self) -> list[ActionResult]:
        """Execute all pending actions."""
        results: list[ActionResult] = []
        while self._pending:
            spec = self._pending.pop(0)
            result = await self.execute(spec)
            results.append(result)
        return results

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def results(self) -> list[ActionResult]:
        return list(self._results)

    def clear_results(self) -> None:
        self._results.clear()
