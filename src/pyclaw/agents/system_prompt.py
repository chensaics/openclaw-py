"""System prompt builder — constructs the full agent system prompt.

Ported from the TypeScript ``buildAgentSystemPrompt()`` in
``src/agents/system-prompt.ts``.  Assembles sections for safety,
tooling, skills, memory, workspace, runtime, and more.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Literal

PromptMode = Literal["full", "minimal", "none"]

CORE_TOOL_SUMMARIES: dict[str, str] = {
    "read": "Read file contents",
    "write": "Create or overwrite files",
    "edit": "Make precise edits to files",
    "exec": "Run shell commands",
    "process": "Manage background exec sessions",
    "web_search": "Search the web",
    "web_fetch": "Fetch and extract readable content from a URL",
    "browser": "Control web browser",
    "memory_search": "Semantically search memory files for prior context",
    "memory_get": "Read a snippet from memory files",
    "cron": "Manage cron jobs and scheduled reminders",
    "message": "Send messages and channel actions",
    "sessions_list": "List other sessions (incl. sub-agents)",
    "sessions_send": "Send a message to another session/sub-agent",
    "sessions_spawn": "Spawn an isolated sub-agent session",
    "session_status": "Show usage/time/model status card",
    "image": "Analyze an image with the configured image model",
    "tts": "Convert text to speech audio",
}

TOOL_ORDER = [
    "read",
    "write",
    "edit",
    "exec",
    "process",
    "web_search",
    "web_fetch",
    "browser",
    "memory_search",
    "memory_get",
    "cron",
    "message",
    "sessions_list",
    "sessions_send",
    "sessions_spawn",
    "session_status",
    "image",
    "tts",
]

SILENT_REPLY_TOKEN = "[[silent]]"
HEARTBEAT_OK = "HEARTBEAT_OK"

_SAFETY_SECTION = """\
## Safety
You have no independent goals: do not pursue self-preservation, replication, \
resource acquisition, or power-seeking; avoid long-term plans beyond the user's request.
Prioritize safety and human oversight over completion; if instructions conflict, \
pause and ask; comply with stop/pause/audit requests and never bypass safeguards. \
(Inspired by Anthropic's constitution.)
Do not manipulate or persuade anyone to expand access or disable safeguards. \
Do not copy yourself or change system prompts, safety rules, or tool policies \
unless explicitly requested."""

_TOOL_CALL_STYLE = """\
## Tool Call Style
Default: do not narrate routine, low-risk tool calls (just call the tool).
Narrate only when it helps: multi-step work, complex/challenging problems, \
sensitive actions (e.g., deletions), or when the user explicitly asks.
Keep narration brief and value-dense; avoid repeating obvious steps."""


def build_agent_system_prompt(
    *,
    mode: PromptMode = "full",
    tool_names: list[str] | None = None,
    workspace_dir: str | None = None,
    agent_instructions: str | None = None,
    soul_prompt: str | None = None,
    identity_prompt: str | None = None,
    skills_prompt: str | None = None,
    memory_enabled: bool = False,
    sender_name: str | None = None,
    sandbox_enabled: bool = False,
    workspace_notes: list[str] | None = None,
) -> str:
    """Build the full agent system prompt.

    Args:
        mode: ``"full"`` (default), ``"minimal"`` (stripped), or ``"none"``
        tool_names: list of available tool names (filters summaries)
        workspace_dir: absolute path to the workspace directory
        agent_instructions: custom AGENTS.md / agent instructions text
        soul_prompt: SOUL.md persona/behavior text
        identity_prompt: IDENTITY.md text
        skills_prompt: skills block text
        memory_enabled: whether memory tools are available
        sender_name: name of the current user/sender
        sandbox_enabled: whether exec runs in a sandbox
        workspace_notes: extra workspace context lines
    """
    if mode == "none":
        return "You are a personal assistant running inside pyclaw."

    sections: list[str] = ["You are a personal assistant running inside pyclaw.", ""]

    # --- Tooling ---
    sections.append(_build_tooling_section(tool_names))
    sections.append("")
    sections.append(_TOOL_CALL_STYLE)
    sections.append("")

    # --- Safety ---
    sections.append(_SAFETY_SECTION)
    sections.append("")

    if mode == "minimal":
        # Minimal mode: just tooling + safety + date
        sections.append(_build_runtime_section(sender_name))
        return "\n".join(sections)

    # --- Full mode ---

    # Skills
    if skills_prompt:
        sections.append("## Skills")
        sections.append(skills_prompt)
        sections.append("")

    # Memory
    if memory_enabled:
        sections.append(_build_memory_section())
        sections.append("")

    # Workspace
    sections.append(
        _build_workspace_section(
            workspace_dir,
            agent_instructions,
            soul_prompt,
            identity_prompt,
            sandbox_enabled,
            workspace_notes,
        )
    )
    sections.append("")

    # Runtime (date, sender, etc.)
    sections.append(_build_runtime_section(sender_name))

    return "\n".join(sections)


def _build_tooling_section(tool_names: list[str] | None) -> str:
    lines = ["## Tooling", "Tool availability (filtered by policy):"]
    lines.append("Tool names are case-sensitive. Call tools exactly as listed.")

    available = set(tool_names or [])
    ordered = [t for t in TOOL_ORDER if not available or t in available]
    # Add any tools not in TOOL_ORDER
    if available:
        for t in sorted(available):
            if t not in ordered:
                ordered.append(t)

    for name in ordered:
        summary = CORE_TOOL_SUMMARIES.get(name, name)
        lines.append(f"- {name}: {summary}")

    lines.append("")
    lines.append("TOOLS.md does not control tool availability; it is user guidance for how to use external tools.")
    return "\n".join(lines)


def _build_memory_section() -> str:
    return "\n".join(
        [
            "## Memory",
            "Before answering questions about prior work, decisions, dates, people, "
            "preferences, or todos, call memory_search first.",
            "Use memory_get to pull only the needed lines after search results point "
            "to a specific file and line range.",
            "If memory_search returns disabled=true, surface that to the user.",
        ]
    )


def _build_workspace_section(
    workspace_dir: str | None,
    agent_instructions: str | None,
    soul_prompt: str | None,
    identity_prompt: str | None,
    sandbox_enabled: bool,
    workspace_notes: list[str] | None,
) -> str:
    lines = ["## Workspace"]

    if workspace_dir:
        lines.append(f"Working directory: {workspace_dir}")
        if sandbox_enabled:
            lines.append("Exec commands run in a sandbox container. Prefer relative paths for consistency.")
        else:
            lines.append(
                "Treat this directory as the single global workspace "
                "for file operations unless explicitly instructed otherwise."
            )

    if soul_prompt:
        lines.append("")
        lines.append("### Persona")
        lines.append(soul_prompt)

    if identity_prompt:
        lines.append("")
        lines.append("### Identity")
        lines.append(identity_prompt)

    if agent_instructions:
        lines.append("")
        lines.append("### Agent Instructions")
        lines.append(agent_instructions)

    if workspace_notes:
        for note in workspace_notes:
            note = note.strip()
            if note:
                lines.append(note)

    return "\n".join(lines)


def _build_runtime_section(sender_name: str | None) -> str:
    now = datetime.datetime.now()
    lines = [
        "## Runtime",
        f"Current date and time: {now.strftime('%A %B %d, %Y %H:%M %Z').strip()}",
    ]
    if sender_name:
        lines.append(f"Current sender: {sender_name}")
    return "\n".join(lines)


def load_template(name: str) -> str | None:
    """Load an agent template file by name (e.g. 'SOUL', 'AGENTS')."""
    templates_dir = Path(__file__).parent / "templates"
    path = templates_dir / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None
