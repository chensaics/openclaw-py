"""Allowlist boundary enforcement — DM-group isolation and pairing-store constraints.

Ported from ``src/security/`` allowlist and pairing boundary logic.

Ensures:
- DM allowlists and group allowlists are evaluated independently
- Pairing-store entries are DM-only (never auto-grant group access)
- Cross-boundary leaks are detected and reported
- Allowlist entries can be scoped to specific channels
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AllowlistScope(str, Enum):
    DM = "dm"
    GROUP = "group"
    BOTH = "both"


class AllowlistSource(str, Enum):
    CONFIG = "config"
    PAIRING = "pairing"
    RUNTIME = "runtime"


@dataclass
class AllowlistEntry:
    """A single allowlist entry with scope and source tracking."""

    sender_id: str
    scope: AllowlistScope = AllowlistScope.DM
    source: AllowlistSource = AllowlistSource.CONFIG
    channel_id: str = ""  # empty = all channels
    added_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BoundaryViolation:
    """A detected boundary violation."""

    sender_id: str
    violation_type: str
    detail: str
    channel_id: str = ""


class AllowlistBoundaryStore:
    """Manages allowlist entries with DM-group boundary enforcement."""

    def __init__(self) -> None:
        self._entries: dict[str, AllowlistEntry] = {}
        self._violations: list[BoundaryViolation] = []

    def add_entry(self, entry: AllowlistEntry) -> None:
        """Add an allowlist entry."""
        key = self._key(entry.sender_id, entry.channel_id)

        # Pairing-store entries are DM-only
        if entry.source == AllowlistSource.PAIRING and entry.scope != AllowlistScope.DM:
            violation = BoundaryViolation(
                sender_id=entry.sender_id,
                violation_type="pairing_scope_violation",
                detail=f"Pairing entry forced to DM scope (was {entry.scope.value})",
                channel_id=entry.channel_id,
            )
            self._violations.append(violation)
            logger.warning(
                "Pairing entry scope forced to DM: sender=%s channel=%s",
                entry.sender_id,
                entry.channel_id,
            )
            entry.scope = AllowlistScope.DM

        self._entries[key] = entry

    def remove_entry(self, sender_id: str, *, channel_id: str = "") -> None:
        key = self._key(sender_id, channel_id)
        self._entries.pop(key, None)

    def is_allowed(
        self,
        sender_id: str,
        *,
        is_group: bool = False,
        channel_id: str = "",
    ) -> bool:
        """Check if a sender is allowed for the given context.

        Enforces DM-group boundary: DM-scoped entries do not grant group access.
        """
        # Check channel-specific entry first
        entry = self._entries.get(self._key(sender_id, channel_id))

        # Fallback to global entry
        if entry is None and channel_id:
            entry = self._entries.get(self._key(sender_id, ""))

        if entry is None:
            return False

        if entry.scope == AllowlistScope.BOTH:
            return True

        if is_group:
            if entry.scope == AllowlistScope.DM:
                return False
            return entry.scope == AllowlistScope.GROUP

        # DM context
        if entry.scope == AllowlistScope.GROUP:
            return False
        return entry.scope == AllowlistScope.DM

    def get_dm_allowed(self, *, channel_id: str = "") -> set[str]:
        """Get all sender IDs allowed for DMs."""
        return {
            e.sender_id
            for e in self._entries.values()
            if e.scope in (AllowlistScope.DM, AllowlistScope.BOTH)
            and (not channel_id or not e.channel_id or e.channel_id == channel_id)
        }

    def get_group_allowed(self, *, channel_id: str = "") -> set[str]:
        """Get all sender IDs allowed for groups."""
        return {
            e.sender_id
            for e in self._entries.values()
            if e.scope in (AllowlistScope.GROUP, AllowlistScope.BOTH)
            and (not channel_id or not e.channel_id or e.channel_id == channel_id)
        }

    def get_violations(self) -> list[BoundaryViolation]:
        return list(self._violations)

    def clear_violations(self) -> None:
        self._violations.clear()

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def _key(self, sender_id: str, channel_id: str) -> str:
        return f"{channel_id}:{sender_id}" if channel_id else f"*:{sender_id}"


def validate_pairing_dm_only(
    pairing_entries: list[dict[str, Any]],
) -> tuple[list[AllowlistEntry], list[BoundaryViolation]]:
    """Validate that pairing-store entries are DM-only.

    Returns valid entries and detected violations.
    """
    valid: list[AllowlistEntry] = []
    violations: list[BoundaryViolation] = []

    for raw in pairing_entries:
        sender_id = raw.get("sender_id", raw.get("senderId", ""))
        scope_str = raw.get("scope", "dm")
        channel_id = raw.get("channel_id", raw.get("channelId", ""))

        try:
            scope = AllowlistScope(scope_str)
        except ValueError:
            scope = AllowlistScope.DM

        if scope != AllowlistScope.DM:
            violations.append(
                BoundaryViolation(
                    sender_id=sender_id,
                    violation_type="pairing_non_dm_scope",
                    detail=f"Pairing entry has scope={scope.value}, forced to dm",
                    channel_id=channel_id,
                )
            )
            scope = AllowlistScope.DM

        valid.append(
            AllowlistEntry(
                sender_id=sender_id,
                scope=scope,
                source=AllowlistSource.PAIRING,
                channel_id=channel_id,
            )
        )

    return valid, violations
