"""HTML session export — Markdown to HTML rendering with tool calls.

Ported from ``src/auto-reply/reply/export-html/`` in the TypeScript codebase.

Provides:
- Session to HTML export
- Markdown to HTML conversion
- Tool call rendering
- CSS styling for exported sessions
"""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass


@dataclass
class ExportEntry:
    """A single conversation entry for export."""

    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: float = 0.0
    tool_name: str = ""
    tool_input: str = ""
    tool_output: str = ""
    model: str = ""


@dataclass
class ExportOptions:
    """Options for HTML export."""

    title: str = "pyclaw Session Export"
    include_system: bool = False
    include_tools: bool = True
    include_timestamps: bool = True
    theme: str = "light"  # "light" | "dark"


_EXPORT_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }
.entry { margin: 16px 0; padding: 12px 16px; border-radius: 8px; }
.user { background: #e3f2fd; border-left: 4px solid #1976d2; }
.assistant { background: #f5f5f5; border-left: 4px solid #616161; }
.system { background: #fff3e0; border-left: 4px solid #f57c00; font-size: 0.9em; }
.tool { background: #e8f5e9; border-left: 4px solid #388e3c; font-size: 0.9em; }
.role { font-weight: 600; font-size: 0.85em; text-transform: uppercase;
        color: #666; margin-bottom: 4px; }
.timestamp { font-size: 0.75em; color: #999; float: right; }
.model-tag { font-size: 0.75em; color: #888; margin-left: 8px; }
pre { background: #263238; color: #eee; padding: 12px; border-radius: 4px;
      overflow-x: auto; font-size: 0.9em; }
code { font-family: 'SF Mono', Monaco, monospace; }
.tool-name { font-weight: 600; color: #2e7d32; }
.tool-io { margin: 4px 0; }
.dark body { background: #1a1a1a; color: #e0e0e0; }
.dark .user { background: #1a237e33; border-color: #5c6bc0; }
.dark .assistant { background: #21212133; border-color: #9e9e9e; }
"""


def markdown_to_html(text: str) -> str:
    """Convert basic Markdown to HTML for export."""
    result = text

    # Code blocks
    result = re.sub(
        r"```(\w*)\n(.*?)```",
        lambda m: f'<pre><code class="lang-{m.group(1)}">{html.escape(m.group(2))}</code></pre>',
        result,
        flags=re.DOTALL,
    )

    # Inline code
    result = re.sub(r"`([^`]+)`", lambda m: f"<code>{html.escape(m.group(1))}</code>", result)

    # Bold
    result = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", result)
    # Italic
    result = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", result)
    # Links
    result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', result)
    # Line breaks
    result = result.replace("\n\n", "</p><p>")
    result = result.replace("\n", "<br>")
    result = f"<p>{result}</p>"

    return result


def _format_timestamp(ts: float) -> str:
    t = time.localtime(ts)
    return time.strftime("%Y-%m-%d %H:%M:%S", t)


def _render_entry(entry: ExportEntry, options: ExportOptions) -> str:
    if entry.role == "system" and not options.include_system:
        return ""
    if entry.role == "tool" and not options.include_tools:
        return ""

    parts: list[str] = []
    parts.append(f'<div class="entry {entry.role}">')

    # Header
    ts_html = ""
    if options.include_timestamps and entry.timestamp:
        ts_html = f'<span class="timestamp">{_format_timestamp(entry.timestamp)}</span>'

    model_html = ""
    if entry.model and entry.role == "assistant":
        model_html = f'<span class="model-tag">{html.escape(entry.model)}</span>'

    parts.append(f'<div class="role">{html.escape(entry.role)}{model_html}{ts_html}</div>')

    # Content
    if entry.role == "tool":
        parts.append(f'<div class="tool-name">{html.escape(entry.tool_name)}</div>')
        if entry.tool_input:
            parts.append(
                f'<div class="tool-io"><strong>Input:</strong><pre>{html.escape(entry.tool_input)}</pre></div>'
            )
        if entry.tool_output:
            parts.append(
                f'<div class="tool-io"><strong>Output:</strong><pre>{html.escape(entry.tool_output[:2000])}</pre></div>'
            )
    else:
        parts.append(f'<div class="content">{markdown_to_html(entry.content)}</div>')

    parts.append("</div>")
    return "\n".join(parts)


def export_session_html(
    entries: list[ExportEntry],
    options: ExportOptions | None = None,
) -> str:
    """Export a session as an HTML document."""
    opts = options or ExportOptions()
    theme_class = f' class="{opts.theme}"' if opts.theme == "dark" else ""

    parts: list[str] = [
        "<!DOCTYPE html>",
        f"<html{theme_class}>",
        "<head>",
        f"<title>{html.escape(opts.title)}</title>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<style>{_EXPORT_CSS}</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(opts.title)}</h1>",
        f'<p class="timestamp">Exported: {_format_timestamp(time.time())}</p>',
        "<hr>",
    ]

    for entry in entries:
        rendered = _render_entry(entry, opts)
        if rendered:
            parts.append(rendered)

    parts.extend(["</body>", "</html>"])
    return "\n".join(parts)
