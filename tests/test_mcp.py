"""Tests for MCP (Model Context Protocol) support."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyclaw.mcp.registry import (
    McpRegistry,
    McpToolAdapter,
    _mcp_result_to_tool_result,
    _parse_server_config,
)
from pyclaw.mcp.types import (
    JsonRpcRequest,
    JsonRpcResponse,
    McpServerConfig,
    McpToolInfo,
)


class TestMcpServerConfig:
    def test_stdio_config(self) -> None:
        cfg = McpServerConfig(name="test", command="npx", args=["-y", "server"])
        assert cfg.is_stdio
        assert not cfg.is_http

    def test_http_config(self) -> None:
        cfg = McpServerConfig(name="test", url="https://example.com/mcp")
        assert cfg.is_http
        assert not cfg.is_stdio

    def test_default_timeout(self) -> None:
        cfg = McpServerConfig(name="test", command="echo")
        assert cfg.tool_timeout == 30


class TestJsonRpcRequest:
    def test_to_dict(self) -> None:
        req = JsonRpcRequest(method="test", params={"a": 1}, id=42)
        d = req.to_dict()
        assert d == {"jsonrpc": "2.0", "method": "test", "params": {"a": 1}, "id": 42}

    def test_to_dict_no_params(self) -> None:
        req = JsonRpcRequest(method="test", id=1)
        d = req.to_dict()
        assert "params" not in d

    def test_to_dict_no_id(self) -> None:
        req = JsonRpcRequest(method="notify")
        d = req.to_dict()
        assert "id" not in d


class TestJsonRpcResponse:
    def test_from_dict_success(self) -> None:
        data = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        resp = JsonRpcResponse.from_dict(data)
        assert resp.id == 1
        assert resp.result == {"tools": []}
        assert not resp.is_error

    def test_from_dict_error(self) -> None:
        data = {"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "fail"}}
        resp = JsonRpcResponse.from_dict(data)
        assert resp.is_error
        assert resp.error["message"] == "fail"


class TestMcpToolInfo:
    def test_fields(self) -> None:
        info = McpToolInfo(
            name="read_file",
            description="Read a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            server_name="fs",
        )
        assert info.name == "read_file"
        assert info.server_name == "fs"


class TestParseServerConfig:
    def test_stdio(self) -> None:
        raw: dict[str, Any] = {"command": "npx", "args": ["-y", "server"], "env": {"FOO": "bar"}}
        cfg = _parse_server_config("test", raw)
        assert cfg.name == "test"
        assert cfg.command == "npx"
        assert cfg.args == ["-y", "server"]
        assert cfg.env == {"FOO": "bar"}
        assert cfg.is_stdio

    def test_http(self) -> None:
        raw: dict[str, Any] = {"url": "https://example.com/mcp", "headers": {"Auth": "Bearer x"}, "toolTimeout": 60}
        cfg = _parse_server_config("remote", raw)
        assert cfg.name == "remote"
        assert cfg.url == "https://example.com/mcp"
        assert cfg.headers == {"Auth": "Bearer x"}
        assert cfg.tool_timeout == 60
        assert cfg.is_http

    def test_defaults(self) -> None:
        raw: dict[str, Any] = {"command": "echo"}
        cfg = _parse_server_config("min", raw)
        assert cfg.args == []
        assert cfg.env == {}
        assert cfg.headers == {}
        assert cfg.tool_timeout == 30


class TestMcpResultConversion:
    def test_text_content(self) -> None:
        result = {"content": [{"type": "text", "text": "hello"}], "isError": False}
        tr = _mcp_result_to_tool_result(result)
        assert tr.content[0]["text"] == "hello"
        assert not tr.is_error

    def test_error_flag(self) -> None:
        result = {"content": [{"type": "text", "text": "oops"}], "isError": True}
        tr = _mcp_result_to_tool_result(result)
        assert tr.is_error

    def test_string_content(self) -> None:
        result = {"content": "raw text", "isError": False}
        tr = _mcp_result_to_tool_result(result)
        assert tr.content[0]["text"] == "raw text"

    def test_plain_string(self) -> None:
        tr = _mcp_result_to_tool_result("just a string")
        assert tr.content[0]["text"] == "just a string"

    def test_list_of_strings(self) -> None:
        result = {"content": ["line1", "line2"]}
        tr = _mcp_result_to_tool_result(result)
        assert "line1" in tr.content[0]["text"]


class TestMcpToolAdapter:
    def test_name_prefixed(self) -> None:
        info = McpToolInfo(name="read", description="Read", input_schema={}, server_name="fs")
        client = MagicMock()
        adapter = McpToolAdapter(info, client)
        assert adapter.name == "mcp_fs_read"

    def test_description_prefixed(self) -> None:
        info = McpToolInfo(name="read", description="Read a file", input_schema={}, server_name="fs")
        client = MagicMock()
        adapter = McpToolAdapter(info, client)
        assert "[MCP: fs]" in adapter.description

    def test_parameters_passthrough(self) -> None:
        schema = {"type": "object", "properties": {"path": {"type": "string"}}}
        info = McpToolInfo(name="read", description="", input_schema=schema, server_name="fs")
        client = MagicMock()
        adapter = McpToolAdapter(info, client)
        assert adapter.parameters == schema

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        info = McpToolInfo(name="read", description="", input_schema={}, server_name="fs")
        client = MagicMock()
        client.call_tool = AsyncMock(return_value={"content": [{"type": "text", "text": "ok"}]})
        client._config = McpServerConfig(name="fs", command="echo")
        adapter = McpToolAdapter(info, client)
        result = await adapter.execute("call-1", {"path": "/tmp"})
        assert result.content[0]["text"] == "ok"
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_execute_error(self) -> None:
        info = McpToolInfo(name="read", description="", input_schema={}, server_name="fs")
        client = MagicMock()
        client.call_tool = AsyncMock(side_effect=RuntimeError("boom"))
        client._config = McpServerConfig(name="fs", command="echo")
        adapter = McpToolAdapter(info, client)
        result = await adapter.execute("call-1", {})
        assert result.is_error
        assert "boom" in result.content[0]["text"]


class TestMcpRegistry:
    def test_empty_registry(self) -> None:
        reg = McpRegistry()
        assert reg.server_count == 0
        assert reg.tool_count == 0
        assert reg.get_tools() == []
        assert reg.get_status() == []
