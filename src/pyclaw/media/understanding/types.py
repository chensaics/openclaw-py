"""Types for media understanding providers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class MediaCapability(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass
class MediaAttachment:
    path: str | None = None
    url: str | None = None
    mime: str | None = None
    index: int = 0
    already_transcribed: bool = False
    buffer: bytes | None = None


@dataclass
class MediaUnderstandingOutput:
    kind: MediaCapability
    attachment_index: int
    text: str = ""
    provider: str = ""
    model: str = ""


@dataclass
class ImageDescriptionRequest:
    buffer: bytes
    file_name: str = ""
    mime: str = "image/jpeg"
    model: str = ""
    provider: str = ""
    prompt: str = ""
    max_tokens: int = 1024
    timeout_ms: int = 30_000
    api_key: str = ""
    base_url: str = ""


@dataclass
class ImageDescriptionResult:
    text: str = ""
    model: str = ""


@dataclass
class AudioTranscriptionRequest:
    buffer: bytes
    file_name: str = ""
    mime: str = "audio/wav"
    model: str = ""
    language: str = ""
    prompt: str = ""
    timeout_ms: int = 60_000
    api_key: str = ""
    base_url: str = ""


@dataclass
class AudioTranscriptionResult:
    text: str = ""
    model: str = ""


@dataclass
class VideoDescriptionRequest:
    buffer: bytes
    file_name: str = ""
    mime: str = "video/mp4"
    model: str = ""
    prompt: str = ""
    timeout_ms: int = 60_000
    api_key: str = ""
    base_url: str = ""


@dataclass
class VideoDescriptionResult:
    text: str = ""
    model: str = ""


class MediaUnderstandingProvider(Protocol):
    """Protocol for media understanding providers."""

    @property
    def id(self) -> str: ...

    @property
    def capabilities(self) -> list[MediaCapability]: ...

    async def describe_image(self, request: ImageDescriptionRequest) -> ImageDescriptionResult: ...

    async def transcribe_audio(self, request: AudioTranscriptionRequest) -> AudioTranscriptionResult: ...

    async def describe_video(self, request: VideoDescriptionRequest) -> VideoDescriptionResult: ...
