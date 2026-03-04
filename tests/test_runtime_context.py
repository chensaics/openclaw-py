"""Tests for pyclaw.agents.tools.runtime_context."""

from pyclaw.agents.tools.runtime_context import (
    RuntimeContext,
    get_runtime_context,
    get_runtime_context_or_default,
    reset_runtime_context,
    set_runtime_context,
)


class TestRuntimeContext:
    def test_default_values(self) -> None:
        ctx = RuntimeContext()
        assert ctx.channel == ""
        assert ctx.chat_id == ""
        assert ctx.is_channel_bound is False

    def test_channel_bound(self) -> None:
        ctx = RuntimeContext(channel="telegram", chat_id="123")
        assert ctx.is_channel_bound is True

    def test_set_and_get(self) -> None:
        ctx = RuntimeContext(channel="discord", chat_id="456", session_key="s1")
        token = set_runtime_context(ctx)
        try:
            retrieved = get_runtime_context()
            assert retrieved is not None
            assert retrieved.channel == "discord"
            assert retrieved.session_key == "s1"
        finally:
            reset_runtime_context(token)

    def test_get_default(self) -> None:
        ctx = get_runtime_context_or_default()
        assert ctx.channel == ""

    def test_reset(self) -> None:
        ctx = RuntimeContext(channel="slack")
        token = set_runtime_context(ctx)
        reset_runtime_context(token)
        assert get_runtime_context() is None
