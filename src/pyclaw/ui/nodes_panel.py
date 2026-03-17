"""Nodes panel — device pairing, paired list, and exec bindings."""

from __future__ import annotations

import asyncio
from typing import Any

import flet as ft

from pyclaw.ui.components import card_tile, empty_state_simple, error_state, page_header
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import get_theme


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


def build_nodes_panel(*, gateway_client: Any = None) -> ft.Column:
    theme = get_theme()
    pending_list = ft.ListView(spacing=6)
    paired_list = ft.ListView(spacing=6, expand=True)
    bindings_list = ft.ListView(spacing=6, expand=True)

    def _safe_update(control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass

    def _token_summary(token: str) -> str:
        if not token:
            return "-"
        if len(token) <= 12:
            return token[:4] + "***"
        return token[:4] + "..." + token[-4:]

    async def _refresh_all() -> None:
        if not gateway_client or not gateway_client.connected:
            pending_list.controls.clear()
            pending_list.controls.append(
                error_state(
                    t("nodes.offline", default="Connect to gateway to view nodes."),
                    on_retry=_refresh_all,
                )
            )
            paired_list.controls.clear()
            bindings_list.controls.clear()
            _safe_update(pending_list)
            _safe_update(paired_list)
            _safe_update(bindings_list)
            return

        try:
            pending_result = await gateway_client.call("nodes.pendingPairs")
            pending_items = pending_result.get("pending", [])
            pending_list.controls.clear()
            if pending_items:
                for item in pending_items:
                    pair_id = item.get("id", "")
                    name = item.get("name", item.get("id", "?"))
                    tile = card_tile(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.LINK, size=18, color=theme.colors.warning),
                                        ft.Text(name, size=14, weight=ft.FontWeight.BOLD, expand=True),
                                    ],
                                    spacing=8,
                                ),
                                ft.Row(
                                    [
                                        ft.Button(
                                            t("nodes.approve", default="Approve"),
                                            icon=ft.Icons.CHECK,
                                            on_click=lambda e, pid=pair_id: _fire_async(_approve_pair, pid),
                                        ),
                                        ft.OutlinedButton(
                                            t("nodes.reject", default="Reject"),
                                            icon=ft.Icons.CLOSE,
                                            on_click=lambda e, pid=pair_id: _fire_async(_reject_pair, pid),
                                        ),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            spacing=8,
                        ),
                    )
                    pending_list.controls.append(tile)
            else:
                pending_list.controls.append(
                    empty_state_simple(
                        t("nodes.no_pending", default="No pending pair requests."),
                        icon=ft.Icons.LINK_OFF,
                    )
                )
            _safe_update(pending_list)

            paired_result = await gateway_client.call("nodes.paired")
            paired_items = paired_result.get("nodes", [])
            paired_list.controls.clear()
            if paired_items:
                for item in paired_items:
                    node_id = item.get("id", "")
                    name = item.get("name", item.get("id", "?"))
                    token_preview = _token_summary(item.get("token", ""))
                    tile = card_tile(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.DEVICES, size=18, color=theme.colors.primary),
                                        ft.Column(
                                            [
                                                ft.Text(name, size=14, weight=ft.FontWeight.BOLD),
                                                ft.Text(f"Token: {token_preview}", size=11, color=theme.colors.muted),
                                            ],
                                            spacing=2,
                                            expand=True,
                                            tight=True,
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.REFRESH,
                                            tooltip=t("nodes.rotate_token", default="Rotate Token"),
                                            icon_size=18,
                                            on_click=lambda e, nid=node_id: _fire_async(_rotate_token, nid),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.LINK_OFF,
                                            tooltip=t("nodes.revoke", default="Revoke"),
                                            icon_size=18,
                                            on_click=lambda e, nid=node_id: _fire_async(_revoke_node, nid),
                                        ),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            spacing=4,
                        ),
                    )
                    paired_list.controls.append(tile)
            else:
                paired_list.controls.append(
                    empty_state_simple(
                        t("nodes.no_paired", default="No paired devices."),
                        icon=ft.Icons.DEVICES_OTHER,
                    )
                )
            _safe_update(paired_list)

            bindings_result = await gateway_client.call("nodes.execBindings")
            bindings_items = bindings_result.get("bindings", [])
            bindings_list.controls.clear()
            if bindings_items:
                for b in bindings_items:
                    node_id = b.get("nodeId", "")
                    exec_id = b.get("execId", "")
                    tile = card_tile(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.CODE, size=18, color=theme.colors.muted),
                                ft.Text(f"Node: {node_id}", size=12),
                                ft.Text(" → ", size=12, color=theme.colors.muted),
                                ft.Text(f"Exec: {exec_id}", size=12),
                            ],
                            spacing=8,
                        ),
                    )
                    bindings_list.controls.append(tile)
            else:
                bindings_list.controls.append(
                    empty_state_simple(
                        t("nodes.no_bindings", default="No exec bindings."),
                        icon=ft.Icons.CODE_OFF,
                    )
                )
            _safe_update(bindings_list)
        except Exception as exc:
            pending_list.controls.clear()
            pending_list.controls.append(error_state(str(exc), on_retry=_refresh_all))
            paired_list.controls.clear()
            bindings_list.controls.clear()
            _safe_update(pending_list)
            _safe_update(paired_list)
            _safe_update(bindings_list)

    async def _approve_pair(pid: str) -> None:
        if not gateway_client:
            return
        try:
            await gateway_client.call("nodes.approvePair", {"id": pid})
            await _refresh_all()
        except Exception:
            pass

    async def _reject_pair(pid: str) -> None:
        if not gateway_client:
            return
        try:
            await gateway_client.call("nodes.rejectPair", {"id": pid})
            await _refresh_all()
        except Exception:
            pass

    async def _rotate_token(nid: str) -> None:
        if not gateway_client:
            return
        try:
            await gateway_client.call("nodes.rotateToken", {"id": nid})
            await _refresh_all()
        except Exception:
            pass

    async def _revoke_node(nid: str) -> None:
        if not gateway_client:
            return
        try:
            await gateway_client.call("nodes.revoke", {"id": nid})
            await _refresh_all()
        except Exception:
            pass

    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip=t("channels.refresh", default="Refresh"),
        icon_size=20,
        on_click=lambda e: _fire_async(_refresh_all),
    )

    pending_section = ft.Column(
        [
            ft.Text(t("nodes.pending_pairs", default="Pending Pairs"), size=14, weight=ft.FontWeight.BOLD),
            ft.Container(content=pending_list, height=180),
        ],
        spacing=8,
    )

    paired_section = ft.Column(
        [
            ft.Text(t("nodes.paired_devices", default="Paired Devices"), size=14, weight=ft.FontWeight.BOLD),
            paired_list,
        ],
        spacing=8,
        expand=True,
    )

    bindings_section = ft.Column(
        [
            ft.Text(t("nodes.exec_bindings", default="Exec Node Bindings"), size=14, weight=ft.FontWeight.BOLD),
            bindings_list,
        ],
        spacing=8,
        expand=True,
    )

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.HUB,
                t("nodes.title", default="Nodes"),
                actions=[refresh_btn],
            ),
            ft.Container(
                content=ft.Column(
                    [
                        pending_section,
                        ft.Divider(),
                        paired_section,
                        ft.Divider(),
                        bindings_section,
                    ],
                    spacing=16,
                    expand=True,
                ),
                padding=16,
            ),
        ],
        expand=True,
        spacing=0,
    )

    _fire_async(_refresh_all)
    return panel
