from __future__ import annotations

from pyclaw.agents.providers.registry import ProviderInfo, ProviderRegistry


def test_capability_registry_includes_registered_info() -> None:
    registry = ProviderRegistry()
    registry._info["demo"] = ProviderInfo(name="demo", category="generic", models=["a", "b"])

    snapshot = registry.capability_registry()
    assert "demo" in snapshot
    assert snapshot["demo"]["model_count"] == 2
    assert snapshot["demo"]["has_active_client"] is False


def test_health_probe_for_unknown_provider() -> None:
    registry = ProviderRegistry()
    probe = registry.health_probe("unknown")
    assert probe["status"] == "missing"
    assert probe["active"] is False
