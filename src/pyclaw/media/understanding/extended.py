"""Extended media understanding providers — Groq, Mistral, Deepgram, xAI.

Ported from ``src/media/understanding/providers/`` in the TypeScript codebase.

Provides:
- Groq audio/vision understanding adapter
- Mistral vision understanding adapter
- Deepgram audio transcription adapter
- xAI (Zai) vision understanding adapter
- Unified provider interface
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class MediaInputType(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


@dataclass
class UnderstandingRequest:
    """Request for media understanding."""

    input_type: MediaInputType
    url: str = ""
    data: bytes = b""
    mime_type: str = ""
    prompt: str = ""
    language: str = "en"
    max_tokens: int = 4096


@dataclass
class UnderstandingResult:
    """Result from media understanding."""

    text: str
    provider: str
    model: str = ""
    tokens_used: int = 0
    duration_ms: float = 0
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class UnderstandingProvider(Protocol):
    """Protocol for media understanding providers."""

    @property
    def name(self) -> str: ...
    @property
    def supported_types(self) -> list[MediaInputType]: ...
    def build_request(self, req: UnderstandingRequest) -> dict[str, Any]: ...
    def parse_response(self, response: dict[str, Any]) -> UnderstandingResult: ...


# ---------------------------------------------------------------------------
# Groq Provider
# ---------------------------------------------------------------------------


@dataclass
class GroqConfig:
    api_key: str = ""
    base_url: str = "https://api.groq.com/openai/v1"
    vision_model: str = "llama-3.2-90b-vision-preview"
    audio_model: str = "whisper-large-v3-turbo"


class GroqUnderstandingProvider:
    """Groq provider for vision and audio understanding."""

    def __init__(self, config: GroqConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "groq"

    @property
    def supported_types(self) -> list[MediaInputType]:
        return [MediaInputType.IMAGE, MediaInputType.AUDIO]

    def build_request(self, req: UnderstandingRequest) -> dict[str, Any]:
        if req.input_type == MediaInputType.AUDIO:
            return {
                "url": f"{self._config.base_url}/audio/transcriptions",
                "model": self._config.audio_model,
                "headers": {"Authorization": f"Bearer {self._config.api_key}"},
                "body": {"model": self._config.audio_model, "language": req.language},
            }

        return {
            "url": f"{self._config.base_url}/chat/completions",
            "model": self._config.vision_model,
            "headers": {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": self._config.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": req.prompt or "Describe this image."},
                            {"type": "image_url", "image_url": {"url": req.url}},
                        ],
                    }
                ],
                "max_tokens": req.max_tokens,
            },
        }

    def parse_response(self, response: dict[str, Any]) -> UnderstandingResult:
        if "text" in response:
            return UnderstandingResult(text=response["text"], provider="groq", model=self._config.audio_model)
        choices = response.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            return UnderstandingResult(text=content, provider="groq", model=self._config.vision_model)
        return UnderstandingResult(text="", provider="groq")


# ---------------------------------------------------------------------------
# Mistral Provider
# ---------------------------------------------------------------------------


@dataclass
class MistralConfig:
    api_key: str = ""
    base_url: str = "https://api.mistral.ai/v1"
    model: str = "pixtral-large-latest"


class MistralUnderstandingProvider:
    """Mistral provider for vision understanding."""

    def __init__(self, config: MistralConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "mistral"

    @property
    def supported_types(self) -> list[MediaInputType]:
        return [MediaInputType.IMAGE]

    def build_request(self, req: UnderstandingRequest) -> dict[str, Any]:
        return {
            "url": f"{self._config.base_url}/chat/completions",
            "model": self._config.model,
            "headers": {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": self._config.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": req.prompt or "Describe this image."},
                            {"type": "image_url", "image_url": {"url": req.url}},
                        ],
                    }
                ],
                "max_tokens": req.max_tokens,
            },
        }

    def parse_response(self, response: dict[str, Any]) -> UnderstandingResult:
        choices = response.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = response.get("usage", {})
        return UnderstandingResult(
            text=content,
            provider="mistral",
            model=self._config.model,
            tokens_used=usage.get("total_tokens", 0),
        )


# ---------------------------------------------------------------------------
# Deepgram Provider
# ---------------------------------------------------------------------------


@dataclass
class DeepgramConfig:
    api_key: str = ""
    base_url: str = "https://api.deepgram.com/v1"
    model: str = "nova-2"
    language: str = "en"


class DeepgramUnderstandingProvider:
    """Deepgram provider for audio transcription."""

    def __init__(self, config: DeepgramConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "deepgram"

    @property
    def supported_types(self) -> list[MediaInputType]:
        return [MediaInputType.AUDIO]

    def build_request(self, req: UnderstandingRequest) -> dict[str, Any]:
        params = f"model={self._config.model}&language={req.language or self._config.language}"
        return {
            "url": f"{self._config.base_url}/listen?{params}",
            "model": self._config.model,
            "headers": {
                "Authorization": f"Token {self._config.api_key}",
                "Content-Type": req.mime_type or "audio/wav",
            },
            "body_type": "binary",
        }

    def parse_response(self, response: dict[str, Any]) -> UnderstandingResult:
        results = response.get("results", {})
        channels = results.get("channels", [])
        if channels:
            alternatives = channels[0].get("alternatives", [])
            if alternatives:
                transcript = alternatives[0].get("transcript", "")
                confidence = alternatives[0].get("confidence", 0.0)
                return UnderstandingResult(
                    text=transcript,
                    provider="deepgram",
                    model=self._config.model,
                    confidence=confidence,
                )
        return UnderstandingResult(text="", provider="deepgram")


# ---------------------------------------------------------------------------
# xAI (Zai) Provider
# ---------------------------------------------------------------------------


@dataclass
class XAIConfig:
    api_key: str = ""
    base_url: str = "https://api.x.ai/v1"
    model: str = "grok-2-vision-1212"


class XAIUnderstandingProvider:
    """xAI (Grok) provider for vision understanding."""

    def __init__(self, config: XAIConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "xai"

    @property
    def supported_types(self) -> list[MediaInputType]:
        return [MediaInputType.IMAGE]

    def build_request(self, req: UnderstandingRequest) -> dict[str, Any]:
        return {
            "url": f"{self._config.base_url}/chat/completions",
            "model": self._config.model,
            "headers": {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": self._config.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": req.prompt or "Describe this image."},
                            {"type": "image_url", "image_url": {"url": req.url}},
                        ],
                    }
                ],
                "max_tokens": req.max_tokens,
            },
        }

    def parse_response(self, response: dict[str, Any]) -> UnderstandingResult:
        choices = response.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""
        return UnderstandingResult(text=content, provider="xai", model=self._config.model)


# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------

ALL_EXTENDED_PROVIDERS = {
    "groq": GroqUnderstandingProvider,
    "mistral": MistralUnderstandingProvider,
    "deepgram": DeepgramUnderstandingProvider,
    "xai": XAIUnderstandingProvider,
}


def select_provider(
    providers: list[Any],
    input_type: MediaInputType,
) -> Any | None:
    """Select the first provider that supports the given input type."""
    for p in providers:
        if input_type in p.supported_types:
            return p
    return None
