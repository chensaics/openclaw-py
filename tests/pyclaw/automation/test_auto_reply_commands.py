"""Tests for Phase 24 — slash command registry, directives, message queue, dispatcher."""

from __future__ import annotations

import pytest

from pyclaw.auto_reply.commands_core import (
    handle_help,
    handle_status,
    handle_whoami,
    register_core_commands,
)
from pyclaw.auto_reply.commands_model import (
    handle_model,
    handle_think,
)
from pyclaw.auto_reply.commands_registry import (
    BUILTIN_COMMANDS,
    CommandContext,
    CommandDef,
    CommandRegistry,
    CommandResult,
    CommandScope,
    ParsedCommand,
    create_default_registry,
)
from pyclaw.auto_reply.commands_session import (
    handle_session,
    handle_stop,
)
from pyclaw.auto_reply.directives import (
    DirectivePersistence,
    apply_directives,
    is_fast_lane,
    parse_directives,
)
from pyclaw.auto_reply.message_queue import (
    DropPolicy,
    MessageQueue,
    QueuedMessage,
    QueueMode,
    QueueSettings,
)
from pyclaw.auto_reply.reply_dispatcher import (
    DispatcherRegistry,
    DispatchResult,
    DispatchRoute,
    InboundDeduplicator,
    InboundMessage,
    ReplyDispatcher,
)

# ===== Command Registry =====


class TestCommandRegistry:
    def test_register_and_parse(self) -> None:
        registry = CommandRegistry()
        defn = CommandDef(name="test", aliases=["t"], description="Test command")

        async def handler(ctx: CommandContext) -> CommandResult:
            return CommandResult(text="ok")

        registry.register(defn, handler)
        parsed = registry.parse("/test")
        assert parsed is not None
        assert parsed.name == "test"

    def test_parse_alias(self) -> None:
        registry = CommandRegistry()
        defn = CommandDef(name="help", aliases=["h", "?"])

        async def handler(ctx: CommandContext) -> CommandResult:
            return CommandResult(text="ok")

        registry.register(defn, handler)
        parsed = registry.parse("/h")
        assert parsed is not None
        assert parsed.name == "help"

    def test_parse_with_args(self) -> None:
        registry = CommandRegistry()
        defn = CommandDef(name="model")

        async def handler(ctx: CommandContext) -> CommandResult:
            return CommandResult(text="ok")

        registry.register(defn, handler)
        parsed = registry.parse("/model gpt-4o")
        assert parsed is not None
        assert parsed.args == ["gpt-4o"]
        assert parsed.raw_args == "gpt-4o"

    def test_parse_not_command(self) -> None:
        registry = CommandRegistry()
        assert registry.parse("hello") is None
        assert registry.parse("") is None

    def test_prefix_match(self) -> None:
        registry = CommandRegistry()
        defn = CommandDef(name="status")

        async def handler(ctx: CommandContext) -> CommandResult:
            return CommandResult(text="ok")

        registry.register(defn, handler)
        parsed = registry.parse("/sta")
        assert parsed is not None
        assert parsed.name == "status"

    def test_ambiguous_prefix(self) -> None:
        registry = CommandRegistry()
        for name in ["session", "send"]:
            defn = CommandDef(name=name)

            async def handler(ctx: CommandContext) -> CommandResult:
                return CommandResult(text="ok")

            registry.register(defn, handler)

        assert registry.parse("/se") is None  # ambiguous

    @pytest.mark.asyncio
    async def test_dispatch_scope_check(self) -> None:
        registry = CommandRegistry()
        defn = CommandDef(name="admin", scope=CommandScope.OWNER)

        async def handler(ctx: CommandContext) -> CommandResult:
            return CommandResult(text="admin ok")

        registry.register(defn, handler)
        ctx = CommandContext(
            command=ParsedCommand(name="admin", args=[], raw_args=""),
            is_owner=False,
        )
        result = await registry.dispatch(ctx)
        assert result is not None
        assert not result.success

    @pytest.mark.asyncio
    async def test_dispatch_success(self) -> None:
        registry = CommandRegistry()
        defn = CommandDef(name="ping")

        async def handler(ctx: CommandContext) -> CommandResult:
            return CommandResult(text="pong")

        registry.register(defn, handler)
        ctx = CommandContext(
            command=ParsedCommand(name="ping", args=[], raw_args=""),
        )
        result = await registry.dispatch(ctx)
        assert result is not None
        assert result.text == "pong"

    def test_list_commands(self) -> None:
        registry = create_default_registry()
        commands = registry.list_commands()
        assert len(commands) >= 15
        names = {c.name for c in commands}
        assert "help" in names
        assert "model" in names

    def test_hidden_not_listed(self) -> None:
        registry = create_default_registry()
        commands = registry.list_commands(include_hidden=False)
        names = {c.name for c in commands}
        assert "debug" not in names

    def test_builtin_commands_count(self) -> None:
        assert len(BUILTIN_COMMANDS) >= 18


