"""Channel-specific markdown rendering.

Ported from the channel-specific formatters in ``src/markdown/``:
- ``whatsapp.ts``
- ``telegram/format.ts``
- ``signal/format.ts``
- ``slack/format.ts``
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pyclaw.markdown.ir import MarkdownIR, MarkdownStyle, StyleSpan, markdown_to_ir
from pyclaw.markdown.render import RenderOptions, StyleMarker, render_markdown_with_markers
from pyclaw.markdown.tables import TableMode, convert_markdown_tables


# ---------------------------------------------------------------------------
# WhatsApp
# ---------------------------------------------------------------------------

def markdown_to_whatsapp(text: str) -> str:
    """Convert standard markdown to WhatsApp formatting.

    WhatsApp uses: *bold*, _italic_, ~strikethrough~, ```code```, `inline code`.
    """
    # Protect code blocks
    blocks: list[tuple[str, str]] = []
    counter = 0

    def _protect_block(m: re.Match[str]) -> str:
        nonlocal counter
        ph = f"\x00WA{counter}\x00"
        blocks.append((ph, m.group(0)))
        counter += 1
        return ph

    result = re.sub(r"```[\s\S]*?```", _protect_block, text)

    # Protect inline code
    inlines: list[tuple[str, str]] = []

    def _protect_inline(m: re.Match[str]) -> str:
        nonlocal counter
        ph = f"\x00WI{counter}\x00"
        inlines.append((ph, m.group(0)))
        counter += 1
        return ph

    result = re.sub(r"`[^`\n]+?`", _protect_inline, result)

    # Bold: ** or __ → *
    result = re.sub(r"\*\*(.+?)\*\*", r"*\1*", result)
    result = re.sub(r"__(.+?)__", r"*\1*", result)
    # Strikethrough: ~~ → ~
    result = re.sub(r"~~(.+?)~~", r"~\1~", result)
    # Italic: single * → _ (but not inside bold)
    # (simplified — avoids edge cases in regex-only approach)

    # Restore
    for ph, orig in inlines:
        result = result.replace(ph, orig, 1)
    for ph, orig in blocks:
        result = result.replace(ph, orig, 1)

    return result


# ---------------------------------------------------------------------------
# Telegram HTML
# ---------------------------------------------------------------------------

_TELEGRAM_MARKERS = {
    MarkdownStyle.BOLD: StyleMarker("<b>", "</b>"),
    MarkdownStyle.ITALIC: StyleMarker("<i>", "</i>"),
    MarkdownStyle.STRIKETHROUGH: StyleMarker("<s>", "</s>"),
    MarkdownStyle.CODE: StyleMarker("<code>", "</code>"),
    MarkdownStyle.CODE_BLOCK: StyleMarker("<pre>", "</pre>"),
    MarkdownStyle.SPOILER: StyleMarker('<span class="tg-spoiler">', "</span>"),
    MarkdownStyle.BLOCKQUOTE: StyleMarker("<blockquote>", "</blockquote>"),
}


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_telegram_link(text: str, url: str, title: str) -> str:
    return f'<a href="{_escape_html(url)}">{_escape_html(text)}</a>'


def markdown_to_telegram_html(text: str) -> str:
    """Convert markdown to Telegram HTML."""
    ir = markdown_to_ir(text)
    return render_markdown_with_markers(ir, RenderOptions(
        style_markers=_TELEGRAM_MARKERS,
        escape_text=_escape_html,
        build_link=_build_telegram_link,
    ))


def markdown_to_telegram_chunks(text: str, max_chars: int = 4096) -> list[str]:
    from pyclaw.markdown.ir import chunk_markdown_ir

    ir = markdown_to_ir(text)
    chunks = chunk_markdown_ir(ir, max_chars)
    return [
        render_markdown_with_markers(chunk, RenderOptions(
            style_markers=_TELEGRAM_MARKERS,
            escape_text=_escape_html,
            build_link=_build_telegram_link,
        ))
        for chunk in chunks
    ]


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------

@dataclass
class SignalStyleRange:
    style: str  # "BOLD" | "ITALIC" | "STRIKETHROUGH" | "MONOSPACE" | "SPOILER"
    start: int
    length: int


@dataclass
class SignalFormattedText:
    text: str = ""
    styles: list[SignalStyleRange] = field(default_factory=list)


_SIGNAL_STYLE_MAP = {
    MarkdownStyle.BOLD: "BOLD",
    MarkdownStyle.ITALIC: "ITALIC",
    MarkdownStyle.STRIKETHROUGH: "STRIKETHROUGH",
    MarkdownStyle.CODE: "MONOSPACE",
    MarkdownStyle.CODE_BLOCK: "MONOSPACE",
    MarkdownStyle.SPOILER: "SPOILER",
}


def markdown_to_signal_text(text: str) -> SignalFormattedText:
    """Convert markdown to Signal's formatted text with style ranges."""
    ir = markdown_to_ir(text)

    # Strip markdown markers from text and map spans
    plain = ir.text
    # For simplicity, use the raw text (with markers) and map styles
    styles: list[SignalStyleRange] = []
    for s in ir.styles:
        signal_style = _SIGNAL_STYLE_MAP.get(s.style)
        if signal_style:
            styles.append(SignalStyleRange(
                style=signal_style,
                start=s.start,
                length=s.end - s.start,
            ))

    # Expand links as (url) in plain text
    result_text = plain
    for l in reversed(ir.links):
        link_text = plain[l.start:l.end]
        result_text = result_text[:l.start] + f"{link_text} ({l.url})" + result_text[l.end:]

    return SignalFormattedText(text=result_text, styles=styles)


# ---------------------------------------------------------------------------
# Slack mrkdwn
# ---------------------------------------------------------------------------

_SLACK_MARKERS = {
    MarkdownStyle.BOLD: StyleMarker("*", "*"),
    MarkdownStyle.ITALIC: StyleMarker("_", "_"),
    MarkdownStyle.STRIKETHROUGH: StyleMarker("~", "~"),
    MarkdownStyle.CODE: StyleMarker("`", "`"),
    MarkdownStyle.CODE_BLOCK: StyleMarker("```", "```"),
}


def _build_slack_link(text: str, url: str, title: str) -> str:
    return f"<{url}|{text}>"


def markdown_to_slack_mrkdwn(text: str) -> str:
    """Convert standard markdown to Slack mrkdwn format."""
    ir = markdown_to_ir(text)
    return render_markdown_with_markers(ir, RenderOptions(
        style_markers=_SLACK_MARKERS,
        build_link=_build_slack_link,
    ))


def markdown_to_slack_mrkdwn_chunks(text: str, max_chars: int = 3000) -> list[str]:
    from pyclaw.markdown.ir import chunk_markdown_ir

    ir = markdown_to_ir(text)
    chunks = chunk_markdown_ir(ir, max_chars)
    return [
        render_markdown_with_markers(chunk, RenderOptions(
            style_markers=_SLACK_MARKERS,
            build_link=_build_slack_link,
        ))
        for chunk in chunks
    ]
