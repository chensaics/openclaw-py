"""Agents management panel — list, create, and switch agents in Flet UI."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from pyclaw.config.defaults import DEFAULT_MODEL, DEFAULT_PROVIDER
from pyclaw.ui.components import card_tile, empty_state, page_header, status_chip
from pyclaw.ui.i18n import t

logger = logging.getLogger(__name__)


def build_agents_panel(
    *,
    agents_dir: str | Path | None = None,
    gateway_client: Any = None,
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

    def _safe_update(control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass

    def _show_file_content(agent_id: str, file_path: Path) -> None:
        detail_column.controls.clear()
        back_btn = ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            tooltip="Back",
            on_click=lambda e: _show_agent_detail_sync(agent_id),
        )
        content_area = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
        if file_path.exists():
            try:
                raw = file_path.read_text(encoding="utf-8")
                if file_path.suffix.lower() in (".md", ".markdown"):
                    content_area.controls.append(ft.Markdown(value=raw, selectable=True))
                else:
                    content_area.controls.append(ft.Text(raw, selectable=True))
            except (OSError, UnicodeDecodeError):
                content_area.controls.append(ft.Text(f"Cannot read: {file_path.name}", color=ft.Colors.ERROR))
        else:
            content_area.controls.append(ft.Text("File not found", color=ft.Colors.ERROR))
        detail_column.controls.append(ft.Row([back_btn, ft.Text(file_path.name, size=16, weight=ft.FontWeight.BOLD)]))
        detail_column.controls.append(content_area)
        _safe_update(detail_column)

    def _build_overview_tab(cfg: dict[str, Any], agent_id: str, agent_path: Path) -> ft.Control:
        col = ft.Column(spacing=8)
        col.controls.append(ft.Text(agent_id, size=18, weight=ft.FontWeight.BOLD))
        col.controls.append(ft.Text(str(agent_path), size=11))
        col.controls.append(
            ft.Text(
                f"Model: {cfg.get('model', 'N/A')} | Provider: {cfg.get('provider', 'N/A')}",
                size=13,
            )
        )
        if cfg.get("systemPrompt"):
            col.controls.append(
                ft.Container(
                    content=ft.Text(cfg["systemPrompt"][:500], size=12),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=6,
                    padding=8,
                )
            )
        agent_md = agent_path / "AGENTS.md"
        if agent_md.exists():
            try:
                md_text = agent_md.read_text(encoding="utf-8")[:500]
                col.controls.append(ft.Markdown(value=md_text, selectable=True))
            except OSError:
                pass
        return ft.Container(content=ft.ListView(controls=col.controls, expand=True), expand=True)

    def _build_files_tab(agent_path: Path) -> ft.Control:
        lv = ft.ListView(expand=True, spacing=4)
        if not agent_path.is_dir():
            lv.controls.append(ft.Text("Agent directory not found"))
            return ft.Container(content=lv, expand=True)
        try:
            children = sorted(agent_path.iterdir())
        except OSError:
            lv.controls.append(ft.Text("Cannot list files"))
            return ft.Container(content=lv, expand=True)
        for p in children:
            try:
                st = p.stat() if p.exists() else None
                size_str = f"{st.st_size} B" if st and p.is_file() else "-"
                mtime_str = f"{st.st_mtime:.0f}" if st else "-"
                if st:
                    from datetime import datetime

                    mtime_str = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                size_str = "-"
                mtime_str = "-"
            tile = card_tile(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.INSERT_DRIVE_FILE if p.is_file() else ft.Icons.FOLDER),
                        ft.Column(
                            [
                                ft.Text(p.name, weight=ft.FontWeight.W_500),
                                ft.Text(f"{size_str} · {mtime_str}", size=11),
                            ],
                            spacing=2,
                            expand=True,
                            tight=True,
                        ),
                    ],
                    spacing=8,
                ),
                on_click=lambda e, fp=p: _show_file_content(selected_agent_id[0], fp) if fp.is_file() else None,
            )
            lv.controls.append(tile)
        if not lv.controls:
            lv.controls.append(ft.Text("No files"))
        return ft.Container(content=lv, expand=True)

    def _build_tools_tab(tools: list[str]) -> ft.Control:
        col = ft.Column(spacing=4)
        for tname in tools:
            col.controls.append(card_tile(content=ft.Row([ft.Icon(ft.Icons.BUILD), ft.Text(tname)], spacing=8)))
        if not col.controls:
            col.controls.append(ft.Text("No tools configured"))
        return ft.Container(content=ft.ListView(controls=col.controls, expand=True), expand=True)

    def _build_skills_tab(skills: list[dict[str, Any]]) -> ft.Control:
        col = ft.Column(spacing=4)
        for s in skills:
            name = s.get("id") or s.get("name") or "?"
            enabled = s.get("enabled", True)
            chip = status_chip("enabled" if enabled else "disabled", ft.Colors.GREEN if enabled else ft.Colors.GREY_400)
            col.controls.append(
                card_tile(
                    content=ft.Row(
                        [ft.Icon(ft.Icons.AUTO_AWESOME), ft.Text(name, expand=True), chip],
                        spacing=8,
                    )
                )
            )
        if not col.controls:
            col.controls.append(ft.Text("No skills configured"))
        return ft.Container(content=ft.ListView(controls=col.controls, expand=True), expand=True)

    def _build_channels_tab(channels: list[Any]) -> ft.Control:
        col = ft.Column(spacing=4)
        for ch in channels:
            name = ch if isinstance(ch, str) else ch.get("id") or ch.get("name") or str(ch)
            col.controls.append(card_tile(content=ft.Row([ft.Icon(ft.Icons.LINK), ft.Text(name)], spacing=8)))
        if not col.controls:
            col.controls.append(ft.Text("No channels configured"))
        return ft.Container(content=ft.ListView(controls=col.controls, expand=True), expand=True)

    def _build_cron_tab(cron_items: list[Any]) -> ft.Control:
        col = ft.Column(spacing=4)
        for c in cron_items:
            label = c if isinstance(c, str) else c.get("id") or c.get("schedule") or str(c)
            col.controls.append(card_tile(content=ft.Row([ft.Icon(ft.Icons.SCHEDULE), ft.Text(label)], spacing=8)))
        if not col.controls:
            col.controls.append(ft.Text("No cron tasks configured"))
        return ft.Container(content=ft.ListView(controls=col.controls, expand=True), expand=True)

    def _select_agent(e: Any, agent_id: str) -> None:
        selected_agent_id[0] = agent_id
        _refresh_list()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_show_agent_detail_async(agent_id))
        except RuntimeError:
            _show_agent_detail_sync(agent_id)
        if on_select:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(on_select(agent_id))
            except RuntimeError:
                pass

    def _show_agent_detail_sync(agent_id: str) -> None:
        agent_path = effective_dir / agent_id
        config_file = agent_path / "agent.json"
        cfg: dict[str, Any] = {}
        if config_file.exists():
            try:
                cfg = json.loads(config_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        _build_detail_tabs(agent_id, cfg, [])

    async def _show_agent_detail_async(agent_id: str) -> None:
        agent_path = effective_dir / agent_id
        config_file = agent_path / "agent.json"
        cfg: dict[str, Any] = {}
        if config_file.exists():
            try:
                cfg = json.loads(config_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        gw_tools: list[str] = []
        if gateway_client and gateway_client.connected:
            try:
                res = await gateway_client.call("agents.tools", {"agentId": agent_id}, timeout=5.0)
                tools = res.get("tools") or res.get("names") or []
                gw_tools = [x if isinstance(x, str) else x.get("name", str(x)) for x in tools]
            except Exception:
                pass

        _build_detail_tabs(agent_id, cfg, gw_tools)

    def _build_detail_tabs(agent_id: str, cfg: dict[str, Any], gw_tools: list[str]) -> None:
        agent_path = effective_dir / agent_id
        tools = gw_tools or cfg.get("tools") or []
        if isinstance(tools, dict):
            tools = list(tools.keys()) if tools else []
        tools = [str(t) for t in tools]

        skills = cfg.get("skills") or []
        if isinstance(skills, dict):
            skills = [{"id": k, "enabled": v} if isinstance(v, bool) else {"id": k, **v} for k, v in skills.items()]
        elif not isinstance(skills, list):
            skills = []

        channels = cfg.get("channels") or []
        if isinstance(channels, dict):
            channels = list(channels.keys())
        channels = [str(c) if not isinstance(c, dict) else c for c in channels]

        cron_items = cfg.get("cron") or []
        if isinstance(cron_items, dict):
            cron_items = list(cron_items.values()) if cron_items else []
        elif not isinstance(cron_items, list):
            cron_items = [cron_items] if cron_items else []

        overview = _build_overview_tab(cfg, agent_id, agent_path)
        files = _build_files_tab(agent_path)
        tools_tab = _build_tools_tab(tools)
        skills_tab = _build_skills_tab(skills)
        channels_tab = _build_channels_tab(channels)
        cron_tab = _build_cron_tab(cron_items)

        tabs = ft.Tabs(
            selected_index=0,
            expand=True,
            tabs=[
                ft.Tab(text="Overview", content=overview),
                ft.Tab(text="Files", content=files),
                ft.Tab(text="Tools", content=tools_tab),
                ft.Tab(text="Skills", content=skills_tab),
                ft.Tab(text="Channels", content=channels_tab),
                ft.Tab(text="Cron", content=cron_tab),
            ],
        )

        detail_column.controls.clear()
        detail_column.controls.append(tabs)
        _safe_update(detail_column)

    async def _handle_create(e: Any) -> None:
        name = name_field.value
        if not name:
            status_text.value = t("agents.name_required", default="Name is required")
            status_text.update()
            return

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
