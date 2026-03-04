"""Model overrides — channel/group-level model selection and capability schema.

Ported from ``src/channels/channel-plugin-sdk/model-overrides*.ts``.

Provides:
- Per-channel model override configuration
- Per-group model override
- Channel capability schema for model selection
- Override resolution (group > channel > default)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ModelOverride:
    """A model override specification."""

    model: str
    think_level: str = ""  # "low" | "medium" | "high" | ""
    max_tokens: int = 0
    temperature: float | None = None
    reason: str = ""  # Why override was applied


@dataclass
class ChannelModelConfig:
    """Model configuration at the channel level."""

    default_model: str = ""
    allowed_models: list[str] = field(default_factory=list)
    blocked_models: list[str] = field(default_factory=list)
    group_overrides: dict[str, ModelOverride] = field(default_factory=dict)
    think_level: str = ""


@dataclass
class CapabilitySchema:
    """Channel capability schema for model selection."""

    supports_streaming: bool = True
    supports_tools: bool = True
    supports_vision: bool = False
    supports_audio: bool = False
    max_message_length: int = 4096
    max_media_size_mb: int = 20
    supported_media_types: list[str] = field(default_factory=lambda: ["image", "document"])


class ModelOverrideResolver:
    """Resolve model overrides from channel/group configuration."""

    def __init__(self) -> None:
        self._channel_configs: dict[str, ChannelModelConfig] = {}

    def set_channel_config(self, channel_id: str, config: ChannelModelConfig) -> None:
        self._channel_configs[channel_id] = config

    def get_channel_config(self, channel_id: str) -> ChannelModelConfig | None:
        return self._channel_configs.get(channel_id)

    def resolve(
        self,
        channel_id: str,
        group_id: str = "",
        default_model: str = "",
    ) -> ModelOverride | None:
        """Resolve the effective model override.

        Priority: group override > channel default > None
        """
        config = self._channel_configs.get(channel_id)
        if not config:
            return None

        # Group-level override
        if group_id and group_id in config.group_overrides:
            override = config.group_overrides[group_id]
            return ModelOverride(
                model=override.model,
                think_level=override.think_level or config.think_level,
                max_tokens=override.max_tokens,
                temperature=override.temperature,
                reason=f"group:{group_id}",
            )

        # Channel-level default
        if config.default_model:
            return ModelOverride(
                model=config.default_model,
                think_level=config.think_level,
                reason=f"channel:{channel_id}",
            )

        return None

    def is_model_allowed(self, channel_id: str, model: str) -> bool:
        """Check if a model is allowed for a channel."""
        config = self._channel_configs.get(channel_id)
        if not config:
            return True  # No restrictions

        if config.blocked_models and model in config.blocked_models:
            return False

        return not (config.allowed_models and model not in config.allowed_models)

    def list_allowed_models(self, channel_id: str) -> list[str] | None:
        """List explicitly allowed models for a channel, or None if unrestricted."""
        config = self._channel_configs.get(channel_id)
        if not config or not config.allowed_models:
            return None
        return list(config.allowed_models)
