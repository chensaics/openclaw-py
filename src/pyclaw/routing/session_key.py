"""Session key utilities — compatible with TypeScript session key format.

Session key formats:
  - agent:{agentId}:{mainKey}                                (main DM)
  - agent:{agentId}:{channel}:direct:{peerId}                (per-peer DM)
  - agent:{agentId}:{channel}:{accountId}:direct:{peerId}    (per-account-channel-peer)
  - agent:{agentId}:{channel}:{peerKind}:{peerId}            (group/channel)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedSessionKey:
    agent_id: str
    rest: str


def parse_session_key(key: str) -> ParsedSessionKey | None:
    """Parse an agent session key into its components.

    Returns None if the key is malformed.
    """
    parts = key.split(":")
    if len(parts) < 3 or parts[0] != "agent":
        return None
    agent_id = parts[1]
    rest = ":".join(parts[2:])
    if not agent_id or not rest:
        return None
    return ParsedSessionKey(agent_id=agent_id, rest=rest)


def build_main_session_key(agent_id: str, main_key: str = "main") -> str:
    """Build a main session key: agent:{agentId}:{mainKey}."""
    return f"agent:{agent_id}:{main_key}"


def build_peer_session_key(
    agent_id: str,
    channel: str,
    peer_id: str,
    peer_kind: str = "direct",
    account_id: str | None = None,
) -> str:
    """Build a peer-scoped session key."""
    if account_id:
        return f"agent:{agent_id}:{channel}:{account_id}:{peer_kind}:{peer_id}"
    return f"agent:{agent_id}:{channel}:{peer_kind}:{peer_id}"


def normalize_agent_id(agent_id: str | None) -> str:
    """Normalize agent ID, defaulting to 'main'."""
    return agent_id or "main"
