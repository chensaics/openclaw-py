"""Per-channel onboarding — configuration wizards for each channel type.

Ported from ``src/channels/*/onboarding.ts``.

Provides:
- Step-based onboarding flows for Discord, iMessage, Signal, Slack, Telegram, WhatsApp
- Step validation and prerequisite checking
- Configuration generation from wizard answers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class StepType(str, Enum):
    INPUT = "input"
    SELECT = "select"
    CONFIRM = "confirm"
    INFO = "info"
    ACTION = "action"


@dataclass
class OnboardingStep:
    """A single onboarding step."""

    step_id: str
    title: str
    description: str = ""
    step_type: StepType = StepType.INPUT
    field_name: str = ""
    required: bool = True
    placeholder: str = ""
    options: list[dict[str, str]] = field(default_factory=list)
    validation_pattern: str = ""
    docs_url: str = ""
    default_value: str = ""


@dataclass
class OnboardingFlow:
    """A complete onboarding flow for a channel."""

    channel_type: str
    display_name: str
    steps: list[OnboardingStep] = field(default_factory=list)
    prerequisite_info: str = ""

    @property
    def step_count(self) -> int:
        return len(self.steps)


@dataclass
class OnboardingResult:
    """Result of completing an onboarding flow."""

    channel_type: str
    config: dict[str, Any] = field(default_factory=dict)
    completed: bool = False
    errors: list[str] = field(default_factory=list)


def validate_step_answer(step: OnboardingStep, answer: str) -> tuple[bool, str]:
    """Validate an answer for an onboarding step."""
    if step.required and not answer.strip():
        return False, f"{step.title} is required"

    if step.validation_pattern:
        import re

        if not re.match(step.validation_pattern, answer):
            return False, f"Invalid format for {step.title}"

    return True, ""


# ---------------------------------------------------------------------------
# Per-channel onboarding flow definitions
# ---------------------------------------------------------------------------


def create_telegram_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="telegram",
        display_name="Telegram",
        prerequisite_info="You'll need a Telegram bot token from @BotFather.",
        steps=[
            OnboardingStep(
                step_id="token",
                title="Bot Token",
                description="Paste the token from @BotFather (format: 123456:ABC-DEF...)",
                field_name="token",
                placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                validation_pattern=r"^\d+:.+$",
            ),
            OnboardingStep(
                step_id="allowed_users",
                title="Allowed Users",
                description="Comma-separated Telegram usernames (leave empty for owner-only)",
                field_name="allowedUsers",
                required=False,
                placeholder="user1,user2",
            ),
            OnboardingStep(
                step_id="confirm",
                title="Confirm Setup",
                step_type=StepType.CONFIRM,
                description="Start the Telegram bot with these settings?",
            ),
        ],
    )


def create_discord_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="discord",
        display_name="Discord",
        prerequisite_info="You'll need a Discord bot token from the Developer Portal.",
        steps=[
            OnboardingStep(
                step_id="token",
                title="Bot Token",
                description="Paste the bot token from Discord Developer Portal",
                field_name="token",
            ),
            OnboardingStep(
                step_id="guild_id",
                title="Server ID",
                description="The Discord server (guild) ID to connect to",
                field_name="guildId",
                required=False,
                placeholder="123456789012345678",
            ),
            OnboardingStep(
                step_id="confirm",
                title="Confirm",
                step_type=StepType.CONFIRM,
                description="Start the Discord bot?",
            ),
        ],
    )


def create_slack_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="slack",
        display_name="Slack",
        prerequisite_info="You'll need both a Bot Token and an App Token from api.slack.com.",
        steps=[
            OnboardingStep(
                step_id="bot_token",
                title="Bot Token",
                description="The xoxb-... token",
                field_name="botToken",
                placeholder="xoxb-...",
                validation_pattern=r"^xoxb-.+$",
            ),
            OnboardingStep(
                step_id="app_token",
                title="App Token",
                description="The xapp-... token (for Socket Mode)",
                field_name="appToken",
                placeholder="xapp-...",
                validation_pattern=r"^xapp-.+$",
            ),
            OnboardingStep(
                step_id="confirm",
                title="Confirm",
                step_type=StepType.CONFIRM,
                description="Start the Slack bot?",
            ),
        ],
    )


def create_signal_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="signal",
        display_name="Signal",
        prerequisite_info="You'll need signal-cli installed and a registered phone number.",
        steps=[
            OnboardingStep(
                step_id="phone",
                title="Phone Number",
                description="The Signal phone number (with country code, e.g. +1234567890)",
                field_name="phoneNumber",
                placeholder="+1234567890",
                validation_pattern=r"^\+\d{10,15}$",
            ),
            OnboardingStep(
                step_id="confirm",
                title="Confirm",
                step_type=StepType.CONFIRM,
                description="Start the Signal bridge?",
            ),
        ],
    )


def create_whatsapp_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="whatsapp",
        display_name="WhatsApp",
        prerequisite_info="WhatsApp Web will show a QR code to scan.",
        steps=[
            OnboardingStep(
                step_id="info",
                title="QR Code Pairing",
                step_type=StepType.INFO,
                description="A QR code will be displayed. Scan it with WhatsApp on your phone.",
            ),
            OnboardingStep(
                step_id="confirm",
                title="Start",
                step_type=StepType.CONFIRM,
                description="Start WhatsApp Web connection?",
            ),
        ],
    )


def create_imessage_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="imessage",
        display_name="iMessage",
        prerequisite_info="Requires macOS with iMessage enabled and the imsg bridge installed.",
        steps=[
            OnboardingStep(
                step_id="check",
                title="Prerequisites Check",
                step_type=StepType.INFO,
                description="Ensure iMessage is signed in on this Mac and imsg is installed.",
            ),
            OnboardingStep(
                step_id="confirm",
                title="Start",
                step_type=StepType.CONFIRM,
                description="Start the iMessage bridge?",
            ),
        ],
    )


def create_matrix_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="matrix",
        display_name="Matrix",
        prerequisite_info="You'll need a Matrix homeserver URL and access token.",
        steps=[
            OnboardingStep(
                step_id="homeserver",
                title="Homeserver URL",
                description="Matrix homeserver URL (e.g. https://matrix.org)",
                field_name="homeserver",
                placeholder="https://matrix.org",
                validation_pattern=r"^https?://.+$",
            ),
            OnboardingStep(
                step_id="access_token",
                title="Access Token",
                description="Bot access token from the homeserver",
                field_name="accessToken",
            ),
            OnboardingStep(
                step_id="confirm",
                title="Confirm",
                step_type=StepType.CONFIRM,
                description="Start the Matrix bot?",
            ),
        ],
    )


def create_feishu_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="feishu",
        display_name="Feishu / Lark",
        prerequisite_info="You'll need an App ID and App Secret from the Feishu Open Platform.",
        steps=[
            OnboardingStep(
                step_id="app_id",
                title="App ID",
                description="Feishu application App ID",
                field_name="appId",
            ),
            OnboardingStep(
                step_id="app_secret",
                title="App Secret",
                description="Feishu application App Secret",
                field_name="appSecret",
            ),
            OnboardingStep(
                step_id="verification_token",
                title="Verification Token",
                description="Event subscription verification token (optional)",
                field_name="verificationToken",
                required=False,
            ),
            OnboardingStep(
                step_id="confirm",
                title="Confirm",
                step_type=StepType.CONFIRM,
                description="Start the Feishu bot?",
            ),
        ],
    )


def create_msteams_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="msteams",
        display_name="Microsoft Teams",
        prerequisite_info="You'll need a Bot Framework App ID and Password from Azure.",
        steps=[
            OnboardingStep(
                step_id="app_id",
                title="App ID",
                description="Microsoft App ID from Azure Bot registration",
                field_name="appId",
            ),
            OnboardingStep(
                step_id="app_password",
                title="App Password",
                description="Microsoft App Password (client secret)",
                field_name="appPassword",
            ),
            OnboardingStep(
                step_id="confirm",
                title="Confirm",
                step_type=StepType.CONFIRM,
                description="Start the Teams bot?",
            ),
        ],
    )


def create_dingtalk_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="dingtalk",
        display_name="DingTalk",
        prerequisite_info="You'll need a DingTalk App Key and App Secret.",
        steps=[
            OnboardingStep(
                step_id="client_id",
                title="App Key (Client ID)",
                description="DingTalk application AppKey",
                field_name="clientId",
            ),
            OnboardingStep(
                step_id="client_secret",
                title="App Secret (Client Secret)",
                description="DingTalk application AppSecret",
                field_name="clientSecret",
            ),
            OnboardingStep(
                step_id="confirm",
                title="Confirm",
                step_type=StepType.CONFIRM,
                description="Start the DingTalk bot?",
            ),
        ],
    )


def create_qq_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="qq",
        display_name="QQ",
        prerequisite_info="You'll need a QQ Bot App ID and Secret from the QQ Open Platform.",
        steps=[
            OnboardingStep(
                step_id="app_id",
                title="App ID",
                description="QQ Bot application App ID",
                field_name="appId",
            ),
            OnboardingStep(
                step_id="secret",
                title="Secret",
                description="QQ Bot application Secret",
                field_name="secret",
            ),
            OnboardingStep(
                step_id="confirm",
                title="Confirm",
                step_type=StepType.CONFIRM,
                description="Start the QQ bot?",
            ),
        ],
    )


def create_irc_onboarding() -> OnboardingFlow:
    return OnboardingFlow(
        channel_type="irc",
        display_name="IRC",
        prerequisite_info="You'll need an IRC server address, channel, and nickname.",
        steps=[
            OnboardingStep(
                step_id="server",
                title="Server",
                description="IRC server address (e.g. irc.libera.chat)",
                field_name="server",
                placeholder="irc.libera.chat",
            ),
            OnboardingStep(
                step_id="channel_name",
                title="Channel",
                description="IRC channel to join (e.g. #mychannel)",
                field_name="channel",
                placeholder="#mychannel",
                validation_pattern=r"^#.+$",
            ),
            OnboardingStep(
                step_id="nick",
                title="Nickname",
                description="Bot nickname",
                field_name="nick",
                placeholder="pyclaw-bot",
            ),
            OnboardingStep(
                step_id="confirm",
                title="Confirm",
                step_type=StepType.CONFIRM,
                description="Connect to IRC?",
            ),
        ],
    )


# Registry of all onboarding flow creators
ONBOARDING_FLOWS: dict[str, Any] = {
    "telegram": create_telegram_onboarding,
    "discord": create_discord_onboarding,
    "slack": create_slack_onboarding,
    "signal": create_signal_onboarding,
    "whatsapp": create_whatsapp_onboarding,
    "imessage": create_imessage_onboarding,
    "matrix": create_matrix_onboarding,
    "feishu": create_feishu_onboarding,
    "msteams": create_msteams_onboarding,
    "dingtalk": create_dingtalk_onboarding,
    "qq": create_qq_onboarding,
    "irc": create_irc_onboarding,
}


def get_onboarding_flow(channel_type: str) -> OnboardingFlow | None:
    """Get the onboarding flow for a channel type."""
    creator = ONBOARDING_FLOWS.get(channel_type)
    return creator() if creator else None


def list_onboarding_channels() -> list[str]:
    """List channel types that have onboarding flows."""
    return list(ONBOARDING_FLOWS.keys())


def build_config_from_answers(
    flow: OnboardingFlow,
    answers: dict[str, str],
) -> OnboardingResult:
    """Build a channel config from onboarding answers."""
    errors: list[str] = []
    config: dict[str, Any] = {"type": flow.channel_type}

    for step in flow.steps:
        if not step.field_name:
            continue

        answer = answers.get(step.step_id, answers.get(step.field_name, ""))
        ok, err = validate_step_answer(step, answer)
        if not ok:
            errors.append(err)
            continue

        if answer:
            config[step.field_name] = answer

    return OnboardingResult(
        channel_type=flow.channel_type,
        config=config,
        completed=not errors,
        errors=errors,
    )
