"""Tests for non-channel extension framework."""

from __future__ import annotations

import pytest

from pyclaw.plugins.extensions import (
    Extension,
    ExtensionContext,
    ExtensionManifest,
    ExtensionRegistry,
)


class DummyExtension(Extension):
    """Simple test extension."""

    def __init__(
        self, name: str = "dummy", provides: list[str] | None = None, requires: list[str] | None = None
    ) -> None:
        self._manifest = ExtensionManifest(
            name=name,
            version="1.0.0",
            description="Test extension",
            provides=provides or [],
            requires=requires or [],
        )
        self.loaded = False
        self.unloaded = False
        self.gateway_started = False
        self.gateway_stopped = False

    @property
    def manifest(self) -> ExtensionManifest:
        return self._manifest

    async def on_load(self, context: ExtensionContext) -> None:
        self.loaded = True

    async def on_unload(self) -> None:
        self.unloaded = True

    async def on_gateway_start(self) -> None:
        self.gateway_started = True

    async def on_gateway_stop(self) -> None:
        self.gateway_stopped = True


class FailingExtension(Extension):
    """Extension that fails on load."""

    @property
    def manifest(self) -> ExtensionManifest:
        return ExtensionManifest(name="failing", version="0.1.0")

    async def on_load(self, context: ExtensionContext) -> None:
        raise RuntimeError("Load failed")


class TestExtensionManifest:
    def test_to_dict(self) -> None:
        m = ExtensionManifest(
            name="test",
            version="1.0.0",
            description="desc",
            provides=["memory-backend"],
        )
        d = m.to_dict()
        assert d["name"] == "test"
        assert d["provides"] == ["memory-backend"]

    def test_defaults(self) -> None:
        m = ExtensionManifest(name="minimal")
        assert m.version == "0.0.0"
        assert m.requires == []
        assert m.provides == []


class TestExtensionRegistry:
    @pytest.fixture
    def registry(self) -> ExtensionRegistry:
        return ExtensionRegistry()

    def test_register_and_get(self, registry: ExtensionRegistry) -> None:
        ext = DummyExtension("my-ext")
        registry.register(ext)

        assert registry.get("my-ext") is ext
        assert len(registry.list_all()) == 1

    def test_register_replaces(self, registry: ExtensionRegistry) -> None:
        ext1 = DummyExtension("my-ext")
        ext2 = DummyExtension("my-ext")
        registry.register(ext1)
        registry.register(ext2)

        assert registry.get("my-ext") is ext2
        assert len(registry.list_all()) == 1

    def test_list_manifests(self, registry: ExtensionRegistry) -> None:
        registry.register(DummyExtension("a"))
        registry.register(DummyExtension("b"))
        manifests = registry.list_manifests()
        names = [m.name for m in manifests]
        assert "a" in names
        assert "b" in names

    @pytest.mark.asyncio
    async def test_load_all(self, registry: ExtensionRegistry) -> None:
        ext = DummyExtension("loadable")
        registry.register(ext)

        loaded = await registry.load_all(ExtensionContext())
        assert "loadable" in loaded
        assert ext.loaded is True

    @pytest.mark.asyncio
    async def test_load_failing_extension(self, registry: ExtensionRegistry) -> None:
        ext = FailingExtension()
        registry.register(ext)

        loaded = await registry.load_all(ExtensionContext())
        assert "failing" not in loaded

    @pytest.mark.asyncio
    async def test_unload_all(self, registry: ExtensionRegistry) -> None:
        ext = DummyExtension("unloadable")
        registry.register(ext)
        await registry.load_all(ExtensionContext())
        await registry.unload_all()
        assert ext.unloaded is True
        assert len(registry.list_all()) == 0

    @pytest.mark.asyncio
    async def test_gateway_lifecycle(self, registry: ExtensionRegistry) -> None:
        ext = DummyExtension("lifecycle")
        registry.register(ext)

        await registry.notify_gateway_start()
        assert ext.gateway_started is True

        await registry.notify_gateway_stop()
        assert ext.gateway_stopped is True

    @pytest.mark.asyncio
    async def test_dependency_order(self, registry: ExtensionRegistry) -> None:
        # B requires "feature-a" which A provides
        ext_a = DummyExtension("a", provides=["feature-a"])
        ext_b = DummyExtension("b", requires=["feature-a"])

        # Register B first, but A should load first
        registry.register(ext_b)
        registry.register(ext_a)

        loaded = await registry.load_all(ExtensionContext())
        assert loaded.index("a") < loaded.index("b")

    @pytest.mark.asyncio
    async def test_missing_dependency(self, registry: ExtensionRegistry) -> None:
        ext = DummyExtension("needy", requires=["nonexistent-cap"])
        registry.register(ext)

        loaded = await registry.load_all(ExtensionContext())
        assert "needy" not in loaded
        assert ext.loaded is False
