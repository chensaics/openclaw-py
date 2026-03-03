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

# Bundled translations keyed by locale
_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app.title": "pyclaw",
        "app.subtitle": "AI Assistant",
        "chat.placeholder": "Type a message...",
        "chat.send": "Send",
        "chat.thinking": "Thinking...",
        "chat.clear": "Clear Chat",
        "chat.copy": "Copy",
        "chat.retry": "Retry",
        "settings.title": "Settings",
        "settings.language": "Language",
        "settings.theme": "Theme",
        "settings.theme.light": "Light",
        "settings.theme.dark": "Dark",
        "settings.theme.system": "System",
        "settings.model": "Model",
        "settings.api_key": "API Key",
        "settings.save": "Save",
        "settings.cancel": "Cancel",
        "channels.title": "Channels",
        "channels.refresh": "Refresh",
        "channels.no_configured": "No channels configured",
        "channels.enabled": "Enabled",
        "channels.disabled": "Disabled",
        "channels.status": "Status",
        "channels.connected": "Connected",
        "channels.disconnected": "Disconnected",
        "channels.configure": "Configure",
        "tools.title": "Tools",
        "tools.running": "Running...",
        "tools.completed": "Completed",
        "tools.failed": "Failed",
        "memory.title": "Memory",
        "memory.search": "Search memories",
        "memory.add": "Add Memory",
        "memory.delete": "Delete",
        "memory.empty": "No memories yet.",
        "sessions.title": "Sessions",
        "sessions.new": "New Session",
        "sessions.delete": "Delete Session",
        "onboarding.welcome": "Welcome to pyclaw",
        "onboarding.subtitle": "Let's get you set up in a few quick steps.",
        "onboarding.step": "Step {current} of {total}",
        "onboarding.back": "Back",
        "onboarding.next": "Next",
        "onboarding.finish": "Finish",
        "onboarding.choose_provider": "Choose your AI provider",
        "onboarding.provider_label": "AI Provider",
        "onboarding.change_later": "You can change this later in settings.",
        "onboarding.enter_api_key": "Enter your API key",
        "onboarding.key_stored_locally": "Your key is stored locally and never sent to pyclaw servers.",
        "onboarding.select_model": "Select your default model",
        "onboarding.default_model": "Default Model",
        "onboarding.connect_channels": "Connect messaging channels (optional)",
        "onboarding.channels_later": "You can configure channel credentials later via the CLI or Settings.",
        "onboarding.setup": "Let's set up your assistant.",
        "onboarding.skip": "Skip",
        "onboarding.done": "Done",
        "media.expand": "Click to expand",
        "media.audio_file": "Audio file",
        "media.close": "Close",
        "voice.ready": "Ready",
        "voice.synthesizing": "Synthesizing...",
        "voice.saved": "Audio saved: {name}",
        "voice.error": "TTS error: {error}",
        "voice.select_audio": "Select an audio file to transcribe...",
        "voice.speak": "Speak",
        "voice.transcribe": "Transcribe",
        "voice.title": "Voice Interaction",
        "voice.text_label": "Text to speak",
        "tray.open": "Open pyclaw",
        "tray.quit": "Quit",
        "error.generic": "Something went wrong.",
        "error.network": "Network error. Please check your connection.",
        "error.auth": "Authentication failed.",
        "chat.role.user": "You",
        "chat.role.assistant": "pyclaw",
        "chat.no_response": "(no response)",
        "chat.error": "Error: {error}",
        "sessions.new_tooltip": "New session",
        "sessions.delete_tooltip": "Delete",
        "settings.provider": "Provider",
        "settings.model_id": "Model ID",
        "settings.base_url": "Base URL (optional)",
        "settings.dark_mode": "Dark Mode",
        "settings.model_config": "Model Configuration",
        "settings.appearance": "Appearance",
        "settings.saved": "Settings saved!",
        "nav.chat": "Chat",
        "nav.channels": "Channels",
        "nav.settings": "Settings",
        "nav.agents": "Agents",
        "nav.plans": "Plans",
        "nav.cron": "Cron",
        "nav.system": "System",
        "chat.abort": "Stop",
        "chat.edit": "Edit",
        "chat.search": "Search messages...",
        "sessions.search": "Search sessions...",
        "settings.gateway": "Gateway",
        "settings.gateway_url": "Gateway URL",
        "settings.seed_color": "Theme Color",
    },
    "zh-CN": {
        "app.title": "pyclaw",
        "app.subtitle": "AI 助手",
        "chat.placeholder": "输入消息...",
        "chat.send": "发送",
        "chat.thinking": "思考中...",
        "chat.clear": "清空对话",
        "chat.copy": "复制",
        "chat.retry": "重试",
        "settings.title": "设置",
        "settings.language": "语言",
        "settings.theme": "主题",
        "settings.theme.light": "浅色",
        "settings.theme.dark": "深色",
        "settings.theme.system": "跟随系统",
        "settings.model": "模型",
        "settings.save": "保存",
        "settings.cancel": "取消",
        "channels.title": "通道",
        "channels.status": "状态",
        "channels.connected": "已连接",
        "channels.disconnected": "未连接",
        "channels.configure": "配置",
        "tools.title": "工具",
        "tools.running": "运行中...",
        "tools.completed": "已完成",
        "tools.failed": "失败",
        "memory.title": "记忆",
        "memory.search": "搜索记忆",
        "memory.add": "添加记忆",
        "memory.delete": "删除",
        "memory.empty": "暂无记忆。",
        "sessions.title": "会话",
        "sessions.new": "新建会话",
        "sessions.delete": "删除会话",
        "onboarding.welcome": "欢迎使用 pyclaw",
        "onboarding.setup": "让我们来配置您的助手。",
        "onboarding.next": "下一步",
        "onboarding.skip": "跳过",
        "onboarding.done": "完成",
        "error.generic": "出了点问题。",
        "error.network": "网络错误，请检查连接。",
        "error.auth": "认证失败。",
        "chat.role.user": "你",
        "chat.role.assistant": "pyclaw",
        "chat.no_response": "(无回复)",
        "chat.error": "错误: {error}",
        "sessions.new_tooltip": "新建会话",
        "sessions.delete_tooltip": "删除",
        "settings.provider": "提供商",
        "settings.model_id": "模型 ID",
        "settings.api_key": "API 密钥",
        "settings.base_url": "基础 URL (可选)",
        "settings.dark_mode": "深色模式",
        "settings.model_config": "模型配置",
        "settings.appearance": "外观",
        "settings.saved": "设置已保存！",
        "nav.chat": "聊天",
        "nav.channels": "通道",
        "nav.settings": "设置",
        "nav.agents": "代理",
        "nav.plans": "计划",
        "nav.cron": "定时任务",
        "nav.system": "系统",
        "chat.abort": "停止",
        "chat.edit": "编辑",
        "chat.search": "搜索消息...",
        "sessions.search": "搜索会话...",
        "settings.gateway": "网关",
        "settings.gateway_url": "网关地址",
        "settings.seed_color": "主题色",
        "channels.no_configured": "未配置通道",
        "channels.enabled": "已启用",
        "channels.disabled": "已禁用",
        "channels.refresh": "刷新",
        "onboarding.subtitle": "让我们快速完成几个设置步骤。",
        "onboarding.step": "第 {current} 步，共 {total} 步",
        "onboarding.back": "返回",
        "onboarding.finish": "完成",
        "onboarding.choose_provider": "选择 AI 提供商",
        "onboarding.change_later": "您可以稍后在设置中修改。",
        "onboarding.enter_api_key": "输入 API 密钥",
        "onboarding.key_stored_locally": "密钥存储在本地，不会发送到 pyclaw 服务器。",
        "onboarding.select_model": "选择默认模型",
        "onboarding.connect_channels": "连接消息通道 (可选)",
        "onboarding.channels_later": "您可以稍后通过 CLI 或设置配置通道凭据。",
        "onboarding.provider_label": "AI 提供商",
        "onboarding.default_model": "默认模型",
        "media.expand": "点击放大",
        "media.audio_file": "音频文件",
        "media.close": "关闭",
        "voice.ready": "就绪",
        "voice.synthesizing": "合成中...",
        "voice.saved": "音频已保存: {name}",
        "voice.error": "TTS 错误: {error}",
        "voice.select_audio": "选择要转录的音频文件...",
        "voice.speak": "朗读",
        "voice.transcribe": "转录",
        "voice.title": "语音交互",
        "voice.text_label": "要朗读的文本",
        "tray.open": "打开 pyclaw",
        "tray.quit": "退出",
    },
    "ja": {
        "app.title": "pyclaw",
        "app.subtitle": "AIアシスタント",
        "chat.placeholder": "メッセージを入力...",
        "chat.send": "送信",
        "chat.thinking": "考え中...",
        "chat.clear": "チャットをクリア",
        "chat.copy": "コピー",
        "chat.retry": "再試行",
        "settings.title": "設定",
        "settings.language": "言語",
        "settings.theme": "テーマ",
        "settings.theme.light": "ライト",
        "settings.theme.dark": "ダーク",
        "settings.theme.system": "システム",
        "settings.model": "モデル",
        "settings.save": "保存",
        "settings.cancel": "キャンセル",
        "channels.title": "チャンネル",
        "channels.status": "ステータス",
        "channels.connected": "接続済み",
        "channels.disconnected": "未接続",
        "channels.configure": "設定",
        "tools.title": "ツール",
        "tools.running": "実行中...",
        "tools.completed": "完了",
        "tools.failed": "失敗",
        "memory.title": "メモリ",
        "memory.search": "メモリを検索",
        "memory.add": "メモリを追加",
        "memory.delete": "削除",
        "memory.empty": "メモリはまだありません。",
        "sessions.title": "セッション",
        "sessions.new": "新しいセッション",
        "sessions.delete": "セッションを削除",
        "onboarding.welcome": "pyclawへようこそ",
        "onboarding.setup": "アシスタントを設定しましょう。",
        "onboarding.next": "次へ",
        "onboarding.skip": "スキップ",
        "onboarding.done": "完了",
        "error.generic": "問題が発生しました。",
        "error.network": "ネットワークエラー。接続を確認してください。",
        "error.auth": "認証に失敗しました。",
        "chat.role.user": "あなた",
        "chat.role.assistant": "pyclaw",
        "chat.no_response": "(応答なし)",
        "chat.error": "エラー: {error}",
        "sessions.new_tooltip": "新しいセッション",
        "sessions.delete_tooltip": "削除",
        "settings.provider": "プロバイダー",
        "settings.model_id": "モデルID",
        "settings.api_key": "APIキー",
        "settings.base_url": "ベースURL (任意)",
        "settings.dark_mode": "ダークモード",
        "settings.model_config": "モデル設定",
        "settings.appearance": "外観",
        "settings.saved": "設定を保存しました！",
        "nav.chat": "チャット",
        "nav.channels": "チャンネル",
        "nav.settings": "設定",
        "nav.agents": "エージェント",
        "nav.plans": "プラン",
        "nav.cron": "スケジュール",
        "nav.system": "システム",
        "chat.abort": "停止",
        "chat.edit": "編集",
        "chat.search": "メッセージを検索...",
        "sessions.search": "セッションを検索...",
        "settings.gateway": "ゲートウェイ",
        "settings.gateway_url": "ゲートウェイURL",
        "settings.seed_color": "テーマカラー",
        "channels.refresh": "更新",
        "channels.no_configured": "チャンネル未設定",
        "channels.enabled": "有効",
        "channels.disabled": "無効",
        "onboarding.subtitle": "簡単なステップで設定を始めましょう。",
        "onboarding.step": "ステップ {current}/{total}",
        "onboarding.back": "戻る",
        "onboarding.finish": "完了",
        "onboarding.choose_provider": "AIプロバイダーを選択",
        "onboarding.change_later": "後で設定で変更できます。",
        "onboarding.enter_api_key": "APIキーを入力",
        "onboarding.key_stored_locally": "キーはローカルに保存され、pyclawサーバーに送信されません。",
        "onboarding.select_model": "デフォルトモデルを選択",
        "onboarding.connect_channels": "メッセージチャンネルを接続 (任意)",
        "onboarding.channels_later": "チャンネルの認証情報はCLIまたは設定から後で設定できます。",
        "onboarding.provider_label": "AIプロバイダー",
        "onboarding.default_model": "デフォルトモデル",
        "media.expand": "クリックで拡大",
        "media.audio_file": "音声ファイル",
        "media.close": "閉じる",
        "voice.ready": "準備完了",
        "voice.synthesizing": "合成中...",
        "voice.saved": "音声保存: {name}",
        "voice.error": "TTSエラー: {error}",
        "voice.select_audio": "転写する音声ファイルを選択...",
        "voice.speak": "読み上げ",
        "voice.transcribe": "転写",
        "voice.title": "音声操作",
        "voice.text_label": "読み上げるテキスト",
        "tray.open": "pyclawを開く",
        "tray.quit": "終了",
    },
}


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
