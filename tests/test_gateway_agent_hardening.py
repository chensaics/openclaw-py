"""Tests for Phase 21 — Gateway + Agent hardening: WS flood guard, compaction,
config migrations, and command gating."""

from __future__ import annotations

import pytest

from pyclaw.agents.compaction_policy import (
    content_hash,
    detect_near_duplicates,
    estimate_tokens,
    filter_unavailable_tools,
    is_identifier_message,
    plan_compaction,
)
from pyclaw.channels.command_gating import (
    CommandGatingConfig,
    CommandGatingManager,
    CommandPermission,
)
from pyclaw.config.migrations import (
    ConfigMigrationRegistry,
    MigrationStep,
    StateMigrationRegistry,
    create_default_registry,
    detect_config_version,
)
from pyclaw.gateway.ws_guard import (
    WsFloodGuard,
    WsGuardConfig,
)

# ===== WS Flood Guard =====


class TestWsFloodGuard:
    def test_allows_normal_connections(self) -> None:
        guard = WsFloodGuard(WsGuardConfig(max_connections_per_window=10))
        for _ in range(5):
            assert guard.check_connection("1.2.3.4") is True

    def test_blocks_over_limit(self) -> None:
        guard = WsFloodGuard(WsGuardConfig(max_connections_per_window=3))
        for _ in range(3):
            guard.check_connection("1.2.3.4")
        assert guard.check_connection("1.2.3.4") is False

    def test_separate_ips(self) -> None:
        guard = WsFloodGuard(WsGuardConfig(max_connections_per_window=2))
        guard.check_connection("1.1.1.1")
        guard.check_connection("1.1.1.1")
        assert guard.check_connection("1.1.1.1") is False
        assert guard.check_connection("2.2.2.2") is True

    def test_auto_ban(self) -> None:
        guard = WsFloodGuard(WsGuardConfig(max_connections_per_window=2, ban_duration_s=100))
        guard.check_connection("1.1.1.1")
        guard.check_connection("1.1.1.1")
        guard.check_connection("1.1.1.1")  # triggers ban
        assert guard.is_banned("1.1.1.1") is True

    def test_unban(self) -> None:
        guard = WsFloodGuard(WsGuardConfig(max_connections_per_window=1, ban_duration_s=100))
        guard.check_connection("1.1.1.1")
        guard.check_connection("1.1.1.1")
        assert guard.is_banned("1.1.1.1") is True
        guard.unban("1.1.1.1")
        assert guard.is_banned("1.1.1.1") is False

    def test_disabled(self) -> None:
        guard = WsFloodGuard(WsGuardConfig(enabled=False))
        for _ in range(100):
            assert guard.check_connection("1.1.1.1") is True

    def test_ip_cap(self) -> None:
        guard = WsFloodGuard(WsGuardConfig(max_tracked_ips=3))
        guard.check_connection("1.1.1.1")
        guard.check_connection("2.2.2.2")
        guard.check_connection("3.3.3.3")
        assert guard.check_connection("4.4.4.4") is False

    def test_stats(self) -> None:
        guard = WsFloodGuard(WsGuardConfig(max_connections_per_window=2))
        guard.check_connection("1.1.1.1")
        guard.check_connection("1.1.1.1")
        guard.check_connection("1.1.1.1")  # blocked
        stats = guard.get_stats()
        assert stats["tracked_ips"] >= 1
        assert stats["total_blocked"] >= 1

    def test_recent_events(self) -> None:
        guard = WsFloodGuard(WsGuardConfig(max_connections_per_window=1))
        guard.check_connection("1.1.1.1")
        guard.check_connection("1.1.1.1")
        events = guard.get_recent_events()
        assert len(events) >= 1
        assert events[0].ip == "1.1.1.1"

    def test_reset(self) -> None:
        guard = WsFloodGuard(WsGuardConfig(max_connections_per_window=1))
        guard.check_connection("1.1.1.1")
        guard.check_connection("1.1.1.1")
        guard.reset()
        assert guard.get_stats()["tracked_ips"] == 0
        assert guard.check_connection("1.1.1.1") is True


# ===== Compaction Policy =====


class TestCompactionHelpers:
    def test_estimate_tokens(self) -> None:
        assert estimate_tokens("hello") >= 1
        assert estimate_tokens("a" * 400) == 100

    def test_content_hash_deterministic(self) -> None:
        h1 = content_hash("Hello world")
        h2 = content_hash("Hello world")
        assert h1 == h2

    def test_content_hash_normalized(self) -> None:
        h1 = content_hash("Hello  world")
        h2 = content_hash("Hello world")
        assert h1 == h2

    def test_is_identifier_system(self) -> None:
        assert is_identifier_message("anything", role="system") is True

    def test_is_identifier_tool_def(self) -> None:
        assert is_identifier_message('{"function": "test", "parameters": {"type": "object"}}') is True

    def test_is_identifier_normal(self) -> None:
        assert is_identifier_message("Hello, how are you?") is False


