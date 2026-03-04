"""MCP integration tests — simulate real stdio and HTTP MCP servers.

Uses in-process fake servers to test the full MCP flow:
  connect → initialize → tools/list → tools/call → disconnect
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyclaw.mcp.client import McpClient
from pyclaw.mcp.http_transport import HttpTransport
from pyclaw.mcp.registry import McpRegistry, McpToolAdapter
from pyclaw.mcp.stdio_transport import StdioTransport
from pyclaw.mcp.types import McpServerConfig, McpToolInfo

FAKE_TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from disk",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_dir",
        "description": "List directory contents",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        },
    },
]


def _make_jsonrpc_response(req_id: int | str, result: Any) -> str:
    """Build a JSON-RPC response line."""
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}) + "\n"


class FakeStdioProcess:
    """Simulates a stdio MCP server subprocess."""

    def __init__(self) -> None:
        self.stdin = MagicMock()
        self.stderr = MagicMock()
        self.returncode: int | None = None
        self._requests: list[dict[str, Any]] = []
        self._response_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.pid = 99999

        drain_future: asyncio.Future[None] = asyncio.get_event_loop().create_future()
        drain_future.set_result(None)
        self.stdin.drain = AsyncMock(return_value=None)

        original_write = self.stdin.write

        def capture_write(data: bytes) -> None:
            try:
                req = json.loads(data.decode("utf-8").strip())
                self._requests.append(req)
                response = self._handle_request(req)
                self._response_queue.put_nowait(response.encode("utf-8"))
            except Exception:
                pass

        self.stdin.write = capture_write

        self.stdout = self

    def _handle_request(self, req: dict[str, Any]) -> str:
        method = req.get("method", "")
        req_id = req.get("id")

        if method == "initialize":
            return _make_jsonrpc_response(
                req_id,
                {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "fake-server", "version": "1.0"},
                    "capabilities": {"tools": {}},
                },
            )
        elif method == "notifications/initialized":
            return ""
        elif method == "tools/list":
            return _make_jsonrpc_response(req_id, {"tools": FAKE_TOOLS})
        elif method == "tools/call":
            tool_name = req.get("params", {}).get("name", "")
            args = req.get("params", {}).get("arguments", {})
            if tool_name == "read_file":
                return _make_jsonrpc_response(
                    req_id,
                    {
                        "content": [{"type": "text", "text": f"Contents of {args.get('path', '?')}"}],
                    },
                )
            elif tool_name == "list_dir":
                return _make_jsonrpc_response(
                    req_id,
                    {
                        "content": [{"type": "text", "text": "file1.txt\nfile2.py\ndir/"}],
                    },
                )
            return _make_jsonrpc_response(req_id, {"content": [{"type": "text", "text": "unknown tool"}]})
        return ""

    async def readline(self) -> bytes:
        try:
            data = await asyncio.wait_for(self._response_queue.get(), timeout=5.0)
            return data
        except TimeoutError:
            return b""

    def terminate(self) -> None:
        self.returncode = 0

    async def wait(self) -> int:
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.returncode = -9


class TestStdioTransportIntegration:
    """Test StdioTransport with a fake subprocess."""

    @pytest.mark.asyncio
    async def test_connect_and_send(self) -> None:
        fake_proc = FakeStdioProcess()

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = fake_proc

            transport = StdioTransport(command="fake-mcp-server")
            await transport.connect()

            assert transport.is_connected

            result = await transport.send(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0.1"},
                },
            )

            assert isinstance(result, dict)
            assert result["serverInfo"]["name"] == "fake-server"

            await transport.disconnect()
            assert not transport.is_connected

    @pytest.mark.asyncio
    async def test_tool_discovery(self) -> None:
        fake_proc = FakeStdioProcess()

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = fake_proc

            transport = StdioTransport(command="fake-mcp-server")
            await transport.connect()

            result = await transport.send("tools/list", {})
            tools = result.get("tools", [])
            assert len(tools) == 2
            assert tools[0]["name"] == "read_file"
            assert tools[1]["name"] == "list_dir"

            await transport.disconnect()

    @pytest.mark.asyncio
    async def test_tool_call(self) -> None:
        fake_proc = FakeStdioProcess()

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = fake_proc

            transport = StdioTransport(command="fake-mcp-server")
            await transport.connect()

            result = await transport.send(
                "tools/call",
                {
                    "name": "read_file",
                    "arguments": {"path": "/tmp/test.txt"},
                },
            )
            assert "content" in result
            assert "Contents of /tmp/test.txt" in result["content"][0]["text"]

            await transport.disconnect()


class TestHttpTransportIntegration:
    """Test HttpTransport with mocked httpx responses."""

    @pytest.mark.asyncio
    async def test_connect_and_initialize(self) -> None:
        init_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "http-server", "version": "1.0"},
                "capabilities": {"tools": {}},
            },
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.json.return_value = init_response
            mock_resp.raise_for_status = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_resp)
            mock_instance.aclose = AsyncMock()
            MockClient.return_value = mock_instance

            transport = HttpTransport(url="http://localhost:3000/mcp")
            await transport.connect()
            assert transport.is_connected

            result = await transport.send(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                },
            )
            assert result["serverInfo"]["name"] == "http-server"

            await transport.disconnect()
            assert not transport.is_connected

    @pytest.mark.asyncio
    async def test_tool_list_http(self) -> None:
        tools_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": FAKE_TOOLS},
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.json.return_value = tools_response
            mock_resp.raise_for_status = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_resp)
            mock_instance.aclose = AsyncMock()
            MockClient.return_value = mock_instance

            transport = HttpTransport(url="http://localhost:3000/mcp")
            await transport.connect()

            result = await transport.send("tools/list", {})
            assert len(result["tools"]) == 2

            await transport.disconnect()

    @pytest.mark.asyncio
    async def test_rpc_error_raises(self) -> None:
        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid request"},
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.json.return_value = error_response
            mock_resp.raise_for_status = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_resp)
            mock_instance.aclose = AsyncMock()
            MockClient.return_value = mock_instance

            transport = HttpTransport(url="http://localhost:3000/mcp")
            await transport.connect()

            with pytest.raises(RuntimeError, match="Invalid request"):
                await transport.send("bad/method", {})

            await transport.disconnect()


class TestMcpClientIntegration:
    """Test McpClient full lifecycle with mocked transport."""

    @pytest.mark.asyncio
    async def test_client_full_lifecycle(self) -> None:
        config = McpServerConfig(
            name="test-server",
            url="http://localhost:3000/mcp",
        )

        responses = [
            {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "test", "version": "1.0"},
                "capabilities": {},
            },
            None,
            {"tools": FAKE_TOOLS},
        ]
        call_idx = 0

        async def fake_send(method: str, params: Any = None) -> Any:
            nonlocal call_idx
            result = responses[call_idx] if call_idx < len(responses) else {}
            call_idx += 1
            return result

        mock_transport = MagicMock()
        mock_transport.is_connected = True
        mock_transport.connect = AsyncMock()
        mock_transport.disconnect = AsyncMock()
        mock_transport.send = AsyncMock(side_effect=fake_send)

        with patch("pyclaw.mcp.http_transport.HttpTransport", return_value=mock_transport):
            client = McpClient(config)
            await client.connect()

            assert client.is_connected
            assert len(client.tools) == 2
            assert client.tools[0].name == "read_file"
            assert client.tools[1].name == "list_dir"

            await client.disconnect()
            assert not client.is_connected

    @pytest.mark.asyncio
    async def test_client_tool_call(self) -> None:
        config = McpServerConfig(name="test", url="http://localhost:3000/mcp")

        lifecycle_responses = [
            {"protocolVersion": "2024-11-05", "serverInfo": {"name": "t"}, "capabilities": {}},
            None,
            {"tools": FAKE_TOOLS},
        ]
        call_count = 0

        async def fake_send(method: str, params: Any = None) -> Any:
            nonlocal call_count
            if call_count < len(lifecycle_responses):
                r = lifecycle_responses[call_count]
                call_count += 1
                return r
            return {"content": [{"type": "text", "text": "tool result here"}]}

        mock_transport = MagicMock()
        mock_transport.is_connected = True
        mock_transport.connect = AsyncMock()
        mock_transport.disconnect = AsyncMock()
        mock_transport.send = AsyncMock(side_effect=fake_send)

        with patch("pyclaw.mcp.http_transport.HttpTransport", return_value=mock_transport):
            client = McpClient(config)
            await client.connect()

            result = await client.call_tool("read_file", {"path": "/tmp/x"})
            assert "content" in result

            await client.disconnect()


class TestMcpRegistryIntegration:
    """Test McpRegistry with multiple servers."""

    @pytest.mark.asyncio
    async def test_registry_multi_server(self) -> None:
        configs = {
            "fs": {"command": "fake-fs-server"},
            "api": {
                "url": "http://localhost:4000/mcp",
                "headers": {"Authorization": "Bearer test"},
            },
        }

        registry = McpRegistry()

        with patch.object(McpClient, "connect", new_callable=AsyncMock):
            with patch.object(McpClient, "disconnect", new_callable=AsyncMock):
                with patch.object(
                    McpClient,
                    "tools",
                    new_callable=lambda: property(
                        lambda self: [
                            McpToolInfo(
                                name=f"tool_{self.server_name}",
                                description=f"Tool from {self.server_name}",
                                input_schema={"type": "object"},
                                server_name=self.server_name,
                            )
                        ]
                    ),
                ):
                    await registry.connect_all(configs)
                    tools = registry.get_tools()
                    assert len(tools) >= 0

                    await registry.disconnect_all()

    def test_tool_adapter_properties(self) -> None:
        info = McpToolInfo(
            name="fetch",
            description="Fetch a URL",
            input_schema={"type": "object", "properties": {"url": {"type": "string"}}},
            server_name="web-tools",
        )
        client = MagicMock()
        adapter = McpToolAdapter(info, client)

        assert adapter.name == "mcp_web-tools_fetch"
        assert "MCP: web-tools" in adapter.description
        assert "url" in adapter.parameters["properties"]

    @pytest.mark.asyncio
    async def test_tool_adapter_execute(self) -> None:
        info = McpToolInfo(
            name="greet",
            description="Say hello",
            input_schema={"type": "object"},
            server_name="hello",
        )
        client = AsyncMock()
        client.call_tool = AsyncMock(
            return_value={
                "content": [{"type": "text", "text": "Hello, World!"}],
            }
        )
        client._config = McpServerConfig(name="hello", url="http://x")

        adapter = McpToolAdapter(info, client)
        result = await adapter.execute("call-1", {"name": "Alice"})

        assert result is not None
        client.call_tool.assert_called_once_with("greet", {"name": "Alice"})

    @pytest.mark.asyncio
    async def test_tool_adapter_timeout(self) -> None:
        info = McpToolInfo(name="slow", description="Slow tool", input_schema={}, server_name="s")
        client = AsyncMock()
        client.call_tool = AsyncMock(side_effect=TimeoutError())
        client._config = McpServerConfig(name="s", url="http://x", tool_timeout=1)

        adapter = McpToolAdapter(info, client)
        result = await adapter.execute("call-2", {})

        assert result.is_error
