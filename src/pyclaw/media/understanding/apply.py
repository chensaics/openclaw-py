"""Apply media understanding to message attachments.

Orchestrates image, audio, and video understanding across providers.
"""

from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

from pyclaw.media.understanding.registry import (
    build_media_understanding_registry,
    resolve_provider_for_capability,
)
from pyclaw.media.understanding.types import (
    AudioTranscriptionRequest,
    ImageDescriptionRequest,
    MediaAttachment,
    MediaCapability,
    MediaUnderstandingOutput,
    MediaUnderstandingProvider,
    VideoDescriptionRequest,
)

logger = logging.getLogger(__name__)


@dataclass
class ApplyMediaUnderstandingResult:
    outputs: list[MediaUnderstandingOutput] = field(default_factory=list)
    body_additions: list[str] = field(default_factory=list)
    transcripts: list[str] = field(default_factory=list)
    echo_transcript: str = ""


def _capability_for_mime(mime: str) -> MediaCapability | None:
    if mime.startswith("image/"):
        return MediaCapability.IMAGE
    if mime.startswith("audio/"):
        return MediaCapability.AUDIO
    if mime.startswith("video/"):
        return MediaCapability.VIDEO
    return None


def _read_attachment_buffer(attachment: MediaAttachment) -> bytes | None:
    if attachment.buffer:
        return attachment.buffer
    if attachment.path:
        try:
            return Path(attachment.path).read_bytes()
        except OSError:
            return None
    return None


async def apply_media_understanding(
    attachments: list[MediaAttachment],
    *,
    api_keys: dict[str, str] | None = None,
    preferred_provider: str | None = None,
    providers: dict[str, MediaUnderstandingProvider] | None = None,
    image_prompt: str = "",
    audio_prompt: str = "",
    video_prompt: str = "",
    echo_transcript: bool = False,
) -> ApplyMediaUnderstandingResult:
    """Process media attachments through understanding providers.

    Returns descriptions and transcripts for each processed attachment.
    """
    registry = providers or build_media_understanding_registry()
    keys = api_keys or {}
    result = ApplyMediaUnderstandingResult()

    for attachment in attachments:
        mime = attachment.mime
        if not mime and attachment.path:
            mime, _ = mimetypes.guess_type(attachment.path)
        if not mime:
            continue

        capability = _capability_for_mime(mime)
        if not capability:
            continue

        if attachment.already_transcribed:
            continue

        provider = resolve_provider_for_capability(capability, registry, preferred_provider)
        if not provider:
            logger.debug("No provider for %s", capability)
            continue

        buf = _read_attachment_buffer(attachment)
        if not buf:
            continue

        api_key = keys.get(provider.id, "")

        try:
            output: MediaUnderstandingOutput | None = None

            if capability == MediaCapability.IMAGE:
                img_req = ImageDescriptionRequest(
                    buffer=buf,
                    file_name=attachment.path or "",
                    mime=mime,
                    prompt=image_prompt,
                    api_key=api_key,
                )
                img_desc = await provider.describe_image(img_req)
                output = MediaUnderstandingOutput(
                    kind=MediaCapability.IMAGE,
                    attachment_index=attachment.index,
                    text=img_desc.text or "",
                    provider=provider.id,
                    model=img_desc.model or "",
                )
                result.body_additions.append(f"[Image: {img_desc.text}]")

            elif capability == MediaCapability.AUDIO:
                if len(buf) < 1000:
                    logger.debug("Skipping tiny audio file (%d bytes)", len(buf))
                    continue
                audio_req = AudioTranscriptionRequest(
                    buffer=buf,
                    file_name=attachment.path or "",
                    mime=mime,
                    prompt=audio_prompt,
                    api_key=api_key,
                )
                trans = await provider.transcribe_audio(audio_req)
                transcript_text = trans.text or ""
                if echo_transcript and transcript_text:
                    result.body_additions.append(f"[Transcription]: {transcript_text}")
                    result.echo_transcript = transcript_text
                output = MediaUnderstandingOutput(
                    kind=MediaCapability.AUDIO,
                    attachment_index=attachment.index,
                    text=transcript_text,
                    provider=provider.id,
                    model=trans.model or "",
                )
                result.transcripts.append(transcript_text)

            elif capability == MediaCapability.VIDEO:
                video_req = VideoDescriptionRequest(
                    buffer=buf,
                    file_name=attachment.path or "",
                    mime=mime,
                    prompt=video_prompt,
                    api_key=api_key,
                )
                video_desc = await provider.describe_video(video_req)
                output = MediaUnderstandingOutput(
                    kind=MediaCapability.VIDEO,
                    attachment_index=attachment.index,
                    text=video_desc.text or "",
                    provider=provider.id,
                    model=video_desc.model or "",
                )
                result.body_additions.append(f"[Video: {video_desc.text}]")

            if output:
                result.outputs.append(output)

        except Exception:
            logger.exception("Media understanding error for %s (provider=%s)", capability, provider.id)

    return result
