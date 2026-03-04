"""Tests for catalog / schema / implementation single-source-of-truth alignment.

These tests form the P2 regression baseline, catching drift between:
- BUILTIN_CATALOG entries
- ChannelsConfig explicit fields
- On-disk channel implementations (src/pyclaw/channels/*/channel.py)
"""

from __future__ import annotations

import pathlib

import pytest

from pyclaw.channels.plugins.catalog import (
    BUILTIN_CATALOG,
    ChannelCatalog,
    ChannelCategory,
)
from pyclaw.config.schema import ChannelsConfig

CHANNELS_ROOT = pathlib.Path(__file__).resolve().parent.parent / "src" / "pyclaw" / "channels"


# ---------- Catalog <-> Schema ----------


class TestCatalogSchemaAlignment:
    def _schema_channel_fields(self) -> set[str]:
        skip = {"defaults"}
        return {name for name in ChannelsConfig.model_fields if name not in skip}

    def test_catalog_entries_have_schema_fields(self):
        """Every catalog entry should have a corresponding ChannelsConfig field."""
        schema_fields = self._schema_channel_fields()
        missing = sorted(set(BUILTIN_CATALOG.keys()) - schema_fields)
        assert missing == [], f"Catalog entries without ChannelsConfig fields: {missing}"

    def test_schema_extra_allows_unknown_channels(self):
        """ChannelsConfig uses extra='allow', so unknown channels don't break parsing."""
        cfg = ChannelsConfig.model_validate({"my_new_channel": {"enabled": True}})
        assert cfg.model_extra is not None
        assert "my_new_channel" in cfg.model_extra

    def test_catalog_validate_against_schema_method(self):
        catalog = ChannelCatalog()
        result = catalog.validate_against_schema()
        assert result["in_catalog_not_schema"] == [], (
            f"Catalog types missing from schema: {result['in_catalog_not_schema']}"
        )


# ---------- Catalog <-> Implementations ----------


class TestCatalogImplementationAlignment:
    def _implemented_channels(self) -> set[str]:
        impl: set[str] = set()
        if not CHANNELS_ROOT.exists():
            pytest.skip("Channels source directory not found")
        for child in CHANNELS_ROOT.iterdir():
            if child.is_dir() and (child / "channel.py").exists():
                impl.add(child.name)
        impl.discard("plugins")
        return impl

    def test_implemented_channels_have_catalog_entries(self):
        """Every on-disk channel implementation should have a catalog entry."""
        implemented = self._implemented_channels()
        catalog_types = set(BUILTIN_CATALOG.keys())
        missing = sorted(implemented - catalog_types)
        assert missing == [], f"Implemented channels without catalog entry: {missing}"

    # Catalog entries that intentionally have no standalone channel.py
    # (e.g. webchat is embedded in the UI, onebot is a reserved slot).
    CATALOG_ONLY = {"webchat", "onebot"}

    def test_catalog_entries_have_implementations(self):
        """Every catalog entry should have an on-disk implementation."""
        implemented = self._implemented_channels()
        catalog_types = set(BUILTIN_CATALOG.keys()) - self.CATALOG_ONLY
        orphan = sorted(catalog_types - implemented)
        assert orphan == [], f"Catalog entries without implementation: {orphan}"

    def test_catalog_validate_against_implementations_method(self):
        catalog = ChannelCatalog()
        result = catalog.validate_against_implementations(
            str(CHANNELS_ROOT),
        )
        unexpected = [t for t in result["in_catalog_not_implemented"] if t not in self.CATALOG_ONLY]
        assert unexpected == []
        assert result["implemented_not_in_catalog"] == []


# ---------- CatalogEntry completeness ----------


class TestCatalogEntryCompleteness:
    @pytest.mark.parametrize("channel_type", list(BUILTIN_CATALOG.keys()))
    def test_entry_has_display_name(self, channel_type: str):
        entry = BUILTIN_CATALOG[channel_type]
        assert entry.display_name, f"{channel_type} missing display_name"

    @pytest.mark.parametrize("channel_type", list(BUILTIN_CATALOG.keys()))
    def test_entry_has_category(self, channel_type: str):
        entry = BUILTIN_CATALOG[channel_type]
        assert isinstance(entry.category, ChannelCategory)

    @pytest.mark.parametrize("channel_type", list(BUILTIN_CATALOG.keys()))
    def test_entry_has_color(self, channel_type: str):
        entry = BUILTIN_CATALOG[channel_type]
        assert entry.color, f"{channel_type} missing color"
        assert entry.color.startswith("#"), f"{channel_type} color should be hex"

    @pytest.mark.parametrize("channel_type", list(BUILTIN_CATALOG.keys()))
    def test_channel_type_matches_key(self, channel_type: str):
        entry = BUILTIN_CATALOG[channel_type]
        assert entry.channel_type == channel_type


# ---------- ChannelPlugin meta / dod_report ----------


class TestChannelPluginMeta:
    def test_base_plugin_dod_report(self):
        from pyclaw.channels.base import (
            ChannelPlugin,
            ChannelReply,
        )

        class Dummy(ChannelPlugin):
            @property
            def id(self) -> str:
                return "dummy"

            @property
            def name(self) -> str:
                return "Dummy"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def send_reply(self, reply: ChannelReply) -> None:
                pass

        d = Dummy()
        report = d.dod_report()
        assert report["channel_id"] == "dummy"
        assert report["meta"]["stability"] == "alpha"
        assert report["has_catalog_entry"] is False

    def test_stability_levels(self):
        from pyclaw.channels.base import StabilityLevel

        assert StabilityLevel.STABLE.value == "stable"
        assert StabilityLevel.BETA.value == "beta"
        assert StabilityLevel.ALPHA.value == "alpha"
        assert StabilityLevel.EXPERIMENTAL.value == "experimental"