# ===== Core Commands =====


class TestCoreCommands:
    @pytest.mark.asyncio
    async def test_help(self) -> None:
        registry = create_default_registry()
        register_core_commands(registry)
        ctx = CommandContext(
            command=ParsedCommand(name="help", args=[], raw_args=""),
            metadata={"registry": registry},
        )
        result = await handle_help(ctx)
        assert "Available Commands" in result.text

    @pytest.mark.asyncio
    async def test_status(self) -> None:
        ctx = CommandContext(
            command=ParsedCommand(name="status", args=[], raw_args=""),
            channel_id="test-ch",
            session_id="sess-1",
        )
        result = await handle_status(ctx)
        assert "test-ch" in result.text

    @pytest.mark.asyncio
    async def test_whoami(self) -> None:
        ctx = CommandContext(
            command=ParsedCommand(name="whoami", args=[], raw_args=""),
            sender_id="user-1",
            is_owner=True,
        )
        result = await handle_whoami(ctx)
        assert "user-1" in result.text
        assert "yes" in result.text


# ===== Session Commands =====


class TestSessionCommands:
    @pytest.mark.asyncio
    async def test_session_new(self) -> None:
        ctx = CommandContext(
            command=ParsedCommand(name="session", args=["new"], raw_args="new"),
        )
        result = await handle_session(ctx)
        assert "New session" in result.text

    @pytest.mark.asyncio
    async def test_session_list(self) -> None:
        ctx = CommandContext(
            command=ParsedCommand(name="session", args=["list"], raw_args="list"),
            metadata={"sessions": [{"id": "s1", "model": "gpt-4o", "turns": 5}]},
        )
        result = await handle_session(ctx)
        assert "s1" in result.text

    @pytest.mark.asyncio
    async def test_stop(self) -> None:
        result = await handle_stop(
            CommandContext(
                command=ParsedCommand(name="stop", args=[], raw_args=""),
            )
        )
        assert result.stop_processing is True


# ===== Model Commands =====


class TestModelCommands:
    @pytest.mark.asyncio
    async def test_model_show(self) -> None:
        ctx = CommandContext(
            command=ParsedCommand(name="model", args=[], raw_args=""),
            metadata={"current_model": "gpt-4o"},
        )
        result = await handle_model(ctx)
        assert "gpt-4o" in result.text

    @pytest.mark.asyncio
    async def test_model_switch(self) -> None:
        ctx = CommandContext(
            command=ParsedCommand(name="model", args=["claude-3"], raw_args="claude-3"),
        )
        result = await handle_model(ctx)
        assert "claude-3" in result.text

    @pytest.mark.asyncio
    async def test_think_valid(self) -> None:
        ctx = CommandContext(
            command=ParsedCommand(name="think", args=["low"], raw_args="low"),
        )
        result = await handle_think(ctx)
        assert "low" in result.text

    @pytest.mark.asyncio
    async def test_think_invalid(self) -> None:
        ctx = CommandContext(
            command=ParsedCommand(name="think", args=["extreme"], raw_args="extreme"),
        )
        result = await handle_think(ctx)
        assert not result.success


# ===== Directives =====


class TestDirectives:
    def test_parse_think(self) -> None:
        ds = parse_directives("Hello @think low world")
        assert ds.has_directives
        assert ds.think_level == "low"
        assert "Hello" in ds.cleaned_text
        assert "@think" not in ds.cleaned_text

    def test_parse_model(self) -> None:
        ds = parse_directives("@model gpt-4o explain this")
        assert ds.model_override == "gpt-4o"

    def test_parse_multiple(self) -> None:
        ds = parse_directives("@think high @verbose tell me")
        assert ds.think_level == "high"
        assert ds.is_verbose

    def test_no_directives(self) -> None:
        ds = parse_directives("Just a normal message")
        assert not ds.has_directives
        assert ds.cleaned_text == "Just a normal message"

    def test_apply(self) -> None:
        ds = parse_directives("@model gpt-4o @think low")
        overrides = apply_directives(ds)
        assert overrides.model == "gpt-4o"
        assert overrides.think_level == "low"

    def test_fast_lane_directive_only(self) -> None:
        ds = parse_directives("@think high")
        assert is_fast_lane(ds)

    def test_not_fast_lane_with_text(self) -> None:
        ds = parse_directives("@think high tell me something")
        assert not is_fast_lane(ds)

    def test_not_fast_lane_verbose(self) -> None:
        ds = parse_directives("@verbose")
        assert not is_fast_lane(ds)

    def test_persistence(self) -> None:
        persist = DirectivePersistence()
        ds = parse_directives("@model gpt-4o")
        persist.update(ds)
        overrides = persist.get_sticky_overrides()
        assert overrides.model == "gpt-4o"

    def test_persistence_clear(self) -> None:
        persist = DirectivePersistence()
        persist.update(parse_directives("@think low"))
        persist.clear()
        assert persist.get_sticky_overrides().think_level is None

    def test_elevated(self) -> None:
        ds = parse_directives("@elevated do this")
        assert ds.is_elevated

    def test_exec(self) -> None:
        ds = parse_directives("@exec ls -la")
        assert ds.is_exec


