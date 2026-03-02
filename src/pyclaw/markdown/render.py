"""Markdown IR rendering with pluggable style markers.

Ported from ``src/markdown/render.ts``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pyclaw.markdown.ir import LinkSpan, MarkdownIR, MarkdownStyle, StyleSpan


@dataclass
class StyleMarker:
    open: str
    close: str


@dataclass
class RenderOptions:
    style_markers: dict[MarkdownStyle, StyleMarker] = field(default_factory=dict)
    escape_text: Callable[[str], str] | None = None
    build_link: Callable[[str, str, str], str] | None = None


# Default markdown-style markers
DEFAULT_MARKERS: dict[MarkdownStyle, StyleMarker] = {
    MarkdownStyle.BOLD: StyleMarker("**", "**"),
    MarkdownStyle.ITALIC: StyleMarker("*", "*"),
    MarkdownStyle.STRIKETHROUGH: StyleMarker("~~", "~~"),
    MarkdownStyle.CODE: StyleMarker("`", "`"),
    MarkdownStyle.CODE_BLOCK: StyleMarker("```", "```"),
    MarkdownStyle.SPOILER: StyleMarker("||", "||"),
    MarkdownStyle.BLOCKQUOTE: StyleMarker("> ", ""),
}


def render_markdown_with_markers(
    ir: MarkdownIR,
    options: RenderOptions | None = None,
) -> str:
    """Render an IR back to text with custom open/close markers."""
    opts = options or RenderOptions()
    markers = opts.style_markers or DEFAULT_MARKERS

    # Build boundary events
    events: list[tuple[int, str, str]] = []  # (position, "open"/"close", marker_text)

    for s in ir.styles:
        marker = markers.get(s.style)
        if not marker:
            continue
        events.append((s.start, "open", marker.open))
        events.append((s.end, "close", marker.close))

    for l in ir.links:
        if opts.build_link:
            link_text = ir.text[l.start:l.end]
            rendered = opts.build_link(link_text, l.url, l.title)
            events.append((l.start, "link_open", rendered))
            events.append((l.end, "link_close", ""))

    # Sort: position, then closes before opens at same position
    events.sort(key=lambda e: (e[0], 0 if e[1].startswith("close") or e[1] == "link_close" else 1))

    result: list[str] = []
    last_pos = 0

    for pos, kind, text_marker in events:
        if pos > last_pos:
            segment = ir.text[last_pos:pos]
            if opts.escape_text:
                segment = opts.escape_text(segment)
            result.append(segment)
        if kind == "link_open":
            result.append(text_marker)
        elif kind != "link_close":
            result.append(text_marker)
        last_pos = pos

    if last_pos < len(ir.text):
        segment = ir.text[last_pos:]
        if opts.escape_text:
            segment = opts.escape_text(segment)
        result.append(segment)

    return "".join(result)
