"""Tests for Phase 28 — env substitution, includes, backup, session store, runtime overrides."""

from __future__ import annotations

import json
import os
import tempfile
import time

import pytest

from pyclaw.config.env_substitution import (
    MissingEnvVarError,
    list_env_refs,
    substitute_env,
    substitute_env_recursive,
    validate_env_refs,
)
from pyclaw.config.includes import (
    CircularIncludeError,
    IncludeResult,
    MaxDepthError,
    resolve_include_path,
    resolve_includes,
)
from pyclaw.config.backup import (
    BackupConfig,
    atomic_write,
    create_backup,
    list_backups,
)
from pyclaw.config.session_store import (
    DeliveryInfo,
    SessionMetadata,
    SessionStore,
    StoreConfig,
)
from pyclaw.config.runtime_overrides import (
    ChannelCapabilityOverride,
    GroupPolicy,
    PluginAutoEnable,
    RuntimeOverrides,
    create_config_snapshot,
    redact_config,
)


# ===== Environment Variable Substitution =====

class TestEnvSubstitution:
    def test_simple_substitution(self) -> None:
        result = substitute_env("Hello ${USER}", env={"USER": "alice"})
        assert result == "Hello alice"

    def test_no_substitution(self) -> None:
        assert substitute_env("Hello world") == "Hello world"

    def test_default_value(self) -> None:
        result = substitute_env("${MISSING:-fallback}", env={})
        assert result == "fallback"

    def test_escaped_literal(self) -> None:
        result = substitute_env("Use $${VAR} for literal", env={"VAR": "nope"})
        assert result == "Use ${VAR} for literal"

    def test_multiple_vars(self) -> None:
        result = substitute_env("${A} and ${B}", env={"A": "one", "B": "two"})
        assert result == "one and two"

    def test_strict_missing(self) -> None:
        with pytest.raises(MissingEnvVarError):
            substitute_env("${MISSING_VAR}", env={}, strict=True)

    def test_strict_with_default(self) -> None:
        result = substitute_env("${MISSING:-ok}", env={}, strict=True)
        assert result == "ok"

    def test_non_strict_leaves_unresolved(self) -> None:
        result = substitute_env("${UNDEFINED}", env={}, strict=False)
        assert result == "${UNDEFINED}"

    def test_uppercase_only(self) -> None:
        result = substitute_env("${lowercase}", env={"lowercase": "bad"})
        assert result == "${lowercase}"  # Invalid name, left as-is

    def test_recursive_substitution(self) -> None:
        data = {"key": "Hello ${NAME}", "nested": {"val": "${NAME}"}}
        result = substitute_env_recursive(data, env={"NAME": "world"})
        assert result["key"] == "Hello world"
        assert result["nested"]["val"] == "world"

    def test_list_refs(self) -> None:
        refs = list_env_refs("${A} and ${B} and ${A}")
        assert refs == ["A", "B"]

    def test_validate_refs(self) -> None:
        missing = validate_env_refs("${A} ${B}", env={"A": "1"})
        assert missing == ["B"]


# ===== Config Includes =====

