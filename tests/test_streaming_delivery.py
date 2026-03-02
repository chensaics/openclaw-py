"""Tests for Phase 25 — block streaming, target resolver, send service, message actions, HTML export."""

from __future__ import annotations

import pytest

from pyclaw.auto_reply.block_streaming import (
    BlockCoalescer,
    StreamBlock,
    StreamingConfig,
    get_streaming_config,
)
from pyclaw.infra.outbound.target_resolver import (
    DeliveryTarget,
    TargetResolutionContext,
    TargetResolver,
)
from pyclaw.infra.outbound.send_service import (
    MessageEnvelope,
    MessageFormat,
    OutboundSendService,
    SendResult,
    SenderIdentity,
    generate_conversation_id,
)
from pyclaw.infra.outbound.message_actions import (
    ActionResult,
    ActionSpec,
    ActionType,
    MessageActionRunner,
)
from pyclaw.infra.outbound.channel_adapters import (
    ChannelAdapterRegistry,
    ChannelCapabilities,
    MediaType,
    OutboundPayload,
    OutboundResult,
)
from pyclaw.auto_reply.export_html import (
    ExportEntry,
    ExportOptions,
    export_session_html,
    markdown_to_html,
)


# ===== Block Streaming =====

class TestStreamingConfig:
    def test_defaults(self) -> None:
        config = get_streaming_config("openai")
        assert config.min_chars == 15

    def test_unknown_provider(self) -> None:
        config = get_streaming_config("unknown")
        assert config.min_chars == 20  # default


class TestBlockCoalescer:
    def test_small_chunk_buffered(self) -> None:
        coal = BlockCoalescer(StreamingConfig(min_chars=20))
        blocks = coal.feed("Hi")
        assert blocks == []
        assert coal.buffer_size == 2

    def test_large_chunk_emitted(self) -> None:
        coal = BlockCoalescer(StreamingConfig(min_chars=5, max_chars=50, coalesce_ms=0))
        blocks = coal.feed("Hello world, this is a test message.")
        assert len(blocks) >= 1

    def test_paragraph_flush(self) -> None:
        coal = BlockCoalescer(StreamingConfig(min_chars=5, paragraph_flush=True, coalesce_ms=0))
        blocks = coal.feed("First paragraph.\n\nSecond paragraph.")
        assert len(blocks) >= 1

    def test_flush_remainder(self) -> None:
        coal = BlockCoalescer(StreamingConfig(min_chars=100))
        coal.feed("Hello")
        final = coal.flush()
        assert final is not None
        assert final.text == "Hello"
        assert final.is_final

    def test_flush_empty(self) -> None:
        coal = BlockCoalescer()
        assert coal.flush() is None

    def test_strip_directives(self) -> None:
        coal = BlockCoalescer(StreamingConfig(min_chars=5, strip_directives=True, coalesce_ms=0))
        blocks = coal.feed("Hello @think low world testing text")
        final = coal.flush()
        all_text = "".join(b.text for b in blocks)
        if final:
            all_text += final.text
        assert "@think" not in all_text
        assert "Hello" in all_text

    def test_reset(self) -> None:
        coal = BlockCoalescer()
        coal.feed("some text")
        coal.reset()
        assert coal.buffer_size == 0
        assert coal.total_chars == 0

    def test_max_chars_split(self) -> None:
        coal = BlockCoalescer(StreamingConfig(min_chars=5, max_chars=30, coalesce_ms=0))
        text = "a" * 100
        blocks = coal.feed(text)
        remaining = coal.flush()
        total_len = sum(len(b.text) for b in blocks)
        if remaining:
            total_len += len(remaining.text)
        assert total_len == 100


# ===== Target Resolver =====

class TestTargetResolver:
    def test_resolve_from_bindings(self) -> None:
        resolver = TargetResolver()
        ctx = TargetResolutionContext(
            session_id="s1",
            bindings=[{"channel_id": "telegram", "chat_id": "123"}],
        )
        result = resolver.resolve(ctx)
        assert result.has_targets
        assert result.primary is not None
        assert result.primary.channel_id == "telegram"

    def test_resolve_from_origin(self) -> None:
        resolver = TargetResolver()
        ctx = TargetResolutionContext(
            session_id="s1",
            channel_id="discord",
            sender_id="user-1",
        )
        result = resolver.resolve(ctx)
        assert result.has_targets
        assert result.primary.channel_id == "discord"

    def test_resolve_no_targets(self) -> None:
        resolver = TargetResolver()
        ctx = TargetResolutionContext(session_id="s1")
        result = resolver.resolve(ctx)
        assert not result.has_targets
        assert len(result.errors) > 0

    def test_select_channel_preferred(self) -> None:
        resolver = TargetResolver()
        targets = [
            DeliveryTarget(channel_id="telegram", chat_id="1"),
            DeliveryTarget(channel_id="discord", chat_id="2"),
        ]
        selected = resolver.select_channel(targets, preferred="discord")
        assert selected is not None
        assert selected.channel_id == "discord"

    def test_select_channel_first(self) -> None:
        resolver = TargetResolver()
        targets = [
            DeliveryTarget(channel_id="telegram", chat_id="1"),
        ]
        selected = resolver.select_channel(targets)
        assert selected is not None
        assert selected.channel_id == "telegram"


# ===== Send Service =====

