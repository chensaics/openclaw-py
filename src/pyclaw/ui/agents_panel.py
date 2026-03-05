"""Agents management panel — list, create, and switch agents in Flet UI."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from pyclaw.config.defaults import DEFAULT_MODEL, DEFAULT_PROVIDER
from pyclaw.ui.components import card_tile, empty_state, page_header
from pyclaw.ui.i18n import t

logger = logging.getLogger(__name__)


def build_agents_panel(
    *,
    agents_dir: str | Path | None = None,
    on_select: Callable[[str], Coroutine[Any, Any, None]] | None = None,
    on_create: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None,
) -> Any:
    """Build a Flet panel for managing agents.

    Returns a ``ft.Column`` with agent list, create form, and details.
    """
    try:
        import flet as ft
    except ImportError:
        return None

    from pyclaw.config.paths import resolve_agents_dir

    effective_dir = Path(agents_dir) if agents_dir else resolve_agents_dir()

    agent_list = ft.ListView(expand=True, spacing=4, padding=8)
    selected_agent_id: list[str] = [""]

    detail_column = ft.Column(expand=True, spacing=8)
    name_field = ft.TextField(label=t("agents.name", default="Agent Name"), dense=True)
    model_field = ft.TextField(label=t("agents.model", default="Model"), dense=True, value=DEFAULT_MODEL)
    provider_field = ft.TextField(label=t("agents.provider", default="Provider"), dense=True, value=DEFAULT_PROVIDER)
    system_prompt_field = ft.TextField(
        label=t("agents.system_prompt", default="System Prompt"),
        multiline=True,
        min_lines=3,
        max_lines=8,
        dense=True,
    )
    status_text = ft.Text("", size=12)

    def _scan_agents() -> list[dict[str, str]]:
        agents: list[dict[str, str]] = []
        if not effective_dir.is_dir():
            return agents
        for child in sorted(effective_dir.iterdir()):
            if child.is_dir():
                config_file = child / "agent.json"
                agent_md = child / "AGENTS.md"
                name = child.name
                if config_file.exists() or agent_md.exists():
                    agents.append({"id": child.name, "name": name, "path": str(child)})
        return agents

    def _refresh_list(*, _mounted: bool = True) -> None:
        agents = _scan_agents()
        agent_list.controls.clear()
        for agent in agents:
            is_selected = agent["id"] == selected_agent_id[0]
            tile = card_tile(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.SMART_TOY if is_selected else ft.Icons.SMART_TOY_OUTLINED),
                        ft.Column(
                            [
                                ft.Text(agent["name"], weight=ft.FontWeight.BOLD if is_selected else None),
                                ft.Text(agent["path"], size=11),
                            ],
                            spacing=2,
                            expand=True,
                            tight=True,
                        ),
                    ],
                    spacing=8,
                ),
                on_click=lambda e, aid=agent["id"]: _select_agent(e, aid),
                data=agent["id"],
            )
            agent_list.controls.append(tile)

        if not agents:
            agent_list.controls.append(empty_state(ft.Icons.SMART_TOY_OUTLINED, "暂无 Agent 配置"))
        if _mounted:
            agent_list.update()

    def _select_agent(e: Any, agent_id: str) -> None:
        selected_agent_id[0] = agent_id
        _refresh_list()
        _show_agent_detail(agent_id)
        if on_select:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(on_select(agent_id))
            except RuntimeError:
                pass

    def _show_agent_detail(agent_id: str) -> None:
        agent_path = effective_dir / agent_id
        config_file = agent_path / "agent.json"
        detail_column.controls.clear()

        detail_column.controls.append(ft.Text(agent_id, size=18, weight=ft.FontWeight.BOLD))
        detail_column.controls.append(ft.Text(str(agent_path), size=11))

        if config_file.exists():
            import json

            try:
                cfg = json.loads(config_file.read_text(encoding="utf-8"))
                detail_column.controls.append(
                    ft.Text(
                        f"Model: {cfg.get('model', 'N/A')} | Provider: {cfg.get('provider', 'N/A')}",
                        size=13,
                    )
                )
                if cfg.get("systemPrompt"):
                    detail_column.controls.append(
                        ft.Container(
                            content=ft.Text(cfg["systemPrompt"][:200], size=12),
                            bgcolor=ft.Colors.SURFACE_CONTAINER,
                            border_radius=6,
                            padding=8,
                        )
                    )
            except (json.JSONDecodeError, OSError):
                pass

        agent_md = agent_path / "AGENTS.md"
        if agent_md.exists():
            try:
                md_text = agent_md.read_text(encoding="utf-8")[:500]
                detail_column.controls.append(ft.Markdown(value=md_text, selectable=True))
            except OSError:
                pass

        detail_column.update()

    async def _handle_create(e: Any) -> None:
        name = name_field.value
        if not name:
            status_text.value = t("agents.name_required", default="Name is required")
            status_text.update()
            return

        import json

        agent_path = effective_dir / name.strip().lower().replace(" ", "-")
        agent_path.mkdir(parents=True, exist_ok=True)

        config = {
            "model": model_field.value or DEFAULT_MODEL,
            "provider": provider_field.value or DEFAULT_PROVIDER,
            "systemPrompt": system_prompt_field.value or "",
        }
        (agent_path / "agent.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

        status_text.value = t("agents.created", default=f"Agent '{name}' created", name=name)
        status_text.update()
        name_field.value = ""
        name_field.update()

        _refresh_list()

        if on_create:
            await on_create({"id": agent_path.name, "path": str(agent_path), **config})

    create_btn = ft.Button(
        t("agents.create", default="Create Agent"),
        icon=ft.Icons.ADD,
        on_click=_handle_create,
    )

    refresh_btn = ft.IconButton(icon=ft.Icons.REFRESH, tooltip="Refresh", on_click=lambda e: _refresh_list())

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.SMART_TOY,
                t("agents.title", default="Agents"),
                actions=[refresh_btn],
            ),
            ft.Divider(height=1),
            ft.Row(
                controls=[
                    ft.Container(content=agent_list, width=260, expand=False),
                    ft.VerticalDivider(width=1),
                    ft.Container(content=detail_column, expand=True, padding=12),
                ],
                expand=True,
            ),
            ft.Divider(height=1),
            ft.ExpansionTile(
                title=ft.Text(t("agents.new", default="New Agent"), size=14),
                controls=[
                    ft.Container(
                        content=ft.Column(
                            [
                                name_field,
                                model_field,
                                provider_field,
                                system_prompt_field,
                                create_btn,
                                status_text,
                            ],
                            spacing=8,
                        ),
                        padding=12,
                    ),
                ],
            ),
        ],
        spacing=8,
        expand=True,
    )

    _refresh_list(_mounted=False)
    return panel
