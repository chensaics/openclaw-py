"""Per-channel status issues — issue detection, config schema generation.

Ported from ``src/channels/*/status-issues.ts``.

Provides:
- Per-channel issue checks (BlueBubbles, Discord, Telegram, WhatsApp, Signal)
- Config schema auto-generation from channel requirements
- Issue aggregation and formatting
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, cast

from pyclaw.channels.plugin_sdk.status_issues import (
    ChannelIssue,
    IssueCategory,
    IssueSeverity,
)

logger = logging.getLogger(__name__)


@dataclass
class ConfigField:
    """A configuration field for a channel."""
    name: str
    label: str
    field_type: str = "string"  # string | number | boolean | select
    required: bool = False
    description: str = ""
    default: Any = None
    options: list[dict[str, str]] = field(default_factory=list)
    sensitive: bool = False
    validation_pattern: str = ""


@dataclass
class ChannelConfigSchema:
    """Auto-generated config schema for a channel."""
    channel_type: str
    fields: list[ConfigField] = field(default_factory=list)
    documentation_url: str = ""

    def to_json_schema(self) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for f in self.fields:
            prop: dict[str, Any] = {
                "type": f.field_type if f.field_type != "select" else "string",
                "description": f.description or f.label,
            }
            if f.default is not None:
                prop["default"] = f.default
            if f.options:
                prop["enum"] = [o["value"] for o in f.options]
            properties[f.name] = prop
            if f.required:
                required.append(f.name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }


# ---------------------------------------------------------------------------
# Per-channel issue checkers
# ---------------------------------------------------------------------------

def check_telegram_issues(config: dict[str, Any]) -> list[ChannelIssue]:
    issues: list[ChannelIssue] = []
    if not config.get("token"):
        issues.append(ChannelIssue(
            code="telegram_no_token",
            message="Telegram bot token is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.AUTH,
            fix_hint="Set channels.telegram.token in config",
        ))
    token = config.get("token", "")
    if token and ":" not in token:
        issues.append(ChannelIssue(
            code="telegram_invalid_token",
            message="Telegram bot token format appears invalid",
            severity=IssueSeverity.WARNING,
            category=IssueCategory.AUTH,
            fix_hint="Token should be in format: 123456:ABC-DEF...",
        ))
    return issues


def check_discord_issues(config: dict[str, Any]) -> list[ChannelIssue]:
    issues: list[ChannelIssue] = []
    if not config.get("token"):
        issues.append(ChannelIssue(
            code="discord_no_token",
            message="Discord bot token is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.AUTH,
            fix_hint="Set channels.discord.token in config",
        ))
    return issues


def check_whatsapp_issues(config: dict[str, Any]) -> list[ChannelIssue]:
    issues: list[ChannelIssue] = []
    # WhatsApp doesn't require explicit config but may have session issues
    if config.get("sessionExpired"):
        issues.append(ChannelIssue(
            code="whatsapp_session_expired",
            message="WhatsApp session has expired — re-scan QR code",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.CONNECTION,
            fix_hint="Restart the gateway and re-scan the QR code",
        ))
    return issues


def check_signal_issues(config: dict[str, Any]) -> list[ChannelIssue]:
    issues: list[ChannelIssue] = []
    if not config.get("phoneNumber"):
        issues.append(ChannelIssue(
            code="signal_no_phone",
            message="Signal phone number is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.AUTH,
            fix_hint="Set channels.signal.phoneNumber in config",
        ))
    return issues


def check_bluebubbles_issues(config: dict[str, Any]) -> list[ChannelIssue]:
    issues: list[ChannelIssue] = []
    if not config.get("serverUrl"):
        issues.append(ChannelIssue(
            code="bb_no_server",
            message="BlueBubbles server URL is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.CONFIG,
            fix_hint="Set channels.bluebubbles.serverUrl in config",
        ))
    if not config.get("password"):
        issues.append(ChannelIssue(
            code="bb_no_password",
            message="BlueBubbles password is not configured",
            severity=IssueSeverity.WARNING,
            category=IssueCategory.AUTH,
        ))
    return issues


def check_slack_issues(config: dict[str, Any]) -> list[ChannelIssue]:
    issues: list[ChannelIssue] = []
    if not config.get("botToken"):
        issues.append(ChannelIssue(
            code="slack_no_bot_token",
            message="Slack bot token (xoxb-...) is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.AUTH,
            fix_hint="Set channels.slack.botToken in config",
        ))
    if not config.get("appToken"):
        issues.append(ChannelIssue(
            code="slack_no_app_token",
            message="Slack app token (xapp-...) is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.AUTH,
            fix_hint="Set channels.slack.appToken in config (required for Socket Mode)",
        ))
    return issues


def check_matrix_issues(config: dict[str, Any]) -> list[ChannelIssue]:
    issues: list[ChannelIssue] = []
    if not config.get("homeserver"):
        issues.append(ChannelIssue(
            code="matrix_no_homeserver",
            message="Matrix homeserver URL is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.CONFIG,
            fix_hint="Set channels.matrix.homeserver in config",
        ))
    if not config.get("accessToken"):
        issues.append(ChannelIssue(
            code="matrix_no_token",
            message="Matrix access token is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.AUTH,
            fix_hint="Set channels.matrix.accessToken in config",
        ))
    return issues


def check_feishu_issues(config: dict[str, Any]) -> list[ChannelIssue]:
    issues: list[ChannelIssue] = []
    if not config.get("appId"):
        issues.append(ChannelIssue(
            code="feishu_no_app_id",
            message="Feishu App ID is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.AUTH,
            fix_hint="Set channels.feishu.appId in config",
        ))
    if not config.get("appSecret"):
        issues.append(ChannelIssue(
            code="feishu_no_app_secret",
            message="Feishu App Secret is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.AUTH,
            fix_hint="Set channels.feishu.appSecret in config",
        ))
    return issues


def check_msteams_issues(config: dict[str, Any]) -> list[ChannelIssue]:
    issues: list[ChannelIssue] = []
    if not config.get("appId"):
        issues.append(ChannelIssue(
            code="msteams_no_app_id",
            message="Microsoft Teams App ID is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.AUTH,
            fix_hint="Set channels.msteams.appId in config",
        ))
    if not config.get("appPassword"):
        issues.append(ChannelIssue(
            code="msteams_no_password",
            message="Microsoft Teams App Password is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.AUTH,
        ))
    return issues


def check_dingtalk_issues(config: dict[str, Any]) -> list[ChannelIssue]:
    issues: list[ChannelIssue] = []
    if not config.get("clientId"):
        issues.append(ChannelIssue(
            code="dingtalk_no_client_id",
            message="DingTalk Client ID (App Key) is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.AUTH,
        ))
    return issues


def check_irc_issues(config: dict[str, Any]) -> list[ChannelIssue]:
    issues: list[ChannelIssue] = []
    if not config.get("server"):
        issues.append(ChannelIssue(
            code="irc_no_server",
            message="IRC server address is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.CONFIG,
        ))
    if not config.get("channel"):
        issues.append(ChannelIssue(
            code="irc_no_channel",
            message="IRC channel is not configured",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.CONFIG,
        ))
    return issues


CHANNEL_ISSUE_CHECKERS: dict[str, Any] = {
    "telegram": check_telegram_issues,
    "discord": check_discord_issues,
    "whatsapp": check_whatsapp_issues,
    "signal": check_signal_issues,
    "bluebubbles": check_bluebubbles_issues,
    "slack": check_slack_issues,
    "matrix": check_matrix_issues,
    "feishu": check_feishu_issues,
    "msteams": check_msteams_issues,
    "dingtalk": check_dingtalk_issues,
    "irc": check_irc_issues,
}


def check_channel_issues(channel_type: str, config: dict[str, Any]) -> list[ChannelIssue]:
    """Run issue checks for a specific channel."""
    checker = CHANNEL_ISSUE_CHECKERS.get(channel_type)
    if not checker:
        return []
    return cast(list[ChannelIssue], checker(config))


def check_all_channels(
    channels_config: dict[str, dict[str, Any]],
) -> dict[str, list[ChannelIssue]]:
    """Check issues for all configured channels."""
    result: dict[str, list[ChannelIssue]] = {}
    for ch_type, config in channels_config.items():
        issues = check_channel_issues(ch_type, config)
        if issues:
            result[ch_type] = issues
    return result


# ---------------------------------------------------------------------------
# Config schemas
# ---------------------------------------------------------------------------

CHANNEL_CONFIG_SCHEMAS: dict[str, ChannelConfigSchema] = {
    "telegram": ChannelConfigSchema(
        channel_type="telegram",
        documentation_url="https://docs.openclaw.ai/channels/telegram",
        fields=[
            ConfigField("token", "Bot Token", required=True, sensitive=True,
                        description="Telegram bot token from @BotFather"),
            ConfigField("allowedUsers", "Allowed Users",
                        description="Comma-separated Telegram usernames"),
            ConfigField("groupMode", "Group Mode", field_type="select",
                        options=[{"value": "off", "label": "Off"},
                                 {"value": "mention", "label": "Mention only"},
                                 {"value": "all", "label": "All messages"}],
                        default="mention"),
        ],
    ),
    "discord": ChannelConfigSchema(
        channel_type="discord",
        documentation_url="https://docs.openclaw.ai/channels/discord",
        fields=[
            ConfigField("token", "Bot Token", required=True, sensitive=True),
            ConfigField("guildId", "Server ID",
                        description="Discord server (guild) ID"),
        ],
    ),
    "slack": ChannelConfigSchema(
        channel_type="slack",
        documentation_url="https://docs.openclaw.ai/channels/slack",
        fields=[
            ConfigField("botToken", "Bot Token", required=True, sensitive=True,
                        validation_pattern=r"^xoxb-.+$"),
            ConfigField("appToken", "App Token", required=True, sensitive=True,
                        validation_pattern=r"^xapp-.+$"),
        ],
    ),
    "matrix": ChannelConfigSchema(
        channel_type="matrix",
        fields=[
            ConfigField("homeserver", "Homeserver URL", required=True,
                        description="Matrix homeserver URL (e.g. https://matrix.org)"),
            ConfigField("accessToken", "Access Token", required=True, sensitive=True),
        ],
    ),
    "feishu": ChannelConfigSchema(
        channel_type="feishu",
        fields=[
            ConfigField("appId", "App ID", required=True),
            ConfigField("appSecret", "App Secret", required=True, sensitive=True),
            ConfigField("verificationToken", "Verification Token", sensitive=True),
        ],
    ),
    "msteams": ChannelConfigSchema(
        channel_type="msteams",
        fields=[
            ConfigField("appId", "App ID", required=True),
            ConfigField("appPassword", "App Password", required=True, sensitive=True),
        ],
    ),
    "signal": ChannelConfigSchema(
        channel_type="signal",
        fields=[
            ConfigField("phoneNumber", "Phone Number", required=True,
                        description="Signal phone number with country code",
                        validation_pattern=r"^\+\d{10,15}$"),
        ],
    ),
    "whatsapp": ChannelConfigSchema(
        channel_type="whatsapp",
        fields=[
            ConfigField("phoneNumber", "Phone Number",
                        description="WhatsApp phone number (optional)"),
        ],
    ),
    "irc": ChannelConfigSchema(
        channel_type="irc",
        fields=[
            ConfigField("server", "Server", required=True),
            ConfigField("channel", "Channel", required=True,
                        description="IRC channel (e.g. #mychannel)"),
            ConfigField("nick", "Nickname", required=True),
            ConfigField("password", "Password", sensitive=True),
        ],
    ),
}


def get_config_schema(channel_type: str) -> ChannelConfigSchema | None:
    return CHANNEL_CONFIG_SCHEMAS.get(channel_type)
