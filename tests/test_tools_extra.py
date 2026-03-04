"""Tests for extra tools -- nodes, gateway, canvas tool handlers."""

from __future__ import annotations

from pyclaw.tools.canvas_tools import (
    tool_canvas_list,
    tool_canvas_read,
    tool_canvas_snapshot,
    tool_canvas_write,
)
from pyclaw.tools.gateway_tools import (
    tool_gateway_config,
    tool_gateway_restart,
    tool_gateway_status,
)
from pyclaw.tools.nodes import tool_nodes_invoke, tool_nodes_list


class TestNodeTools:
    def test_nodes_list_schema(self):
        schema = tool_nodes_list()
        assert schema["name"] == "nodes_list"
        assert "description" in schema

    def test_nodes_invoke_schema(self):
        schema = tool_nodes_invoke()
        assert schema["name"] == "nodes_invoke"
        assert "description" in schema
        props = schema.get("parameters", {}).get("properties", {})
        assert "node_id" in props or "command" in props


class TestGatewayTools:
    def test_status_schema(self):
        schema = tool_gateway_status()
        assert schema["name"] == "gateway_status"

    def test_restart_schema(self):
        schema = tool_gateway_restart()
        assert schema["name"] == "gateway_restart"

    def test_config_schema(self):
        schema = tool_gateway_config()
        assert schema["name"] == "gateway_config"


class TestCanvasTools:
    def test_read_schema(self):
        schema = tool_canvas_read()
        assert schema["name"] == "canvas_read"

    def test_write_schema(self):
        schema = tool_canvas_write()
        assert schema["name"] == "canvas_write"
        props = schema.get("parameters", {}).get("properties", {})
        assert "path" in props or "content" in props or "file_path" in props

    def test_list_schema(self):
        schema = tool_canvas_list()
        assert schema["name"] == "canvas_list"

    def test_snapshot_schema(self):
        schema = tool_canvas_snapshot()
        assert schema["name"] == "canvas_snapshot"
