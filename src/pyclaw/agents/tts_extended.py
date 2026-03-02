"""Extended TTS — ElevenLabs, OpenAI TTS providers, auto mode, long-text summary.

Ported from ``src/agents/tts*.ts``.

Provides:
- ElevenLabs TTS provider adapter
- OpenAI TTS provider adapter
- Auto mode (off/always/inbound/tagged)
- Long text summarization before synthesis
- Voice name validation
- TTS directive processing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class TTSAutoMode(str, Enum):
    OFF = "off"
    ALWAYS = "always"
    INBOUND = "inbound"       # Only when user sent audio
    TAGGED = "tagged"         # Only with /tts or @tts directive


@dataclass
class TTSConfig:
    """Global TTS configuration."""
    auto_mode: TTSAutoMode = TTSAutoMode.OFF
    default_provider: str = "edge-tts"
    default_voice: str = ""
    max_text_length: int = 4096
    summarize_long_text: bool = True
    summary_max_length: int = 500


@dataclass
class TTSRequest:
    """Request for text-to-speech synthesis."""
    text: str
    voice: str = ""
    provider: str = ""
    language: str = ""
    speed: float = 1.0


@dataclass
class TTSResult:
    """Result from TTS synthesis."""
    audio_data: bytes = b""
    audio_url: str = ""
    mime_type: str = "audio/mpeg"
    provider: str = ""
    voice: str = ""
    duration_s: float = 0.0
    error: str = ""

    @property
    def success(self) -> bool:
        return bool(self.audio_data or self.audio_url) and not self.error


class TTSProvider(Protocol):
    """Protocol for TTS providers."""
    @property
    def name(self) -> str: ...
    @property
    def available_voices(self) -> list[str]: ...
    def build_request(self, req: TTSRequest) -> dict[str, Any]: ...
    def validate_voice(self, voice: str) -> bool: ...


# ---------------------------------------------------------------------------
# ElevenLabs Provider
# ---------------------------------------------------------------------------

@dataclass
class ElevenLabsConfig:
    api_key: str = ""
    base_url: str = "https://api.elevenlabs.io/v1"
    model_id: str = "eleven_multilingual_v2"
    default_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel


ELEVENLABS_VOICES: dict[str, str] = {
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "adam": "pNInz6obpgDQGcFmaJgB",
    "antoni": "ErXwobaYiN019PkySvjV",
    "bella": "EXAVITQu4vr4xnSDxMaL",
    "domi": "AZnzlk1XvdvUeBnXmlld",
    "elli": "MF3mGyEYCl7XYWbV9V6O",
    "josh": "TxGEqnHWrfWFTfGW9XjX",
    "sam": "yoZ06aMxZJJ28mfd3POQ",
}


class ElevenLabsTTSProvider:
    """ElevenLabs TTS provider."""

    def __init__(self, config: ElevenLabsConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "elevenlabs"

    @property
    def available_voices(self) -> list[str]:
        return list(ELEVENLABS_VOICES.keys())

    def validate_voice(self, voice: str) -> bool:
        return voice.lower() in ELEVENLABS_VOICES

    def resolve_voice_id(self, voice: str) -> str:
        return ELEVENLABS_VOICES.get(voice.lower(), self._config.default_voice_id)

    def build_request(self, req: TTSRequest) -> dict[str, Any]:
        voice_id = self.resolve_voice_id(req.voice) if req.voice else self._config.default_voice_id
        return {
            "url": f"{self._config.base_url}/text-to-speech/{voice_id}",
            "headers": {
                "xi-api-key": self._config.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            "body": {
                "text": req.text,
                "model_id": self._config.model_id,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            },
        }


# ---------------------------------------------------------------------------
# OpenAI TTS Provider
# ---------------------------------------------------------------------------

@dataclass
class OpenAITTSConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "tts-1"
    default_voice: str = "alloy"


OPENAI_TTS_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


class OpenAITTSProvider:
    """OpenAI TTS provider."""

    def __init__(self, config: OpenAITTSConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "openai-tts"

    @property
    def available_voices(self) -> list[str]:
        return list(OPENAI_TTS_VOICES)

    def validate_voice(self, voice: str) -> bool:
        return voice.lower() in OPENAI_TTS_VOICES

    def build_request(self, req: TTSRequest) -> dict[str, Any]:
        voice = req.voice if req.voice and self.validate_voice(req.voice) else self._config.default_voice
        return {
            "url": f"{self._config.base_url}/audio/speech",
            "headers": {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": self._config.model,
                "input": req.text,
                "voice": voice,
                "speed": req.speed,
                "response_format": "mp3",
            },
        }


# ---------------------------------------------------------------------------
# TTS Helpers
# ---------------------------------------------------------------------------

def should_synthesize(
    config: TTSConfig,
    *,
    has_tts_directive: bool = False,
    inbound_has_audio: bool = False,
) -> bool:
    """Determine if TTS should be performed based on auto mode."""
    if config.auto_mode == TTSAutoMode.OFF:
        return False
    if config.auto_mode == TTSAutoMode.ALWAYS:
        return True
    if config.auto_mode == TTSAutoMode.INBOUND:
        return inbound_has_audio
    if config.auto_mode == TTSAutoMode.TAGGED:
        return has_tts_directive
    return False


def prepare_text_for_tts(
    text: str,
    config: TTSConfig,
    *,
    summarize_fn: Any = None,
) -> str:
    """Prepare text for TTS, optionally summarizing long text."""
    if len(text) <= config.max_text_length:
        return text

    if config.summarize_long_text and summarize_fn:
        return summarize_fn(text, config.summary_max_length)

    return text[:config.max_text_length]


def parse_tts_directive(text: str) -> tuple[bool, str, str]:
    """Parse /tts or @tts directive from text.

    Returns (has_directive, voice_override, cleaned_text).
    """
    stripped = text.strip()

    if stripped.startswith("/tts"):
        rest = stripped[4:].strip()
        parts = rest.split(maxsplit=1)
        if len(parts) >= 2 and not parts[0].startswith("/"):
            return True, parts[0], parts[1]
        return True, "", rest

    if "@tts" in stripped:
        cleaned = stripped.replace("@tts", "").strip()
        return True, "", cleaned

    return False, "", text
