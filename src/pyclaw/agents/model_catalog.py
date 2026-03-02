"""Model catalog — provider discovery, model metadata, normalization, cost tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ThinkLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]

# Provider ID aliases
_PROVIDER_ALIASES: dict[str, str] = {
    "z.ai": "zai",
    "bedrock": "amazon-bedrock",
    "aws-bedrock": "amazon-bedrock",
    "claude": "anthropic",
    "gpt": "openai",
}

# Known providers with metadata
_KNOWN_PROVIDERS: dict[str, dict[str, Any]] = {
    "anthropic": {"name": "Anthropic", "env_key": "ANTHROPIC_API_KEY"},
    "openai": {"name": "OpenAI", "env_key": "OPENAI_API_KEY"},
    "google": {"name": "Google", "env_key": "GOOGLE_API_KEY"},
    "openrouter": {"name": "OpenRouter", "env_key": "OPENROUTER_API_KEY"},
    "together": {"name": "Together", "env_key": "TOGETHER_API_KEY"},
    "groq": {"name": "Groq", "env_key": "GROQ_API_KEY"},
    "ollama": {"name": "Ollama (local)", "env_key": ""},
    "amazon-bedrock": {"name": "Amazon Bedrock", "env_key": "AWS_BEARER_TOKEN_BEDROCK"},
    "mistral": {"name": "Mistral", "env_key": "MISTRAL_API_KEY"},
    "deepseek": {"name": "DeepSeek", "env_key": "DEEPSEEK_API_KEY"},
    "xai": {"name": "xAI", "env_key": "XAI_API_KEY"},
    "fireworks": {"name": "Fireworks", "env_key": "FIREWORKS_API_KEY"},
}


@dataclass(frozen=True)
class ModelRef:
    """Reference to a specific model."""

    provider: str
    model: str

    @property
    def key(self) -> str:
        return f"{self.provider}/{self.model}"


@dataclass
class ModelInfo:
    """Metadata about a model."""

    provider: str
    model_id: str
    display_name: str = ""
    max_tokens: int = 8192
    context_window: int = 200_000
    supports_tools: bool = True
    supports_vision: bool = False
    supports_thinking: bool = False
    cost_per_1m_input: float = 0.0
    cost_per_1m_output: float = 0.0

    @property
    def key(self) -> str:
        return f"{self.provider}/{self.model_id}"


@dataclass
class ModelAliasIndex:
    """Bidirectional alias ↔ model ref mapping."""

    by_alias: dict[str, ModelRef] = field(default_factory=dict)
    by_key: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ModelRefStatus:
    key: str
    in_catalog: bool
    allow_any: bool
    allowed: bool


# ─── Built-in model catalog ─────────────────────────────────────────────

_CATALOG: list[ModelInfo] = [
    ModelInfo(
        "anthropic",
        "claude-opus-4-6",
        "Claude Opus 4.6",
        8192,
        200_000,
        True,
        True,
        True,
        15.0,
        75.0,
    ),
    ModelInfo(
        "anthropic",
        "claude-sonnet-4-6",
        "Claude Sonnet 4.6",
        8192,
        200_000,
        True,
        True,
        True,
        3.0,
        15.0,
    ),
    ModelInfo(
        "anthropic",
        "claude-haiku-3-5",
        "Claude Haiku 3.5",
        8192,
        200_000,
        True,
        True,
        False,
        0.8,
        4.0,
    ),
    ModelInfo("openai", "gpt-5.2", "GPT 5.2", 16384, 128_000, True, True, True, 2.5, 10.0),
    ModelInfo("openai", "gpt-4o", "GPT-4o", 16384, 128_000, True, True, False, 2.5, 10.0),
    ModelInfo("openai", "gpt-4o-mini", "GPT-4o Mini", 16384, 128_000, True, True, False, 0.15, 0.6),
    ModelInfo("openai", "o3", "o3", 100_000, 200_000, True, True, True, 10.0, 40.0),
    ModelInfo("openai", "o4-mini", "o4-mini", 65_536, 200_000, True, True, True, 1.1, 4.4),
    ModelInfo(
        "google",
        "gemini-3-pro-preview",
        "Gemini 3 Pro",
        8192,
        1_000_000,
        True,
        True,
        True,
        1.25,
        5.0,
    ),
    ModelInfo(
        "google",
        "gemini-2.5-flash",
        "Gemini 2.5 Flash",
        8192,
        1_000_000,
        True,
        True,
        True,
        0.15,
        0.6,
    ),
    ModelInfo(
        "deepseek", "deepseek-r1", "DeepSeek R1", 8192, 128_000, True, False, True, 0.55, 2.19
    ),
    ModelInfo(
        "deepseek", "deepseek-chat", "DeepSeek V3", 8192, 128_000, True, False, False, 0.27, 1.1
    ),
    ModelInfo(
        "mistral",
        "mistral-large-latest",
        "Mistral Large",
        8192,
        128_000,
        True,
        False,
        False,
        2.0,
        6.0,
    ),
    ModelInfo("xai", "grok-3", "Grok 3", 8192, 131_072, True, True, True, 3.0, 15.0),
]


class ModelCatalog:
    """Registry of known models with lookup and alias resolution."""

    def __init__(self) -> None:
        self._models: dict[str, ModelInfo] = {}
        self._alias_index = ModelAliasIndex()
        for info in _CATALOG:
            self._models[info.key] = info

    def get(self, provider: str, model: str) -> ModelInfo | None:
        key = f"{provider}/{model}"
        return self._models.get(key)

    def list_models(self, provider: str | None = None) -> list[ModelInfo]:
        if provider:
            return [m for m in self._models.values() if m.provider == provider]
        return list(self._models.values())

    def list_providers(self) -> list[dict[str, str]]:
        seen: dict[str, dict[str, str]] = {}
        for info in _KNOWN_PROVIDERS.values():
            pass
        return [{"id": pid, "name": info["name"]} for pid, info in _KNOWN_PROVIDERS.items()]

    def register(self, info: ModelInfo) -> None:
        self._models[info.key] = info

    def set_alias(self, alias: str, ref: ModelRef) -> None:
        self._alias_index.by_alias[alias] = ref
        key = ref.key
        if key not in self._alias_index.by_key:
            self._alias_index.by_key[key] = []
        if alias not in self._alias_index.by_key[key]:
            self._alias_index.by_key[key].append(alias)

    def resolve_alias(self, alias: str) -> ModelRef | None:
        return self._alias_index.by_alias.get(alias)

    @property
    def alias_index(self) -> ModelAliasIndex:
        return self._alias_index


# ─── Utility functions ───────────────────────────────────────────────────


def model_key(provider: str, model: str) -> str:
    return f"{provider}/{model}"


def normalize_provider_id(provider: str) -> str:
    """Normalize a provider identifier."""
    p = provider.strip().lower()
    return _PROVIDER_ALIASES.get(p, p)


def parse_model_ref(raw: str, default_provider: str = "openai") -> ModelRef:
    """Parse 'provider/model' or 'model' into a ModelRef."""
    raw = raw.strip()
    if "/" in raw:
        parts = raw.split("/", 1)
        return ModelRef(
            provider=normalize_provider_id(parts[0]),
            model=parts[1],
        )
    return ModelRef(provider=default_provider, model=raw)


def resolve_model_ref_from_string(
    raw: str,
    *,
    default_provider: str = "openai",
    alias_index: ModelAliasIndex | None = None,
) -> ModelRef:
    """Resolve a model string, checking aliases first."""
    if alias_index:
        alias_ref = alias_index.by_alias.get(raw.strip().lower())
        if alias_ref:
            return alias_ref
    return parse_model_ref(raw, default_provider)


def resolve_default_model_for_agent(
    config: dict[str, Any],
    agent_id: str = "main",
) -> ModelRef | None:
    """Resolve the default model from config."""
    models = config.get("models", {})

    # Agent-specific override
    agents = config.get("agents", {})
    agent_cfg = agents.get(agent_id, {})
    agent_model = agent_cfg.get("model")
    if agent_model:
        return parse_model_ref(agent_model)

    # Global default
    default = models.get("default")
    if default:
        return parse_model_ref(default)

    return None


def build_default_alias_index() -> ModelAliasIndex:
    """Build the standard model alias index."""
    from pyclaw.config.defaults import DEFAULT_MODEL_ALIASES

    index = ModelAliasIndex()
    for alias, model_str in DEFAULT_MODEL_ALIASES.items():
        ref = parse_model_ref(model_str)
        index.by_alias[alias] = ref
        key = ref.key
        if key not in index.by_key:
            index.by_key[key] = []
        index.by_key[key].append(alias)

    return index


def resolve_thinking_default(provider: str, model: str) -> ThinkLevel:
    """Default thinking level for a model."""
    if "o3" in model or "o4" in model or "r1" in model:
        return "medium"
    if provider == "anthropic" and ("opus" in model or "sonnet" in model):
        return "low"
    return "off"
