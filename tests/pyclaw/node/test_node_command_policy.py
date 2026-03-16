"""Tests for node command policy and platform-aware tool generation."""

from __future__ import annotations

import pytest

from pyclaw.gateway.node_command_policy import (
    ANDROID_ALL_COMMANDS,
    IOS_ALL_COMMANDS,
    MACOS_ALL_COMMANDS,
    NodeCapabilities,
    filter_commands_by_capabilities,
    get_allowed_commands,
    get_node_tool_definitions,
    is_command_allowed,
)
from pyclaw.tools.nodes import get_platform_tools


class TestPlatformAllowlists:
    def test_android_has_most_commands(self) -> None:
        assert len(ANDROID_ALL_COMMANDS) > len(IOS_ALL_COMMANDS)
        assert len(ANDROID_ALL_COMMANDS) > len(MACOS_ALL_COMMANDS)

    def test_system_commands_on_all_platforms(self) -> None:
        for platform in ["android", "ios", "macos", "linux", "windows"]:
            cmds = get_allowed_commands(platform)
            assert "system.run" in cmds
            assert "system.which" in cmds

    def test_android_exclusive_commands(self) -> None:
        android = set(ANDROID_ALL_COMMANDS)
        ios = set(IOS_ALL_COMMANDS)
        assert "camera.snap" in android
        assert "camera.snap" not in ios
        assert "contacts.add" in android
        assert "calendar.add" in android
        assert "notifications.actions" in android
        assert "system.notify" in android

    def test_unknown_platform_gets_system_commands(self) -> None:
        cmds = get_allowed_commands("unknown-platform")
        assert "system.run" in cmds
        assert "system.which" in cmds
        assert len(cmds) == 2

    def test_case_insensitive_platform(self) -> None:
        assert get_allowed_commands("Android") == get_allowed_commands("android")
        assert get_allowed_commands("IOS") == get_allowed_commands("ios")

    def test_commands_are_sorted(self) -> None:
        assert sorted(ANDROID_ALL_COMMANDS) == ANDROID_ALL_COMMANDS
        assert sorted(IOS_ALL_COMMANDS) == IOS_ALL_COMMANDS
        assert sorted(MACOS_ALL_COMMANDS) == MACOS_ALL_COMMANDS


class TestIsCommandAllowed:
    def test_allowed_command(self) -> None:
        assert is_command_allowed("system.run", "android") is True
        assert is_command_allowed("camera.snap", "android") is True

    def test_disallowed_command(self) -> None:
        assert is_command_allowed("camera.snap", "macos") is False
        assert is_command_allowed("notifications.actions", "ios") is False

    def test_with_node_capabilities(self) -> None:
        caps = NodeCapabilities(platform="android", commands=["system.run"])
        assert is_command_allowed("system.run", "android", caps) is True
        # Command allowed by platform but not advertised by node
        assert is_command_allowed("camera.snap", "android", caps) is False

    def test_without_caps_uses_platform(self) -> None:
        assert is_command_allowed("device.info", "android") is True
        assert is_command_allowed("device.permissions", "android") is True


class TestFilterByCapabilities:
    def test_filter_with_caps(self) -> None:
        caps = NodeCapabilities(commands=["system.run", "device.info"])
        result = filter_commands_by_capabilities(["system.run", "device.info", "camera.snap"], caps)
        assert result == ["system.run", "device.info"]

    def test_filter_without_caps_returns_all(self) -> None:
        caps = NodeCapabilities()
        cmds = ["system.run", "device.info"]
        assert filter_commands_by_capabilities(cmds, caps) == cmds


class TestToolDefinitions:
    def test_android_tools(self) -> None:
        tools = get_node_tool_definitions("android")
        names = {t["name"] for t in tools}
        assert "node_system_run" in names
        assert "node_camera_snap" in names
        assert "node_notifications_actions" in names

    def test_macos_tools_are_minimal(self) -> None:
        tools = get_node_tool_definitions("macos")
        names = {t["name"] for t in tools}
        assert "node_system_run" in names
        assert "node_camera_snap" not in names

    def test_tools_have_node_command_ref(self) -> None:
        tools = get_node_tool_definitions("android")
        for tool in tools:
            assert "_node_command" in tool

    def test_tool_definitions_with_caps(self) -> None:
        caps = NodeCapabilities(platform="android", commands=["system.run"])
        tools = get_node_tool_definitions("android", caps)
        assert len(tools) == 1
        assert tools[0]["_node_command"] == "system.run"

    def test_get_platform_tools_wrapper(self) -> None:
        tools = get_platform_tools("android")
        assert len(tools) > 0
        assert all("name" in t for t in tools)


class TestNodeTools:
    @pytest.mark.asyncio
    async def test_handle_nodes_list_no_context(self) -> None:
        from pyclaw.tools.nodes import handle_nodes_list

        result = await handle_nodes_list({})
        assert result == "No connected nodes."

    @pytest.mark.asyncio
    async def test_handle_nodes_invoke_missing_params(self) -> None:
        from pyclaw.tools.nodes import handle_nodes_invoke

        result = await handle_nodes_invoke({})
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_handle_nodes_invoke_no_context(self) -> None:
        from pyclaw.tools.nodes import handle_nodes_invoke

        result = await handle_nodes_invoke({"node_id": "n1", "command": "system.run"})
        assert "not connected" in result
