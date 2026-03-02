"""Tests for pyclaw.agents.interrupt — cancel/append interrupt system."""

import pytest

from pyclaw.agents.interrupt import InterruptibleContext, InterruptMode


class TestInterruptibleContext:
    def test_initial_state(self) -> None:
        ctx = InterruptibleContext()
        assert ctx.is_cancelled is False
        assert ctx.has_appended is False
        assert ctx.history == []

    def test_cancel(self) -> None:
        ctx = InterruptibleContext()
        ctx.request_cancel("Stop now")
        assert ctx.is_cancelled is True
        assert len(ctx.history) == 1
        assert ctx.history[0].mode == InterruptMode.CANCEL

    def test_append(self) -> None:
        ctx = InterruptibleContext()
        ctx.request_append("Also do X")
        assert ctx.is_cancelled is False
        assert ctx.has_appended is True

        messages = ctx.drain_appended()
        assert messages == ["Also do X"]
        assert ctx.has_appended is False

    def test_multiple_appends(self) -> None:
        ctx = InterruptibleContext()
        ctx.request_append("First")
        ctx.request_append("Second")
        ctx.request_append("Third")

        messages = ctx.drain_appended()
        assert len(messages) == 3
        assert messages[0] == "First"
        assert messages[2] == "Third"

    def test_drain_empty(self) -> None:
        ctx = InterruptibleContext()
        assert ctx.drain_appended() == []

    def test_history_tracking(self) -> None:
        ctx = InterruptibleContext()
        ctx.request_append("a")
        ctx.request_append("b")
        ctx.request_cancel("stop")

        assert len(ctx.history) == 3
        assert ctx.history[0].mode == InterruptMode.APPEND
        assert ctx.history[2].mode == InterruptMode.CANCEL
