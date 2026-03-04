"""Agent bindings — account-scoped routing with 7-tier priority matching.

Ported from ``src/commands/agents.bindings.ts`` and
``src/routing/resolve-route.ts``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pyclaw.routing.session_key import normalize_agent_id

logger = logging.getLogger(__name__)

DEFAULT_ACCOUNT_ID = "*"


@dataclass
class PeerMatch:
    kind: str  # "direct", "group", "channel"
    id: str


@dataclass
class AgentBindingMatch:
    channel: str
    account_id: str | None = None
    peer: PeerMatch | None = None
    guild_id: str | None = None
    team_id: str | None = None
    roles: list[str] | None = None


@dataclass
class AgentBinding:
    agent_id: str
    match: AgentBindingMatch
    comment: str | None = None


def binding_match_identity_key(match: AgentBindingMatch) -> str:
    """Build a stable identity key for a binding match (excluding account)."""
    roles = sorted(set(r.strip() for r in (match.roles or []) if r.strip()))
    return "|".join(
        [
            match.channel,
            (match.peer.kind if match.peer else ""),
            (match.peer.id if match.peer else ""),
            match.guild_id or "",
            match.team_id or "",
            ",".join(roles),
        ]
    )


def binding_match_key(match: AgentBindingMatch) -> str:
    """Build a full match key including account."""
    account_id = (match.account_id or "").strip() or DEFAULT_ACCOUNT_ID
    return f"{binding_match_identity_key(match)}|{account_id}"


def describe_binding(binding: AgentBinding) -> str:
    """Human-readable description of a binding."""
    parts = [binding.match.channel]
    if binding.match.account_id:
        parts.append(f"accountId={binding.match.account_id}")
    if binding.match.peer:
        parts.append(f"peer={binding.match.peer.kind}:{binding.match.peer.id}")
    if binding.match.guild_id:
        parts.append(f"guild={binding.match.guild_id}")
    if binding.match.team_id:
        parts.append(f"team={binding.match.team_id}")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Apply / manage bindings
# ---------------------------------------------------------------------------


@dataclass
class ApplyBindingsResult:
    bindings: list[AgentBinding]
    added: list[AgentBinding] = field(default_factory=list)
    updated: list[AgentBinding] = field(default_factory=list)
    skipped: list[AgentBinding] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)


def apply_agent_bindings(
    existing: list[AgentBinding],
    incoming: list[AgentBinding],
) -> ApplyBindingsResult:
    """Apply new bindings, detecting conflicts and upgrades."""
    all_bindings = list(existing)
    existing_map: dict[str, str] = {}
    for b in all_bindings:
        key = binding_match_key(b.match)
        if key not in existing_map:
            existing_map[key] = normalize_agent_id(b.agent_id)

    result = ApplyBindingsResult(bindings=all_bindings)

    for binding in incoming:
        agent_id = normalize_agent_id(binding.agent_id)
        key = binding_match_key(binding.match)
        existing_agent = existing_map.get(key)

        if existing_agent:
            if existing_agent == agent_id:
                result.skipped.append(binding)
            else:
                result.conflicts.append(
                    {
                        "binding": binding,
                        "existingAgentId": existing_agent,
                    }
                )
            continue

        # Check for account-scope upgrade
        upgrade_idx = _find_upgrade_candidate(all_bindings, binding, agent_id)
        if upgrade_idx is not None:
            current = all_bindings[upgrade_idx]
            old_key = binding_match_key(current.match)
            upgraded = AgentBinding(
                agent_id=agent_id,
                match=AgentBindingMatch(
                    channel=current.match.channel,
                    account_id=(binding.match.account_id or "").strip() or None,
                    peer=current.match.peer,
                    guild_id=current.match.guild_id,
                    team_id=current.match.team_id,
                    roles=current.match.roles,
                ),
                comment=current.comment,
            )
            all_bindings[upgrade_idx] = upgraded
            existing_map.pop(old_key, None)
            existing_map[binding_match_key(upgraded.match)] = agent_id
            result.updated.append(upgraded)
            continue

        existing_map[key] = agent_id
        result.added.append(AgentBinding(agent_id=agent_id, match=binding.match, comment=binding.comment))

    result.bindings = all_bindings + result.added
    return result


def remove_agent_bindings(
    existing: list[AgentBinding],
    specs: list[AgentBindingMatch],
    *,
    agent_id: str | None = None,
    remove_all: bool = False,
) -> tuple[list[AgentBinding], list[AgentBinding]]:
    """Remove bindings matching the given specs or agent_id.

    Returns (remaining, removed).
    """
    if remove_all and agent_id:
        normalized = normalize_agent_id(agent_id)
        removed = [b for b in existing if normalize_agent_id(b.agent_id) == normalized]
        remaining = [b for b in existing if normalize_agent_id(b.agent_id) != normalized]
        return remaining, removed

    spec_keys = {binding_match_key(s) for s in specs}
    remaining_bindings: list[AgentBinding] = []
    removed_bindings: list[AgentBinding] = []
    for b in existing:
        key = binding_match_key(b.match)
        if key in spec_keys:
            if agent_id and normalize_agent_id(b.agent_id) != normalize_agent_id(agent_id):
                remaining_bindings.append(b)
            else:
                removed_bindings.append(b)
        else:
            remaining_bindings.append(b)
    return remaining_bindings, removed_bindings


def _find_upgrade_candidate(
    bindings: list[AgentBinding],
    incoming: AgentBinding,
    incoming_agent_id: str,
) -> int | None:
    """Find a binding that can be upgraded from channel-only to account-scoped."""
    if not (incoming.match.account_id or "").strip():
        return None
    for i, existing in enumerate(bindings):
        if (existing.match.account_id or "").strip():
            continue
        if normalize_agent_id(existing.agent_id) != incoming_agent_id:
            continue
        if binding_match_identity_key(existing.match) == binding_match_identity_key(incoming.match):
            return i
    return None


# ---------------------------------------------------------------------------
# Route resolution with 7-tier priority
# ---------------------------------------------------------------------------


def resolve_agent_route(
    bindings: list[AgentBinding],
    channel: str,
    *,
    account_id: str | None = None,
    peer_kind: str | None = None,
    peer_id: str | None = None,
    guild_id: str | None = None,
    team_id: str | None = None,
    roles: list[str] | None = None,
) -> AgentBinding | None:
    """Resolve the best-matching binding using 7-tier priority.

    Priority (highest to lowest):
    1. peer-specific (channel + peer.kind + peer.id)
    2. parent-peer (channel + peer parent)
    3. guild+roles (channel + guildId + roles)
    4. guild-only (channel + guildId)
    5. team-only (channel + teamId)
    6. account-scoped (channel + accountId)
    7. channel-only (channel)
    """
    candidates = [b for b in bindings if b.match.channel == channel]
    if not candidates:
        return None

    # Filter by account if provided
    if account_id:
        account_candidates = [b for b in candidates if _matches_account(b.match.account_id, account_id)]
        if account_candidates:
            candidates = account_candidates

    best: AgentBinding | None = None
    best_tier = 999

    for b in candidates:
        tier = _binding_tier(b.match, peer_kind, peer_id, guild_id, team_id, roles)
        if tier < best_tier:
            best_tier = tier
            best = b

    return best


def _matches_account(binding_account: str | None, request_account: str) -> bool:
    if not binding_account or binding_account.strip() == "" or binding_account == "*":
        return True
    return binding_account.strip() == request_account.strip()


def _binding_tier(
    match: AgentBindingMatch,
    peer_kind: str | None,
    peer_id: str | None,
    guild_id: str | None,
    team_id: str | None,
    roles: list[str] | None,
) -> int:
    # Tier 1: peer-specific
    if match.peer and peer_kind and peer_id and match.peer.kind == peer_kind and match.peer.id == peer_id:
        return 1

    # Tier 3: guild+roles
    if match.guild_id and match.roles and guild_id and roles and match.guild_id == guild_id:
        match_roles = set(match.roles)
        if match_roles.issubset(set(roles)):
            return 3

    # Tier 4: guild-only
    if match.guild_id and not match.roles and guild_id and match.guild_id == guild_id:
        return 4

    # Tier 5: team-only
    if match.team_id and team_id and match.team_id == team_id:
        return 5

    # Tier 6: account-scoped
    if match.account_id and match.account_id != "*" and not match.peer and not match.guild_id and not match.team_id:
        return 6

    # Tier 7: channel-only
    if not match.peer and not match.guild_id and not match.team_id:
        if not match.account_id or match.account_id == "*":
            return 7

    return 999  # no match


# ---------------------------------------------------------------------------
# Binding spec parsing (CLI)
# ---------------------------------------------------------------------------


def parse_binding_spec(spec: str) -> AgentBindingMatch:
    """Parse a binding spec string like ``channel[:accountId]``.

    Examples: ``telegram``, ``discord:123456``, ``slack:T01234``
    """
    parts = spec.split(":", 1)
    channel = parts[0].strip()
    account_id = parts[1].strip() if len(parts) > 1 else None
    return AgentBindingMatch(channel=channel, account_id=account_id)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def binding_to_dict(binding: AgentBinding) -> dict[str, Any]:
    result: dict[str, Any] = {
        "agentId": binding.agent_id,
        "match": {"channel": binding.match.channel},
    }
    if binding.match.account_id:
        result["match"]["accountId"] = binding.match.account_id
    if binding.match.peer:
        result["match"]["peer"] = {"kind": binding.match.peer.kind, "id": binding.match.peer.id}
    if binding.match.guild_id:
        result["match"]["guildId"] = binding.match.guild_id
    if binding.match.team_id:
        result["match"]["teamId"] = binding.match.team_id
    if binding.match.roles:
        result["match"]["roles"] = binding.match.roles
    if binding.comment:
        result["comment"] = binding.comment
    return result


def binding_from_dict(data: dict[str, Any]) -> AgentBinding:
    match_data = data.get("match", {})
    peer = None
    if "peer" in match_data:
        peer = PeerMatch(kind=match_data["peer"].get("kind", "direct"), id=match_data["peer"].get("id", ""))
    return AgentBinding(
        agent_id=data.get("agentId", "main"),
        match=AgentBindingMatch(
            channel=match_data.get("channel", ""),
            account_id=match_data.get("accountId"),
            peer=peer,
            guild_id=match_data.get("guildId"),
            team_id=match_data.get("teamId"),
            roles=match_data.get("roles"),
        ),
        comment=data.get("comment"),
    )
