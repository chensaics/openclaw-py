"""Fenced code block detection and safe-break analysis.

Ported from ``src/markdown/fences.ts``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})(\w*)$", re.MULTILINE)


@dataclass
class FenceSpan:
    start: int
    end: int
    language: str = ""


def parse_fence_spans(text: str) -> list[FenceSpan]:
    """Find all fenced code block spans in *text*."""
    spans: list[FenceSpan] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = _FENCE_OPEN_RE.match(lines[i])
        if m:
            fence_char = m.group(1)[0]
            fence_len = len(m.group(1))
            lang = m.group(2)
            start_line = i
            start_offset = sum(len(lines[j]) + 1 for j in range(i))
            i += 1
            while i < len(lines):
                close_match = re.match(rf"^{re.escape(fence_char)}{{{fence_len},}}$", lines[i])
                if close_match:
                    end_offset = sum(len(lines[j]) + 1 for j in range(i + 1))
                    spans.append(FenceSpan(start=start_offset, end=end_offset, language=lang))
                    i += 1
                    break
                i += 1
            else:
                # Unclosed fence — span to end
                spans.append(FenceSpan(start=start_offset, end=len(text), language=lang))
        else:
            i += 1
    return spans


def find_fence_span_at(spans: list[FenceSpan], position: int) -> FenceSpan | None:
    """Return the fence span containing *position*, if any."""
    for span in spans:
        if span.start <= position < span.end:
            return span
    return None


def is_safe_fence_break(text: str, position: int, spans: list[FenceSpan] | None = None) -> bool:
    """Check whether breaking the text at *position* is safe (not inside a fence)."""
    if spans is None:
        spans = parse_fence_spans(text)
    return find_fence_span_at(spans, position) is None