class TestNearDuplicates:
    def test_no_duplicates(self) -> None:
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        assert detect_near_duplicates(messages) == []

    def test_exact_duplicates(self) -> None:
        messages = [
            {"role": "assistant", "content": "Same response"},
            {"role": "user", "content": "Different question"},
            {"role": "assistant", "content": "Same response"},
        ]
        dups = detect_near_duplicates(messages)
        assert len(dups) == 1
        assert dups[0] == (0, 2)


class TestFilterUnavailableTools:
    def test_keeps_available_tools(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "file_read"},
                ],
            },
            {"role": "tool", "tool_use_id": "t1", "content": "result"},
        ]
        result = filter_unavailable_tools(messages, {"file_read"})
        assert len(result) == 2

    def test_prunes_unavailable_tools(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "removed_tool"},
                ],
            },
            {"role": "tool", "tool_use_id": "t1", "content": "result"},
            {"role": "user", "content": "next message"},
        ]
        result = filter_unavailable_tools(messages, {"file_read"})
        # tool_use and tool_result for removed_tool should be gone
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_mixed_tool_blocks(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "file_read"},
                    {"type": "tool_use", "id": "t2", "name": "removed"},
                    {"type": "text", "text": "some text"},
                ],
            },
            {"role": "tool", "tool_use_id": "t1", "content": "ok"},
            {"role": "tool", "tool_use_id": "t2", "content": "gone"},
        ]
        result = filter_unavailable_tools(messages, {"file_read"})
        assert len(result) == 2  # assistant (with file_read + text) + tool t1


class TestPlanCompaction:
    def test_small_conversation_no_compaction(self) -> None:
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        result = plan_compaction(messages)
        assert len(result.prune_indices) == 0

    def test_duplicates_pruned(self) -> None:
        messages = [
            {"role": "system", "content": "System"},
            {"role": "assistant", "content": "Duplicate response"},
            {"role": "user", "content": "Something"},
            {"role": "assistant", "content": "Duplicate response"},
            {"role": "user", "content": "Latest"},
            {"role": "assistant", "content": "Latest reply"},
        ]
        result = plan_compaction(messages)
        assert result.duplicates_found >= 1

    def test_system_preserved(self) -> None:
        messages = [
            {"role": "system", "content": "You are helpful"},
        ] + [{"role": "user", "content": f"msg {i}"} for i in range(20)]

        result = plan_compaction(messages)
        assert 0 in result.keep_indices


# ===== Config Migrations =====


class TestDetectVersion:
    def test_schema_version(self) -> None:
        assert detect_config_version({"$schema": "https://openclaw.ai/config/v2"}) == "v2"

    def test_explicit_version(self) -> None:
        assert detect_config_version({"version": "v3"}) == "v3"

    def test_numeric_version(self) -> None:
        assert detect_config_version({"version": "2"}) == "v2"

    def test_heuristic_v2(self) -> None:
        assert detect_config_version({"agents": {"default": {}}}) == "v2"

    def test_default_v1(self) -> None:
        assert detect_config_version({}) == "v1"


class TestConfigMigrationRegistry:
    def test_default_registry(self) -> None:
        registry = create_default_registry()
        assert registry.step_count >= 2

    def test_v1_to_v2_migration(self) -> None:
        registry = create_default_registry()
        config = {
            "model": "gpt-4o",
            "allowFrom": ["user1"],
            "systemPrompt": "You are helpful",
        }
        result = registry.migrate(config, target_version="v2")
        assert result.success is True
        assert config.get("version") == "v2"
        assert "model" not in config
        assert config["agents"]["default"]["model"] == "gpt-4o"
        assert config["agents"]["default"]["systemPrompt"] == "You are helpful"

    def test_v2_to_v3_migration(self) -> None:
        registry = create_default_registry()
        config = {
            "version": "v2",
            "gateway": {"authToken": "secret123"},
            "exec": {"security": "allowlist"},
        }
        result = registry.migrate(config, target_version="v3")
        assert result.success is True
        assert config["gateway"]["token"] == "secret123"
        assert "authToken" not in config["gateway"]
        assert config["exec"]["approval"] == "allowlist"

    def test_full_migration_v1_to_v3(self) -> None:
        registry = create_default_registry()
        config = {
            "model": "gpt-4o",
            "allowFrom": ["u1"],
        }
        result = registry.migrate(config, target_version="v3")
        assert result.success is True
        assert len(result.steps_applied) == 2
        assert config.get("version") == "v3"

    def test_already_at_target(self) -> None:
        registry = create_default_registry()
        config = {"version": "v3"}
        result = registry.migrate(config, target_version="v3")
        assert result.success is True
        assert len(result.steps_applied) == 0

    def test_dry_run(self) -> None:
        registry = create_default_registry()
        config = {"model": "gpt-4o"}
        result = registry.migrate(config, target_version="v2", dry_run=True)
        assert result.success is True
        assert result.dry_run is True
        # Original config should be unchanged
        assert "model" in config
        assert "agents" not in config

    def test_no_path(self) -> None:
        registry = ConfigMigrationRegistry()
        config = {}
        result = registry.migrate(config, target_version="v99")
        assert result.success is False

    def test_custom_step(self) -> None:
        registry = ConfigMigrationRegistry()
        registry.register(
            MigrationStep(
                id="custom-1",
                from_version="v1",
                to_version="v2",
                description="Custom migration",
                migrate=lambda c: {**c, "migrated": True, "version": "v2"},
            )
        )
        config: dict = {}
        result = registry.migrate(config, target_version="v2")
        assert result.success is True
        assert config.get("migrated") is True


