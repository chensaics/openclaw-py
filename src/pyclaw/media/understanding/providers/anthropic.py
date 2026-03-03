"""Anthropic media understanding provider — image description via Claude."""

from __future__ import annotations

import base64
import logging

from pyclaw.media.understanding.types import (
    AudioTranscriptionRequest,
    AudioTranscriptionResult,
    ImageDescriptionRequest,
    ImageDescriptionResult,
    MediaCapability,
    VideoDescriptionRequest,
    VideoDescriptionResult,
)

logger = logging.getLogger(__name__)


class AnthropicMediaProvider:
    """Image description via Claude Vision."""

    @property
    def id(self) -> str:
        return "anthropic"

    @property
    def capabilities(self) -> list[MediaCapability]:
        return [MediaCapability.IMAGE]

    async def describe_image(self, request: ImageDescriptionRequest) -> ImageDescriptionResult:
        try:
            import anthropic
        except ImportError:
            return ImageDescriptionResult(text="anthropic package not installed")

        client = anthropic.AsyncAnthropic(
            api_key=request.api_key or None,
            base_url=request.base_url or None,
        )

        b64 = base64.b64encode(request.buffer).decode("ascii")
        media_type = request.mime or "image/jpeg"

        response = await client.messages.create(
            model=request.model or "claude-sonnet-4-20250514",
            max_tokens=request.max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {  # type: ignore[list-item]
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": (request.prompt or "Describe this image in detail.")},
                ],
            }],
        )

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        return ImageDescriptionResult(text=text, model=response.model)

    async def transcribe_audio(self, request: AudioTranscriptionRequest) -> AudioTranscriptionResult:
        return AudioTranscriptionResult(text="Audio transcription not supported by Anthropic")

    async def describe_video(self, request: VideoDescriptionRequest) -> VideoDescriptionResult:
        return VideoDescriptionResult(text="Video description not supported by Anthropic")
