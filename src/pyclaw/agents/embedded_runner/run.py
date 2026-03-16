"""Embedded runner — main LLM execution loop.

Ported from ``src/agents/pi-embedded-runner/run.ts`` and ``run/attempt.ts``.

Provides:
- Main run loop: attempt → stream → tool → retry
- Payload construction for different providers
- Image injection and pruning
- Compaction timeout handling
- Run state tracking
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyclaw.constants.runtime import (
    STATUS_ABORTED,
    STATUS_COMPACTING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_IDLE,
    STATUS_RUNNING,
    STATUS_TIMEOUT,
    STATUS_TOOL_EXEC,
)

logger = logging.getLogger(__name__)


class RunState(str, Enum):
    IDLE = STATUS_IDLE
    RUNNING = STATUS_RUNNING
    TOOL_EXEC = STATUS_TOOL_EXEC
    COMPACTING = STATUS_COMPACTING
    COMPLETED = STATUS_COMPLETED
    FAILED = STATUS_FAILED
    ABORTED = STATUS_ABORTED
    TIMEOUT = STATUS_TIMEOUT


@dataclass
class RunConfig:
    """Configuration for an embedded run."""

    model: str = ""
    provider: str = ""
    max_turns: int = 50
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout_s: float = 600.0
    compaction_timeout_s: float = 30.0
    enable_thinking: bool = False
    thinking_budget: int = 0
    stream: bool = True
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunAttemptResult:
    """Result of a single run attempt."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    error: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    @property
    def success(self) -> bool:
        return not self.error


@dataclass
class RunRecord:
    """Record of an embedded run execution."""

    run_id: str
    model: str = ""
    state: RunState = RunState.IDLE
    turns: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        if self.started_at == 0:
            return 0
        end = self.finished_at or time.time()
        return end - self.started_at


@dataclass
class Message:
    """A message in the conversation."""

    role: str
    content: str | list[dict[str, Any]] = ""
    tool_call_id: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role}
        if self.content:
            d["content"] = self.content
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.name:
            d["name"] = self.name
        return d


# ---------------------------------------------------------------------------
# Payload Builder
# ---------------------------------------------------------------------------


def build_request_payload(
    messages: list[Message],
    config: RunConfig,
    *,
    tools: list[dict[str, Any]] | None = None,
    system_prompt: str = "",
) -> dict[str, Any]:
    """Build the API request payload for an LLM provider."""
    msg_dicts = []
    if system_prompt:
        msg_dicts.append({"role": "system", "content": system_prompt})
    msg_dicts.extend(m.to_dict() for m in messages)

    payload: dict[str, Any] = {
        "model": config.model,
        "messages": msg_dicts,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "stream": config.stream,
    }

    if tools:
        payload["tools"] = tools

    if config.enable_thinking and config.thinking_budget:
        payload["thinking"] = {"type": "enabled", "budget_tokens": config.thinking_budget}

    payload.update(config.extra_params)
    return payload


# ---------------------------------------------------------------------------
# Image Handling
# ---------------------------------------------------------------------------


@dataclass
class ImageContent:
    """An image content block in a message."""

    url: str = ""
    base64_data: str = ""
    media_type: str = "image/png"
    detail: str = "auto"  # auto | low | high

    def to_content_block(self) -> dict[str, Any]:
        if self.base64_data:
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{self.media_type};base64,{self.base64_data}",
                    "detail": self.detail,
                },
            }
        return {
            "type": "image_url",
            "image_url": {"url": self.url, "detail": self.detail},
        }


def inject_images(
    messages: list[Message],
    images: list[ImageContent],
    *,
    position: int = -1,
) -> None:
    """Inject images into the last user message (or specified position)."""
    if not images:
        return

    idx = position if position >= 0 else len(messages) - 1
    if idx < 0 or idx >= len(messages):
        return

    msg = messages[idx]
    if isinstance(msg.content, str):
        blocks: list[dict[str, Any]] = [{"type": "text", "text": msg.content}]
        blocks.extend(img.to_content_block() for img in images)
        msg.content = blocks
    elif isinstance(msg.content, list):
        msg.content.extend(img.to_content_block() for img in images)


def prune_images(messages: list[Message], *, keep_last_n: int = 2) -> int:
    """Remove images from older messages to reduce token usage."""
    pruned = 0
    image_messages: list[int] = []

    for i, msg in enumerate(messages):
        if isinstance(msg.content, list):
            has_image = any(b.get("type") == "image_url" for b in msg.content)
            if has_image:
                image_messages.append(i)

    to_prune = image_messages[:-keep_last_n] if len(image_messages) > keep_last_n else []

    for idx in to_prune:
        msg = messages[idx]
        if isinstance(msg.content, list):
            original_len = len(msg.content)
            msg.content = [b for b in msg.content if b.get("type") != "image_url"]
            pruned += original_len - len(msg.content)
            if len(msg.content) == 1 and msg.content[0].get("type") == "text":
                msg.content = msg.content[0]["text"]

    return pruned


# ---------------------------------------------------------------------------
# Run Tracker
# ---------------------------------------------------------------------------


class RunTracker:
    """Track multiple embedded runs."""

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._counter = 0

    def start_run(self, model: str = "") -> RunRecord:
        self._counter += 1
        run_id = f"run-{self._counter}"
        record = RunRecord(run_id=run_id, model=model, state=RunState.RUNNING, started_at=time.time())
        self._runs[run_id] = record
        return record

    def finish_run(self, run_id: str, *, state: RunState = RunState.COMPLETED) -> None:
        record = self._runs.get(run_id)
        if record:
            record.state = state
            record.finished_at = time.time()

    def get_run(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)

    @property
    def active_runs(self) -> list[RunRecord]:
        return [r for r in self._runs.values() if r.state == RunState.RUNNING]

    @property
    def total_runs(self) -> int:
        return len(self._runs)