class TestStateMigrationRegistry:
    def test_basic_migration(self) -> None:
        registry = StateMigrationRegistry()
        registry.register(
            MigrationStep(
                id="state-1-to-2",
                from_version="1",
                to_version="2",
                description="Add schema version",
                migrate=lambda s: {**s, "version": "2", "schema": "v2"},
            )
        )
        state: dict = {"version": "1", "data": "value"}
        result = registry.migrate(state, target_version="2")
        assert result.success is True
        assert state["version"] == "2"
        assert state["data"] == "value"


# ===== Command Gating =====


class TestCommandGating:
    @pytest.fixture
    def manager(self) -> CommandGatingManager:
        mgr = CommandGatingManager()
        mgr.register_channel(
            CommandGatingConfig(
                channel_id="telegram",
                owner_ids={"owner1"},
                overrides={"/custom": CommandPermission.ALLOW},
            )
        )
        return mgr

    def test_allowed_command(self, manager: CommandGatingManager) -> None:
        result = manager.check("telegram", "/help", "anyone")
        assert result.allowed is True

    def test_owner_only_denied(self, manager: CommandGatingManager) -> None:
        result = manager.check("telegram", "/model", "anyone")
        assert result.allowed is False
        assert "owner" in result.reason

    def test_owner_only_allowed(self, manager: CommandGatingManager) -> None:
        result = manager.check("telegram", "/model", "owner1")
        assert result.allowed is True

    def test_custom_override(self, manager: CommandGatingManager) -> None:
        result = manager.check("telegram", "/custom", "anyone")
        assert result.allowed is True

    def test_unknown_channel_defaults(self, manager: CommandGatingManager) -> None:
        result = manager.check("unknown", "/help", "anyone")
        assert result.allowed is True

    def test_disabled_channel(self) -> None:
        mgr = CommandGatingManager()
        mgr.register_channel(CommandGatingConfig(channel_id="t", disabled=True))
        result = mgr.check("t", "/help", "anyone")
        assert result.allowed is False

    def test_deny_unlisted(self) -> None:
        mgr = CommandGatingManager()
        mgr.register_channel(
            CommandGatingConfig(
                channel_id="t",
                deny_unlisted=True,
            )
        )
        result = mgr.check("t", "/unknown_command", "anyone")
        assert result.allowed is False

    def test_global_override(self) -> None:
        mgr = CommandGatingManager()
        mgr.register_channel(CommandGatingConfig(channel_id="t"))
        mgr.set_global_override("/custom_global", CommandPermission.DENY)
        result = mgr.check("t", "/custom_global", "anyone")
        assert result.allowed is False

    def test_channel_override_beats_global(self) -> None:
        mgr = CommandGatingManager()
        mgr.register_channel(
            CommandGatingConfig(
                channel_id="t",
                overrides={"/test": CommandPermission.ALLOW},
            )
        )
        mgr.set_global_override("/test", CommandPermission.DENY)
        result = mgr.check("t", "/test", "anyone")
        assert result.allowed is True

    def test_get_available_commands(self, manager: CommandGatingManager) -> None:
        available = manager.get_available_commands("telegram", "anyone")
        assert "/help" in available
        assert "/model" not in available  # owner only

    def test_get_available_commands_owner(self, manager: CommandGatingManager) -> None:
        available = manager.get_available_commands("telegram", "owner1")
        assert "/help" in available
        assert "/model" in available

    def test_unregister(self, manager: CommandGatingManager) -> None:
        manager.unregister_channel("telegram")
        # Falls back to defaults
        result = manager.check("telegram", "/help", "anyone")
        assert result.allowed is True

    def test_normalize_command(self, manager: CommandGatingManager) -> None:
        result = manager.check("telegram", "help", "anyone")
        assert result.allowed is True
        assert result.command == "/help"
