"""Provider registry for media understanding."""

from __future__ import annotations

import logging

from pyclaw.media.understanding.providers.anthropic import AnthropicMediaProvider
from pyclaw.media.understanding.providers.google import GoogleMediaProvider
from pyclaw.media.understanding.providers.openai import OpenAIMediaProvider
from pyclaw.media.understanding.types import MediaCapability, MediaUnderstandingProvider

logger = logging.getLogger(__name__)


def build_media_understanding_registry(
    overrides: dict[str, MediaUnderstandingProvider] | None = None,
) -> dict[str, MediaUnderstandingProvider]:
    """Build the default provider registry, with optional overrides."""
    registry: dict[str, MediaUnderstandingProvider] = {
        "openai": OpenAIMediaProvider(),
        "google": GoogleMediaProvider(),
        "anthropic": AnthropicMediaProvider(),
    }
    if overrides:
        registry.update(overrides)
    return registry


def resolve_provider_for_capability(
    capability: MediaCapability,
    registry: dict[str, MediaUnderstandingProvider],
    preferred: str | None = None,
) -> MediaUnderstandingProvider | None:
    """Find a provider that supports the given capability."""
    if preferred and preferred in registry:
        p = registry[preferred]
        if capability in p.capabilities:
            return p

    for p in registry.values():
        if capability in p.capabilities:
            return p
    return None
