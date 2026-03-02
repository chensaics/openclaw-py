"""Tests for agent bindings — routing, apply, remove, spec parsing."""

from __future__ import annotations

import pytest

from pyclaw.routing.bindings import (
    AgentBinding,
    AgentBindingMatch,
    PeerMatch,
    apply_agent_bindings,
    binding_from_dict,
    binding_match_key,
    binding_to_dict,
    describe_binding,
    parse_binding_spec,
    remove_agent_bindings,
    resolve_agent_route,
)


# ---------------------------------------------------------------------------
# Binding spec parsing
# ---------------------------------------------------------------------------

class TestParseBindingSpec:
    def test_channel_only(self) -> None:
        match = parse_binding_spec("telegram")
        assert match.channel == "telegram"
        assert match.account_id is None

    def test_channel_with_account(self) -> None:
        match = parse_binding_spec("discord:123456")
        assert match.channel == "discord"
        assert match.account_id == "123456"

    def test_channel_with_whitespace(self) -> None:
        match = parse_binding_spec("  slack : T01234 ")
        assert match.channel == "slack"
        assert match.account_id == "T01234"


# ---------------------------------------------------------------------------
# Apply bindings
# ---------------------------------------------------------------------------

class TestApplyBindings:
    def test_add_new_binding(self) -> None:
        existing: list[AgentBinding] = []
        incoming = [AgentBinding(
            agent_id="main",
            match=AgentBindingMatch(channel="telegram"),
        )]
        result = apply_agent_bindings(existing, incoming)
        assert len(result.added) == 1
        assert result.added[0].match.channel == "telegram"

    def test_skip_duplicate(self) -> None:
        existing = [AgentBinding(
            agent_id="main",
            match=AgentBindingMatch(channel="telegram"),
        )]
        incoming = [AgentBinding(
            agent_id="main",
            match=AgentBindingMatch(channel="telegram"),
        )]
        result = apply_agent_bindings(existing, incoming)
        assert len(result.skipped) == 1
        assert len(result.added) == 0

    def test_conflict(self) -> None:
        existing = [AgentBinding(
            agent_id="main",
            match=AgentBindingMatch(channel="telegram"),
        )]
        incoming = [AgentBinding(
            agent_id="other",
            match=AgentBindingMatch(channel="telegram"),
        )]
        result = apply_agent_bindings(existing, incoming)
        assert len(result.conflicts) == 1

    def test_upgrade_to_account_scoped(self) -> None:
        existing = [AgentBinding(
            agent_id="main",
            match=AgentBindingMatch(channel="discord"),
        )]
        incoming = [AgentBinding(
            agent_id="main",
            match=AgentBindingMatch(channel="discord", account_id="123"),
        )]
        result = apply_agent_bindings(existing, incoming)
        assert len(result.updated) == 1
        assert result.updated[0].match.account_id == "123"


# ---------------------------------------------------------------------------
# Remove bindings
# ---------------------------------------------------------------------------

class TestRemoveBindings:
    def test_remove_by_spec(self) -> None:
        existing = [
            AgentBinding(agent_id="main", match=AgentBindingMatch(channel="telegram")),
            AgentBinding(agent_id="main", match=AgentBindingMatch(channel="discord")),
        ]
        specs = [AgentBindingMatch(channel="telegram")]
        remaining, removed = remove_agent_bindings(existing, specs)
        assert len(remaining) == 1
        assert len(removed) == 1
        assert removed[0].match.channel == "telegram"

    def test_remove_all_for_agent(self) -> None:
        existing = [
            AgentBinding(agent_id="main", match=AgentBindingMatch(channel="telegram")),
            AgentBinding(agent_id="other", match=AgentBindingMatch(channel="discord")),
        ]
        remaining, removed = remove_agent_bindings(
            existing, [], agent_id="main", remove_all=True
        )
        assert len(remaining) == 1
        assert remaining[0].agent_id == "other"
        assert len(removed) == 1


# ---------------------------------------------------------------------------
# Route resolution (7-tier)
# ---------------------------------------------------------------------------

class TestResolveAgentRoute:
    def test_channel_only(self) -> None:
        bindings = [AgentBinding(agent_id="bot1", match=AgentBindingMatch(channel="telegram"))]
        result = resolve_agent_route(bindings, "telegram")
        assert result is not None
        assert result.agent_id == "bot1"

    def test_no_match(self) -> None:
        bindings = [AgentBinding(agent_id="bot1", match=AgentBindingMatch(channel="telegram"))]
        result = resolve_agent_route(bindings, "discord")
        assert result is None

    def test_peer_specific_priority(self) -> None:
        bindings = [
            AgentBinding(agent_id="generic", match=AgentBindingMatch(channel="discord")),
            AgentBinding(
                agent_id="specific",
                match=AgentBindingMatch(
                    channel="discord",
                    peer=PeerMatch(kind="direct", id="user123"),
                ),
            ),
        ]
        result = resolve_agent_route(
            bindings, "discord", peer_kind="direct", peer_id="user123"
        )
        assert result is not None
        assert result.agent_id == "specific"

    def test_guild_priority_over_channel(self) -> None:
        bindings = [
            AgentBinding(agent_id="channel-bot", match=AgentBindingMatch(channel="discord")),
            AgentBinding(
                agent_id="guild-bot",
                match=AgentBindingMatch(channel="discord", guild_id="G123"),
            ),
        ]
        result = resolve_agent_route(bindings, "discord", guild_id="G123")
        assert result is not None
        assert result.agent_id == "guild-bot"

    def test_account_scoped(self) -> None:
        bindings = [
            AgentBinding(agent_id="default", match=AgentBindingMatch(channel="slack")),
            AgentBinding(
                agent_id="team-bot",
                match=AgentBindingMatch(channel="slack", account_id="T01234"),
            ),
        ]
        result = resolve_agent_route(bindings, "slack", account_id="T01234")
        assert result is not None
        assert result.agent_id == "team-bot"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestBindingSerialization:
    def test_roundtrip(self) -> None:
        binding = AgentBinding(
            agent_id="main",
            match=AgentBindingMatch(
                channel="discord",
                account_id="123",
                peer=PeerMatch(kind="direct", id="user1"),
                guild_id="G1",
            ),
        )
        data = binding_to_dict(binding)
        restored = binding_from_dict(data)
        assert restored.agent_id == "main"
        assert restored.match.channel == "discord"
        assert restored.match.account_id == "123"
        assert restored.match.peer is not None
        assert restored.match.peer.id == "user1"
        assert restored.match.guild_id == "G1"

    def test_describe(self) -> None:
        binding = AgentBinding(
            agent_id="main",
            match=AgentBindingMatch(channel="telegram"),
        )
        desc = describe_binding(binding)
        assert "telegram" in desc