class TestOutboundSendService:
    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        service = OutboundSendService()

        async def sender(ch: str, chat_id: str, env: MessageEnvelope) -> SendResult:
            return SendResult(success=True, message_id="m1")

        service.register_sender("telegram", sender)
        env = MessageEnvelope(conversation_id="c1", text="Hello")
        result = await service.send("telegram", "123", env)
        assert result.success
        assert service.send_count == 1

    @pytest.mark.asyncio
    async def test_send_no_sender(self) -> None:
        service = OutboundSendService()
        env = MessageEnvelope(conversation_id="c1", text="Hello")
        result = await service.send("unknown", "123", env)
        assert not result.success

    @pytest.mark.asyncio
    async def test_send_with_fallback(self) -> None:
        service = OutboundSendService()
        attempts: list[str] = []

        async def sender(ch: str, chat_id: str, env: MessageEnvelope) -> SendResult:
            attempts.append(env.format.value)
            if env.format == MessageFormat.MARKDOWN:
                return SendResult(success=False, error="Markdown not supported")
            return SendResult(success=True, message_id="m1")

        service.register_sender("slack", sender)
        env = MessageEnvelope(conversation_id="c1", text="Hello", format=MessageFormat.MARKDOWN)
        result = await service.send_with_fallback("slack", "ch1", env)
        assert result.success
        assert len(attempts) == 2

    def test_conversation_id(self) -> None:
        cid = generate_conversation_id("telegram", "123")
        assert cid == "telegram:123"


# ===== Message Actions =====

class TestMessageActions:
    @pytest.mark.asyncio
    async def test_execute_action(self) -> None:
        runner = MessageActionRunner()

        async def react(spec: ActionSpec) -> ActionResult:
            return ActionResult(success=True, action_type=spec.type, message_id=spec.message_id)

        runner.register_executor("telegram", ActionType.REACTION, react)
        spec = ActionSpec(type=ActionType.REACTION, message_id="m1", channel_id="telegram")
        result = await runner.execute(spec)
        assert result.success

    @pytest.mark.asyncio
    async def test_no_executor(self) -> None:
        runner = MessageActionRunner()
        spec = ActionSpec(type=ActionType.REACTION, message_id="m1", channel_id="unknown")
        result = await runner.execute(spec)
        assert not result.success

    @pytest.mark.asyncio
    async def test_queue_and_run(self) -> None:
        runner = MessageActionRunner()

        async def react(spec: ActionSpec) -> ActionResult:
            return ActionResult(success=True, action_type=spec.type, message_id=spec.message_id)

        runner.register_executor("ch1", ActionType.REACTION, react)
        runner.queue_action(ActionSpec(type=ActionType.REACTION, message_id="m1", channel_id="ch1"))
        runner.queue_action(ActionSpec(type=ActionType.REACTION, message_id="m2", channel_id="ch1"))
        results = await runner.run_pending()
        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_retry_on_failure(self) -> None:
        runner = MessageActionRunner()
        call_count = 0

        async def flaky(spec: ActionSpec) -> ActionResult:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("temporary error")
            return ActionResult(success=True, action_type=spec.type, message_id=spec.message_id)

        runner.register_executor("ch1", ActionType.PIN, flaky)
        spec = ActionSpec(type=ActionType.PIN, message_id="m1", channel_id="ch1", max_retries=2)
        result = await runner.execute(spec)
        assert result.success
        assert call_count == 2


# ===== Channel Adapters =====

class TestChannelAdapterRegistry:
    def test_list_channels(self) -> None:
        registry = ChannelAdapterRegistry()
        assert registry.list_channels() == []

    def test_get_nonexistent(self) -> None:
        registry = ChannelAdapterRegistry()
        assert registry.get("unknown") is None


# ===== HTML Export =====

class TestMarkdownToHtml:
    def test_bold(self) -> None:
        result = markdown_to_html("**bold**")
        assert "<strong>bold</strong>" in result

    def test_code(self) -> None:
        result = markdown_to_html("`code`")
        assert "<code>code</code>" in result

    def test_link(self) -> None:
        result = markdown_to_html("[click](https://x.com)")
        assert '<a href="https://x.com">' in result


class TestExportHtml:
    def test_basic_export(self) -> None:
        entries = [
            ExportEntry(role="user", content="Hello"),
            ExportEntry(role="assistant", content="Hi there!", model="gpt-4o"),
        ]
        html = export_session_html(entries)
        assert "<!DOCTYPE html>" in html
        assert "Hello" in html
        assert "Hi there!" in html
        assert "gpt-4o" in html

    def test_tool_entry(self) -> None:
        entries = [
            ExportEntry(
                role="tool",
                content="",
                tool_name="exec",
                tool_input='{"cmd": "ls"}',
                tool_output="file1.txt\nfile2.txt",
            ),
        ]
        html = export_session_html(entries)
        assert "exec" in html
        assert "file1.txt" in html

    def test_system_excluded(self) -> None:
        entries = [
            ExportEntry(role="system", content="System prompt"),
            ExportEntry(role="user", content="Hello"),
        ]
        html = export_session_html(entries, ExportOptions(include_system=False))
        assert "System prompt" not in html

    def test_dark_theme(self) -> None:
        entries = [ExportEntry(role="user", content="Hi")]
        html = export_session_html(entries, ExportOptions(theme="dark"))
        assert 'class="dark"' in html

    def test_empty_export(self) -> None:
        html = export_session_html([])
        assert "<!DOCTYPE html>" in html
