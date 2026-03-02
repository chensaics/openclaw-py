"""Audio utilities — tag parsing and voice detection.

Ported from ``src/media/`` audio handling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_AUDIO_TAG_RE = re.compile(r"\[\[audio_as_voice\]\]", re.IGNORECASE)


@dataclass
class AudioTag:
    """Parsed audio tag from LLM output."""
    tag: str
    as_voice: bool = False


def parse_audio_tag(text: str) -> AudioTag | None:
    """Parse ``[[audio_as_voice]]`` tags from text."""
    m = _AUDIO_TAG_RE.search(text)
    if not m:
        return None
    return AudioTag(tag=m.group(0), as_voice=True)


def strip_audio_tags(text: str) -> str:
    """Remove audio tags from text, returning clean text."""
    return _AUDIO_TAG_RE.sub("", text).strip()


def extract_media_tokens(text: str) -> list[dict[str, Any]]:
    """Extract media-related tokens/tags from LLM output.

    Returns a list of dicts with ``type`` and ``value`` keys.
    Currently supports audio voice tags; extensible for future media tokens.
    """
    tokens: list[dict[str, Any]] = []

    for m in _AUDIO_TAG_RE.finditer(text):
        tokens.append({
            "type": "audio_voice",
            "value": m.group(0),
            "start": m.start(),
            "end": m.end(),
        })

    return tokens