# ===== Message Queue =====


class TestMessageQueue:
    def test_enqueue_dequeue(self) -> None:
        q = MessageQueue()
        q.enqueue(QueuedMessage(text="hello"))
        assert q.size == 1
        result = q.drain()
        assert len(result.messages) == 1
        assert q.is_empty

    def test_capacity_drop_oldest(self) -> None:
        q = MessageQueue(QueueSettings(max_size=2, drop_policy=DropPolicy.DROP_OLDEST))
        q.enqueue(QueuedMessage(text="a"))
        q.enqueue(QueuedMessage(text="b"))
        q.enqueue(QueuedMessage(text="c"))
        assert q.size == 2
        result = q.drain()
        assert result.messages[0].text == "b"

    def test_capacity_reject(self) -> None:
        q = MessageQueue(QueueSettings(max_size=1, drop_policy=DropPolicy.REJECT))
        assert q.enqueue(QueuedMessage(text="a")) is True
        assert q.enqueue(QueuedMessage(text="b")) is False
        assert q.size == 1

    def test_steer_drain(self) -> None:
        q = MessageQueue(QueueSettings(mode=QueueMode.STEER))
        q.enqueue(QueuedMessage(text="first"))
        q.enqueue(QueuedMessage(text="second"))
        result = q.drain_for_steer()
        assert len(result.messages) == 1
        assert result.messages[0].text == "second"

    def test_normalize(self) -> None:
        q = MessageQueue()
        q.enqueue(QueuedMessage(text="hi", sender_id="u1"))
        q.enqueue(QueuedMessage(text="hi", sender_id="u1"))
        q.enqueue(QueuedMessage(text="hello", sender_id="u1"))
        q.normalize()
        assert q.size == 2

    def test_clear(self) -> None:
        q = MessageQueue()
        q.enqueue(QueuedMessage(text="a"))
        q.enqueue(QueuedMessage(text="b"))
        cleared = q.clear()
        assert cleared == 2
        assert q.is_empty


# ===== Reply Dispatcher =====


class TestInboundDeduplicator:
    def test_not_duplicate(self) -> None:
        dedup = InboundDeduplicator()
        msg = InboundMessage(text="hello", sender_id="u1", channel_id="c1")
        assert dedup.is_duplicate(msg) is False

    def test_duplicate(self) -> None:
        dedup = InboundDeduplicator()
        msg = InboundMessage(text="hello", sender_id="u1", channel_id="c1", message_id="m1")
        assert dedup.is_duplicate(msg) is False
        assert dedup.is_duplicate(msg) is True

    def test_different_not_duplicate(self) -> None:
        dedup = InboundDeduplicator()
        msg1 = InboundMessage(text="hello", sender_id="u1", channel_id="c1", message_id="m1")
        msg2 = InboundMessage(text="world", sender_id="u1", channel_id="c1", message_id="m2")
        assert dedup.is_duplicate(msg1) is False
        assert dedup.is_duplicate(msg2) is False


class TestReplyDispatcher:
    @pytest.mark.asyncio
    async def test_dispatch_route(self) -> None:
        dispatcher = ReplyDispatcher()

        async def handler(msg: InboundMessage) -> DispatchResult:
            return DispatchResult(reply_text="handled")

        dispatcher.add_route(DispatchRoute(name="default", handler=handler))
        msg = InboundMessage(text="hi", sender_id="u1", channel_id="c1")
        result = await dispatcher.dispatch(msg)
        assert result.dispatched
        assert result.routed_to == "default"

    @pytest.mark.asyncio
    async def test_dedup(self) -> None:
        dispatcher = ReplyDispatcher()

        async def handler(msg: InboundMessage) -> DispatchResult:
            return DispatchResult(reply_text="ok")

        dispatcher.add_route(DispatchRoute(name="default", handler=handler))
        msg = InboundMessage(text="hi", sender_id="u1", channel_id="c1", message_id="m1")
        r1 = await dispatcher.dispatch(msg)
        r2 = await dispatcher.dispatch(msg)
        assert r1.dispatched
        assert not r2.dispatched
        assert r2.deduplicated

    @pytest.mark.asyncio
    async def test_no_route(self) -> None:
        dispatcher = ReplyDispatcher()
        msg = InboundMessage(text="hi", sender_id="u1", channel_id="c1")
        result = await dispatcher.dispatch(msg)
        assert not result.dispatched

    def test_dispatcher_registry(self) -> None:
        registry = DispatcherRegistry()
        d = ReplyDispatcher()
        d.start()
        registry.register("main", d)
        assert registry.list_active() == ["main"]
        d.stop()
        assert registry.list_active() == []
