"""Tests for plugin loader."""

import types

from pyclaw.plugins.loader import PluginLoader


def test_loader_empty():
    loader = PluginLoader()
    assert loader.names() == []
    assert loader.all() == []


def test_loader_load_module():
    # Create a fake plugin module
    mod = types.ModuleType("fake_plugin")
    mod.__version__ = "1.0.0"

    def register():
        return {"channels": [], "tools": ["fake_tool"]}

    mod.register = register

    loader = PluginLoader()
    info = loader._register_module("fake", mod)

    assert info is not None
    assert info.name == "fake"
    assert info.version == "1.0.0"
    assert info.tools == ["fake_tool"]
    assert loader.get("fake") is info


def test_loader_module_without_register():
    mod = types.ModuleType("bare_plugin")
    loader = PluginLoader()
    info = loader._register_module("bare", mod)
    assert info is not None
    assert info.name == "bare"
    assert info.tools == []


def test_loader_names():
    loader = PluginLoader()
    loader._register_module("a", types.ModuleType("a"))
    loader._register_module("b", types.ModuleType("b"))
    assert set(loader.names()) == {"a", "b"}
