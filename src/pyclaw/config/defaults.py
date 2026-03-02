"""Configuration defaults — model aliases, limits, and fallback values.

Ported from ``src/config/defaults.ts``, ``src/agents/defaults.ts``,
and ``src/config/agent-limits.ts``.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-opus-4-6"
DEFAULT_CONTEXT_TOKENS = 200_000
DEFAULT_MODEL_MAX_TOKENS = 8192
DEFAULT_MODEL_INPUT: list[str] = ["text"]

DEFAULT_MODEL_ALIASES: dict[str, str] = {
    "opus": "anthropic/claude-opus-4-6",
    "sonnet": "anthropic/claude-sonnet-4-6",
    "gpt": "openai/gpt-5.2",
    "gpt-mini": "openai/gpt-5-mini",
    "gemini": "google/gemini-3-pro-preview",
    "gemini-flash": "google/gemini-3-flash-preview",
}

DEFAULT_MODEL_COST: dict[str, float] = {
    "input": 0.0,
    "output": 0.0,
    "cache_read": 0.0,
    "cache_write": 0.0,
}

# ---------------------------------------------------------------------------
# Agent concurrency limits
# ---------------------------------------------------------------------------

DEFAULT_AGENT_MAX_CONCURRENT = 4
DEFAULT_SUBAGENT_MAX_CONCURRENT = 8
DEFAULT_SUBAGENT_MAX_SPAWN_DEPTH = 1

# ---------------------------------------------------------------------------
# Network ports
# ---------------------------------------------------------------------------

DEFAULT_GATEWAY_PORT = 18789
DEFAULT_BRIDGE_PORT = 18790
DEFAULT_BROWSER_PORT = 18791
DEFAULT_CANVAS_PORT = 18793

# ---------------------------------------------------------------------------
# Compaction / context pruning
# ---------------------------------------------------------------------------

DEFAULT_COMPACTION_MODE = "safeguard"
DEFAULT_CONTEXT_PRUNING_MODE = "cache-ttl"
DEFAULT_CONTEXT_PRUNING_TTL = "1h"
DEFAULT_HEARTBEAT_INTERVAL_OAUTH = "1h"
DEFAULT_HEARTBEAT_INTERVAL_API_KEY = "30m"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

DEFAULT_REDACT_SENSITIVE = "tools"


# ---------------------------------------------------------------------------
# Provider defaults — base_url and default model for OpenAI-compatible providers
# ---------------------------------------------------------------------------

_PROVIDER_DEFAULTS: dict[str, tuple[str, str]] = {
    # provider_id -> (default_base_url, default_model)
    "ollama": ("http://localhost:11434/v1", "llama3"),
    "vllm": ("http://localhost:8000/v1", "default"),
    "litellm": ("http://localhost:4000/v1", "gpt-4o"),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-max"),
    "moonshot": ("https://api.moonshot.cn/v1", "moonshot-v1-128k"),
    "volcengine": ("https://ark.cn-beijing.volces.com/api/v3", "doubao-pro-256k"),
    "zhipu": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-plus"),
    "minimax": ("https://api.minimax.chat/v1", "abab6.5s-chat"),
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "together": ("https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    "openrouter": ("https://openrouter.ai/api/v1", "anthropic/claude-sonnet-4-6"),
    "fireworks": ("https://api.fireworks.ai/inference/v1", "accounts/fireworks/models/llama-v3p3-70b-instruct"),
    "perplexity": ("https://api.perplexity.ai", "sonar-pro"),
    "xai": ("https://api.x.ai/v1", "grok-3"),
}


def get_provider_defaults(provider_id: str) -> tuple[str, str]:
    """Return (default_base_url, default_model) for a known provider.

    Returns ("", "") for unknown providers — callers should fall back
    to OpenAI defaults or raise.
    """
    return _PROVIDER_DEFAULTS.get(provider_id, ("", ""))


def resolve_model_alias(raw: str) -> str:
    """Resolve a model alias (e.g. ``"opus"``) to its full ref."""
    key = raw.strip().lower()
    return DEFAULT_MODEL_ALIASES.get(key, raw.strip())


def resolve_agent_max_concurrent(cfg: dict[str, Any] | None = None) -> int:
    """Return the effective agent max-concurrent limit from config."""
    if cfg:
        raw = (cfg.get("agents") or {}).get("defaults", {}).get("maxConcurrent")
        if isinstance(raw, (int, float)) and raw > 0:
            return max(1, int(raw))
    return DEFAULT_AGENT_MAX_CONCURRENT


def resolve_subagent_max_concurrent(cfg: dict[str, Any] | None = None) -> int:
    """Return the effective subagent max-concurrent limit from config."""
    if cfg:
        sub = (cfg.get("agents") or {}).get("defaults", {}).get("subagents", {})
        raw = sub.get("maxConcurrent")
        if isinstance(raw, (int, float)) and raw > 0:
            return max(1, int(raw))
    return DEFAULT_SUBAGENT_MAX_CONCURRENT


def resolve_model_max_tokens(
    raw_max_tokens: int | None,
    context_window: int | None,
) -> int:
    """Compute effective max_tokens capped to context window."""
    ctx = (
        context_window
        if isinstance(context_window, int) and context_window > 0
        else DEFAULT_CONTEXT_TOKENS
    )
    default = min(DEFAULT_MODEL_MAX_TOKENS, ctx)
    if isinstance(raw_max_tokens, int) and raw_max_tokens > 0:
        return min(raw_max_tokens, ctx)
    return default
