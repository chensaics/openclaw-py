"""Tests for the hooks system -- registry, loader, types."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pyclaw.hooks.registry import (
    clear_hooks,
    create_hook_event,
    register_hook,
    trigger_hook,
    unregister_hook,
)
from pyclaw.hooks.types import HookEvent, HookEventType


@pytest.fixture(autouse=True)
def _clean_hooks():
    clear_hooks()
    yield
    clear_hooks()


class TestHookRegistry:
    def test_register_and_trigger(self):
        called = []

        async def handler(event: HookEvent) -> None:
            called.append(event.action)

        register_hook("command", handler)
        event = create_hook_event(HookEventType.COMMAND, "new")
        asyncio.run(trigger_hook(event))
        assert called == ["new"]

    def test_register_specific_key(self):
        called = []

        async def handler(event: HookEvent) -> None:
            called.append(event.action)

        register_hook("command:reset", handler)
        event_new = create_hook_event(HookEventType.COMMAND, "new")
        asyncio.run(trigger_hook(event_new))
        assert called == []

        event_reset = create_hook_event(HookEventType.COMMAND, "reset")
        asyncio.run(trigger_hook(event_reset))
        assert called == ["reset"]

    def test_unregister(self):
        called = []

        async def handler(event: HookEvent) -> None:
            called.append(1)

        register_hook("session", handler)
        unregister_hook("session", handler)
        event = create_hook_event(HookEventType.SESSION, "start")
        asyncio.run(trigger_hook(event))
        assert called == []

    def test_clear_hooks(self):
        register_hook("command", AsyncMock())
        register_hook("session", AsyncMock())
        clear_hooks()
        event = create_hook_event(HookEventType.COMMAND, "x")
        asyncio.run(trigger_hook(event))

    def test_handler_error_does_not_stop_others(self):
        results = []

        async def bad_handler(event: HookEvent) -> None:
            raise ValueError("boom")

        async def good_handler(event: HookEvent) -> None:
            results.append("ok")

        register_hook("command", bad_handler)
        register_hook("command", good_handler)
        event = create_hook_event(HookEventType.COMMAND, "go")
        asyncio.run(trigger_hook(event))
        assert results == ["ok"]

    def test_multiple_handlers(self):
        order = []

        async def h1(event: HookEvent) -> None:
            order.append("h1")

        async def h2(event: HookEvent) -> None:
            order.append("h2")

        register_hook("command", h1)
        register_hook("command", h2)
        event = create_hook_event(HookEventType.COMMAND, "go")
        asyncio.run(trigger_hook(event))
        assert order == ["h1", "h2"]


class TestCreateHookEvent:
    def test_basic(self):
        event = create_hook_event(HookEventType.COMMAND, "new", session_key="s1")
        assert event.type == HookEventType.COMMAND
        assert event.action == "new"
        assert event.session_key == "s1"
        assert event.timestamp > 0

    def test_enum_type(self):
        event = create_hook_event(HookEventType.GATEWAY, "start")
        assert event.type == HookEventType.GATEWAY

    def test_context_and_messages(self):
        event = create_hook_event(HookEventType.MESSAGE, "received", context={"k": "v"}, messages=[{"role": "user"}])
        assert event.context == {"k": "v"}
        assert len(event.messages) == 1


class TestHookLoader:
    def test_parse_frontmatter(self):
        from pyclaw.hooks.loader import _parse_frontmatter

        text = "---\nname: test-hook\nevents: [command:new, session:start]\nrequires: memory\n---\n# Hook"
        result = _parse_frontmatter(text)
        assert result["name"] == "test-hook"
        assert "command:new" in result["events"]
        assert result["requires"] == "memory"

    def test_parse_frontmatter_empty(self):
        from pyclaw.hooks.loader import _parse_frontmatter

        result = _parse_frontmatter("No frontmatter here")
        assert result == {}

    def test_load_hook_entries_no_hooks(self):
        from pyclaw.hooks.loader import load_hook_entries

        with tempfile.TemporaryDirectory() as td:
            entries = load_hook_entries(Path(td))
            assert entries == []
