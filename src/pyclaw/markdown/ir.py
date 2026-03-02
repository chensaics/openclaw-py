"""Markdown IR — intermediate representation for cross-channel rendering.

Ported from ``src/markdown/ir.ts``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MarkdownStyle(str, Enum):
    BOLD = "bold"
    ITALIC = "italic"
    STRIKETHROUGH = "strikethrough"
    CODE = "code"
    CODE_BLOCK = "code_block"
    SPOILER = "spoiler"
    BLOCKQUOTE = "blockquote"


@dataclass
class StyleSpan:
    style: MarkdownStyle
    start: int
    end: int
    language: str = ""  # for code blocks


@dataclass
class LinkSpan:
    start: int
    end: int
    url: str
    title: str = ""


@dataclass
class MarkdownIR:
    text: str = ""
    styles: list[StyleSpan] = field(default_factory=list)
    links: list[LinkSpan] = field(default_factory=list)


@dataclass
class MarkdownParseOptions:
    linkify: bool = True
    enable_spoilers: bool = True
    heading_style: str = "bold"  # "bold" | "plain"
    blockquote_prefix: str = "> "
    table_mode: str = "off"  # "off" | "bullets" | "code"


# Regex patterns for inline markdown
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__", re.DOTALL)
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")
_STRIKE_RE = re.compile(r"~~(.+?)~~")
_CODE_RE = re.compile(r"`([^`\n]+?)`")
_CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
_SPOILER_RE = re.compile(r"\|\|(.+?)\|\|")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^>\s?(.*)$", re.MULTILINE)


def markdown_to_ir(
    markdown: str,
    options: MarkdownParseOptions | None = None,
) -> MarkdownIR:
    """Parse markdown text into an intermediate representation."""
    opts = options or MarkdownParseOptions()
    ir = MarkdownIR()
    text = markdown

    # Extract code blocks first to protect them from further parsing
    code_blocks: list[tuple[str, str, str]] = []  # (placeholder, lang, content)
    counter = 0

    def _replace_code_block(m: re.Match[str]) -> str:
        nonlocal counter
        ph = f"\x00CB{counter}\x00"
        code_blocks.append((ph, m.group(1) or "", m.group(2)))
        counter += 1
        return ph

    text = _CODE_BLOCK_RE.sub(_replace_code_block, text)

    # Extract inline code
    inline_codes: list[tuple[str, str]] = []

    def _replace_inline_code(m: re.Match[str]) -> str:
        nonlocal counter
        ph = f"\x00IC{counter}\x00"
        inline_codes.append((ph, m.group(1)))
        counter += 1
        return ph

    text = _CODE_RE.sub(_replace_inline_code, text)

    # Headings → bold
    if opts.heading_style == "bold":
        text = _HEADING_RE.sub(lambda m: f"**{m.group(2)}**", text)

    # Blockquotes
    text = _BLOCKQUOTE_RE.sub(lambda m: f"{opts.blockquote_prefix}{m.group(1)}", text)

    # Build the final text and collect spans
    ir.text = text
    styles: list[StyleSpan] = []
    links: list[LinkSpan] = []

    # Bold
    for m in _BOLD_RE.finditer(text):
        content = m.group(1) or m.group(2)
        styles.append(StyleSpan(MarkdownStyle.BOLD, m.start(), m.end()))

    # Italic
    for m in _ITALIC_RE.finditer(text):
        styles.append(StyleSpan(MarkdownStyle.ITALIC, m.start(), m.end()))

    # Strikethrough
    for m in _STRIKE_RE.finditer(text):
        styles.append(StyleSpan(MarkdownStyle.STRIKETHROUGH, m.start(), m.end()))

    # Spoiler
    if opts.enable_spoilers:
        for m in _SPOILER_RE.finditer(text):
            styles.append(StyleSpan(MarkdownStyle.SPOILER, m.start(), m.end()))

    # Links
    for m in _LINK_RE.finditer(text):
        links.append(LinkSpan(m.start(), m.end(), url=m.group(2), title=m.group(1)))

    # Restore inline code
    for ph, content in inline_codes:
        idx = ir.text.find(ph)
        if idx >= 0:
            ir.text = ir.text.replace(ph, f"`{content}`", 1)
            styles.append(StyleSpan(MarkdownStyle.CODE, idx, idx + len(content) + 2))

    # Restore code blocks
    for ph, lang, content in code_blocks:
        idx = ir.text.find(ph)
        if idx >= 0:
            block_text = f"```{lang}\n{content}```"
            ir.text = ir.text.replace(ph, block_text, 1)
            styles.append(StyleSpan(
                MarkdownStyle.CODE_BLOCK, idx, idx + len(block_text), language=lang,
            ))

    ir.styles = sorted(styles, key=lambda s: s.start)
    ir.links = sorted(links, key=lambda l: l.start)
    return ir


def chunk_markdown_ir(ir: MarkdownIR, max_chars: int = 4096) -> list[MarkdownIR]:
    """Split an IR into chunks that fit within *max_chars*."""
    if len(ir.text) <= max_chars:
        return [ir]

    chunks: list[MarkdownIR] = []
    text = ir.text
    pos = 0

    while pos < len(text):
        end = min(pos + max_chars, len(text))
        # Try to break at newline
        if end < len(text):
            nl = text.rfind("\n", pos, end)
            if nl > pos:
                end = nl + 1

        chunk_text = text[pos:end]
        chunk_styles = [
            StyleSpan(s.style, s.start - pos, s.end - pos, s.language)
            for s in ir.styles
            if s.start < end and s.end > pos
        ]
        chunk_links = [
            LinkSpan(l.start - pos, l.end - pos, l.url, l.title)
            for l in ir.links
            if l.start < end and l.end > pos
        ]
        chunks.append(MarkdownIR(text=chunk_text, styles=chunk_styles, links=chunk_links))
        pos = end

    return chunks
