"""Channel authorization guard — unified DM/group/reaction/interaction auth checks.

Ported from ``src/channels/`` auth logic and ``src/security/audit-channel.ts``.

Provides a fail-closed authorization framework that:
- Gates DM messages, group messages, reactions, and interactions
- Supports per-channel auth config overrides
- Integrates with allowlists and pairing store
- Logs denied attempts for auditing
- Supports rate-limiting auth checks per sender
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyclaw.security.dm_policy import (
    DmGroupAccessDecision,
    DmPolicy,
    GroupPolicy,
    resolve_dm_group_access,
    resolve_effective_allow_from,
)

logger = logging.getLogger(__name__)


class AuthAction(str, Enum):
    MESSAGE = "message"
    REACTION = "reaction"
    INTERACTION = "interaction"
    COMMAND = "command"
    FILE_UPLOAD = "file_upload"


class AuthDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    PAIRING = "pairing"
    RATE_LIMITED = "rate_limited"


@dataclass
class AuthRequest:
    """An authorization request for a channel action."""

    channel_id: str
    sender_id: str
    action: AuthAction
    is_group: bool = False
    group_id: str = ""
    chat_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthResponse:
    """The result of an authorization check."""

    decision: AuthDecision
    reason: str = ""
    request: AuthRequest | None = None


@dataclass
class ChannelAuthConfig:
    """Per-channel authorization configuration."""

    channel_id: str
    dm_policy: DmPolicy = "allowlist"
    group_policy: GroupPolicy = "allowlist"
    allow_reactions: bool = True
    allow_interactions: bool = True
    allow_file_uploads: bool = True
    config_allow_list: list[str] | None = None
    pairing_allow_list: list[str] | None = None
    owner_ids: set[str] = field(default_factory=set)
    # Rate limiting
    max_auth_checks_per_minute: int = 60


class AuthRateLimiter:
    """Per-sender rate limiter for auth checks to prevent enumeration attacks."""

    def __init__(self, max_per_minute: int = 60) -> None:
        self._max = max_per_minute
        self._window_s = 60.0
        self._buckets: dict[str, list[float]] = {}

    def check(self, sender_id: str) -> bool:
        """Returns True if the sender is within rate limits."""
        now = time.time()
        cutoff = now - self._window_s

        if sender_id not in self._buckets:
            self._buckets[sender_id] = []

        bucket = self._buckets[sender_id]
        bucket[:] = [t for t in bucket if t > cutoff]

        if len(bucket) >= self._max:
            return False

        bucket.append(now)
        return True

    def reset(self, sender_id: str) -> None:
        self._buckets.pop(sender_id, None)


class ChannelAuthGuard:
    """Unified authorization guard for all channel actions.

    Fail-closed: unknown actions or missing config result in denial.
    """

    def __init__(self) -> None:
        self._configs: dict[str, ChannelAuthConfig] = {}
        self._rate_limiters: dict[str, AuthRateLimiter] = {}
        self._deny_log: list[AuthResponse] = []
        self._max_deny_log = 1000

    def register_channel(self, config: ChannelAuthConfig) -> None:
        """Register auth configuration for a channel."""
        self._configs[config.channel_id] = config
        self._rate_limiters[config.channel_id] = AuthRateLimiter(
            max_per_minute=config.max_auth_checks_per_minute,
        )

    def unregister_channel(self, channel_id: str) -> None:
        self._configs.pop(channel_id, None)
        self._rate_limiters.pop(channel_id, None)

    def check(self, request: AuthRequest) -> AuthResponse:
        """Check authorization for a channel action. Fail-closed on unknown."""
        config = self._configs.get(request.channel_id)
        if not config:
            return self._deny(request, "no auth config registered for channel")

        # Rate limiting
        limiter = self._rate_limiters.get(request.channel_id)
        if limiter and not limiter.check(request.sender_id):
            return self._deny(request, "rate limited", AuthDecision.RATE_LIMITED)

        # Owner bypass
        if request.sender_id in config.owner_ids:
            return AuthResponse(decision=AuthDecision.ALLOW, reason="owner", request=request)

        if request.action == AuthAction.MESSAGE:
            return self._check_message(request, config)
        elif request.action == AuthAction.REACTION:
            return self._check_reaction(request, config)
        elif request.action == AuthAction.INTERACTION:
            return self._check_interaction(request, config)
        elif request.action == AuthAction.COMMAND:
            return self._check_command(request, config)
        elif request.action == AuthAction.FILE_UPLOAD:
            return self._check_file_upload(request, config)

        # Fail-closed for unknown actions
        return self._deny(request, f"unknown action: {request.action}")

    def get_deny_log(self, *, limit: int = 50) -> list[AuthResponse]:
        """Get recent deny log entries."""
        return self._deny_log[-limit:]

    def clear_deny_log(self) -> None:
        self._deny_log.clear()

    def _check_message(self, request: AuthRequest, config: ChannelAuthConfig) -> AuthResponse:
        """Check message authorization using DM/group policy."""
        decision = resolve_dm_group_access(
            request.sender_id,
            is_group=request.is_group,
            dm_policy=config.dm_policy,
            group_policy=config.group_policy,
            config_allow_list=config.config_allow_list,
            pairing_allow_list=config.pairing_allow_list,
        )

        if decision == DmGroupAccessDecision.ALLOW:
            return AuthResponse(decision=AuthDecision.ALLOW, request=request)
        elif decision == DmGroupAccessDecision.PAIRING:
            return AuthResponse(decision=AuthDecision.PAIRING, reason="pairing required", request=request)
        else:
            return self._deny(request, "message denied by policy")

    def _check_reaction(self, request: AuthRequest, config: ChannelAuthConfig) -> AuthResponse:
        """Reactions require allowlist membership AND reactions enabled."""
        if not config.allow_reactions:
            return self._deny(request, "reactions disabled for channel")

        effective = resolve_effective_allow_from(
            config.config_allow_list,
            config.pairing_allow_list,
        )
        if effective and request.sender_id not in effective:
            return self._deny(request, "reaction sender not in allowlist")

        return AuthResponse(decision=AuthDecision.ALLOW, request=request)

    def _check_interaction(self, request: AuthRequest, config: ChannelAuthConfig) -> AuthResponse:
        """Interactions (buttons, menus) require allowlist membership."""
        if not config.allow_interactions:
            return self._deny(request, "interactions disabled for channel")

        effective = resolve_effective_allow_from(
            config.config_allow_list,
            config.pairing_allow_list,
        )
        if effective and request.sender_id not in effective:
            return self._deny(request, "interaction sender not in allowlist")

        return AuthResponse(decision=AuthDecision.ALLOW, request=request)

    def _check_command(self, request: AuthRequest, config: ChannelAuthConfig) -> AuthResponse:
        """Commands require message-level auth."""
        return self._check_message(request, config)

    def _check_file_upload(self, request: AuthRequest, config: ChannelAuthConfig) -> AuthResponse:
        """File uploads require allowlist membership AND uploads enabled."""
        if not config.allow_file_uploads:
            return self._deny(request, "file uploads disabled for channel")

        effective = resolve_effective_allow_from(
            config.config_allow_list,
            config.pairing_allow_list,
        )
        if effective and request.sender_id not in effective:
            return self._deny(request, "file upload sender not in allowlist")

        return AuthResponse(decision=AuthDecision.ALLOW, request=request)

    def _deny(
        self,
        request: AuthRequest,
        reason: str,
        decision: AuthDecision = AuthDecision.DENY,
    ) -> AuthResponse:
        """Create a deny response and log it."""
        response = AuthResponse(decision=decision, reason=reason, request=request)

        logger.debug(
            "Auth denied: channel=%s sender=%s action=%s reason=%s",
            request.channel_id,
            request.sender_id,
            request.action.value,
            reason,
        )

        if len(self._deny_log) >= self._max_deny_log:
            self._deny_log = self._deny_log[-self._max_deny_log // 2 :]
        self._deny_log.append(response)

        return response
