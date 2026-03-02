"""MIME type detection — magic bytes and file extension based.

Ported from ``src/media/`` MIME detection utilities.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

# Magic byte signatures for common media types
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),  # needs further check for WEBP
    (b"BM", "image/bmp"),
    (b"\x00\x00\x01\x00", "image/x-icon"),
    (b"\x00\x00\x02\x00", "image/x-icon"),
    # Audio
    (b"ID3", "audio/mpeg"),
    (b"\xff\xfb", "audio/mpeg"),
    (b"\xff\xf3", "audio/mpeg"),
    (b"\xff\xf2", "audio/mpeg"),
    (b"OggS", "audio/ogg"),
    (b"fLaC", "audio/flac"),
    (b"RIFF", "audio/wav"),  # needs further check for WAVE
    # Video
    (b"\x00\x00\x00\x1cftyp", "video/mp4"),
    (b"\x00\x00\x00\x20ftyp", "video/mp4"),
    # PDF
    (b"%PDF", "application/pdf"),
]


def detect_mime_type(
    data: bytes | None = None,
    *,
    path: str | Path | None = None,
    default: str = "application/octet-stream",
) -> str:
    """Detect MIME type from magic bytes and/or file extension.

    Checks magic bytes first (if data provided), then falls back
    to file extension (if path provided).
    """
    if data:
        for sig, mime in _MAGIC_SIGNATURES:
            if data[:len(sig)] == sig:
                # Additional check for RIFF containers (WEBP vs WAV)
                if sig == b"RIFF" and len(data) >= 12:
                    fourcc = data[8:12]
                    if fourcc == b"WEBP":
                        return "image/webp"
                    if fourcc == b"WAVE":
                        return "audio/wav"
                    continue
                return mime

    if path:
        mime_guess, _ = mimetypes.guess_type(str(path))
        if mime_guess:
            return mime_guess

    return default


def detect_mime_from_base64(b64_string: str) -> str:
    """Detect MIME type from a base64-encoded string by decoding the header."""
    try:
        # Decode just enough bytes for magic detection
        header = base64.b64decode(b64_string[:64], validate=True)
        return detect_mime_type(header)
    except Exception:
        return "application/octet-stream"


def is_image_mime(mime: str) -> bool:
    return mime.startswith("image/")


def is_audio_mime(mime: str) -> bool:
    return mime.startswith("audio/")


def is_video_mime(mime: str) -> bool:
    return mime.startswith("video/")
