"""ANSI-safe table renderer with Unicode box-drawing."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal

from pyclaw.terminal.ansi import visible_width

BorderStyle = Literal["unicode", "ascii", "none"]


@dataclass
class TableColumn:
    key: str
    header: str
    align: Literal["left", "right", "center"] = "left"
    min_width: int = 4
    max_width: int = 60
    flex: bool = False


@dataclass
class _Resolved:
    col: TableColumn
    width: int = 0


def render_table(
    columns: list[TableColumn],
    rows: list[dict[str, str]],
    *,
    width: int | None = None,
    padding: int = 1,
    border: BorderStyle = "unicode",
) -> str:
    """Render *rows* into a formatted table string."""
    if not columns:
        return ""

    term_width = width or _terminal_width()

    # Phase 1: compute natural widths
    resolved: list[_Resolved] = []
    for col in columns:
        natural = visible_width(col.header)
        for row in rows:
            cell_w = visible_width(row.get(col.key, ""))
            natural = max(natural, cell_w)
        natural = max(natural, col.min_width)
        natural = min(natural, col.max_width)
        resolved.append(_Resolved(col=col, width=natural))

    # Phase 2: distribute remaining width to flex columns
    sep_w = len(resolved) + 1 if border != "none" else 0
    pad_w = padding * 2 * len(resolved)
    used = sum(r.width for r in resolved) + sep_w + pad_w

    if used < term_width:
        flex_cols = [r for r in resolved if r.col.flex]
        if flex_cols:
            extra = term_width - used
            per_col = extra // len(flex_cols)
            for r in flex_cols:
                r.width = min(r.width + per_col, r.col.max_width)

    # Phase 3: choose border characters
    if border == "unicode":
        h, v = "─", "│"
        tl, tr, bl, br = "┌", "┐", "└", "┘"
        tj, bj, lj, rj, cross = "┬", "┴", "├", "┤", "┼"
    elif border == "ascii":
        h, v = "-", "|"
        tl, tr, bl, br = "+", "+", "+", "+"
        tj, bj, lj, rj, cross = "+", "+", "+", "+", "+"
    else:
        h = v = tl = tr = bl = br = tj = bj = lj = rj = cross = ""

    pad = " " * padding

    def _hline(left: str, mid: str, right: str) -> str:
        segments = [h * (r.width + padding * 2) for r in resolved]
        return left + mid.join(segments) + right

    def _row_str(cells: list[str]) -> str:
        parts = []
        for cell_text, r in zip(cells, resolved):
            aligned = _align(cell_text, r.width, r.col.align)
            parts.append(f"{pad}{aligned}{pad}")
        if border != "none":
            return v + v.join(parts) + v
        return "  ".join(parts)

    lines: list[str] = []

    # Top border
    if border != "none":
        lines.append(_hline(tl, tj, tr))

    # Header
    headers = [_truncate(col.header, r.width) for col, r in zip(columns, resolved)]
    lines.append(_row_str(headers))

    # Header separator
    if border != "none":
        lines.append(_hline(lj, cross, rj))

    # Data rows
    for row in rows:
        cells = [_truncate(row.get(r.col.key, ""), r.width) for r in resolved]
        lines.append(_row_str(cells))

    # Bottom border
    if border != "none":
        lines.append(_hline(bl, bj, br))

    return "\n".join(lines)


def _align(text: str, width: int, align: str) -> str:
    vw = visible_width(text)
    if vw >= width:
        return text
    gap = width - vw
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def _truncate(text: str, width: int) -> str:
    if visible_width(text) <= width:
        return text
    result: list[str] = []
    w = 0
    for ch in text:
        cw = 2 if _is_wide(ch) else 1
        if w + cw > width - 1:
            break
        result.append(ch)
        w += cw
    return "".join(result) + "…"


def _is_wide(ch: str) -> bool:
    import unicodedata
    return unicodedata.east_asian_width(ch) in ("W", "F")


def _terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except (ValueError, OSError):
        return 80
