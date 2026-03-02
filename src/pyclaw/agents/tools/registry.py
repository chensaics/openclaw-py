"""Tool registry — collects and resolves available tools for an agent run."""

from __future__ import annotations

from typing import Any

from pyclaw.agents.types import AgentTool


class ToolRegistry:
    """Mutable collection of tools with lookup by name."""

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        self._tools[tool.name] = tool

    def register_all(self, tools: list[AgentTool]) -> None:
        for t in tools:
            self.register(t)

    def get(self, name: str) -> AgentTool | None:
        return self._tools.get(name)

    def all(self) -> list[AgentTool]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def create_default_tools(
    *,
    workspace_root: str | None = None,
    enable_exec: bool = True,
    enable_web: bool = True,
    enable_browser: bool = False,
    enable_memory: bool = False,
    enable_cron: bool = False,
    enable_tts: bool = False,
    enable_subagents: bool = False,
    memory_store: Any = None,
    scheduler: Any = None,
    agents_dir: Any = None,
    subagent_manager: Any = None,
    mcp_tools: list[Any] | None = None,
) -> ToolRegistry:
    """Create a registry pre-loaded with default built-in tools."""
    from pyclaw.agents.tools.exec_tool import ExecTool
    from pyclaw.agents.tools.file_tools import EditTool, ReadTool, WriteTool
    from pyclaw.agents.tools.process_tool import ProcessTool
    from pyclaw.agents.tools.session_tools import SessionsListTool, SessionsSendTool
    from pyclaw.agents.tools.web_tools import WebFetchTool, WebSearchTool

    registry = ToolRegistry()

    from pyclaw.agents.tools.fs_tools import FindTool, GrepTool, LsTool

    registry.register(ReadTool(workspace_root=workspace_root))
    registry.register(WriteTool(workspace_root=workspace_root))
    registry.register(EditTool(workspace_root=workspace_root))
    registry.register(GrepTool(workspace_root=workspace_root))
    registry.register(FindTool(workspace_root=workspace_root))
    registry.register(LsTool(workspace_root=workspace_root))

    if enable_exec:
        registry.register(ExecTool(workspace_root=workspace_root))
        registry.register(ProcessTool(workspace_root=workspace_root))

    if enable_web:
        registry.register(WebFetchTool())
        registry.register(WebSearchTool())

    if enable_browser:
        from pyclaw.agents.tools.browser_tool import BrowserTool

        registry.register(BrowserTool())

    if enable_memory and memory_store:
        from pyclaw.agents.tools.memory_tools import MemoryGetTool, MemorySearchTool

        registry.register(MemorySearchTool(memory_store=memory_store))
        registry.register(MemoryGetTool(memory_store=memory_store))

    if enable_cron and scheduler:
        from pyclaw.agents.tools.cron_tool import CronTool

        registry.register(CronTool(scheduler=scheduler))

    if enable_tts:
        from pyclaw.agents.tools.tts_tool import ImageTool, TtsTool

        registry.register(TtsTool())
        registry.register(ImageTool())

    # Patch tool always available
    from pyclaw.agents.tools.patch_tool import ApplyPatchTool

    registry.register(ApplyPatchTool(workspace_root=workspace_root))

    # Subagent tools
    if enable_subagents and subagent_manager:
        from pyclaw.agents.tools.subagent_tools import (
            AgentsListTool,
            SessionsSpawnTool,
            SessionStatusTool,
            SubagentsTool,
        )

        registry.register(AgentsListTool(agents_dir=agents_dir))
        registry.register(SessionsSpawnTool(subagent_manager=subagent_manager))
        registry.register(SubagentsTool(subagent_manager=subagent_manager))
        registry.register(SessionStatusTool())

    # Session tools are always available
    from pathlib import Path

    agents_path = Path(agents_dir) if agents_dir else None
    registry.register(SessionsListTool(agents_dir=agents_path))
    registry.register(SessionsSendTool())

    # MCP tools from external servers
    if mcp_tools:
        registry.register_all(mcp_tools)

    # Social platform tools (always available, gracefully degrade if no registry)
    from pyclaw.agents.tools.social_tools import SocialJoinTool, SocialStatusTool

    registry.register(SocialJoinTool())
    registry.register(SocialStatusTool())

    return registry
