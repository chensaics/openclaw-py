"""Models CLI — list, auth, aliases, fallbacks, provider info.

Ported from ``src/commands/models/*.ts``.

Provides:
- Model listing with provider/capability info
- Provider authentication status
- Model alias management
- Fallback chain configuration
- Image model fallback resolution
- Model selector (interactive)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import json
import os

import typer

from pyclaw.cli.commands.models_deep import format_auth_table
from pyclaw.cli.commands.models_deep import format_models_table
from pyclaw.cli.commands.models_deep import get_auth_overview
from pyclaw.cli.commands.models_deep import probe_model
from pyclaw.cli.commands.models_deep import scan_providers
from pyclaw.config.io import load_config
from pyclaw.config.paths import resolve_config_path


class ModelCapability(str, Enum):
    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"
    CODE = "code"
    EMBEDDING = "embedding"
    IMAGE_GEN = "image_gen"


@dataclass
class ModelInfo:
    """Information about a specific model."""
    model_id: str
    display_name: str
    provider: str
    capabilities: list[ModelCapability] = field(default_factory=list)
    context_window: int = 0
    max_output: int = 0
    supports_streaming: bool = True
    supports_tools: bool = True
    is_default: bool = False


@dataclass
class ModelAlias:
    """A model alias mapping."""
    alias: str
    model_id: str
    provider: str = ""


@dataclass
class FallbackChain:
    """A model fallback chain."""
    primary: str
    fallbacks: list[str] = field(default_factory=list)


@dataclass
class ProviderStatus:
    """Auth and availability status for a provider."""
    provider_id: str
    display_name: str
    authenticated: bool = False
    model_count: int = 0
    default_model: str = ""


# ---------------------------------------------------------------------------
# Built-in Model Registry
# ---------------------------------------------------------------------------

BUILTIN_MODELS: list[ModelInfo] = [
    ModelInfo("gpt-4o", "GPT-4o", "openai", [ModelCapability.TEXT, ModelCapability.VISION], 128000, 16384),
    ModelInfo("gpt-4o-mini", "GPT-4o Mini", "openai", [ModelCapability.TEXT, ModelCapability.VISION], 128000, 16384),
    ModelInfo("o3-mini", "o3-mini", "openai", [ModelCapability.TEXT], 200000, 100000),
    ModelInfo("claude-sonnet-4-20250514", "Claude Sonnet 4", "anthropic", [ModelCapability.TEXT, ModelCapability.VISION], 200000, 64000),
    ModelInfo("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", "anthropic", [ModelCapability.TEXT], 200000, 8192),
    ModelInfo("gemini-2.0-flash", "Gemini 2.0 Flash", "google", [ModelCapability.TEXT, ModelCapability.VISION, ModelCapability.AUDIO], 1048576, 8192),
    ModelInfo("gemini-2.5-pro-preview-05-06", "Gemini 2.5 Pro", "google", [ModelCapability.TEXT, ModelCapability.VISION], 1048576, 65536),
    ModelInfo("deepseek-chat", "DeepSeek V3", "deepseek", [ModelCapability.TEXT, ModelCapability.CODE], 64000, 8192),
    ModelInfo("deepseek-reasoner", "DeepSeek R1", "deepseek", [ModelCapability.TEXT], 64000, 8192),
    ModelInfo("moonshot-v1-128k", "Moonshot v1 128K", "moonshot", [ModelCapability.TEXT], 128000, 8192),
    ModelInfo("qwen-max", "Qwen Max", "qwen", [ModelCapability.TEXT], 32000, 8192),
    ModelInfo("glm-4-plus", "GLM-4 Plus", "zhipu", [ModelCapability.TEXT], 128000, 4096),
]

DEFAULT_ALIASES: list[ModelAlias] = [
    ModelAlias("default", "gpt-4o", "openai"),
    ModelAlias("fast", "gpt-4o-mini", "openai"),
    ModelAlias("smart", "claude-sonnet-4-20250514", "anthropic"),
    ModelAlias("reasoning", "o3-mini", "openai"),
    ModelAlias("code", "deepseek-chat", "deepseek"),
]

DEFAULT_FALLBACK_CHAINS: list[FallbackChain] = [
    FallbackChain("gpt-4o", ["claude-sonnet-4-20250514", "gemini-2.0-flash"]),
    FallbackChain("claude-sonnet-4-20250514", ["gpt-4o", "gemini-2.5-pro-preview-05-06"]),
]


class ModelRegistry:
    """Registry for models, aliases, and fallbacks."""

    def __init__(self) -> None:
        self._models: list[ModelInfo] = list(BUILTIN_MODELS)
        self._aliases: dict[str, ModelAlias] = {a.alias: a for a in DEFAULT_ALIASES}
        self._fallbacks: dict[str, FallbackChain] = {f.primary: f for f in DEFAULT_FALLBACK_CHAINS}

    def list_models(self, *, provider: str = "", capability: ModelCapability | None = None) -> list[ModelInfo]:
        models = self._models
        if provider:
            models = [m for m in models if m.provider == provider]
        if capability:
            models = [m for m in models if capability in m.capabilities]
        return models

    def get_model(self, model_id: str) -> ModelInfo | None:
        for m in self._models:
            if m.model_id == model_id:
                return m
        return None

    def resolve_alias(self, alias: str) -> str:
        entry = self._aliases.get(alias)
        return entry.model_id if entry else alias

    def set_alias(self, alias: str, model_id: str, provider: str = "") -> None:
        self._aliases[alias] = ModelAlias(alias=alias, model_id=model_id, provider=provider)

    def remove_alias(self, alias: str) -> bool:
        return self._aliases.pop(alias, None) is not None

    def list_aliases(self) -> list[ModelAlias]:
        return list(self._aliases.values())

    def get_fallbacks(self, model_id: str) -> list[str]:
        chain = self._fallbacks.get(model_id)
        return chain.fallbacks if chain else []

    def set_fallback_chain(self, primary: str, fallbacks: list[str]) -> None:
        self._fallbacks[primary] = FallbackChain(primary=primary, fallbacks=fallbacks)

    def resolve_image_fallback(self, model_id: str) -> str | None:
        """Find the best model with vision capability as fallback."""
        model = self.get_model(model_id)
        if model and ModelCapability.VISION in model.capabilities:
            return model_id

        vision_models = self.list_models(capability=ModelCapability.VISION)
        if vision_models:
            return vision_models[0].model_id
        return None

    def list_providers(self) -> list[str]:
        return sorted(set(m.provider for m in self._models))

    def add_model(self, model: ModelInfo) -> None:
        self._models.append(model)


def models_list_command(*, output_json: bool = False) -> None:
    """List known models from the built-in registry."""
    registry = ModelRegistry()
    models = [
        {
            "model": m.model_id,
            "provider": m.provider,
            "capabilities": [c.value for c in m.capabilities],
        }
        for m in registry.list_models()
    ]
    if output_json:
        typer.echo(json.dumps(models, ensure_ascii=False))
        return
    for item in models:
        caps = ",".join(item["capabilities"])
        typer.echo(f"{item['model']:32}  {item['provider']:10}  {caps}")


def _load_provider_keys() -> dict[str, str]:
    providers: dict[str, str] = {}
    env_candidates = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "moonshot": "MOONSHOT_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "zhipu": "ZHIPU_API_KEY",
    }
    for provider, env_key in env_candidates.items():
        value = os.environ.get(env_key)
        if value:
            providers[provider] = value

    config_path = resolve_config_path()
    if config_path.exists():
        try:
            cfg = load_config(config_path)
            if cfg.models and cfg.models.providers:
                for provider_name, provider_cfg in cfg.models.providers.items():
                    key = provider_cfg.api_key if provider_cfg else None
                    if isinstance(key, str) and key:
                        providers.setdefault(provider_name, key)
        except Exception:
            pass
    return providers


def models_status_command(
    *,
    output_json: bool = False,
    probe: bool = False,
) -> None:
    """Show a lightweight provider/model status summary."""
    registry = ModelRegistry()
    providers = registry.list_providers()
    provider_keys = _load_provider_keys()
    auth = get_auth_overview(provider_keys)
    probes = []
    if probe:
        for provider in providers:
            models = registry.list_models(provider=provider)
            if not models:
                continue
            model = models[0]
            probes.append(
                probe_model(
                    model=model.model_id,
                    provider=provider,
                    api_key=provider_keys.get(provider, ""),
                )
            )
    data: dict[str, Any] = {
        "providers": providers,
        "total_models": len(registry.list_models()),
        "default_aliases": [a.alias for a in registry.list_aliases()],
        "auth_overview": [
            {
                "provider": entry.provider,
                "configured": entry.configured,
                "auth_method": entry.auth_method,
                "key_prefix": entry.key_prefix,
            }
            for entry in auth
        ],
        "probe": [
            {
                "provider": p.provider,
                "model": p.model,
                "available": p.available,
                "error": p.error,
            }
            for p in probes
        ],
    }
    if output_json:
        typer.echo(json.dumps(data, ensure_ascii=False))
        return
    typer.echo(f"Providers: {', '.join(providers)}")
    typer.echo(f"Models: {data['total_models']}")
    typer.echo(f"Aliases: {', '.join(data['default_aliases'])}")
    if auth:
        typer.echo("\nAuth overview:")
        typer.echo(format_auth_table(auth))
    if probe and probes:
        typer.echo("\nProbe:")
        typer.echo(format_models_table(probes))


def models_scan_command(*, output_json: bool = False) -> None:
    """Scan configured providers and report availability."""
    provider_keys = _load_provider_keys()
    scan = scan_providers(provider_keys)
    if output_json:
        typer.echo(
            json.dumps(
                {
                    "total_providers": scan.total_providers,
                    "available_count": scan.available_count,
                    "scan_duration_ms": scan.scan_duration_ms,
                    "results": [
                        {
                            "provider": r.provider,
                            "model": r.model,
                            "available": r.available,
                            "error": r.error,
                        }
                        for r in scan.results
                    ],
                },
                ensure_ascii=False,
            )
        )
        return
    typer.echo(format_models_table(scan.results))


def models_probe_command(
    *,
    model: str,
    provider: str,
    api_key: str = "",
    timeout_s: float = 10.0,
    output_json: bool = False,
) -> None:
    """Probe one model/provider pair."""
    result = probe_model(model=model, provider=provider, api_key=api_key, timeout_s=timeout_s)
    payload = {
        "model": result.model,
        "provider": result.provider,
        "available": result.available,
        "error": result.error,
        "context_window": result.context_window,
        "supports_tools": result.supports_tools,
        "supports_vision": result.supports_vision,
    }
    if output_json:
        typer.echo(json.dumps(payload, ensure_ascii=False))
        return
    typer.echo(format_models_table([result]))


def models_auth_overview_command(*, output_json: bool = False) -> None:
    """Show provider auth overview."""
    auth = get_auth_overview(_load_provider_keys())
    payload = [
        {
            "provider": entry.provider,
            "configured": entry.configured,
            "auth_method": entry.auth_method,
            "key_prefix": entry.key_prefix,
        }
        for entry in auth
    ]
    if output_json:
        typer.echo(json.dumps(payload, ensure_ascii=False))
        return
    typer.echo(format_auth_table(auth))