class TestConfigIncludes:
    def test_resolve_path_relative(self) -> None:
        result = resolve_include_path("sub/config.json", "/home/user")
        assert result == "/home/user/sub/config.json"

    def test_resolve_path_absolute(self) -> None:
        result = resolve_include_path("/etc/config.json", "/home/user")
        assert result == "/etc/config.json"

    def test_no_includes(self) -> None:
        data = {"key": "value"}
        result = resolve_includes(data, "/tmp")
        assert result.data == {"key": "value"}
        assert result.included_files == []

    def test_single_include(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            inc_path = os.path.join(tmpdir, "inc.json")
            with open(inc_path, "w") as f:
                json.dump({"base": "included"}, f)

            data = {"$include": "inc.json", "override": "main"}
            result = resolve_includes(data, tmpdir)
            assert result.data["base"] == "included"
            assert result.data["override"] == "main"
            assert len(result.included_files) == 1

    def test_multiple_includes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for name, content in [("a.json", {"a": 1}), ("b.json", {"b": 2})]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    json.dump(content, f)

            data = {"$include": ["a.json", "b.json"]}
            result = resolve_includes(data, tmpdir)
            assert result.data["a"] == 1
            assert result.data["b"] == 2

    def test_deep_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "base.json"), "w") as f:
                json.dump({"a": {"x": 1, "y": 2}}, f)

            data = {"$include": "base.json", "a": {"y": 99, "z": 3}}
            result = resolve_includes(data, tmpdir)
            assert result.data["a"]["x"] == 1
            assert result.data["a"]["y"] == 99
            assert result.data["a"]["z"] == 3

    def test_circular_include(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            a_path = os.path.join(tmpdir, "a.json")
            b_path = os.path.join(tmpdir, "b.json")
            with open(a_path, "w") as f:
                json.dump({"$include": "b.json"}, f)
            with open(b_path, "w") as f:
                json.dump({"$include": "a.json"}, f)

            data = {"$include": "a.json"}
            with pytest.raises(CircularIncludeError):
                resolve_includes(data, tmpdir)

    def test_missing_include_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {"$include": "nonexistent.json"}
            with pytest.raises(Exception, match="not found"):
                resolve_includes(data, tmpdir)


# ===== Backup Rotation =====

class TestBackup:
    def test_create_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            with open(path, "w") as f:
                f.write('{"key": "value"}')

            info = create_backup(path)
            assert info is not None
            assert os.path.exists(info.path)
            assert info.size_bytes > 0

    def test_no_backup_if_missing(self) -> None:
        info = create_backup("/nonexistent/path.json")
        assert info is None

    def test_backup_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            with open(path, "w") as f:
                f.write("{}")

            info = create_backup(path, BackupConfig(enabled=False))
            assert info is None

    def test_list_backups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            with open(path, "w") as f:
                f.write("{}")

            create_backup(path)
            backups = list_backups(path)
            assert len(backups) == 1

    def test_prune_old_backups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            config = BackupConfig(max_backups=2)

            for i in range(4):
                with open(path, "w") as f:
                    f.write(f'{{"i": {i}}}')
                create_backup(path, config)
                time.sleep(0.05)

            backups = list_backups(path)
            assert len(backups) <= 2

    def test_atomic_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            atomic_write(path, '{"new": true}')
            with open(path) as f:
                data = json.load(f)
            assert data["new"] is True

    def test_atomic_write_with_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            with open(path, "w") as f:
                f.write('{"old": true}')

            atomic_write(path, '{"new": true}', backup_config=BackupConfig())
            backups = list_backups(path)
            assert len(backups) >= 1


# ===== Session Store =====

class TestSessionStore:
    def _make_store(self, tmpdir: str) -> SessionStore:
        return SessionStore(StoreConfig(base_dir=tmpdir))

    def test_create_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            meta = SessionMetadata(session_id="s1", model="gpt-4o")
            path = store.create_session(meta)
            assert os.path.isdir(path)

    def test_get_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            store.create_session(SessionMetadata(session_id="s1", model="gpt-4o", turn_count=5))
            meta = store.get_metadata("s1")
            assert meta is not None
            assert meta.model == "gpt-4o"
            assert meta.turn_count == 5

    def test_update_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            store.create_session(SessionMetadata(session_id="s1", model="gpt-4o"))
            store.update_metadata("s1", turn_count=10, status="idle")
            meta = store.get_metadata("s1")
            assert meta is not None
            assert meta.turn_count == 10
            assert meta.status == "idle"

    def test_delete_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            store.create_session(SessionMetadata(session_id="s1"))
            assert store.delete_session("s1") is True
            assert store.get_metadata("s1") is None

    def test_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            store.create_session(SessionMetadata(session_id="s1"))
            store.append_transcript("s1", {"role": "user", "content": "hello"})
            store.append_transcript("s1", {"role": "assistant", "content": "hi"})
            entries = store.read_transcript("s1")
            assert len(entries) == 2
            assert entries[0]["role"] == "user"

    def test_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            store.create_session(SessionMetadata(session_id="s1"))
            store.record_delivery("s1", DeliveryInfo(
                message_id="m1", channel_id="telegram", chat_id="123",
            ))

    def test_list_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            store.create_session(SessionMetadata(session_id="s1", status="active"))
            store.create_session(SessionMetadata(session_id="s2", status="idle"))
            all_sessions = store.list_sessions()
            assert len(all_sessions) == 2
            active = store.list_sessions(status="active")
            assert len(active) == 1

    def test_session_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            store.create_session(SessionMetadata(session_id="s1"))
            store.create_session(SessionMetadata(session_id="s2"))
            assert store.session_count == 2

    def test_disk_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            store.create_session(SessionMetadata(session_id="s1"))
            usage = store.get_disk_usage_mb()
            assert usage >= 0


# ===== Runtime Overrides =====

class TestRuntimeOverrides:
    def test_group_policy(self) -> None:
        overrides = RuntimeOverrides()
        policy = GroupPolicy(group_id="g1", model="claude-3", think_level="high")
        overrides.set_group_policy(policy)
        assert overrides.get_group_policy("g1") is not None
        assert overrides.get_group_policy("g1").model == "claude-3"

    def test_remove_group_policy(self) -> None:
        overrides = RuntimeOverrides()
        overrides.set_group_policy(GroupPolicy(group_id="g1"))
        assert overrides.remove_group_policy("g1") is True
        assert overrides.get_group_policy("g1") is None

    def test_channel_override(self) -> None:
        overrides = RuntimeOverrides()
        overrides.set_channel_override(ChannelCapabilityOverride(
            channel_id="ch1",
            streaming_enabled=False,
            max_message_length=2000,
        ))
        ov = overrides.get_channel_override("ch1")
        assert ov is not None
        assert ov.streaming_enabled is False

    def test_plugin_auto_enable(self) -> None:
        overrides = RuntimeOverrides()
        overrides.add_plugin_rule(PluginAutoEnable(plugin_name="memory", condition="always"))
        overrides.add_plugin_rule(PluginAutoEnable(
            plugin_name="telegram-ext",
            condition="if_channel",
            channel_types=["telegram"],
        ))
        plugins = overrides.get_auto_enable_plugins()
        assert "memory" in plugins

        plugins = overrides.get_auto_enable_plugins(channel_type="telegram")
        assert "telegram-ext" in plugins

        plugins = overrides.get_auto_enable_plugins(channel_type="discord")
        assert "telegram-ext" not in plugins

    def test_generic_overrides(self) -> None:
        overrides = RuntimeOverrides()
        overrides.set("model.default", "gpt-4o")
        assert overrides.get("model.default") == "gpt-4o"

    def test_apply_to_config(self) -> None:
        overrides = RuntimeOverrides()
        overrides.set("agent.model", "claude-3")
        config = {"agent": {"model": "gpt-4o", "tools": True}}
        result = overrides.apply_to_config(config)
        assert result["agent"]["model"] == "claude-3"
        assert result["agent"]["tools"] is True
        assert config["agent"]["model"] == "gpt-4o"  # Original unchanged

    def test_redact_config(self) -> None:
        config = {
            "api_key": "sk-secret123",
            "model": "gpt-4o",
            "nested": {"bot_token": "xoxb-123", "name": "Bot"},
        }
        redacted = redact_config(config)
        assert redacted["api_key"] == "***REDACTED***"
        assert redacted["model"] == "gpt-4o"
        assert redacted["nested"]["bot_token"] == "***REDACTED***"
        assert redacted["nested"]["name"] == "Bot"

    def test_redact_empty_value(self) -> None:
        config = {"api_key": "", "model": "gpt-4o"}
        redacted = redact_config(config)
        assert redacted["api_key"] == ""  # Empty strings not redacted

    def test_create_snapshot(self) -> None:
        overrides = RuntimeOverrides()
        overrides.set("debug", True)
        config = {"api_key": "secret", "debug": False}
        snapshot = create_config_snapshot(config, overrides, redact=True)
        assert snapshot["api_key"] == "***REDACTED***"
        assert snapshot["debug"] is True
