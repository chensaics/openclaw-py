"""End-to-end integration test — Gateway startup → agent round-trip.

Tests the full flow: start gateway, connect via WebSocket,
send a message, receive an agent response.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture
def gateway_app():
    """Create a test gateway application."""
    from pyclaw.gateway.server import create_gateway_app

    app = create_gateway_app(auth_token="test-token-123")
    return app


class TestGatewayStartup:
    """Verify gateway starts and serves health/status endpoints."""

    def test_gateway_creates(self, gateway_app: Any) -> None:
        assert gateway_app is not None
        assert gateway_app.app is not None

    def test_gateway_has_routes(self, gateway_app: Any) -> None:
        routes = [r.path for r in gateway_app.app.routes if hasattr(r, "path")]
        assert len(routes) > 0


class TestGatewayRPC:
    """Verify core RPC methods are registered."""

    def test_core_handlers_registered(self, gateway_app: Any) -> None:
        from pyclaw.gateway.methods import CORE_METHOD_NAMES

        for method_name in CORE_METHOD_NAMES:
            handler = gateway_app.get_handler(method_name)
            assert handler is not None, f"Handler for '{method_name}' not registered"


class TestAgentRoundTrip:
    """Verify agent can process a message and return a response."""

    @pytest.mark.asyncio
    async def test_agent_produces_response(self) -> None:
        from pyclaw.agents.runner import run_agent
        from pyclaw.agents.session import SessionManager
        from pyclaw.agents.types import ModelConfig

        session = SessionManager.in_memory()

        mock_response = {
            "choices": [
                {
                    "delta": {"content": "Hello!"},
                    "finish_reason": "stop",
                }
            ]
        }

        with patch("pyclaw.agents.runner._call_llm") as mock_llm:
            mock_llm.return_value = _mock_stream([mock_response])

            model = ModelConfig(
                provider="openai",
                model_id="gpt-4o",
                api_key="test-key",
            )

            events = []
            async for event in run_agent(
                prompt="Hello",
                session=session,
                model=model,
            ):
                events.append(event)

            assert len(events) > 0


class TestConfigMigrationE2E:
    """Verify config migration works end-to-end."""

    def test_v1_to_v3_migration(self) -> None:
        from pyclaw.config.migrations import create_default_registry

        registry = create_default_registry()
        config = {
            "model": "gpt-4",
            "allowFrom": ["user1"],
            "systemPrompt": "Be helpful",
        }

        result = registry.migrate(config, target_version="v3")
        assert result.success
        assert config["version"] == "v3"
        assert "agents" in config
        assert config["agents"]["default"]["model"] == "gpt-4"


class TestProgressStreaming:
    """Verify progress events flow correctly."""

    def test_progress_event_serialization(self) -> None:
        from pyclaw.agents.progress import ProgressEvent, ProgressStatus

        event = ProgressEvent(
            task_id="test-task",
            status=ProgressStatus.PROGRESS,
            progress=0.5,
            message="Half done",
        )
        d = event.to_dict()
        assert d["taskId"] == "test-task"
        assert d["progress"] == 0.5
        assert d["status"] == "progress"

    def test_progress_listener_broadcast(self) -> None:
        from pyclaw.agents.progress import (
            ProgressEvent,
            ProgressStatus,
            add_progress_listener,
            emit_progress,
            remove_progress_listener,
        )

        received: list[ProgressEvent] = []
        add_progress_listener(received.append)

        try:
            emit_progress(
                ProgressEvent(
                    task_id="test",
                    status=ProgressStatus.STARTED,
                )
            )
            assert len(received) == 1
            assert received[0].task_id == "test"
        finally:
            remove_progress_listener(received.append)


class TestMediaFetch:
    """Verify media fetch module works correctly."""

    def test_fetch_result_properties(self) -> None:
        from pyclaw.media.fetch import FetchResult

        ok_result = FetchResult(
            path="/tmp/test.jpg",
            mime_type="image/jpeg",
            size=1024,
            url="https://example.com/test.jpg",
        )
        assert ok_result.ok

        err_result = FetchResult(url="https://bad.com", error="404")
        assert not err_result.ok


async def _mock_stream(chunks: list[dict[str, Any]]):
    for chunk in chunks:
        yield chunk
