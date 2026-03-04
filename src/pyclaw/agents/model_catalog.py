"""Model catalog — provider discovery, model metadata, normalization, cost tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ThinkLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]

# Provider ID aliases — normalize user input to canonical IDs
_PROVIDER_ALIASES: dict[str, str] = {
    "z.ai": "zhipu",
    "zhipuai": "zhipu",
    "bedrock": "amazon-bedrock",
    "aws-bedrock": "amazon-bedrock",
    "aws": "amazon-bedrock",
    "claude": "anthropic",
    "gpt": "openai",
    "gemini": "google",
    "tongyi": "qwen",
    "tongyi-qianwen": "qwen",
    "aliyun": "qwen",
    "dashscope": "qwen",
    "lingyiwanwu": "yi",
    "volcano": "volcengine",
    "doubao": "volcengine",
    "kimi": "moonshot",
    "siliconcloud": "siliconflow",
    "baidu": "qianfan",
}

# Known providers with metadata and default model
_KNOWN_PROVIDERS: dict[str, dict[str, Any]] = {
    "anthropic": {"name": "Anthropic", "env_key": "ANTHROPIC_API_KEY", "default_model": "claude-sonnet-4-6"},
    "openai": {"name": "OpenAI", "env_key": "OPENAI_API_KEY", "default_model": "gpt-4o"},
    "google": {"name": "Google Gemini", "env_key": "GOOGLE_API_KEY", "default_model": "gemini-2.5-flash"},
    "deepseek": {"name": "DeepSeek", "env_key": "DEEPSEEK_API_KEY", "default_model": "deepseek-chat"},
    "mistral": {"name": "Mistral", "env_key": "MISTRAL_API_KEY", "default_model": "mistral-large-latest"},
    "xai": {"name": "xAI (Grok)", "env_key": "XAI_API_KEY", "default_model": "grok-3"},
    "qwen": {"name": "通义千问 (Qwen)", "env_key": "DASHSCOPE_API_KEY", "default_model": "qwen-max"},
    "moonshot": {"name": "Moonshot (Kimi)", "env_key": "MOONSHOT_API_KEY", "default_model": "kimi-k2.5"},
    "zhipu": {"name": "智谱 AI (GLM)", "env_key": "ZHIPU_API_KEY", "default_model": "glm-4-plus"},
    "volcengine": {"name": "火山引擎 (豆包)", "env_key": "VOLCENGINE_API_KEY", "default_model": "doubao-pro-256k"},
    "yi": {"name": "零一万物 (Yi)", "env_key": "YI_API_KEY", "default_model": "yi-lightning"},
    "qianfan": {"name": "百度千帆 (ERNIE)", "env_key": "QIANFAN_API_KEY", "default_model": "ernie-4.5-turbo-128k"},
    "minimax": {"name": "MiniMax", "env_key": "MINIMAX_API_KEY", "default_model": "MiniMax-M2.5"},
    "siliconflow": {"name": "SiliconFlow", "env_key": "SILICONFLOW_API_KEY", "default_model": "deepseek-ai/DeepSeek-V3"},
    "groq": {"name": "Groq", "env_key": "GROQ_API_KEY", "default_model": "llama-3.3-70b-versatile"},
    "ollama": {"name": "Ollama (本地)", "env_key": "", "default_model": "llama3"},
    "openrouter": {"name": "OpenRouter", "env_key": "OPENROUTER_API_KEY", "default_model": "anthropic/claude-sonnet-4-6"},
    "together": {"name": "Together AI", "env_key": "TOGETHER_API_KEY", "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
    "fireworks": {"name": "Fireworks AI", "env_key": "FIREWORKS_API_KEY", "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct"},
    "amazon-bedrock": {"name": "Amazon Bedrock", "env_key": "AWS_BEARER_TOKEN_BEDROCK", "default_model": "anthropic.claude-sonnet-4-6"},
    "perplexity": {"name": "Perplexity", "env_key": "PERPLEXITY_API_KEY", "default_model": "sonar-pro"},
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
    # ═══════════════════════════════════════════════════════════════════
    # Anthropic — https://docs.anthropic.com/en/docs/models
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("anthropic", "claude-opus-4-6", "Claude Opus 4.6", 8192, 200_000, True, True, True, 15.0, 75.0),
    ModelInfo("anthropic", "claude-opus-4-1-20250805", "Claude Opus 4.1", 8192, 200_000, True, True, True, 15.0, 75.0),
    ModelInfo("anthropic", "claude-sonnet-4-5", "Claude Sonnet 4.5", 8192, 200_000, True, True, True, 3.0, 15.0),
    ModelInfo("anthropic", "claude-sonnet-4-6", "Claude Sonnet 4.6", 8192, 200_000, True, True, True, 3.0, 15.0),
    ModelInfo("anthropic", "claude-sonnet-4-20250514", "Claude Sonnet 4", 8192, 200_000, True, True, True, 3.0, 15.0),
    ModelInfo("anthropic", "claude-haiku-4-5", "Claude Haiku 4.5", 8192, 200_000, True, True, False, 0.8, 4.0),
    ModelInfo("anthropic", "claude-3-7-sonnet-latest", "Claude 3.7 Sonnet", 8192, 200_000, True, True, True, 3.0, 15.0),

    # ═══════════════════════════════════════════════════════════════════
    # OpenAI — https://platform.openai.com/docs/models
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("openai", "gpt-5", "GPT-5", 32_768, 400_000, True, True, False, 0.0, 0.0),
    ModelInfo("openai", "gpt-5-mini", "GPT-5 Mini", 32_768, 400_000, True, True, False, 0.0, 0.0),
    ModelInfo("openai", "gpt-4.1-2025-04-14", "GPT-4.1", 32_768, 1_048_576, True, True, False, 2.0, 8.0),
    ModelInfo("openai", "gpt-4.1-mini-2025-04-14", "GPT-4.1 Mini", 32_768, 1_048_576, True, True, False, 0.4, 1.6),
    ModelInfo("openai", "gpt-4.1-nano-2025-04-14", "GPT-4.1 Nano", 32_768, 1_048_576, True, True, False, 0.1, 0.4),
    ModelInfo("openai", "gpt-4o", "GPT-4o", 16_384, 128_000, True, True, False, 2.5, 10.0),
    ModelInfo("openai", "gpt-4o-mini", "GPT-4o Mini", 16_384, 128_000, True, True, False, 0.15, 0.6),
    ModelInfo("openai", "o3", "o3", 100_000, 200_000, True, True, True, 10.0, 40.0),
    ModelInfo("openai", "o3-pro", "o3-pro", 100_000, 200_000, True, True, True, 20.0, 80.0),
    ModelInfo("openai", "o3-mini", "o3-mini", 65_536, 200_000, True, True, True, 1.1, 4.4),
    ModelInfo("openai", "o4-mini", "o4-mini", 65_536, 200_000, True, True, True, 1.1, 4.4),

    # ═══════════════════════════════════════════════════════════════════
    # Google Gemini — https://ai.google.dev/gemini-api/docs/models
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("google", "gemini-3-pro-preview", "Gemini 3 Pro", 65_536, 1_048_576, True, True, True, 0.0, 0.0),
    ModelInfo("google", "gemini-3-flash-preview", "Gemini 3 Flash", 65_536, 1_048_576, True, True, True, 0.0, 0.0),
    ModelInfo("google", "gemini-2.5-pro", "Gemini 2.5 Pro", 65_536, 1_048_576, True, True, True, 1.25, 5.0),
    ModelInfo("google", "gemini-2.5-flash", "Gemini 2.5 Flash", 8192, 1_048_576, True, True, True, 0.15, 0.6),
    ModelInfo("google", "gemini-2.0-flash", "Gemini 2.0 Flash", 8192, 1_048_576, True, True, False, 0.1, 0.4),

    # ═══════════════════════════════════════════════════════════════════
    # DeepSeek — https://api-docs.deepseek.com/
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("deepseek", "deepseek-chat", "DeepSeek V3", 8192, 128_000, True, False, False, 0.27, 1.1),
    ModelInfo("deepseek", "deepseek-reasoner", "DeepSeek R1", 8192, 128_000, True, False, True, 0.55, 2.19),

    # ═══════════════════════════════════════════════════════════════════
    # Mistral — https://docs.mistral.ai/getting-started/models/
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("mistral", "mistral-large-latest", "Mistral Large", 8192, 128_000, True, False, False, 2.0, 6.0),
    ModelInfo("mistral", "mistral-medium-2508", "Mistral Medium 3.1", 8192, 128_000, True, False, False, 1.0, 3.0),
    ModelInfo("mistral", "mistral-small-2506", "Mistral Small 3.2", 8192, 128_000, True, False, False, 0.2, 0.6),
    ModelInfo("mistral", "codestral-latest", "Codestral", 8192, 32_768, True, False, False, 0.3, 0.9),
    ModelInfo("mistral", "magistral-medium-1.2", "Magistral Medium", 8192, 128_000, True, False, False, 2.0, 6.0),
    ModelInfo("mistral", "magistral-small-1.2", "Magistral Small", 8192, 128_000, True, False, False, 0.5, 1.5),

    # ═══════════════════════════════════════════════════════════════════
    # xAI (Grok) — https://docs.x.ai/docs/models
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("xai", "grok-3", "Grok 3", 8192, 131_072, True, True, True, 3.0, 15.0),
    ModelInfo("xai", "grok-3-mini", "Grok 3 Mini", 8192, 131_072, True, True, True, 0.3, 0.5),

    # ═══════════════════════════════════════════════════════════════════
    # 通义千问 (Qwen / Aliyun) — https://help.aliyun.com/zh/model-studio/
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("qwen", "qwen-max", "Qwen Max", 8192, 32_768, True, False, False, 0.0, 0.0),
    ModelInfo("qwen", "qwen-plus", "Qwen Plus", 8192, 131_072, True, False, False, 0.0, 0.0),
    ModelInfo("qwen", "qwen-plus-latest", "Qwen Plus (Latest)", 8192, 131_072, True, False, False, 0.0, 0.0),
    ModelInfo("qwen", "qwen-turbo", "Qwen Turbo", 8192, 131_072, True, False, False, 0.0, 0.0),
    ModelInfo("qwen", "qwen-turbo-latest", "Qwen Turbo (Latest)", 8192, 131_072, True, False, False, 0.0, 0.0),
    ModelInfo("qwen", "qwen-long", "Qwen Long", 8192, 10_000_000, True, False, False, 0.0, 0.0),
    ModelInfo("qwen", "qwen-coder-turbo", "Qwen Coder Turbo", 8192, 131_072, True, False, False, 0.0, 0.0),
    ModelInfo("qwen", "qwen3-coder-plus", "Qwen3 Coder Plus", 8192, 1_000_000, True, False, False, 0.0, 0.0),
    ModelInfo("qwen", "qwq-plus", "QwQ Plus (推理)", 8192, 32_768, True, False, True, 0.0, 0.0),

    # ═══════════════════════════════════════════════════════════════════
    # Moonshot / Kimi — https://platform.moonshot.cn/docs/
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("moonshot", "kimi-k2.5", "Kimi K2.5", 8192, 256_000, True, False, False, 0.0, 0.0),
    ModelInfo("moonshot", "kimi-k2-0905-Preview", "Kimi K2", 8192, 256_000, True, False, False, 0.0, 0.0),
    ModelInfo("moonshot", "kimi-k2-thinking", "Kimi K2 Thinking", 8192, 256_000, True, False, True, 0.0, 0.0),
    ModelInfo("moonshot", "moonshot-v1-128k", "Moonshot v1 128K", 8192, 128_000, True, False, False, 0.0, 0.0),
    ModelInfo("moonshot", "moonshot-v1-32k", "Moonshot v1 32K", 8192, 32_000, True, False, False, 0.0, 0.0),

    # ═══════════════════════════════════════════════════════════════════
    # 智谱 AI (ZhipuAI / GLM) — https://open.bigmodel.cn/dev/api
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("zhipu", "glm-5", "GLM-5", 4096, 200_000, True, False, False, 0.0, 0.0),
    ModelInfo("zhipu", "glm-4.7", "GLM-4.7", 4096, 200_000, True, False, False, 0.0, 0.0),
    ModelInfo("zhipu", "glm-4.7-flash", "GLM-4.7 Flash", 4096, 200_000, True, False, False, 0.0, 0.0),
    ModelInfo("zhipu", "glm-4-plus", "GLM-4 Plus", 4096, 128_000, True, False, False, 0.0, 0.0),
    ModelInfo("zhipu", "glm-4-flash", "GLM-4 Flash", 4096, 128_000, True, False, False, 0.0, 0.0),
    ModelInfo("zhipu", "glm-4-long", "GLM-4 Long", 4096, 1_048_576, True, False, False, 0.0, 0.0),
    ModelInfo("zhipu", "glm-4-5-flash", "GLM-4.5 Flash", 4096, 200_000, True, False, False, 0.0, 0.0),
    ModelInfo("zhipu", "glm-zero-preview", "GLM Zero Preview", 4096, 128_000, True, False, True, 0.0, 0.0),

    # ═══════════════════════════════════════════════════════════════════
    # 火山引擎 / 豆包 (Volcengine / Doubao)
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("volcengine", "doubao-pro-256k", "豆包 Pro 256K", 4096, 256_000, True, False, False, 0.0, 0.0),
    ModelInfo("volcengine", "doubao-lite-128k", "豆包 Lite 128K", 4096, 128_000, True, False, False, 0.0, 0.0),

    # ═══════════════════════════════════════════════════════════════════
    # 零一万物 (Yi / 01.AI) — https://platform.lingyiwanwu.com/
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("yi", "yi-lightning", "Yi Lightning", 8192, 16_384, True, False, False, 0.0, 0.0),
    ModelInfo("yi", "yi-large", "Yi Large", 8192, 32_768, True, False, False, 0.0, 0.0),
    ModelInfo("yi", "yi-large-turbo", "Yi Large Turbo", 8192, 16_384, True, False, False, 0.0, 0.0),
    ModelInfo("yi", "yi-medium", "Yi Medium", 8192, 16_384, True, False, False, 0.0, 0.0),
    ModelInfo("yi", "yi-vision", "Yi Vision", 4096, 16_384, True, True, False, 0.0, 0.0),

    # ═══════════════════════════════════════════════════════════════════
    # 百度千帆 (Qianfan / ERNIE) — https://cloud.baidu.com/doc/WENXINWORKSHOP/
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("qianfan", "ernie-4.5-turbo-128k", "ERNIE 4.5 Turbo 128K", 4096, 128_000, True, False, False, 0.0, 0.0),
    ModelInfo("qianfan", "ernie-4.5-turbo-32k", "ERNIE 4.5 Turbo 32K", 4096, 32_000, True, False, False, 0.0, 0.0),
    ModelInfo("qianfan", "ernie-x1-32k", "ERNIE X1 32K", 4096, 32_000, True, False, True, 0.0, 0.0),
    ModelInfo("qianfan", "ernie-5.0-thinking-latest", "ERNIE 5.0 Thinking", 4096, 32_000, True, False, True, 0.0, 0.0),

    # ═══════════════════════════════════════════════════════════════════
    # MiniMax — https://www.minimax.chat/
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("minimax", "MiniMax-M2.5", "MiniMax M2.5", 8192, 204_800, True, False, False, 0.0, 0.0),
    ModelInfo("minimax", "MiniMax-M2.1", "MiniMax M2.1", 8192, 204_800, True, False, False, 0.0, 0.0),

    # ═══════════════════════════════════════════════════════════════════
    # SiliconFlow — https://siliconflow.cn/
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("siliconflow", "deepseek-ai/DeepSeek-V3", "DeepSeek V3 (SF)", 8192, 64_000, True, False, False, 0.0, 0.0),
    ModelInfo("siliconflow", "deepseek-ai/DeepSeek-R1", "DeepSeek R1 (SF)", 8192, 64_000, True, False, True, 0.0, 0.0),
    ModelInfo("siliconflow", "Qwen/QwQ-32B", "QwQ 32B (SF)", 8192, 32_768, True, False, True, 0.0, 0.0),
    ModelInfo("siliconflow", "Qwen/Qwen2.5-72B-Instruct", "Qwen2.5 72B (SF)", 8192, 32_768, True, False, False, 0.0, 0.0),
    ModelInfo("siliconflow", "THUDM/GLM-4-32B-0414", "GLM-4 32B (SF)", 8192, 128_000, True, False, False, 0.0, 0.0),

    # ═══════════════════════════════════════════════════════════════════
    # Groq — https://groq.com/
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("groq", "llama-3.3-70b-versatile", "Llama 3.3 70B", 8192, 131_072, True, False, False, 0.0, 0.0),
    ModelInfo("groq", "llama-3.1-8b-instant", "Llama 3.1 8B", 8192, 131_072, True, False, False, 0.0, 0.0),

    # ═══════════════════════════════════════════════════════════════════
    # Perplexity — https://docs.perplexity.ai/
    # ═══════════════════════════════════════════════════════════════════
    ModelInfo("perplexity", "sonar-pro", "Sonar Pro", 8192, 128_000, True, False, False, 0.0, 0.0),
    ModelInfo("perplexity", "sonar", "Sonar", 8192, 128_000, True, False, False, 0.0, 0.0),
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
        """Return providers that have at least one model in the catalog."""
        providers_with_models = {m.provider for m in self._models.values()}
        return [
            {"id": pid, "name": meta["name"]}
            for pid, meta in _KNOWN_PROVIDERS.items()
            if pid in providers_with_models
        ]

    def default_model_for_provider(self, provider: str) -> str:
        """Return the default model ID for a provider."""
        meta = _KNOWN_PROVIDERS.get(provider)
        if meta:
            dm = meta.get("default_model", "")
            if self.get(provider, dm):
                return dm
        models = self.list_models(provider)
        return models[0].model_id if models else ""

    def validate_model_for_provider(self, provider: str, model_id: str) -> bool:
        """Check whether *model_id* belongs to *provider* in the catalog."""
        return self.get(provider, model_id) is not None

    def provider_info(self, provider: str) -> dict[str, Any] | None:
        """Return metadata dict for a known provider (or None)."""
        return _KNOWN_PROVIDERS.get(provider)

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
