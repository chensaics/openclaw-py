"""Tests for terminal utilities -- ANSI table, palette."""

from __future__ import annotations

import pytest

from pyclaw.terminal.table import TableColumn, render_table
from pyclaw.terminal.palette import PALETTE, ColorPalette


class TestRenderTable:
    def test_basic_table(self):
        columns = [TableColumn(key="name", header="Name"), TableColumn(key="val", header="Value")]
        rows = [{"name": "key1", "val": "val1"}, {"name": "key2", "val": "val2"}]
        result = render_table(columns, rows)
        assert "Name" in result
        assert "Value" in result
        assert "key1" in result
        assert "val2" in result

    def test_empty_rows(self):
        columns = [TableColumn(key="a", header="A"), TableColumn(key="b", header="B")]
        result = render_table(columns, [])
        assert "A" in result

    def test_single_column(self):
        columns = [TableColumn(key="items", header="Items")]
        rows = [{"items": "one"}, {"items": "two"}, {"items": "three"}]
        result = render_table(columns, rows)
        assert "one" in result
        assert "three" in result


class TestPalette:
    def test_palette_is_color_palette(self):
        assert isinstance(PALETTE, ColorPalette)

    def test_has_common_fields(self):
        assert hasattr(PALETTE, "accent")
        assert hasattr(PALETTE, "success")
        assert hasattr(PALETTE, "error")
        assert hasattr(PALETTE, "warn")
        assert hasattr(PALETTE, "info")
        assert hasattr(PALETTE, "reset")
        assert hasattr(PALETTE, "muted")

    def test_values_are_strings(self):
        for field_name in ("accent", "success", "error", "warn", "info", "reset", "muted"):
            val = getattr(PALETTE, field_name)
            assert isinstance(val, str), f"PALETTE.{field_name} should be str"
