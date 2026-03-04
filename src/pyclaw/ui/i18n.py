"""Web UI internationalization — multi-language support.

Ported from ``src/provider-web/i18n/`` in the TypeScript codebase.
Provides a lightweight i18n system for the Flet UI with bundled
translations and runtime locale switching.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LOCALE = "en"

_LOCALES_DIR = Path(__file__).parent / "locales"


def _load_bundled_translations() -> dict[str, dict[str, str]]:
    """Load all bundled translation JSON files from the ``locales/`` directory."""
    translations: dict[str, dict[str, str]] = {}
    if _LOCALES_DIR.is_dir():
        for locale_file in sorted(_LOCALES_DIR.glob("*.json")):
            locale = locale_file.stem
            try:
                data = json.loads(locale_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if "locale" in data and "translations" in data:
                        translations[data["locale"]] = data["translations"]
                    else:
                        translations[locale] = data
            except Exception:
                logger.warning("Failed to load bundled locale %s", locale_file)
    return translations


_TRANSLATIONS: dict[str, dict[str, str]] = _load_bundled_translations()


class I18n:
    """Internationalization manager for the UI."""

    def __init__(self, locale: str = DEFAULT_LOCALE) -> None:
        self._locale = locale
        self._custom: dict[str, dict[str, str]] = {}

    @property
    def locale(self) -> str:
        return self._locale

    @locale.setter
    def locale(self, value: str) -> None:
        self._locale = value

    @property
    def available_locales(self) -> list[str]:
        all_locales = set(_TRANSLATIONS.keys()) | set(self._custom.keys())
        return sorted(all_locales)

    def t(self, key: str, **kwargs: Any) -> str:
        """Translate a key to the current locale.

        Falls back to English, then returns the key itself.
        """
        # Check custom translations first
        value = self._custom.get(self._locale, {}).get(key)
        if value is None:
            value = _TRANSLATIONS.get(self._locale, {}).get(key)
        if value is None and self._locale != DEFAULT_LOCALE:
            value = _TRANSLATIONS.get(DEFAULT_LOCALE, {}).get(key)
        if value is None:
            return key

        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, IndexError):
                return value
        return value

    def load_translations(self, locale: str, translations: dict[str, str]) -> None:
        """Load custom translations for a locale."""
        if locale not in self._custom:
            self._custom[locale] = {}
        self._custom[locale].update(translations)

    def load_translations_file(self, path: Path) -> None:
        """Load translations from a JSON file.

        File format: ``{"locale": "zh-CN", "translations": {"key": "value"}}``
        or simply ``{"key": "value"}`` with locale inferred from filename.
        """
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load translations from %s", path)
            return

        if "locale" in data and "translations" in data:
            self.load_translations(data["locale"], data["translations"])
        else:
            # Infer locale from filename (e.g. "zh-CN.json")
            locale = path.stem
            self.load_translations(locale, data)

    def get_locale_display_name(self, locale: str) -> str:
        """Get a human-readable name for a locale."""
        names: dict[str, str] = {
            "en": "English",
            "zh-CN": "简体中文",
            "zh-TW": "繁體中文",
            "ja": "日本語",
            "ko": "한국어",
            "fr": "Français",
            "de": "Deutsch",
            "es": "Español",
            "pt": "Português",
            "ru": "Русский",
            "ar": "العربية",
        }
        return names.get(locale, locale)


# Global i18n instance (can be replaced per-app)
_global_i18n = I18n()


def get_i18n() -> I18n:
    """Get the global I18n instance."""
    return _global_i18n


def set_i18n(i18n: I18n) -> None:
    """Set the global I18n instance."""
    global _global_i18n
    _global_i18n = i18n


def t(key: str, **kwargs: Any) -> str:
    """Shorthand for global translation."""
    return _global_i18n.t(key, **kwargs)
