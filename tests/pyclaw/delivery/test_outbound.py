"""Tests for outbound pipeline."""

from __future__ import annotations

import pytest

from pyclaw.channels.outbound import (
    MessageFormat,
    OutboundChunk,
    OutboundMessage,
    escape_html_entities,
    get_channel_max_size,
    markdown_to_html_simple,
    send_with_retry,
    split_message,
    strip_markdown,
)


class TestSplitMessage:
    def test_short_message(self) -> None:
        chunks = split_message("Hello", max_size=100)
        assert len(chunks) == 1
        assert chunks[0] == "Hello"

    def test_split_at_paragraph(self) -> None:
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = split_message(text, max_size=30)
        assert len(chunks) >= 2
        assert "Paragraph one." in chunks[0]

    def test_split_at_newline(self) -> None:
        text = "Line one\nLine two\nLine three\nLine four"
        chunks = split_message(text, max_size=20)
        assert len(chunks) >= 2

    def test_split_at_sentence(self) -> None:
        text = "First sentence. Second sentence. Third sentence."
        chunks = split_message(text, max_size=25)
        assert len(chunks) >= 2

    def test_hard_split(self) -> None:
        text = "a" * 100
        chunks = split_message(text, max_size=30)
        assert all(len(c) <= 30 for c in chunks)

    def test_empty_text(self) -> None:
        chunks = split_message("", max_size=100)
        assert len(chunks) == 1


class TestChannelMaxSize:
    def test_telegram(self) -> None:
        assert get_channel_max_size("telegram") == 4096

    def test_discord(self) -> None:
        assert get_channel_max_size("discord") == 2000

    def test_slack(self) -> None:
        assert get_channel_max_size("slack") == 40000

    def test_unknown(self) -> None:
        assert get_channel_max_size("unknown") == 4000


class TestMarkdownToHtml:
    def test_bold(self) -> None:
        assert "<b>bold</b>" in markdown_to_html_simple("**bold**")

    def test_italic(self) -> None:
        assert "<i>italic</i>" in markdown_to_html_simple("*italic*")

    def test_inline_code(self) -> None:
        result = markdown_to_html_simple("`code`")
        assert "<code>" in result

    def test_link(self) -> None:
        result = markdown_to_html_simple("[click](https://example.com)")
        assert '<a href="https://example.com">' in result

    def test_code_block(self) -> None:
        result = markdown_to_html_simple("```python\nprint('hi')\n```")
        assert "<pre>" in result
        assert "<code>" in result


class TestStripMarkdown:
    def test_bold(self) -> None:
        assert strip_markdown("**bold**") == "bold"

    def test_italic(self) -> None:
        assert strip_markdown("*italic*") == "italic"

    def test_link(self) -> None:
        assert strip_markdown("[text](url)") == "text"

    def test_code(self) -> None:
        assert strip_markdown("`code`") == "code"


class TestEscapeHtml:
    def test_angle_brackets(self) -> None:
        assert escape_html_entities("<div>") == "&lt;div&gt;"

    def test_ampersand(self) -> None:
        assert escape_html_entities("a & b") == "a &amp; b"


class TestSendWithRetry:
    @pytest.mark.asyncio
    async def test_successful_send(self) -> None:
        sent: list[str] = []

        async def send_fn(chunk: OutboundChunk) -> bool:
            sent.append(chunk.text)
            return True

        msg = OutboundMessage(text="Hello", chat_id="c1", channel_id="telegram")
        result = await send_with_retry(msg, send_fn)
        assert result is True
        assert len(sent) == 1

    @pytest.mark.asyncio
    async def test_fallback_to_plain(self) -> None:
        formats: list[MessageFormat] = []

        async def send_fn(chunk: OutboundChunk) -> bool:
            formats.append(chunk.format)
            return chunk.format == MessageFormat.PLAIN

        msg = OutboundMessage(text="**bold**", chat_id="c1", channel_id="test")
        result = await send_with_retry(msg, send_fn)
        assert result is True
        assert MessageFormat.PLAIN in formats

    @pytest.mark.asyncio
    async def test_chunked_send(self) -> None:
        sent: list[str] = []

        async def send_fn(chunk: OutboundChunk) -> bool:
            sent.append(chunk.text)
            return True

        msg = OutboundMessage(text="a" * 200, chat_id="c1", channel_id="test")
        result = await send_with_retry(msg, send_fn, max_size=50)
        assert result is True
        assert len(sent) >= 4
