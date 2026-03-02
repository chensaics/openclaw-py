"""Markdown processing — IR conversion and channel-specific rendering.

Ported from ``src/markdown/``.
"""

from pyclaw.markdown.ir import MarkdownIR, MarkdownStyle, chunk_markdown_ir, markdown_to_ir
from pyclaw.markdown.render import RenderOptions, render_markdown_with_markers
from pyclaw.markdown.tables import TableMode, convert_markdown_tables
from pyclaw.markdown.fences import find_fence_span_at, is_safe_fence_break, parse_fence_spans
from pyclaw.markdown.channel_formats import (
    markdown_to_signal_text,
    markdown_to_slack_mrkdwn,
    markdown_to_telegram_html,
    markdown_to_whatsapp,
)

__all__ = [
    "MarkdownIR",
    "MarkdownStyle",
    "RenderOptions",
    "TableMode",
    "chunk_markdown_ir",
    "convert_markdown_tables",
    "find_fence_span_at",
    "is_safe_fence_break",
    "markdown_to_ir",
    "markdown_to_signal_text",
    "markdown_to_slack_mrkdwn",
    "markdown_to_telegram_html",
    "markdown_to_whatsapp",
    "parse_fence_spans",
    "render_markdown_with_markers",
]
