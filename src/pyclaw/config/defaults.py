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
    "default": "anthropic/claude-sonnet-4-6",
    "opus": "anthropic/claude-opus-4-6",
    "sonnet": "anthropic/claude-sonnet-4-6",
    "haiku": "anthropic/claude-haiku-4-5",
    "gpt": "openai/gpt-4o",
    "gpt-mini": "openai/gpt-4o-mini",
    "gpt-4.1": "openai/gpt-4.1-2025-04-14",
    "gemini": "google/gemini-2.5-pro",
    "gemini-flash": "google/gemini-2.5-flash",
    "deepseek": "deepseek/deepseek-chat",
    "r1": "deepseek/deepseek-reasoner",
    "qwen": "qwen/qwen-max",
    "kimi": "moonshot/kimi-k2.5",
    "moonshot": "moonshot/kimi-k2.5",
    "glm": "zhipu/glm-4-plus",
    "grok": "xai/grok-3",
    "ernie": "qianfan/ernie-4.5-turbo-128k",
    "yi": "yi/yi-lightning",
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
    "anthropic": ("https://api.anthropic.com", "claude-sonnet-4-6"),
    "openai": ("https://api.openai.com/v1", "gpt-4o"),
    "google": ("https://generativelanguage.googleapis.com", "gemini-2.5-flash"),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "mistral": ("https://api.mistral.ai/v1", "mistral-large-latest"),
    "xai": ("https://api.x.ai/v1", "grok-3"),
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-max"),
    "moonshot": ("https://api.moonshot.cn/v1", "kimi-k2.5"),
    "zhipu": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-plus"),
    "volcengine": ("https://ark.cn-beijing.volces.com/api/v3", "doubao-pro-256k"),
    "yi": ("https://api.lingyiwanwu.com/v1", "yi-lightning"),
    "qianfan": ("https://aip.baidubce.com/rpc/2.0/ai_custom/v1", "ernie-4.5-turbo-128k"),
    "minimax": ("https://api.minimax.chat/v1", "MiniMax-M2.5"),
    "siliconflow": ("https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V3"),
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "ollama": ("http://localhost:11434/v1", "llama3"),
    "openrouter": ("https://openrouter.ai/api/v1", "anthropic/claude-sonnet-4-6"),
    "together": ("https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    "fireworks": ("https://api.fireworks.ai/inference/v1", "accounts/fireworks/models/llama-v3p3-70b-instruct"),
    "perplexity": ("https://api.perplexity.ai", "sonar-pro"),
    "amazon-bedrock": ("", "anthropic.claude-sonnet-4-6"),
    "vllm": ("http://localhost:8000/v1", "default"),
    "litellm": ("http://localhost:4000/v1", "default"),
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
