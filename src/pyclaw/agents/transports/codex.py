"""OpenAI Codex transport — WebSocket-first with SSE fallback.

Ported from ``src/agents/pi-embedded-runner/extra-params.ts``.
Handles Codex WebSocket transport selection and context_management injection.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def inject_context_management(
    payload: dict[str, Any],
    *,
    provider: str,
    context_window: int = 128_000,
    responses_server_compaction: bool = False,
    responses_compact_threshold: int | None = None,
) -> dict[str, Any]:
    """Inject context_management for OpenAI Responses models.

    For direct OpenAI providers with server-side compaction enabled,
    adds a ``compaction`` entry that tells OpenAI to handle context
    management on their side.
    """
    if provider != "openai":
        return payload
    if not responses_server_compaction:
        return payload
    if "context_management" in payload:
        return payload

    threshold = responses_compact_threshold
    if threshold is None:
        threshold = min(int(context_window * 0.7), 80_000)

    payload["context_management"] = [
        {
            "type": "compaction",
            "compact_threshold": threshold,
        }
    ]
    return payload


def resolve_codex_transport(
    provider: str,
    transport: str | None = None,
) -> str:
    """Resolve transport type for a provider.

    Codex providers default to WebSocket; others use SSE.
    """
    if transport:
        return transport
    if provider == "openai-codex":
        return "auto"  # WebSocket-first with SSE fallback
    return "sse"


def should_force_responses_store(provider: str) -> bool:
    """Whether to force ``store: true`` for Responses API.

    Codex responses use ``store: false`` (no server-side persistence).
    Direct OpenAI responses use ``store: true``.
    """
    return provider != "openai-codex"


def should_enable_server_compaction(
    provider: str,
    *,
    model_config: dict[str, Any] | None = None,
) -> bool:
    """Whether to enable OpenAI server-side compaction for this provider/model."""
    if provider == "openai-codex":
        return False
    if provider != "openai":
        return False
    # Default to enabled for direct OpenAI
    if model_config and model_config.get("responsesServerCompaction") is not None:
        return bool(model_config["responsesServerCompaction"])
    return True


def resolve_compact_threshold(
    context_window: int,
    *,
    explicit_threshold: int | None = None,
) -> int:
    """Resolve the compaction threshold for context_management."""
    if explicit_threshold is not None:
        return explicit_threshold
    return min(int(context_window * 0.7), 80_000)


def wrap_codex_extra_params(
    payload: dict[str, Any],
    *,
    provider: str,
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply all Codex/Responses-specific parameter transformations."""
    cfg = model_config or {}

    # Transport
    transport = resolve_codex_transport(provider, cfg.get("transport"))
    if transport != "sse":
        payload.setdefault("transport", transport)

    # Store
    if provider == "openai-codex":
        payload["store"] = False
    elif should_force_responses_store(provider):
        payload.setdefault("store", True)

    # Context management
    if should_enable_server_compaction(provider, model_config=cfg):
        context_window = cfg.get("contextWindow", cfg.get("context_window", 128_000))
        payload = inject_context_management(
            payload,
            provider=provider,
            context_window=context_window,
            responses_server_compaction=True,
            responses_compact_threshold=cfg.get("responsesCompactThreshold"),
        )

    return payload
