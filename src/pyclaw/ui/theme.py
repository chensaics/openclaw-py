"""UI theme module — color schemes, typography, and layout constants.

Centralises all visual design tokens so components can stay
theme-agnostic.  Supports light / dark modes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColorScheme:
    primary: str = "#6366f1"       # indigo-500
    secondary: str = "#8b5cf6"     # violet-500
    surface: str = "#ffffff"
    background: str = "#f8fafc"
    error: str = "#ef4444"
    success: str = "#22c55e"
    warning: str = "#f59e0b"
    on_primary: str = "#ffffff"
    on_surface: str = "#1e293b"
    on_background: str = "#0f172a"
    muted: str = "#94a3b8"
    border: str = "#e2e8f0"


@dataclass
class DarkColorScheme(ColorScheme):
    surface: str = "#1e293b"
    background: str = "#0f172a"
    on_surface: str = "#e2e8f0"
    on_background: str = "#f1f5f9"
    muted: str = "#64748b"
    border: str = "#334155"


@dataclass
class Typography:
    font_family: str = "Inter, system-ui, sans-serif"
    mono_family: str = "JetBrains Mono, Fira Code, monospace"
    size_xs: int = 12
    size_sm: int = 14
    size_base: int = 16
    size_lg: int = 18
    size_xl: int = 20
    size_2xl: int = 24
    size_3xl: int = 30


@dataclass
class Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


@dataclass
class AppTheme:
    """Complete application theme."""

    name: str = "light"
    colors: ColorScheme = field(default_factory=ColorScheme)
    typography: Typography = field(default_factory=Typography)
    spacing: Spacing = field(default_factory=Spacing)
    border_radius: int = 8
    sidebar_width: int = 280
    max_message_width: int = 720

    def to_flet_theme(self) -> Any:
        """Convert to a Flet ThemeData object (if flet is available)."""
        try:
            import flet as ft

            return ft.Theme(
                color_scheme_seed=self.colors.primary,
                font_family=self.typography.font_family,
            )
        except ImportError:
            return None


LIGHT_THEME = AppTheme(name="light")
DARK_THEME = AppTheme(
    name="dark",
    colors=DarkColorScheme(),
)

_current_theme: AppTheme = LIGHT_THEME


def get_theme() -> AppTheme:
    return _current_theme


def set_theme(theme: AppTheme) -> None:
    global _current_theme
    _current_theme = theme


def toggle_theme() -> AppTheme:
    global _current_theme
    _current_theme = DARK_THEME if _current_theme.name == "light" else LIGHT_THEME
    return _current_theme
