"""Provider registry — unified provider registration, discovery, config parsing.

Ported from ``src/agents/providers/provider-registry.ts``.

Provides:
- Provider registration and lookup
- Configuration parsing from user config
- Provider builder protocol
- Discovery of available providers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from .cn_providers import ALL_CN_PROVIDERS, build_cn_config
from .openai_compat import (
    PRECONFIGURED_PROVIDERS,
    OpenAICompatProvider,
)

logger = logging.getLogger(__name__)


class ProviderBuilder(Protocol):
    """Protocol for constructing a provider from config."""

    def build(self, config: dict[str, Any]) -> OpenAICompatProvider: ...


@dataclass
class ProviderInfo:
    """Metadata about a registered provider."""

    name: str
    display_name: str = ""
    category: str = "generic"  # "generic" | "cn" | "cloud" | "oauth"
    requires_api_key: bool = True
    requires_oauth: bool = False
    docs_url: str = ""
    models: list[str] = field(default_factory=list)


class ProviderRegistry:
    """Central registry for all LLM providers."""

    def __init__(self) -> None:
        self._providers: dict[str, OpenAICompatProvider] = {}
        self._info: dict[str, ProviderInfo] = {}
        self._builders: dict[str, ProviderBuilder] = {}

    def register(
        self,
        provider: OpenAICompatProvider,
        info: ProviderInfo | None = None,
    ) -> None:
        name = provider.name
        self._providers[name] = provider
        if info:
            self._info[name] = info
        else:
            self._info[name] = ProviderInfo(
                name=name,
                models=provider.list_models(),
            )

    def register_builder(self, name: str, builder: ProviderBuilder) -> None:
        self._builders[name] = builder

    def get(self, name: str) -> OpenAICompatProvider | None:
        return self._providers.get(name)

    def get_info(self, name: str) -> ProviderInfo | None:
        return self._info.get(name)

    def list_providers(self, *, category: str = "") -> list[ProviderInfo]:
        infos = list(self._info.values())
        if category:
            infos = [i for i in infos if i.category == category]
        return sorted(infos, key=lambda i: i.name)

    def list_all_models(self) -> dict[str, list[str]]:
        """Return all available models grouped by provider."""
        result: dict[str, list[str]] = {}
        for name, provider in self._providers.items():
            result[name] = provider.list_models()
        return result

    def resolve_model(self, qualified_name: str) -> tuple[str, str]:
        """Resolve ``provider/model`` to (provider_name, model_id).

        If no ``/`` separator, search all providers for the model alias.
        """
        if "/" in qualified_name:
            parts = qualified_name.split("/", 1)
            provider_name = parts[0]
            model = parts[1]
            provider = self._providers.get(provider_name)
            if provider:
                return provider_name, provider.resolve_model(model)
            return provider_name, model

        for name, provider in self._providers.items():
            if qualified_name in [m.alias for m in (provider._config.models or [])]:
                return name, provider.resolve_model(qualified_name)

        return "", qualified_name

    def build_from_config(self, name: str, config: dict[str, Any]) -> OpenAICompatProvider | None:
        """Build and register a provider from user configuration."""
        builder = self._builders.get(name)
        if builder:
            provider = builder.build(config)
            self.register(provider)
            return provider

        return None

    def unregister(self, name: str) -> bool:
        removed = self._providers.pop(name, None) is not None
        self._info.pop(name, None)
        return removed

    @property
    def provider_count(self) -> int:
        return len(self._providers)


def create_default_registry() -> ProviderRegistry:
    """Create a registry with all known providers (requires API keys to activate)."""
    registry = ProviderRegistry()

    # Register preconfigured OpenAI-compat providers as info entries
    for name, builder_fn in PRECONFIGURED_PROVIDERS.items():
        config = builder_fn("__placeholder__")
        registry._info[name] = ProviderInfo(
            name=name,
            category="generic",
            models=[m.alias for m in config.models],
        )

    # Register Chinese providers as info entries
    for name, spec in ALL_CN_PROVIDERS.items():
        registry._info[name] = ProviderInfo(
            name=name,
            display_name=spec.display_name,
            category="cn",
            docs_url=spec.docs_url,
            models=[m.alias for m in spec.models],
        )

    # Add OAuth-based providers
    for name in ("copilot", "minimax-portal", "qwen-portal"):
        registry._info[name] = ProviderInfo(
            name=name,
            category="oauth",
            requires_api_key=False,
            requires_oauth=True,
        )

    # Add cloud providers
    registry._info["bedrock"] = ProviderInfo(
        name="bedrock",
        display_name="Amazon Bedrock",
        category="cloud",
        requires_api_key=False,
        docs_url="https://docs.aws.amazon.com/bedrock",
    )

    return registry


def activate_provider(
    registry: ProviderRegistry,
    name: str,
    api_key: str,
) -> OpenAICompatProvider | None:
    """Activate a provider by supplying its API key."""
    # Preconfigured OpenAI-compat
    if name in PRECONFIGURED_PROVIDERS:
        config = PRECONFIGURED_PROVIDERS[name](api_key)
        provider = OpenAICompatProvider(config)
        registry.register(provider)
        return provider

    # Chinese providers
    if name in ALL_CN_PROVIDERS:
        spec = ALL_CN_PROVIDERS[name]
        config = build_cn_config(spec, api_key)
        provider = OpenAICompatProvider(config)
        info = ProviderInfo(
            name=name,
            display_name=spec.display_name,
            category="cn",
            docs_url=spec.docs_url,
            models=[m.alias for m in spec.models],
        )
        registry.register(provider, info)
        return provider

    return None
