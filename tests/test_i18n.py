"""Tests for Web UI i18n."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from pyclaw.ui.i18n import I18n, get_i18n, set_i18n, t


class TestI18n:
    @pytest.fixture
    def i18n(self) -> I18n:
        return I18n("en")

    def test_translate_english(self, i18n: I18n) -> None:
        assert i18n.t("chat.send") == "Send"
        assert i18n.t("settings.title") == "Settings"

    def test_translate_chinese(self) -> None:
        i18n = I18n("zh-CN")
        assert i18n.t("chat.send") == "发送"
        assert i18n.t("settings.title") == "设置"

    def test_translate_japanese(self) -> None:
        i18n = I18n("ja")
        assert i18n.t("chat.send") == "送信"

    def test_fallback_to_english(self) -> None:
        i18n = I18n("fr")  # French not fully defined
        assert i18n.t("chat.send") == "Send"

    def test_missing_key_returns_key(self, i18n: I18n) -> None:
        assert i18n.t("nonexistent.key") == "nonexistent.key"

    def test_format_interpolation(self, i18n: I18n) -> None:
        i18n.load_translations("en", {"greeting": "Hello, {name}!"})
        assert i18n.t("greeting", name="World") == "Hello, World!"

    def test_format_missing_arg(self, i18n: I18n) -> None:
        i18n.load_translations("en", {"greeting": "Hello, {name}!"})
        assert i18n.t("greeting") == "Hello, {name}!"

    def test_locale_switch(self) -> None:
        i18n = I18n("en")
        assert i18n.t("chat.send") == "Send"

        i18n.locale = "zh-CN"
        assert i18n.t("chat.send") == "发送"

    def test_available_locales(self, i18n: I18n) -> None:
        locales = i18n.available_locales
        assert "en" in locales
        assert "zh-CN" in locales
        assert "ja" in locales

    def test_custom_translations_priority(self, i18n: I18n) -> None:
        i18n.load_translations("en", {"chat.send": "Submit"})
        assert i18n.t("chat.send") == "Submit"

    def test_load_translations_file_with_locale(self) -> None:
        i18n = I18n("ko")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "locale": "ko",
                    "translations": {"chat.send": "보내기"},
                },
                f,
            )
            f.flush()
            i18n.load_translations_file(Path(f.name))

        assert i18n.t("chat.send") == "보내기"

    def test_load_translations_file_infer_locale(self) -> None:
        i18n = I18n("de")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, prefix="de") as f:
            json.dump({"chat.send": "Senden"}, f)
            f.flush()
            path = Path(f.name)

        # Rename to de.json so stem is inferred
        de_path = path.parent / "de.json"
        path.rename(de_path)
        i18n.load_translations_file(de_path)

        assert i18n.t("chat.send") == "Senden"
        de_path.unlink(missing_ok=True)

    def test_locale_display_name(self, i18n: I18n) -> None:
        assert i18n.get_locale_display_name("en") == "English"
        assert i18n.get_locale_display_name("zh-CN") == "简体中文"
        assert i18n.get_locale_display_name("ja") == "日本語"
        assert i18n.get_locale_display_name("unknown") == "unknown"


class TestGlobalI18n:
    def test_global_t(self) -> None:
        old = get_i18n()
        try:
            set_i18n(I18n("en"))
            assert t("chat.send") == "Send"

            set_i18n(I18n("zh-CN"))
            assert t("chat.send") == "发送"
        finally:
            set_i18n(old)

    def test_get_set_i18n(self) -> None:
        old = get_i18n()
        new_i18n = I18n("ja")
        set_i18n(new_i18n)
        assert get_i18n() is new_i18n
        set_i18n(old)
