"""Tests for Phase 30 — Gateway advanced: config reload, health, rate limit, hooks, discovery."""

from __future__ import annotations

import json
import time
import tempfile
from pathlib import Path

import pytest

from pyclaw.gateway.config_reload import (
    ChangeType,
    ConfigDiff,
    ConfigFileWatcher,
    ReloadStrategy,
    WatcherConfig,
    compute_config_diff,
    determine_strategy,
    file_hash,
    flatten_dict,
)
from pyclaw.gateway.channel_health import (
    ChannelHealthMonitor,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
)
from pyclaw.gateway.control_plane_rate_limit import (
    ControlPlaneRateLimiter,
    RateLimitConfig,
)
from pyclaw.gateway.hooks_mapping import (
    BUILTIN_PRESETS,
    HookMapping,
    apply_hook_mappings,
    resolve_hook_mappings,
    substitute_config,
    substitute_template,
)
from pyclaw.gateway.discovery import (
    DiscoveredService,
    DiscoveryConfig,
    DiscoveryMethod,
    MDNSAdvertiser,
    ServiceDiscoveryManager,
    TailscaleDiscovery,
    resolve_gateway_url,
)


# ===== Config Reload =====

class TestFlattenDict:
    def test_simple(self) -> None:
        assert flatten_dict({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_nested(self) -> None:
        result = flatten_dict({"a": {"b": 1, "c": {"d": 2}}})
        assert result == {"a.b": 1, "a.c.d": 2}

    def test_empty(self) -> None:
        assert flatten_dict({}) == {}


class TestConfigDiff:
    def test_no_changes(self) -> None:
        diff = compute_config_diff({"a": 1}, {"a": 1})
        assert not diff.has_changes

    def test_added(self) -> None:
        diff = compute_config_diff({}, {"a": 1})
        assert diff.change_count == 1
        assert diff.changes[0].change_type == ChangeType.ADDED

    def test_removed(self) -> None:
        diff = compute_config_diff({"a": 1}, {})
        assert diff.changes[0].change_type == ChangeType.REMOVED

    def test_modified(self) -> None:
        diff = compute_config_diff({"a": 1}, {"a": 2})
        assert diff.changes[0].change_type == ChangeType.MODIFIED

    def test_nested_diff(self) -> None:
        old = {"gateway": {"port": 8080}}
        new = {"gateway": {"port": 9090}}
        diff = compute_config_diff(old, new)
        assert diff.has_changes
        assert diff.changes[0].key == "gateway.port"


class TestDetermineStrategy:
    def test_empty(self) -> None:
        assert determine_strategy([]) == ReloadStrategy.IGNORE

    def test_restart_key(self) -> None:
        from pyclaw.gateway.config_reload import ConfigChange
        changes = [ConfigChange(key="gateway.port", change_type=ChangeType.MODIFIED)]
        assert determine_strategy(changes) == ReloadStrategy.RESTART

    def test_hot_reload_key(self) -> None:
        from pyclaw.gateway.config_reload import ConfigChange
        changes = [ConfigChange(key="channels.telegram.token", change_type=ChangeType.MODIFIED)]
        assert determine_strategy(changes) == ReloadStrategy.HOT


class TestConfigFileWatcher:
    def test_lifecycle(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text('{"a": 1}')

        watcher = ConfigFileWatcher(WatcherConfig(config_path=str(config_file)))
        watcher.start()
        assert watcher.is_running

        result = watcher.check()
        assert result is None  # No changes

        watcher.stop()
        assert not watcher.is_running

    def test_detects_change(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text('{"a": 1}')

        watcher = ConfigFileWatcher(WatcherConfig(config_path=str(config_file), debounce_s=0))
        watcher.start()

        config_file.write_text('{"a": 2}')
        diff = watcher.check()
        assert diff is not None
        assert diff.has_changes
        assert watcher.reload_count == 1

    def test_callback(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text('{"a": 1}')

        results: list[ConfigDiff] = []
        watcher = ConfigFileWatcher(WatcherConfig(config_path=str(config_file), debounce_s=0))
        watcher.on_change(results.append)
        watcher.start()

        config_file.write_text('{"a": 2}')
        watcher.check()
        assert len(results) == 1


class TestFileHash:
    def test_hash(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello")
        h = file_hash(f)
        assert len(h) == 64

    def test_missing(self) -> None:
        assert file_hash("/nonexistent") == ""


# ===== Channel Health =====

class TestChannelHealthMonitor:
    def test_register(self) -> None:
        mon = ChannelHealthMonitor()
        mon.register_channel("telegram")
        assert mon.channel_count == 1

    def test_healthy_check(self) -> None:
        mon = ChannelHealthMonitor()
        mon.register_channel("telegram")
        status = mon.record_check(HealthCheckResult(channel_id="telegram", healthy=True))
        assert status == HealthStatus.HEALTHY

    def test_unhealthy_threshold(self) -> None:
        mon = ChannelHealthMonitor(HealthCheckConfig(unhealthy_threshold=2))
        mon.register_channel("tg")
        mon.record_check(HealthCheckResult(channel_id="tg", healthy=False, error="e1"))
        status = mon.record_check(HealthCheckResult(channel_id="tg", healthy=False, error="e2"))
        assert status == HealthStatus.UNHEALTHY

    def test_should_restart(self) -> None:
        mon = ChannelHealthMonitor(HealthCheckConfig(unhealthy_threshold=1, cooldown_s=0))
        mon.register_channel("tg")
        mon.record_check(HealthCheckResult(channel_id="tg", healthy=False))
        decision = mon.should_restart("tg")
        assert decision.should_restart

    def test_cooldown(self) -> None:
        mon = ChannelHealthMonitor(HealthCheckConfig(unhealthy_threshold=1, cooldown_s=9999))
        mon.register_channel("tg")
        mon.record_check(HealthCheckResult(channel_id="tg", healthy=False))
        mon.record_restart("tg")

        mon.record_check(HealthCheckResult(channel_id="tg", healthy=False))
        decision = mon.should_restart("tg")
        assert not decision.should_restart

    def test_max_restarts(self) -> None:
        mon = ChannelHealthMonitor(HealthCheckConfig(
            unhealthy_threshold=1, cooldown_s=0, max_restarts_per_hour=1,
        ))
        mon.register_channel("tg")

        # First failure → unhealthy → restart allowed
        mon.record_check(HealthCheckResult(channel_id="tg", healthy=False))
        d1 = mon.should_restart("tg")
        assert d1.should_restart
        mon.record_restart("tg")

        # Second failure → unhealthy again, but max restarts reached
        mon.record_check(HealthCheckResult(channel_id="tg", healthy=False))
        d2 = mon.should_restart("tg")
        assert not d2.should_restart

    def test_history(self) -> None:
        mon = ChannelHealthMonitor()
        mon.register_channel("tg")
        for i in range(5):
            mon.record_check(HealthCheckResult(channel_id="tg", healthy=True))
        history = mon.get_history("tg", limit=3)
        assert len(history) == 3

    def test_unhealthy_list(self) -> None:
        mon = ChannelHealthMonitor(HealthCheckConfig(unhealthy_threshold=1))
        mon.register_channel("tg")
        mon.register_channel("dc")
        mon.record_check(HealthCheckResult(channel_id="tg", healthy=False))
        mon.record_check(HealthCheckResult(channel_id="dc", healthy=True))
        assert mon.get_unhealthy_channels() == ["tg"]


# ===== Control Plane Rate Limit =====

class TestControlPlaneRateLimiter:
    def test_allow(self) -> None:
        rl = ControlPlaneRateLimiter(RateLimitConfig(max_requests=3, window_s=60))
        result = rl.consume("dev1", "1.2.3.4")
        assert result.allowed
        assert result.remaining == 2

    def test_reject(self) -> None:
        rl = ControlPlaneRateLimiter(RateLimitConfig(max_requests=2, window_s=60))
        rl.consume("d", "ip")
        rl.consume("d", "ip")
        result = rl.consume("d", "ip")
        assert not result.allowed
        assert result.retry_after_s > 0

    def test_different_keys(self) -> None:
        rl = ControlPlaneRateLimiter(RateLimitConfig(max_requests=1))
        rl.consume("d1", "ip")
        result = rl.consume("d2", "ip")
        assert result.allowed

    def test_disabled(self) -> None:
        rl = ControlPlaneRateLimiter(RateLimitConfig(enabled=False))
        for _ in range(10):
            assert rl.consume("d", "ip").allowed

    def test_reset(self) -> None:
        rl = ControlPlaneRateLimiter(RateLimitConfig(max_requests=1))
        rl.consume("d", "ip")
        rl.reset("d", "ip")
        assert rl.consume("d", "ip").allowed

    def test_cleanup(self) -> None:
        rl = ControlPlaneRateLimiter(RateLimitConfig(max_requests=1, window_s=0.01))
        rl.consume("d", "ip")
        time.sleep(0.02)
        removed = rl.cleanup()
        assert removed == 1


# ===== Hooks Mapping =====

class TestSubstituteTemplate:
    def test_basic(self) -> None:
        assert substitute_template("Hello ${NAME}", {"NAME": "World"}) == "Hello World"

    def test_default(self) -> None:
        assert substitute_template("${X:-fallback}", {}) == "fallback"

    def test_override_default(self) -> None:
        assert substitute_template("${X:-fallback}", {"X": "real"}) == "real"

    def test_no_match(self) -> None:
        assert substitute_template("${MISSING}", {}) == "${MISSING}"


class TestSubstituteConfig:
    def test_nested(self) -> None:
        config = {"a": "${X}", "b": {"c": "${Y:-default}"}}
        result = substitute_config(config, {"X": "1"})
        assert result["a"] == "1"
        assert result["b"]["c"] == "default"


class TestResolveHookMappings:
    def test_preset(self) -> None:
        hooks = [{"id": "h1", "preset": "gmail"}]
        result = resolve_hook_mappings(hooks, {"GMAIL_CREDENTIALS_PATH": "/path"})
        assert len(result.mappings) == 1
        assert result.mappings[0].from_preset == "gmail"

    def test_unknown_preset(self) -> None:
        result = resolve_hook_mappings([{"id": "h1", "preset": "unknown"}])
        assert len(result.errors) == 1

    def test_custom_type(self) -> None:
        result = resolve_hook_mappings([{"id": "h1", "type": "custom", "path": "/x"}])
        assert len(result.mappings) == 1
        assert result.mappings[0].hook_type == "custom"

    def test_missing_type(self) -> None:
        result = resolve_hook_mappings([{"id": "h1"}])
        assert len(result.errors) == 1


class TestApplyHookMappings:
    def test_append(self) -> None:
        config: dict = {"hooks": []}
        mapping = HookMapping(hook_id="h1", hook_type="test", config={"x": 1})
        result = apply_hook_mappings(config, [mapping])
        assert len(result["hooks"]) == 1

    def test_replace(self) -> None:
        config: dict = {"hooks": [{"id": "h1", "type": "old"}]}
        mapping = HookMapping(hook_id="h1", hook_type="new")
        result = apply_hook_mappings(config, [mapping])
        assert len(result["hooks"]) == 1
        assert result["hooks"][0]["type"] == "new"

    def test_disabled(self) -> None:
        config: dict = {"hooks": []}
        mapping = HookMapping(hook_id="h1", hook_type="test", enabled=False)
        result = apply_hook_mappings(config, [mapping])
        assert len(result["hooks"]) == 0


# ===== Discovery =====

class TestResolveGatewayUrl:
    def test_config_priority(self) -> None:
        assert resolve_gateway_url(config_url="http://c:1") == "http://c:1"

    def test_env_fallback(self) -> None:
        assert resolve_gateway_url(env_url="http://e:2") == "http://e:2"

    def test_discovered(self) -> None:
        services = [DiscoveredService(name="gw", host="192.168.1.1", port=18789, method=DiscoveryMethod.MDNS)]
        url = resolve_gateway_url(discovered=services)
        assert "192.168.1.1" in url

    def test_default(self) -> None:
        assert resolve_gateway_url() == "http://127.0.0.1:18789"


class TestMDNSAdvertiser:
    def test_build_info(self) -> None:
        adv = MDNSAdvertiser(DiscoveryConfig(service_name="test"))
        info = adv.build_service_info()
        assert info["port"] == 18789

    def test_lifecycle(self) -> None:
        adv = MDNSAdvertiser(DiscoveryConfig())
        state = adv.start()
        assert state.advertising
        adv.stop()
        assert not adv.state.advertising


class TestTailscaleDiscovery:
    def test_dns_record(self) -> None:
        ts = TailscaleDiscovery(DiscoveryConfig(port=8080))
        rec = ts.build_dns_record()
        assert rec["port"] == 8080

    def test_funnel_url(self) -> None:
        ts = TailscaleDiscovery(DiscoveryConfig(hostname="myhost", port=443))
        url = ts.build_funnel_url("example")
        assert "myhost.example.ts.net" in url


class TestServiceDiscoveryManager:
    def test_start_stop(self) -> None:
        mgr = ServiceDiscoveryManager(DiscoveryConfig(mdns_enabled=True, tailscale_enabled=False))
        states = mgr.start()
        assert len(states) >= 1
        assert mgr.is_advertising
        mgr.stop()
        assert not mgr.is_advertising

    def test_resolve(self) -> None:
        mgr = ServiceDiscoveryManager(DiscoveryConfig())
        url = mgr.resolve_url()
        assert "127.0.0.1" in url
