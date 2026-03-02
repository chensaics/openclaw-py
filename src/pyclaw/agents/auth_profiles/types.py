"""Auth profile type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CredentialType = Literal["api_key", "token", "oauth"]
FailureReason = Literal[
    "auth",
    "auth_permanent",
    "format",
    "rate_limit",
    "billing",
    "timeout",
    "model_not_found",
    "unknown",
]


@dataclass
class ApiKeyCredential:
    type: Literal["api_key"] = "api_key"
    provider: str = ""
    key: str = ""
    key_ref: dict[str, Any] | None = None
    email: str = ""
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenCredential:
    type: Literal["token"] = "token"
    provider: str = ""
    token: str = ""
    token_ref: dict[str, Any] | None = None
    expires: str = ""
    email: str = ""
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OAuthCredential:
    type: Literal["oauth"] = "oauth"
    provider: str = ""
    client_id: str = ""
    email: str = ""
    label: str = ""
    access_token: str = ""
    refresh_token: str = ""
    expires_at: str = ""
    scope: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


AuthProfileCredential = ApiKeyCredential | TokenCredential | OAuthCredential


@dataclass
class ProfileUsageStats:
    last_used: str = ""
    cooldown_until: str = ""
    disabled_until: str = ""
    disabled_reason: str = ""
    error_count: int = 0
    failure_counts: dict[str, int] = field(default_factory=dict)
    last_failure_at: str = ""


@dataclass
class AuthProfileStore:
    """Root data model for the auth-profiles.json file."""

    version: int = 1
    profiles: dict[str, AuthProfileCredential] = field(default_factory=dict)
    order: dict[str, list[str]] = field(default_factory=dict)
    last_good: dict[str, str] = field(default_factory=dict)
    usage_stats: dict[str, ProfileUsageStats] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"version": self.version, "profiles": {}}
        for pid, cred in self.profiles.items():
            d: dict[str, Any] = {}
            for k, v in cred.__dict__.items():
                if k == "key_ref":
                    d["keyRef"] = v
                elif k == "token_ref":
                    d["tokenRef"] = v
                elif k == "client_id":
                    d["clientId"] = v
                elif k == "access_token":
                    d["accessToken"] = v
                elif k == "refresh_token":
                    d["refreshToken"] = v
                elif k == "expires_at":
                    d["expiresAt"] = v
                else:
                    d[k] = v
            result["profiles"][pid] = d

        if self.order:
            result["order"] = self.order
        if self.last_good:
            result["lastGood"] = self.last_good
        if self.usage_stats:
            result["usageStats"] = {}
            for pid, stats in self.usage_stats.items():
                result["usageStats"][pid] = {
                    "lastUsed": stats.last_used,
                    "cooldownUntil": stats.cooldown_until,
                    "disabledUntil": stats.disabled_until,
                    "disabledReason": stats.disabled_reason,
                    "errorCount": stats.error_count,
                    "failureCounts": stats.failure_counts,
                    "lastFailureAt": stats.last_failure_at,
                }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuthProfileStore:
        store = cls(version=data.get("version", 1))

        for pid, raw in data.get("profiles", {}).items():
            cred_type = raw.get("type", "api_key")
            # Normalize legacy "mode" → "type"
            if "mode" in raw and "type" not in raw:
                cred_type = raw["mode"]

            if cred_type == "api_key":
                store.profiles[pid] = ApiKeyCredential(
                    provider=raw.get("provider", ""),
                    key=raw.get("key", raw.get("apiKey", "")),
                    key_ref=raw.get("keyRef"),
                    email=raw.get("email", ""),
                    label=raw.get("label", ""),
                    metadata=raw.get("metadata", {}),
                )
            elif cred_type == "token":
                store.profiles[pid] = TokenCredential(
                    provider=raw.get("provider", ""),
                    token=raw.get("token", ""),
                    token_ref=raw.get("tokenRef"),
                    expires=raw.get("expires", ""),
                    email=raw.get("email", ""),
                    label=raw.get("label", ""),
                    metadata=raw.get("metadata", {}),
                )
            elif cred_type == "oauth":
                store.profiles[pid] = OAuthCredential(
                    provider=raw.get("provider", ""),
                    client_id=raw.get("clientId", ""),
                    email=raw.get("email", ""),
                    label=raw.get("label", ""),
                    access_token=raw.get("accessToken", ""),
                    refresh_token=raw.get("refreshToken", ""),
                    expires_at=raw.get("expiresAt", ""),
                    scope=raw.get("scope", ""),
                    metadata=raw.get("metadata", {}),
                )

        store.order = data.get("order", {})
        store.last_good = data.get("lastGood", {})

        for pid, raw_stats in data.get("usageStats", {}).items():
            store.usage_stats[pid] = ProfileUsageStats(
                last_used=raw_stats.get("lastUsed", ""),
                cooldown_until=raw_stats.get("cooldownUntil", ""),
                disabled_until=raw_stats.get("disabledUntil", ""),
                disabled_reason=raw_stats.get("disabledReason", ""),
                error_count=raw_stats.get("errorCount", 0),
                failure_counts=raw_stats.get("failureCounts", {}),
                last_failure_at=raw_stats.get("lastFailureAt", ""),
            )

        return store
