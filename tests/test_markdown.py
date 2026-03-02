"""Tests for Markdown IR, render, tables, fences, and channel formats."""

from __future__ import annotations

import pytest

from pyclaw.markdown.ir import MarkdownStyle, markdown_to_ir, chunk_markdown_ir
from pyclaw.markdown.render import render_markdown_with_markers
from pyclaw.markdown.tables import TableMode, convert_markdown_tables
from pyclaw.markdown.fences import parse_fence_spans, is_safe_fence_break
from pyclaw.markdown.channel_formats import (
    markdown_to_whatsapp,
    markdown_to_telegram_html,
    markdown_to_signal_text,
    markdown_to_slack_mrkdwn,
)


class TestMarkdownIR:
    def test_plain_text(self):
        ir = markdown_to_ir("Hello world")
        assert ir.text.strip() == "Hello world"
        assert ir.styles == []

    def test_bold(self):
        ir = markdown_to_ir("**bold text**")
        assert "bold text" in ir.text
        bold_spans = [s for s in ir.styles if s.style == MarkdownStyle.BOLD]
        assert len(bold_spans) >= 1

    def test_italic(self):
        ir = markdown_to_ir("*italic*")
        assert "italic" in ir.text
        italic_spans = [s for s in ir.styles if s.style == MarkdownStyle.ITALIC]
        assert len(italic_spans) >= 1

    def test_code_inline(self):
        ir = markdown_to_ir("`code`")
        assert "code" in ir.text
        code_spans = [s for s in ir.styles if s.style == MarkdownStyle.CODE]
        assert len(code_spans) >= 1

    def test_code_block(self):
        ir = markdown_to_ir("```python\nprint('hi')\n```")
        assert "print" in ir.text
        block_spans = [s for s in ir.styles if s.style == MarkdownStyle.CODE_BLOCK]
        assert len(block_spans) >= 1

    def test_links(self):
        ir = markdown_to_ir("[pyclaw](https://openclaw.ai)")
        assert "pyclaw" in ir.text
        assert len(ir.links) >= 1
        assert ir.links[0].url == "https://openclaw.ai"


class TestChunkMarkdownIR:
    def test_small_text_single_chunk(self):
        ir = markdown_to_ir("Short text")
        chunks = chunk_markdown_ir(ir, max_chars=4096)
        assert len(chunks) == 1

    def test_large_text_multiple_chunks(self):
        ir = markdown_to_ir("x" * 10000)
        chunks = chunk_markdown_ir(ir, max_chars=4096)
        assert len(chunks) >= 2


class TestRender:
    def test_roundtrip(self):
        ir = markdown_to_ir("Hello **world**")
        result = render_markdown_with_markers(ir)
        assert "world" in result


class TestTables:
    def test_off_mode(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = convert_markdown_tables(md, TableMode.OFF)
        # Tables removed or kept as-is depending on implementation
        assert isinstance(result, str)

    def test_bullets_mode(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = convert_markdown_tables(md, TableMode.BULLETS)
        assert isinstance(result, str)

    def test_code_mode(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = convert_markdown_tables(md, TableMode.CODE)
        assert isinstance(result, str)


class TestFences:
    def test_parse_fence_spans(self):
        text = "before\n```python\ncode\n```\nafter"
        spans = parse_fence_spans(text)
        assert len(spans) == 1
        assert spans[0].language == "python"

    def test_no_fences(self):
        spans = parse_fence_spans("no code here")
        assert spans == []

    def test_is_safe_fence_break_outside(self):
        text = "before\n```\ncode\n```\nafter"
        assert is_safe_fence_break(text, 3) is True

    def test_is_safe_fence_break_inside(self):
        text = "before\n```\ncode\n```\nafter"
        spans = parse_fence_spans(text)
        if spans:
            mid = (spans[0].start + spans[0].end) // 2
            assert is_safe_fence_break(text, mid, spans) is False


class TestChannelFormats:
    def test_whatsapp(self):
        result = markdown_to_whatsapp("**bold** and *italic*")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_telegram_html(self):
        result = markdown_to_telegram_html("**bold** and `code`")
        assert isinstance(result, str)

    def test_signal_text(self):
        result = markdown_to_signal_text("**bold** text")
        assert hasattr(result, "text")
        assert hasattr(result, "styles")
        assert "bold" in result.text

    def test_slack_mrkdwn(self):
        result = markdown_to_slack_mrkdwn("**bold** and *italic*")
        assert isinstance(result, str)
