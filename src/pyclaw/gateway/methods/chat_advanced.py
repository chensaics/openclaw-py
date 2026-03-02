"""Chat advanced — attachment handling, sanitization, abort, persistence, time injection.

Ported from ``src/gateway/method-handlers/chat-*.ts``.

Provides:
- Chat attachment processing (images, files, audio)
- Content sanitization for LLM input
- Chat abort and persistence
- Agent time context injection
- Parameter validation
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChatAttachment:
    """An attachment in a chat message."""
    filename: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    url: str = ""
    base64_data: str = ""
    attachment_type: str = "file"  # file | image | audio | video

    @property
    def is_image(self) -> bool:
        return self.mime_type.startswith("image/") or self.attachment_type == "image"

    @property
    def is_audio(self) -> bool:
        return self.mime_type.startswith("audio/") or self.attachment_type == "audio"


@dataclass
class ChatParams:
    """Validated chat parameters."""
    message: str
    agent_id: str = "main"
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    system_prompt: str = ""
    attachments: list[ChatAttachment] = field(default_factory=list)
    thinking: str = ""
    abort_previous: bool = False
    session_id: str = ""
    temperature: float | None = None

    @property
    def has_attachments(self) -> bool:
        return bool(self.attachments)


def validate_chat_params(params: dict[str, Any]) -> tuple[ChatParams | None, str]:
    """Validate and normalize chat parameters."""
    if not params or "message" not in params:
        return None, "Missing 'message' parameter"

    message = params["message"]
    if not isinstance(message, str) or not message.strip():
        return None, "'message' must be a non-empty string"

    if len(message) > 500000:
        return None, "Message too long (max 500,000 characters)"

    attachments: list[ChatAttachment] = []
    for att in params.get("attachments", []):
        if isinstance(att, dict):
            attachments.append(ChatAttachment(
                filename=att.get("filename", ""),
                mime_type=att.get("mimeType", att.get("mime_type", "")),
                size_bytes=att.get("size", att.get("size_bytes", 0)),
                url=att.get("url", ""),
                base64_data=att.get("base64", att.get("base64_data", "")),
                attachment_type=att.get("type", "file"),
            ))

    temperature = params.get("temperature")
    if temperature is not None:
        try:
            temperature = float(temperature)
            if not (0.0 <= temperature <= 2.0):
                temperature = None
        except (ValueError, TypeError):
            temperature = None

    return ChatParams(
        message=message.strip(),
        agent_id=params.get("agentId", params.get("agent_id", "main")),
        provider=params.get("provider", "openai"),
        model=params.get("model", "gpt-4o"),
        api_key=params.get("apiKey", params.get("api_key", "")),
        system_prompt=params.get("systemPrompt", params.get("system_prompt", "")),
        attachments=attachments,
        thinking=params.get("thinking", ""),
        abort_previous=params.get("abortPrevious", False),
        session_id=params.get("sessionId", params.get("session_id", "")),
        temperature=temperature,
    ), ""


# ---------------------------------------------------------------------------
# Content sanitization
# ---------------------------------------------------------------------------

_SCRIPT_TAG_RE = re.compile(r"<script[^>]*>[\s\S]*?</script>", re.I)
_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_NULL_BYTES_RE = re.compile(r"\x00")

def sanitize_content(text: str) -> str:
    """Sanitize user input before sending to LLM."""
    text = _NULL_BYTES_RE.sub("", text)
    text = _SCRIPT_TAG_RE.sub("[script removed]", text)
    text = _HTML_COMMENT_RE.sub("", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Time injection
# ---------------------------------------------------------------------------

def inject_time_context(system_prompt: str) -> str:
    """Inject current time context into the system prompt."""
    now = datetime.now(timezone.utc)
    time_str = now.strftime("%Y-%m-%d %H:%M UTC (%A)")
    if "Current date" not in system_prompt and "current date" not in system_prompt:
        return f"{system_prompt}\n\nCurrent date and time: {time_str}"
    return system_prompt


# ---------------------------------------------------------------------------
# Abort tracking
# ---------------------------------------------------------------------------

class ChatAbortManager:
    """Track active chat runs and support abort."""

    def __init__(self) -> None:
        self._active: dict[str, float] = {}  # session_id -> started_at

    def register(self, session_id: str) -> None:
        self._active[session_id] = time.time()

    def unregister(self, session_id: str) -> None:
        self._active.pop(session_id, None)

    def is_active(self, session_id: str) -> bool:
        return session_id in self._active

    def abort(self, session_id: str) -> bool:
        return self._active.pop(session_id, None) is not None

    def abort_all(self) -> int:
        count = len(self._active)
        self._active.clear()
        return count

    @property
    def active_count(self) -> int:
        return len(self._active)

    def list_active(self) -> list[dict[str, Any]]:
        return [
            {"sessionId": sid, "startedAt": ts}
            for sid, ts in self._active.items()
        ]
