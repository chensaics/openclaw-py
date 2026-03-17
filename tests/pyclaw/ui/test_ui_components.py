"""Tests for UI reusable components and panel build functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

ft = pytest.importorskip("flet")

from pyclaw.ui.components import (  # noqa: E402
    card_tile,
    empty_state,
    empty_state_simple,
    error_state,
    page_header,
    status_chip,
    streaming_indicator,
)


class TestErrorState:
    def test_returns_container(self) -> None:
        ctrl = error_state("Something went wrong")
        assert isinstance(ctrl, ft.Container)

    def test_contains_message(self) -> None:
        ctrl = error_state("Test error message")
        col = ctrl.content
        assert isinstance(col, ft.Column)
        texts = [c for c in col.controls if isinstance(c, ft.Text)]
        assert any("Test error message" in t.value for t in texts)

    def test_has_retry_button_when_on_retry(self) -> None:
        ctrl = error_state("err", on_retry=lambda: None)
        col = ctrl.content
        buttons = [c for c in col.controls if isinstance(c, ft.Button)]
        assert len(buttons) == 1

    def test_no_retry_button_without_on_retry(self) -> None:
        ctrl = error_state("err")
        col = ctrl.content
        buttons = [c for c in col.controls if isinstance(c, ft.Button)]
        assert len(buttons) == 0


class TestEmptyStateSimple:
    def test_returns_container(self) -> None:
        ctrl = empty_state_simple("No data")
        assert isinstance(ctrl, ft.Container)

    def test_contains_message_and_icon(self) -> None:
        ctrl = empty_state_simple("No items here", icon=ft.Icons.INBOX)
        col = ctrl.content
        assert isinstance(col, ft.Column)
        icons = [c for c in col.controls if isinstance(c, ft.Icon)]
        texts = [c for c in col.controls if isinstance(c, ft.Text)]
        assert len(icons) >= 1
        assert any("No items here" in t.value for t in texts)


class TestEmptyState:
    def test_without_action(self) -> None:
        ctrl = empty_state(ft.Icons.INBOX, "Nothing here")
        assert isinstance(ctrl, ft.Container)

    def test_with_action(self) -> None:
        ctrl = empty_state(
            ft.Icons.ADD,
            "No items",
            action_label="Add",
            on_action=lambda e: None,
        )
        col = ctrl.content
        buttons = [c for c in col.controls if isinstance(c, ft.OutlinedButton)]
        assert len(buttons) == 1


class TestPageHeader:
    def test_returns_container(self) -> None:
        ctrl = page_header(ft.Icons.HOME, "Dashboard")
        assert isinstance(ctrl, ft.Container)

    def test_contains_title(self) -> None:
        ctrl = page_header(ft.Icons.HOME, "Dashboard")
        row = ctrl.content
        assert isinstance(row, ft.Row)
        texts = [c for c in row.controls if isinstance(c, ft.Text)]
        assert any("Dashboard" in t.value for t in texts)

    def test_with_actions(self) -> None:
        action = ft.IconButton(icon=ft.Icons.REFRESH)
        ctrl = page_header(ft.Icons.HOME, "Test", actions=[action])
        row = ctrl.content
        assert action in row.controls


class TestCardTile:
    def test_returns_container(self) -> None:
        content = ft.Text("Hello")
        ctrl = card_tile(content)
        assert isinstance(ctrl, ft.Container)
        assert ctrl.content is content

    def test_has_border_radius(self) -> None:
        ctrl = card_tile(ft.Text("x"))
        assert ctrl.border_radius is not None


class TestStatusChip:
    def test_returns_container(self) -> None:
        ctrl = status_chip("active", "#00ff00")
        assert isinstance(ctrl, ft.Container)

    def test_label_text(self) -> None:
        ctrl = status_chip("running", "#22c55e")
        text = ctrl.content
        assert isinstance(text, ft.Text)
        assert text.value == "running"


class TestStreamingIndicator:
    def test_returns_row_with_three_dots(self) -> None:
        row = streaming_indicator()
        assert isinstance(row, ft.Row)
        dots = [c for c in row.controls if isinstance(c, ft.Container)]
        assert len(dots) == 3


class TestPanelBuildFunctions:
    """Test that panel build functions return valid ft.Column objects."""

    def test_build_plans_panel(self) -> None:
        from pyclaw.ui.plans_panel import build_plans_panel

        panel = build_plans_panel()
        assert isinstance(panel, ft.Column)
        assert hasattr(panel, "refresh")

    def test_build_system_panel(self) -> None:
        from pyclaw.ui.system_panel import build_system_panel

        panel = build_system_panel()
        assert isinstance(panel, ft.Column)
        assert hasattr(panel, "refresh")

    def test_build_channels_panel(self) -> None:
        from pyclaw.ui.channels_panel import build_channels_panel

        panel = build_channels_panel()
        assert isinstance(panel, ft.Column)
        assert hasattr(panel, "refresh")
        assert hasattr(panel, "update_channels")

    def test_build_instances_panel(self) -> None:
        from pyclaw.ui.instances_panel import build_instances_panel

        panel = build_instances_panel()
        assert isinstance(panel, ft.Column)
        assert hasattr(panel, "refresh")

    def test_build_sessions_panel(self) -> None:
        from pyclaw.ui.sessions_panel import build_sessions_panel

        panel = build_sessions_panel()
        assert isinstance(panel, ft.Column)
        assert hasattr(panel, "refresh")

    def test_build_logs_panel(self) -> None:
        from pyclaw.ui.logs_panel import build_logs_panel

        panel = build_logs_panel()
        assert isinstance(panel, ft.Column)
        assert hasattr(panel, "refresh")

    def test_build_overview_panel(self) -> None:
        from pyclaw.ui.overview_panel import build_overview_panel

        panel = build_overview_panel()
        assert isinstance(panel, ft.Column)

    def test_build_cron_panel(self) -> None:
        from pyclaw.ui.cron_panel import build_cron_panel

        panel = build_cron_panel()
        assert isinstance(panel, ft.Column)

    def test_build_debug_panel(self) -> None:
        from pyclaw.ui.debug_panel import build_debug_panel

        panel = build_debug_panel()
        assert isinstance(panel, ft.Column)

    def test_build_skills_panel(self) -> None:
        from pyclaw.ui.skills_panel import build_skills_panel

        panel = build_skills_panel()
        assert isinstance(panel, ft.Column)

    def test_build_nodes_panel(self) -> None:
        from pyclaw.ui.nodes_panel import build_nodes_panel

        panel = build_nodes_panel()
        assert isinstance(panel, ft.Column)

    def test_build_config_panel(self) -> None:
        from pyclaw.ui.config_panel import build_config_panel

        panel = build_config_panel()
        assert isinstance(panel, ft.Column)

    def test_build_usage_panel(self) -> None:
        from pyclaw.ui.usage_panel import build_usage_panel

        panel = build_usage_panel()
        assert isinstance(panel, ft.Column)


class TestChannelsPanelUpdateChannels:
    def test_update_channels_empty(self) -> None:
        from pyclaw.ui.channels_panel import build_channels_panel

        panel = build_channels_panel()
        panel.update_channels([])

    def test_update_channels_with_data(self) -> None:
        from pyclaw.ui.channels_panel import build_channels_panel

        panel = build_channels_panel()
        panel.update_channels(
            [
                {"id": "telegram", "name": "Telegram", "status": "connected"},
                {"id": "discord", "name": "Discord", "status": "disabled"},
            ]
        )

    def test_update_channels_with_error(self) -> None:
        from pyclaw.ui.channels_panel import build_channels_panel

        panel = build_channels_panel()
        panel.update_channels([], error="Connection failed")


class TestGatewayClientMock:
    """Test panels with a mock gateway client."""

    def _make_mock_gw(self) -> MagicMock:
        gw = MagicMock()
        gw.connected = True
        gw.call = AsyncMock(return_value={})
        gw.on_event = MagicMock()
        return gw

    def test_plans_panel_with_gw(self) -> None:
        from pyclaw.ui.plans_panel import build_plans_panel

        gw = self._make_mock_gw()
        panel = build_plans_panel(gateway_client=gw)
        assert isinstance(panel, ft.Column)

    def test_logs_panel_subscribes_events(self) -> None:
        from pyclaw.ui.logs_panel import build_logs_panel

        gw = self._make_mock_gw()
        build_logs_panel(gateway_client=gw)
        event_names = [call.args[0] for call in gw.on_event.call_args_list]
        assert "logs.new" in event_names
        assert "log.entry" in event_names

    def test_instances_panel_subscribes_events(self) -> None:
        from pyclaw.ui.instances_panel import build_instances_panel

        gw = self._make_mock_gw()
        build_instances_panel(gateway_client=gw)
        event_names = [call.args[0] for call in gw.on_event.call_args_list]
        assert "system.presence.changed" in event_names

    def test_system_panel_with_snackbar(self) -> None:
        from pyclaw.ui.system_panel import build_system_panel

        gw = self._make_mock_gw()
        snackbar_calls: list[str] = []
        panel = build_system_panel(
            gateway_client=gw,
            on_snackbar=lambda msg: snackbar_calls.append(msg),
        )
        assert isinstance(panel, ft.Column)
