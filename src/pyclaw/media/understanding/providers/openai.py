"""OpenAI media understanding provider — image description and audio transcription."""

from __future__ import annotations

import base64
import logging
from typing import Any

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


class OpenAIMediaProvider:
    """Image description via GPT-4 Vision, audio transcription via Whisper."""

    @property
    def id(self) -> str:
        return "openai"

    @property
    def capabilities(self) -> list[MediaCapability]:
        return [MediaCapability.IMAGE, MediaCapability.AUDIO]

    async def describe_image(self, request: ImageDescriptionRequest) -> ImageDescriptionResult:
        try:
            import openai
        except ImportError:
            return ImageDescriptionResult(text="openai package not installed")

        client = openai.AsyncOpenAI(
            api_key=request.api_key or None,
            base_url=request.base_url or None,
        )

        b64 = base64.b64encode(request.buffer).decode("ascii")
        data_url = f"data:{request.mime};base64,{b64}"

        response = await client.chat.completions.create(
            model=request.model or "gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": (request.prompt or "Describe this image in detail.")},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=request.max_tokens,
        )

        text = response.choices[0].message.content or ""
        return ImageDescriptionResult(text=text, model=response.model)

    async def transcribe_audio(self, request: AudioTranscriptionRequest) -> AudioTranscriptionResult:
        try:
            import openai
        except ImportError:
            return AudioTranscriptionResult(text="openai package not installed")

        client = openai.AsyncOpenAI(
            api_key=request.api_key or None,
            base_url=request.base_url or None,
        )

        import io

        file_obj = io.BytesIO(request.buffer)
        file_obj.name = request.file_name or "audio.wav"

        transcribe_kwargs: dict[str, Any] = {
            "model": request.model or "whisper-1",
            "file": file_obj,
        }
        if request.language:
            transcribe_kwargs["language"] = request.language
        if request.prompt:
            transcribe_kwargs["prompt"] = request.prompt
        response = await client.audio.transcriptions.create(**transcribe_kwargs)

        return AudioTranscriptionResult(text=response.text, model=request.model or "whisper-1")

    async def describe_video(self, request: VideoDescriptionRequest) -> VideoDescriptionResult:
        return VideoDescriptionResult(text="Video description not supported by OpenAI provider")
