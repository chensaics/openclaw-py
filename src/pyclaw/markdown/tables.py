"""Markdown table conversion — off / bullets / code modes.

Ported from ``src/markdown/tables.ts``.
"""

from __future__ import annotations

import re
from enum import Enum

_TABLE_LINE_RE = re.compile(r"^\|(.+)\|$")
_SEPARATOR_RE = re.compile(r"^\|[\s\-:|]+\|$")


class TableMode(str, Enum):
    OFF = "off"
    BULLETS = "bullets"
    CODE = "code"


def convert_markdown_tables(text: str, mode: TableMode = TableMode.OFF) -> str:
    """Convert markdown tables to an alternative format based on *mode*."""
    if mode == TableMode.OFF:
        return text

    lines = text.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        header_match = _TABLE_LINE_RE.match(lines[i].strip())
        if header_match and i + 1 < len(lines) and _SEPARATOR_RE.match(lines[i + 1].strip()):
            headers = [c.strip() for c in header_match.group(1).split("|")]
            i += 2  # skip header + separator

            rows: list[list[str]] = []
            while i < len(lines):
                row_match = _TABLE_LINE_RE.match(lines[i].strip())
                if not row_match:
                    break
                cells = [c.strip() for c in row_match.group(1).split("|")]
                rows.append(cells)
                i += 1

            if mode == TableMode.BULLETS:
                for row in rows:
                    for j, cell in enumerate(row):
                        h = headers[j] if j < len(headers) else f"col{j}"
                        result.append(f"- **{h}**: {cell}")
                    result.append("")
            elif mode == TableMode.CODE:
                # Render as aligned text block
                col_widths = [len(h) for h in headers]
                for row in rows:
                    for j, cell in enumerate(row):
                        if j < len(col_widths):
                            col_widths[j] = max(col_widths[j], len(cell))

                fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
                result.append("```")
                result.append(fmt.format(*headers[: len(col_widths)]))
                result.append("-" * sum(col_widths + [2 * (len(col_widths) - 1)]))
                for row in rows:
                    padded = row[: len(col_widths)]
                    while len(padded) < len(col_widths):
                        padded.append("")
                    result.append(fmt.format(*padded))
                result.append("```")
                result.append("")
        else:
            result.append(lines[i])
            i += 1

    return "\n".join(result)
