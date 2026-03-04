"""Google (Gemini) media understanding provider."""

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


class GoogleMediaProvider:
    """Image, audio, and video via Gemini multimodal API."""

    @property
    def id(self) -> str:
        return "google"

    @property
    def capabilities(self) -> list[MediaCapability]:
        return [MediaCapability.IMAGE, MediaCapability.AUDIO, MediaCapability.VIDEO]

    async def describe_image(self, request: ImageDescriptionRequest) -> ImageDescriptionResult:
        try:
            import google.generativeai as genai
        except ImportError:
            return ImageDescriptionResult(text="google-generativeai package not installed")

        if request.api_key:
            genai.configure(api_key=request.api_key)  # type: ignore[attr-defined]

        model = genai.GenerativeModel(request.model or "gemini-2.0-flash")  # type: ignore[attr-defined]
        b64 = base64.b64encode(request.buffer).decode("ascii")

        response = await model.generate_content_async(
            [
                request.prompt or "Describe this image in detail.",
                {"mime_type": request.mime, "data": b64},
            ]
        )

        return ImageDescriptionResult(
            text=response.text or "",
            model=request.model or "gemini-2.0-flash",
        )

    async def transcribe_audio(self, request: AudioTranscriptionRequest) -> AudioTranscriptionResult:
        try:
            import google.generativeai as genai
        except ImportError:
            return AudioTranscriptionResult(text="google-generativeai package not installed")

        if request.api_key:
            genai.configure(api_key=request.api_key)  # type: ignore[attr-defined]

        model = genai.GenerativeModel(request.model or "gemini-2.0-flash")  # type: ignore[attr-defined]
        b64 = base64.b64encode(request.buffer).decode("ascii")

        response = await model.generate_content_async(
            [
                request.prompt or "Transcribe this audio recording accurately.",
                {"mime_type": request.mime, "data": b64},
            ]
        )

        return AudioTranscriptionResult(
            text=response.text or "",
            model=request.model or "gemini-2.0-flash",
        )

    async def describe_video(self, request: VideoDescriptionRequest) -> VideoDescriptionResult:
        try:
            import google.generativeai as genai
        except ImportError:
            return VideoDescriptionResult(text="google-generativeai package not installed")

        if request.api_key:
            genai.configure(api_key=request.api_key)  # type: ignore[attr-defined]

        model = genai.GenerativeModel(request.model or "gemini-2.0-flash")  # type: ignore[attr-defined]
        b64 = base64.b64encode(request.buffer).decode("ascii")

        response = await model.generate_content_async(
            [
                request.prompt or "Describe this video in detail.",
                {"mime_type": request.mime, "data": b64},
            ]
        )

        return VideoDescriptionResult(
            text=response.text or "",
            model=request.model or "gemini-2.0-flash",
        )
