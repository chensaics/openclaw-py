"""UI theme module — color schemes, typography, and layout constants.

Centralises all visual design tokens so components can stay
theme-agnostic.  Supports light / dark modes with seed-color theming.

Color system aligned with Flutter App Material 3 design tokens
(see flutter_app/lib/core/theme/ for reference).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Accent seed colors (synced from Flutter AppColors)
# ---------------------------------------------------------------------------

SEED_INDIGO = "#6366f1"
SEED_TEAL = "#14b8a6"
SEED_ROSE = "#f43f5e"

PRESET_SEED_COLORS: dict[str, str] = {
    "indigo": SEED_INDIGO,
    "teal": SEED_TEAL,
    "rose": SEED_ROSE,
    "blue": "#3b82f6",
    "amber": "#f59e0b",
    "emerald": "#10b981",
    "violet": "#8b5cf6",
    "cyan": "#06b6d4",
}


# ---------------------------------------------------------------------------
# Status & role colors (synced from Flutter AppColors)
# ---------------------------------------------------------------------------

class StatusColors:
    SUCCESS = "#22c55e"
    WARNING = "#f59e0b"
    ERROR = "#ef4444"
    INFO = "#3b82f6"


class RoleColors:
    USER = "#6366f1"
    ASSISTANT = "#14b8a6"
    SYSTEM = "#8b5cf6"
    TOOL = "#f59e0b"


class CodeBlockColors:
    LIGHT_BG = "#f5f5f5"
    DARK_BG = "#1e1e1e"


# ---------------------------------------------------------------------------
# Color schemes
# ---------------------------------------------------------------------------

@dataclass
class ColorScheme:
    primary: str = SEED_INDIGO
    secondary: str = "#8b5cf6"     # violet-500
    surface: str = "#ffffff"
    background: str = "#f8fafc"
    error: str = StatusColors.ERROR
    success: str = StatusColors.SUCCESS
    warning: str = StatusColors.WARNING
    info: str = StatusColors.INFO
    on_primary: str = "#ffffff"
    on_surface: str = "#1e293b"
    on_background: str = "#0f172a"
    muted: str = "#94a3b8"
    border: str = "#e2e8f0"
    surface_container: str = "#f1f5f9"
    surface_container_high: str = "#e2e8f0"
    primary_container: str = "#e0e7ff"
    on_primary_container: str = "#3730a3"
    code_block_bg: str = CodeBlockColors.LIGHT_BG


@dataclass
class DarkColorScheme(ColorScheme):
    surface: str = "#1e293b"
    background: str = "#0f172a"
    on_surface: str = "#e2e8f0"
    on_background: str = "#f1f5f9"
    muted: str = "#64748b"
    border: str = "#334155"
    surface_container: str = "#1e293b"
    surface_container_high: str = "#334155"
    primary_container: str = "#312e81"
    on_primary_container: str = "#c7d2fe"
    code_block_bg: str = CodeBlockColors.DARK_BG


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

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
    line_height: float = 1.6
    code_line_height: float = 1.5


# ---------------------------------------------------------------------------
# Spacing & layout
# ---------------------------------------------------------------------------

@dataclass
class Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


# ---------------------------------------------------------------------------
# AppTheme
# ---------------------------------------------------------------------------

@dataclass
class AppTheme:
    """Complete application theme with responsive layout tokens."""

    name: str = "light"
    colors: ColorScheme = field(default_factory=ColorScheme)
    typography: Typography = field(default_factory=Typography)
    spacing: Spacing = field(default_factory=Spacing)
    border_radius: int = 12
    card_border_radius: int = 16
    input_border_radius: int = 24
    sidebar_width: int = 240
    max_message_width: int = 720
    nav_rail_width: int = 72
    breakpoint_mobile: int = 600
    breakpoint_tablet: int = 900
    breakpoint_desktop: int = 1200

    def to_flet_theme(self) -> Any:
        """Convert to a Flet ThemeData object (if flet is available)."""
        try:
            import flet as ft

            return ft.Theme(
                color_scheme_seed=self.colors.primary,
                font_family=self.typography.font_family,
                visual_density=ft.VisualDensity.COMFORTABLE,
            )
        except ImportError:
            return None

    def role_color(self, role: str) -> str:
        """Return the avatar/accent color for a message role."""
        return {
            "user": RoleColors.USER,
            "assistant": RoleColors.ASSISTANT,
            "system": RoleColors.SYSTEM,
            "tool": RoleColors.TOOL,
        }.get(role, self.colors.muted)


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


def set_seed_color(color: str) -> AppTheme:
    """Update the current theme's primary seed color.

    Accepts a hex string ('#6366f1') or a preset name ('indigo', 'teal', ...).
    """
    global _current_theme
    resolved = PRESET_SEED_COLORS.get(color.lower(), color)
    _current_theme.colors.primary = resolved
    return _current_theme


def list_seed_presets() -> dict[str, str]:
    """Return available preset seed colors {name: hex}."""
    return dict(PRESET_SEED_COLORS)
