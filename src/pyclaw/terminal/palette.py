"""Shared CLI color palette (ANSI 256-color)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ColorPalette:
    accent: str
    accent_bright: str
    accent_dim: str
    info: str
    success: str
    warn: str
    error: str
    muted: str
    reset: str


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _make_palette() -> ColorPalette:
    if not _supports_color():
        return ColorPalette(
            accent="", accent_bright="", accent_dim="",
            info="", success="", warn="", error="", muted="", reset="",
        )
    return ColorPalette(
        accent="\x1b[38;5;203m",       # lobster red
        accent_bright="\x1b[38;5;210m",
        accent_dim="\x1b[38;5;167m",
        info="\x1b[38;5;75m",          # light blue
        success="\x1b[38;5;114m",      # green
        warn="\x1b[38;5;221m",         # yellow
        error="\x1b[38;5;196m",        # bright red
        muted="\x1b[38;5;243m",        # gray
        reset="\x1b[0m",
    )


PALETTE = _make_palette()
