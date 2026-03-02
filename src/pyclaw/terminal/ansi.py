"""ANSI escape sequence utilities."""

from __future__ import annotations

import re
import unicodedata

# SGR: \x1b[ ... m   and OSC-8 hyperlinks: \x1b]8;...;...\x1b\\
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m|\x1b\]8;[^;]*;[^\x1b]*\x1b\\")


def strip_ansi(text: str) -> str:
    """Remove ANSI SGR and OSC-8 sequences from *text*."""
    return _ANSI_RE.sub("", text)


def visible_width(text: str) -> int:
    """Character width excluding ANSI sequences (CJK-aware)."""
    clean = strip_ansi(text)
    width = 0
    for ch in clean:
        cat = unicodedata.east_asian_width(ch)
        width += 2 if cat in ("W", "F") else 1
    return width
