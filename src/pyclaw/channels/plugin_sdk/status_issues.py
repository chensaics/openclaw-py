"""Channel status and health checks — issue detection, config schema, media limits.

Ported from ``src/channels/channel-plugin-sdk/status-issues*.ts``.

Provides:
- Channel health check framework
- Issue detection and classification
- Channel configuration schema (for UI/docs)
- Media limits and constraints
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyclaw.constants.runtime import STATUS_ERROR, STATUS_INFO, STATUS_WARNING

logger = logging.getLogger(__name__)


class IssueSeverity(str, Enum):
    ERROR = STATUS_ERROR
    WARNING = STATUS_WARNING
    INFO = STATUS_INFO


class IssueCategory(str, Enum):
    AUTH = "auth"
    CONFIG = "config"
    CONNECTION = "connection"
    RATE_LIMIT = "rate-limit"
    PERMISSIONS = "permissions"
    MEDIA = "media"
    WEBHOOK = "webhook"


@dataclass
class ChannelIssue:
    """A detected issue with a channel."""

    code: str
    message: str
    severity: IssueSeverity = IssueSeverity.WARNING
    category: IssueCategory = IssueCategory.CONFIG
    fix_hint: str = ""
    detected_at: float = 0.0

    def __post_init__(self) -> None:
        if self.detected_at == 0.0:
            self.detected_at = time.time()


@dataclass
class MediaLimits:
    """Media constraints for a channel."""

    max_file_size_mb: int = 50
    max_image_size_mb: int = 10
    max_video_size_mb: int = 50
    max_audio_size_mb: int = 25
    max_caption_length: int = 1024
    supported_image_types: list[str] = field(default_factory=lambda: ["jpg", "png", "gif", "webp"])
    supported_audio_types: list[str] = field(default_factory=lambda: ["mp3", "ogg", "wav"])
    supported_video_types: list[str] = field(default_factory=lambda: ["mp4"])
    supported_document_types: list[str] = field(default_factory=lambda: ["pdf", "txt", "docx", "xlsx"])


@dataclass
class ConfigField:
    """A single configuration field definition."""

    name: str
    field_type: str  # "string" | "number" | "boolean" | "select" | "secret"
    label: str = ""
    description: str = ""
    required: bool = False
    default: Any = None
    options: list[str] = field(default_factory=list)  # For select type
    placeholder: str = ""
    sensitive: bool = False


@dataclass
class ChannelConfigSchema:
    """Configuration schema for a channel (for UI rendering)."""

    channel_type: str
    display_name: str
    fields: list[ConfigField] = field(default_factory=list)
    docs_url: str = ""
    category: str = ""  # "messaging" | "social" | "enterprise" | "other"

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema for validation."""
        properties: dict[str, Any] = {}
        required: list[str] = []

        for f in self.fields:
            prop: dict[str, Any] = {}
            type_map = {
                "string": "string",
                "number": "number",
                "boolean": "boolean",
                "select": "string",
                "secret": "string",
            }
            prop["type"] = type_map.get(f.field_type, "string")
            if f.description:
                prop["description"] = f.description
            if f.default is not None:
                prop["default"] = f.default
            if f.options:
                prop["enum"] = f.options
            properties[f.name] = prop

            if f.required:
                required.append(f.name)

        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required:
            schema["required"] = required
        return schema


@dataclass
class ChannelHealthReport:
    """Complete health report for a channel."""

    channel_id: str
    channel_type: str
    is_healthy: bool = True
    issues: list[ChannelIssue] = field(default_factory=list)
    last_check: float = 0.0
    uptime_s: float = 0.0
    message_count: int = 0
    error_count: int = 0

    def __post_init__(self) -> None:
        if self.last_check == 0.0:
            self.last_check = time.time()

    @property
    def error_issues(self) -> list[ChannelIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    @property
    def warning_issues(self) -> list[ChannelIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]


class ChannelHealthChecker:
    """Framework for running channel health checks."""

    def __init__(self) -> None:
        self._checks: list[tuple[str, Any]] = []  # (name, check_fn)
        self._last_reports: dict[str, ChannelHealthReport] = {}

    def add_check(self, name: str, check_fn: Any) -> None:
        """Register a health check function.

        check_fn(channel_id, channel_config) -> list[ChannelIssue]
        """
        self._checks.append((name, check_fn))

    def run_checks(
        self,
        channel_id: str,
        channel_type: str,
        config: dict[str, Any],
    ) -> ChannelHealthReport:
        """Run all registered checks against a channel."""
        issues: list[ChannelIssue] = []

        for name, check_fn in self._checks:
            try:
                result = check_fn(channel_id, config)
                if isinstance(result, list):
                    issues.extend(result)
                elif isinstance(result, ChannelIssue):
                    issues.append(result)
            except Exception as e:
                issues.append(
                    ChannelIssue(
                        code=f"check-error-{name}",
                        message=f"Health check '{name}' failed: {e}",
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.CONFIG,
                    )
                )

        is_healthy = not any(i.severity == IssueSeverity.ERROR for i in issues)
        report = ChannelHealthReport(
            channel_id=channel_id,
            channel_type=channel_type,
            is_healthy=is_healthy,
            issues=issues,
        )
        self._last_reports[channel_id] = report
        return report

    def get_last_report(self, channel_id: str) -> ChannelHealthReport | None:
        return self._last_reports.get(channel_id)

    @property
    def check_count(self) -> int:
        return len(self._checks)


# ---------------------------------------------------------------------------
# Common health checks
# ---------------------------------------------------------------------------


def check_api_key(channel_id: str, config: dict[str, Any]) -> list[ChannelIssue]:
    """Check if required API key / token is present."""
    issues: list[ChannelIssue] = []
    for key in ("api_key", "token", "bot_token", "access_token"):
        if key in config and not config[key]:
            issues.append(
                ChannelIssue(
                    code="missing-auth",
                    message=f"Required authentication field '{key}' is empty",
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.AUTH,
                    fix_hint=f"Set {key} in channel configuration",
                )
            )
    return issues


def check_webhook_url(channel_id: str, config: dict[str, Any]) -> list[ChannelIssue]:
    """Check if webhook URL is properly configured."""
    issues: list[ChannelIssue] = []
    webhook = config.get("webhook_url", "")
    if webhook and not webhook.startswith("https://"):
        issues.append(
            ChannelIssue(
                code="insecure-webhook",
                message="Webhook URL should use HTTPS",
                severity=IssueSeverity.WARNING,
                category=IssueCategory.WEBHOOK,
                fix_hint="Use an HTTPS URL for the webhook",
            )
        )
    return issues
