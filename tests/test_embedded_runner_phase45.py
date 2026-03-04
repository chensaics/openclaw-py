"""Phase 45 tests — Embedded Runner main path, config switch, abort + usage."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 45a: Runner config switch
# ---------------------------------------------------------------------------


class TestRunnerConfigSwitch:
    """Verify _use_embedded_runner reads config correctly."""

    def test_default_is_embedded(self) -> None:
        from pyclaw.gateway.methods.chat import _use_embedded_runner

        with patch("pyclaw.config.io.load_config_raw", return_value={}):
            assert _use_embedded_runner() is True

    def test_explicit_embedded(self) -> None:
        from pyclaw.gateway.methods.chat import _use_embedded_runner

        with patch("pyclaw.config.io.load_config_raw", return_value={"runner": {"mode": "embedded"}}):
            assert _use_embedded_runner() is True

    def test_legacy_mode(self) -> None:
        from pyclaw.gateway.methods.chat import _use_embedded_runner

        with patch("pyclaw.config.io.load_config_raw", return_value={"runner": {"mode": "legacy"}}):
            assert _use_embedded_runner() is False

    def test_error_defaults_to_embedded(self) -> None:
        from pyclaw.gateway.methods.chat import _use_embedded_runner

        with patch("pyclaw.config.io.load_config_raw", side_effect=Exception("boom")):
            assert _use_embedded_runner() is True


# ---------------------------------------------------------------------------
# 45b: Embedded runner used by default in chat.send
# ---------------------------------------------------------------------------


class TestChatSendRunnerDispatch:
    """Verify chat.send dispatches to embedded or legacy based on config."""

    @pytest.mark.asyncio
    async def test_dispatches_to_embedded(self) -> None:
        from pyclaw.gateway.methods.chat import create_chat_handlers

        handlers = create_chat_handlers()
        handler = handlers["chat.send"]

        conn = MagicMock()
        conn.send_ok = AsyncMock()
        conn.send_event = AsyncMock()
        conn.send_error = AsyncMock()

        with (
            patch("pyclaw.gateway.methods.chat._use_embedded_runner", return_value=True),
            patch("pyclaw.gateway.methods.chat._run_embedded", new_callable=AsyncMock) as mock_embedded,
            patch("pyclaw.gateway.methods.chat._run_legacy", new_callable=AsyncMock) as mock_legacy,
        ):
            await handler({"message": "hi", "provider": "test", "model": "test-model"}, conn)
            mock_embedded.assert_awaited_once()
            mock_legacy.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dispatches_to_legacy(self) -> None:
        from pyclaw.gateway.methods.chat import create_chat_handlers

        handlers = create_chat_handlers()
        handler = handlers["chat.send"]

        conn = MagicMock()
        conn.send_ok = AsyncMock()
        conn.send_event = AsyncMock()
        conn.send_error = AsyncMock()

        with (
            patch("pyclaw.gateway.methods.chat._use_embedded_runner", return_value=False),
            patch("pyclaw.gateway.methods.chat._run_embedded", new_callable=AsyncMock) as mock_embedded,
            patch("pyclaw.gateway.methods.chat._run_legacy", new_callable=AsyncMock) as mock_legacy,
        ):
            await handler({"message": "hi", "provider": "test", "model": "test-model"}, conn)
            mock_legacy.assert_awaited_once()
            mock_embedded.assert_not_awaited()


# ---------------------------------------------------------------------------
# 45c: Abort consistency
# ---------------------------------------------------------------------------


class TestChatAbortConsistency:
    """Verify abort sets the event and is reported."""

    @pytest.mark.asyncio
    async def test_abort_unknown_session(self) -> None:
        from pyclaw.gateway.methods.chat import create_chat_handlers

        handlers = create_chat_handlers()
        conn = MagicMock()
        conn.send_ok = AsyncMock()
        conn.send_error = AsyncMock()

        await handlers["chat.abort"]({"sessionId": "nope", "agentId": "main"}, conn)
        conn.send_ok.assert_awaited_once()
        payload = conn.send_ok.call_args[0][1]
        assert payload["aborted"] is False


# ---------------------------------------------------------------------------
# 45d: Usage tracking in embedded path
# ---------------------------------------------------------------------------


class TestUsageTracking:
    """Verify usage recording is called in embedded runner path."""

    @pytest.mark.asyncio
    async def test_usage_recorded(self) -> None:
        from pyclaw.gateway.methods.chat import _run_embedded

        conn = MagicMock()
        conn.send_event = AsyncMock()
        conn.send_ok = AsyncMock()

        import asyncio

        abort = asyncio.Event()

        mock_event = MagicMock()
        mock_event.type = "done"
        mock_event.delta = None
        mock_event.name = None
        mock_event.result = None
        mock_event.error = None
        mock_event.tool_call_id = None
        mock_event.usage = {"input_tokens": 100, "output_tokens": 50}

        async def fake_run_agent(**kwargs: Any):
            yield mock_event

        mock_model = MagicMock()
        mock_model.model_id = "test-model"
        mock_model.provider = "test-provider"

        mock_session = MagicMock()

        with (
            patch("pyclaw.agents.runner.run_agent", side_effect=fake_run_agent),
            patch("pyclaw.infra.session_cost.record_usage") as mock_record,
        ):
            await _run_embedded(
                message="hello",
                session=mock_session,
                model=mock_model,
                tools=[],
                system_prompt=None,
                abort_event=abort,
                conn=conn,
                session_key="test-key",
            )
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            assert call_kwargs[1]["input_tokens"] == 100
            assert call_kwargs[1]["output_tokens"] == 50


# ---------------------------------------------------------------------------
# 45e: chat.history still works
# ---------------------------------------------------------------------------


class TestChatHistoryRegression:
    """Chat history handler still returns messages."""

    @pytest.mark.asyncio
    async def test_history_no_session(self) -> None:
        from pyclaw.gateway.methods.chat import create_chat_handlers

        handlers = create_chat_handlers()
        conn = MagicMock()
        conn.send_ok = AsyncMock()
        conn.send_error = AsyncMock()

        with patch("pyclaw.config.paths.resolve_sessions_dir") as mock_dir:
            mock_dir.return_value = Path("/tmp/nonexistent-sessions-dir-p45")
            await handlers["chat.history"]({"agentId": "main", "sessionId": "none"}, conn)
            conn.send_ok.assert_awaited_once()
            payload = conn.send_ok.call_args[0][1]
            assert payload["messages"] == []
