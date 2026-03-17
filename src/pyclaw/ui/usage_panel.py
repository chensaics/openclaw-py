"""Usage panel — token usage, session stats, and export."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import flet as ft

from pyclaw.ui.components import card_tile, empty_state_simple, error_state, page_header
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import get_theme

try:
    import flet_charts as fch
except ImportError:
    fch = None


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


_RANGES = [
    ("24h", 1),
    ("7d", 7),
    ("30d", 30),
    ("all", 365),
]


def build_usage_panel(*, gateway_client: Any = None) -> ft.Column:
    theme = get_theme()
    range_dropdown = ft.Dropdown(
        label=t("usage.range", default="Range"),
        value="7d",
        width=120,
        dense=True,
        options=[ft.dropdown.Option(r[0], r[0]) for r in _RANGES],
    )
    sort_dropdown = ft.Dropdown(
        label=t("usage.sort", default="Sort"),
        value="tokens",
        width=130,
        dense=True,
        options=[
            ft.dropdown.Option("tokens", t("usage.sort_tokens", default="Tokens desc")),
            ft.dropdown.Option("updated", t("usage.sort_updated", default="Updated desc")),
        ],
    )
    stats_row = ft.Row(spacing=12, wrap=True)
    charts_expansion = ft.ExpansionTile(
        title=ft.Text(t("usage.charts", default="Charts"), size=14, weight=ft.FontWeight.W_500),
        expanded=True,
        controls=[],
        visible=False,
    )
    session_list = ft.ListView(expand=True, spacing=6)
    summary_ref: dict[str, Any] = {}
    sessions_ref: list[dict[str, Any]] = []

    def _safe_update(control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass

    def _format_updated(path_str: str) -> str:
        try:
            p = Path(path_str)
            if p.exists():
                mtime = p.stat().st_mtime
                dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
                return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        return "-"

    def _range_to_days(r: str) -> int:
        for key, days in _RANGES:
            if key == r:
                return days
        return 7

    def _show_session_detail(page: ft.Page | None, s: dict[str, Any]) -> None:
        if not page:
            return
        path_str = s.get("path", s.get("sessionKey", ""))
        session_key = Path(path_str).name if path_str else s.get("session_id", "-")
        agent = s.get("agentId", s.get("agent", "-"))
        tokens = s.get("tokens", s.get("totalTokens", "-"))
        prompt_tok = s.get("inputTokens", s.get("input_tokens"))
        completion_tok = s.get("outputTokens", s.get("output_tokens"))
        token_breakdown = ""
        if prompt_tok is not None and completion_tok is not None:
            token_breakdown = f"Prompt: {prompt_tok} / Completion: {completion_tok}"
        else:
            token_breakdown = f"Total: {tokens}"
        msg_summary = ""
        for m in (s.get("messages") or [])[:3]:
            role = m.get("role", "")
            content = (m.get("content") or m.get("text") or "")[:80]
            msg_summary += f"{role}: {content}...\n" if len(str(content)) > 80 else f"{role}: {content}\n"
        if msg_summary:
            msg_summary = "Recent messages:\n" + msg_summary
        body = ft.Column(
            [
                ft.Text(f"Session: {session_key}", size=14, weight=ft.FontWeight.W_500),
                ft.Text(f"Agent: {agent}", size=12, color=theme.colors.muted),
                ft.Text(f"Token breakdown: {token_breakdown}", size=12, color=theme.colors.muted),
                ft.Text(msg_summary, size=11, color=theme.colors.muted) if msg_summary else ft.Container(),
            ],
            spacing=8,
        )

        def _close_dlg(e: ft.ControlEvent, p: ft.Page) -> None:
            dlg.open = False
            p.overlay.remove(dlg)
            p.update()

        dlg = ft.AlertDialog(
            title=ft.Text(t("usage.session_detail", default="Session detail")),
            content=body,
            actions=[ft.TextButton(t("usage.close", default="Close"), on_click=lambda e: _close_dlg(e, page))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    async def _refresh() -> None:
        session_list.controls.clear()
        stats_row.controls.clear()
        if not gateway_client or not gateway_client.connected:
            session_list.controls.append(
                error_state(
                    t("usage.offline", default="Connect to gateway to view usage."),
                    on_retry=_refresh,
                )
            )
            _safe_update(session_list)
            return

        try:
            range_val = range_dropdown.value or "7d"
            days = _range_to_days(range_val)
            sort_val = sort_dropdown.value or "tokens"

            try:
                summary_result = await gateway_client.call("usage.summary", {"range": range_val}, timeout=10.0)
            except Exception:
                summary_result = await gateway_client.call("usage.get", {"days": days}, timeout=10.0)
            summary_ref.clear()
            summary_ref.update(summary_result)
            total_tokens = summary_result.get("totalTokens", 0)
            total_sessions = summary_result.get("sessions", summary_result.get("windowDays", 0))
            est_cost = summary_result.get("estimatedCost", summary_result.get("estimatedCostValue", 0))
            if isinstance(est_cost, int | float):
                est_cost = (
                    f"${est_cost:.4f}"
                    if est_cost < 0.01
                    else f"${est_cost:.3f}"
                    if est_cost < 1
                    else f"${est_cost:.2f}"
                )

            stats_row.controls.extend(
                [
                    card_tile(
                        content=ft.Column(
                            [
                                ft.Text(
                                    t("usage.total_tokens", default="Total Tokens"), size=11, color=theme.colors.muted
                                ),
                                ft.Text(str(total_tokens), size=18, weight=ft.FontWeight.BOLD),
                            ],
                            spacing=4,
                        ),
                    ),
                    card_tile(
                        content=ft.Column(
                            [
                                ft.Text(
                                    t("usage.total_sessions", default="Sessions"), size=11, color=theme.colors.muted
                                ),
                                ft.Text(str(total_sessions), size=18, weight=ft.FontWeight.BOLD),
                            ],
                            spacing=4,
                        ),
                    ),
                    card_tile(
                        content=ft.Column(
                            [
                                ft.Text(
                                    t("usage.estimated_cost", default="Est. Cost"), size=11, color=theme.colors.muted
                                ),
                                ft.Text(str(est_cost), size=18, weight=ft.FontWeight.BOLD),
                            ],
                            spacing=4,
                        ),
                    ),
                ]
            )
            _safe_update(stats_row)

            daily_data: list[dict[str, Any]] = []
            hourly_data: list[int] = []
            try:
                daily_data = summary_ref.get("dailyBreakdown") or []
                if not daily_data:
                    daily_res = await gateway_client.call("usage.daily", {"range": range_val}, timeout=5.0)
                    daily_data = daily_res.get("dailyBreakdown", [])
            except Exception:
                pass
            try:
                hourly_data = summary_ref.get("hourlyDistribution") or []
                if not hourly_data:
                    hourly_res = await gateway_client.call("usage.hourly", {"range": range_val}, timeout=5.0)
                    hourly_data = hourly_res.get("hourlyDistribution", [])
            except Exception:
                pass

            chart_controls: list[ft.Control] = []
            if fch and daily_data:
                max_tokens = max((d.get("tokens", 0) or 0) for d in daily_data) or 1
                bar_groups = []
                for i, d in enumerate(daily_data):
                    tok = int(d.get("tokens", 0) or 0)
                    bar_groups.append(
                        fch.BarChartGroup(
                            x=i,
                            spacing=4,
                            rods=[
                                fch.BarChartRod(
                                    from_y=0,
                                    to_y=tok,
                                    color=theme.colors.primary,
                                    width=12,
                                    border_radius=0,
                                ),
                            ],
                        ),
                    )
                bar_chart = fch.BarChart(
                    groups=bar_groups,
                    group_spacing=8,
                    max_y=max_tokens * 1.1 or 100,
                    border=ft.Border.all(0.5, theme.colors.border),
                    interactive=True,
                    left_axis=fch.ChartAxis(labels_size=32, show_labels=True),
                    bottom_axis=fch.ChartAxis(
                        labels=[
                            fch.ChartAxisLabel(
                                value=i,
                                label=ft.Container(
                                    ft.Text(d.get("date", "")[-5:]),
                                    padding=4,
                                ),
                            )
                            for i, d in enumerate(daily_data)
                        ],
                    ),
                )
                chart_controls.append(
                    ft.Container(
                        content=bar_chart,
                        height=200,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                    ),
                )
            if hourly_data and len(hourly_data) >= 24:
                max_h = max(hourly_data) or 1
                hour_boxes = []
                for h in range(24):
                    v = hourly_data[h] or 0
                    opacity = (v / max_h) * 0.9 + 0.1 if max_h > 0 else 0.1
                    hour_boxes.append(
                        ft.Container(
                            width=20,
                            height=20,
                            bgcolor=ft.Colors.with_opacity(opacity, theme.colors.primary),
                            border_radius=2,
                            tooltip=f"{h}h: {v} tokens",
                        ),
                    )
                label_items = []
                for h in range(24):
                    if h in (0, 6, 12, 18):
                        label_items.append(
                            ft.Container(width=20, content=ft.Text(f"{h}h", size=10, color=theme.colors.muted))
                        )
                    else:
                        label_items.append(ft.Container(width=20))
                labels_row = ft.Row(label_items, spacing=2)
                chart_controls.append(
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Row(hour_boxes, spacing=2),
                                labels_row,
                            ],
                            spacing=4,
                        ),
                        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                    ),
                )
            if chart_controls:
                ctrls = charts_expansion.controls
                if ctrls is not None:
                    ctrls.clear()
                    ctrls.extend(chart_controls)
                charts_expansion.visible = True
            else:
                charts_expansion.visible = False
            _safe_update(charts_expansion)

            try:
                sessions_result = await gateway_client.call(
                    "usage.sessions",
                    {"range": range_val, "sort": sort_val},
                    timeout=10.0,
                )
                sessions_ref[:] = sessions_result.get("sessions", [])
            except Exception:
                sessions_result = await gateway_client.call("sessions.list", timeout=10.0)
                raw = sessions_result.get("sessions", [])

                def _sort_key(s: dict) -> float:
                    if sort_val == "tokens":
                        return -float(s.get("tokens", s.get("size", 0)) or 0)
                    ts = s.get("updated", s.get("updatedAt"))
                    if ts is not None:
                        return -float(ts)
                    p = Path(s.get("path", ""))
                    return -(p.stat().st_mtime if p.exists() else 0)

                sessions_ref[:] = sorted(raw, key=_sort_key)[:50]

            if not sessions_ref:
                session_list.controls.append(
                    empty_state_simple(
                        t("usage.no_sessions", default="No sessions in range."),
                        icon=ft.Icons.ANALYTICS_OUTLINED,
                    )
                )
            else:
                for s in sessions_ref:
                    path_str = s.get("path", s.get("sessionKey", ""))
                    key = path_str or s.get("session_id", "")
                    agent = s.get("agentId", s.get("agent", ""))
                    tokens = s.get("tokens", s.get("totalTokens", "-"))
                    updated = s.get("updated", s.get("updatedAt", _format_updated(path_str)))
                    if isinstance(updated, int | float):
                        updated = datetime.fromtimestamp(updated, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                    session_key = Path(path_str).name if path_str else key or "-"

                    def _make_session_click(sess: dict) -> Any:
                        return lambda e: _show_session_detail(e.control.page, sess)

                    tile = card_tile(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.ANALYTICS_OUTLINED, size=18, color=theme.colors.muted),
                                        ft.Text(session_key, size=13, weight=ft.FontWeight.W_500, expand=True),
                                    ],
                                    spacing=8,
                                ),
                                ft.Row(
                                    [
                                        ft.Text(f"Agent: {agent or '-'}", size=10, color=theme.colors.muted),
                                        ft.Text(f"Tokens: {tokens}", size=10, color=theme.colors.muted),
                                        ft.Text(f"Updated: {updated}", size=10, color=theme.colors.muted),
                                    ],
                                    spacing=12,
                                    wrap=True,
                                ),
                            ],
                            spacing=6,
                        ),
                        on_click=_make_session_click(s),
                    )
                    session_list.controls.append(tile)
        except Exception as exc:
            session_list.controls.clear()
            session_list.controls.append(error_state(str(exc), on_retry=_refresh))
        _safe_update(session_list)

    async def _export() -> None:
        lines = []
        lines.append(f"# Usage Summary (range: {range_dropdown.value or '7d'})")
        lines.append(f"Total Tokens: {summary_ref.get('totalTokens', 0)}")
        lines.append(f"Sessions: {summary_ref.get('sessions', 0)}")
        lines.append(f"Est. Cost: {summary_ref.get('estimatedCost', summary_ref.get('estimatedCostValue', 'N/A'))}")
        lines.append("")
        lines.append("# Sessions")
        for s in sessions_ref:
            path_str = s.get("path", s.get("sessionKey", ""))
            agent = s.get("agentId", s.get("agent", ""))
            tokens = s.get("tokens", s.get("totalTokens", "-"))
            updated = s.get("updated", s.get("updatedAt", _format_updated(path_str)))
            lines.append(f"{Path(path_str).name if path_str else '-'}\t{agent}\t{tokens}\t{updated}")
        content = "\n".join(lines)
        try:
            from pyclaw.infra.misc_extras import clipboard_write

            clipboard_write(content)
        except Exception:
            pass

    export_btn = ft.Button(
        t("usage.export", default="Export"),
        icon=ft.Icons.COPY,
        on_click=lambda e: _fire_async(_export),
    )
    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip=t("channels.refresh", default="Refresh"),
        icon_size=20,
        on_click=lambda e: _fire_async(_refresh),
    )

    filter_row = ft.Row(
        [
            range_dropdown,
            sort_dropdown,
            export_btn,
            refresh_btn,
        ],
        spacing=12,
    )
    range_dropdown.on_change = lambda e: _fire_async(_refresh)
    sort_dropdown.on_change = lambda e: _fire_async(_refresh)

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.ANALYTICS,
                t("usage.title", default="Usage"),
                actions=[refresh_btn],
            ),
            ft.Container(content=filter_row, padding=ft.Padding.symmetric(horizontal=16, vertical=8)),
            ft.Container(content=stats_row, padding=ft.Padding.symmetric(horizontal=16, vertical=8)),
            ft.Container(content=charts_expansion, padding=ft.Padding.symmetric(horizontal=16, vertical=4)),
            session_list,
        ],
        expand=True,
        spacing=0,
    )

    _fire_async(_refresh)
    return panel
