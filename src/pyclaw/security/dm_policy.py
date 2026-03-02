"""DM and group access policy resolution.

Ported from ``src/security/dm-policy-shared.ts``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal


class DmGroupAccessDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    PAIRING = "pairing"


DmPolicy = Literal["allowlist", "open", "pairing", "disabled"]
GroupPolicy = Literal["allowlist", "disabled"]


def resolve_effective_allow_from(
    config_allow_list: list[str] | None = None,
    pairing_allow_list: list[str] | None = None,
) -> set[str]:
    """Merge config-based and pairing-based allowlists."""
    result: set[str] = set()
    if config_allow_list:
        result.update(config_allow_list)
    if pairing_allow_list:
        result.update(pairing_allow_list)
    return result


def resolve_dm_group_access(
    sender_id: str,
    *,
    is_group: bool = False,
    dm_policy: DmPolicy = "allowlist",
    group_policy: GroupPolicy = "allowlist",
    config_allow_list: list[str] | None = None,
    pairing_allow_list: list[str] | None = None,
) -> DmGroupAccessDecision:
    """Decide whether a sender should be allowed, blocked, or prompted to pair.

    Args:
        sender_id: the sender's channel-specific ID.
        is_group: True if the message is in a group context.
        dm_policy: DM access policy setting.
        group_policy: Group access policy setting.
        config_allow_list: manually configured allow list.
        pairing_allow_list: allow list from completed pairings.
    """
    effective = resolve_effective_allow_from(config_allow_list, pairing_allow_list)

    if is_group:
        if group_policy == "disabled":
            return DmGroupAccessDecision.BLOCK
        # group allowlist
        if sender_id in effective:
            return DmGroupAccessDecision.ALLOW
        return DmGroupAccessDecision.BLOCK

    # DM
    if dm_policy == "disabled":
        return DmGroupAccessDecision.BLOCK
    if dm_policy == "open":
        return DmGroupAccessDecision.ALLOW
    if dm_policy == "pairing":
        if sender_id in effective:
            return DmGroupAccessDecision.ALLOW
        return DmGroupAccessDecision.PAIRING

    # allowlist
    if sender_id in effective:
        return DmGroupAccessDecision.ALLOW
    return DmGroupAccessDecision.BLOCK
