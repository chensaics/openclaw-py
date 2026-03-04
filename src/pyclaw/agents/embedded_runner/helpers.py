"""Provider helpers — Google/OpenAI/Anthropic-specific adapters.

Ported from ``src/agents/pi-embedded-helpers/*.ts``.

Provides:
- Error mapping (provider errors → user-friendly messages)
- Turn building (provider-specific message formatting)
- Message deduplication
- Bootstrap loading (system prompt enrichment)
- Image handling per provider
- Google-specific schema cleaning
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error Mapping
# ---------------------------------------------------------------------------


@dataclass
class MappedError:
    """A user-friendly error derived from a provider error."""

    code: str
    message: str
    retryable: bool = False
    provider: str = ""
    original: str = ""


# Common error patterns across providers
ERROR_PATTERNS: list[tuple[re.Pattern[str], str, str, bool]] = [
    (re.compile(r"rate.?limit", re.I), "rate_limit", "Rate limit exceeded. Please wait before retrying.", True),
    (
        re.compile(r"context.?length|too.?long|maximum.?context", re.I),
        "context_overflow",
        "Message too long for this model's context window.",
        False,
    ),
    (
        re.compile(r"invalid.?api.?key|auth|unauthorized|401", re.I),
        "auth_error",
        "Authentication failed. Please check your API key.",
        False,
    ),
    (
        re.compile(r"model.?not.?found|does.?not.?exist", re.I),
        "model_not_found",
        "Model not found. Please check the model name.",
        False,
    ),
    (re.compile(r"timeout|timed.?out|deadline", re.I), "timeout", "Request timed out. Please try again.", True),
    (
        re.compile(r"server.?error|500|502|503", re.I),
        "server_error",
        "Provider server error. Please try again later.",
        True,
    ),
    (
        re.compile(r"content.?filter|safety|blocked|refused", re.I),
        "content_filtered",
        "Content was filtered by the provider's safety system.",
        False,
    ),
    (re.compile(r"quota|billing|insufficient", re.I), "quota_exceeded", "API quota or billing limit reached.", False),
    (re.compile(r"overloaded|capacity", re.I), "overloaded", "Provider is overloaded. Please try again later.", True),
]


def map_provider_error(error_text: str, *, provider: str = "") -> MappedError:
    """Map a raw provider error to a user-friendly error."""
    for pattern, code, message, retryable in ERROR_PATTERNS:
        if pattern.search(error_text):
            return MappedError(
                code=code,
                message=message,
                retryable=retryable,
                provider=provider,
                original=error_text,
            )

    return MappedError(
        code="unknown",
        message=f"An error occurred: {error_text[:200]}",
        retryable=False,
        provider=provider,
        original=error_text,
    )


# ---------------------------------------------------------------------------
# Turn Building
# ---------------------------------------------------------------------------


def build_openai_turns(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ensure messages conform to OpenAI's expected format."""
    result: list[dict[str, Any]] = []
    for msg in messages:
        clean: dict[str, Any] = {"role": msg["role"]}

        if "content" in msg:
            clean["content"] = msg["content"]
        if "tool_calls" in msg:
            clean["tool_calls"] = msg["tool_calls"]
        if "tool_call_id" in msg:
            clean["tool_call_id"] = msg["tool_call_id"]
        if "name" in msg:
            clean["name"] = msg["name"]

        result.append(clean)
    return result


def build_anthropic_turns(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Convert messages to Anthropic format.

    Returns (system_prompt, messages_without_system).
    """
    system = ""
    turns: list[dict[str, Any]] = []

    for msg in messages:
        if msg["role"] == "system":
            system = msg.get("content", "")
            continue
        turns.append(msg)

    return system, turns


def build_google_turns(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert messages to Google/Gemini format."""
    result: list[dict[str, Any]] = []

    for msg in messages:
        role = msg["role"]
        if role == "system":
            continue  # System prompt handled separately in Google API
        if role == "assistant":
            role = "model"

        content = msg.get("content", "")
        if isinstance(content, str):
            result.append({"role": role, "parts": [{"text": content}]})
        elif isinstance(content, list):
            parts: list[dict[str, Any]] = []
            for block in content:
                if block.get("type") == "text":
                    parts.append({"text": block["text"]})
                elif block.get("type") == "image_url":
                    parts.append({"inline_data": _convert_image_for_google(block)})
            result.append({"role": role, "parts": parts})

    return result


def _convert_image_for_google(block: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAI-style image block to Google format."""
    url = block.get("image_url", {}).get("url", "")
    if url.startswith("data:"):
        # data:image/png;base64,xxx
        parts = url.split(",", 1)
        mime_match = re.match(r"data:([\w/]+);", parts[0])
        mime = mime_match.group(1) if mime_match else "image/png"
        data = parts[1] if len(parts) > 1 else ""
        return {"mime_type": mime, "data": data}
    return {"mime_type": "image/png", "data": ""}


# ---------------------------------------------------------------------------
# Message Deduplication
# ---------------------------------------------------------------------------


def deduplicate_messages(
    messages: list[dict[str, Any]],
    *,
    window: int = 5,
) -> tuple[list[dict[str, Any]], int]:
    """Remove duplicate consecutive assistant messages.

    Only deduplicates within a sliding window of the last N messages.
    Returns (deduped_messages, removed_count).
    """
    if len(messages) <= 1:
        return messages, 0

    result: list[dict[str, Any]] = []
    removed = 0
    recent_contents: list[str] = []

    for msg in messages:
        content = str(msg.get("content", ""))[:500]

        if msg.get("role") == "assistant" and content in recent_contents[-window:]:
            removed += 1
            continue

        result.append(msg)
        recent_contents.append(content)

    return result, removed


# ---------------------------------------------------------------------------
# Bootstrap Loading
# ---------------------------------------------------------------------------


@dataclass
class BootstrapConfig:
    """Configuration for system prompt bootstrapping."""

    include_datetime: bool = True
    include_model_info: bool = True
    include_tool_hints: bool = True
    extra_instructions: list[str] = field(default_factory=list)


def build_bootstrap(
    base_prompt: str,
    config: BootstrapConfig,
    *,
    model: str = "",
    tool_names: list[str] | None = None,
) -> str:
    """Enrich a system prompt with bootstrap information."""
    parts = [base_prompt]

    if config.include_datetime:
        from datetime import datetime

        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        parts.append(f"\nCurrent date: {now}")

    if config.include_model_info and model:
        parts.append(f"Model: {model}")

    if config.include_tool_hints and tool_names:
        tools_str = ", ".join(tool_names[:20])
        parts.append(f"Available tools: {tools_str}")

    for instruction in config.extra_instructions:
        parts.append(instruction)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Google Schema Cleaning
# ---------------------------------------------------------------------------


def clean_schema_for_gemini(schema: dict[str, Any]) -> dict[str, Any]:
    """Clean a JSON Schema to be compatible with Gemini's requirements.

    Gemini doesn't support: anyOf, oneOf, allOf, $ref, format.
    """
    cleaned: dict[str, Any] = {}

    for key, value in schema.items():
        if key in ("anyOf", "oneOf", "allOf", "$ref"):
            # Flatten: take the first option
            if key in ("anyOf", "oneOf") and isinstance(value, list) and value:
                cleaned.update(clean_schema_for_gemini(value[0]))
            continue

        if key == "format":
            continue

        if isinstance(value, dict):
            cleaned[key] = clean_schema_for_gemini(value)
        elif isinstance(value, list):
            cleaned[key] = [clean_schema_for_gemini(v) if isinstance(v, dict) else v for v in value]
        else:
            cleaned[key] = value

    return cleaned
