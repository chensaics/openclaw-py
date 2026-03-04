"""Tests for Phase 36: Channel Plugins Deep."""

from __future__ import annotations

# Phase 36a: Catalog
from pyclaw.channels.plugins.catalog import (
    BUILTIN_CATALOG,
    CatalogEntry,
    ChannelCatalog,
    ChannelCategory,
)

# Phase 36b: Onboarding
from pyclaw.channels.plugins.onboarding import (
    ONBOARDING_FLOWS,
    OnboardingStep,
    build_config_from_answers,
    get_onboarding_flow,
    list_onboarding_channels,
    validate_step_answer,
)

# Phase 36c: Outbound Adapters
from pyclaw.channels.plugins.outbound_adapters import (
    CHANNEL_OUTBOUND_CONFIGS,
    MessageFormat,
    OutboundAdapter,
    OutboundConfig,
    chunk_message,
    get_outbound_config,
    normalize_target,
)

# Phase 36d: Status Issues
from pyclaw.channels.plugins.status_issues import (
    check_all_channels,
    check_channel_issues,
    get_config_schema,
)

# =====================================================================
# Phase 36a: Channel Catalog
# =====================================================================


class TestChannelCatalog:
    def test_builtin_entries(self) -> None:
        assert len(BUILTIN_CATALOG) >= 6
        assert "telegram" in BUILTIN_CATALOG
        assert "discord" in BUILTIN_CATALOG
        assert "slack" in BUILTIN_CATALOG

    def test_catalog_registry(self) -> None:
        catalog = ChannelCatalog()
        assert catalog.count >= 6
        entry = catalog.get("telegram")
        assert entry is not None
        assert entry.display_name == "Telegram"

    def test_register_custom(self) -> None:
        catalog = ChannelCatalog()
        custom = CatalogEntry(
            channel_type="custom",
            display_name="Custom Channel",
            category=ChannelCategory.OTHER,
        )
        catalog.register(custom)
        assert catalog.get("custom") is not None

    def test_list_by_category(self) -> None:
        catalog = ChannelCatalog()
        messaging = catalog.list_by_category(ChannelCategory.MESSAGING)
        assert len(messaging) >= 3

    def test_media_limits(self) -> None:
        catalog = ChannelCatalog()
        limits = catalog.get_media_limits("telegram")
        assert limits.max_message_length == 4096

    def test_action_spec(self) -> None:
        catalog = ChannelCatalog()
        spec = catalog.get_action_spec("discord")
        assert spec.supports_reactions
        assert spec.supports_buttons
        assert spec.max_buttons == 5

    def test_account_helper(self) -> None:
        catalog = ChannelCatalog()
        helper = catalog.get_account_helper("telegram")
        assert len(helper.steps) >= 1
        assert "token" in helper.required_fields

    def test_summarize(self) -> None:
        catalog = ChannelCatalog()
        summary = catalog.summarize()
        assert len(summary) >= 6
        assert any(s["type"] == "telegram" for s in summary)

    def test_missing_channel(self) -> None:
        catalog = ChannelCatalog()
        assert catalog.get("nonexistent") is None
        limits = catalog.get_media_limits("nonexistent")
        assert limits.max_message_length == 4096  # default


# =====================================================================
# Phase 36b: Onboarding
# =====================================================================


class TestOnboarding:
    def test_flows_registered(self) -> None:
        assert len(ONBOARDING_FLOWS) >= 6
        channels = list_onboarding_channels()
        assert "telegram" in channels
        assert "discord" in channels

    def test_get_flow(self) -> None:
        flow = get_onboarding_flow("telegram")
        assert flow is not None
        assert flow.channel_type == "telegram"
        assert flow.step_count >= 2

    def test_get_flow_missing(self) -> None:
        assert get_onboarding_flow("nonexistent") is None

    def test_validate_step_required(self) -> None:
        step = OnboardingStep(step_id="t", title="Token", required=True)
        ok, err = validate_step_answer(step, "")
        assert not ok
        assert "required" in err

    def test_validate_step_pattern(self) -> None:
        step = OnboardingStep(
            step_id="t",
            title="Token",
            validation_pattern=r"^\d+:.+$",
        )
        ok, _ = validate_step_answer(step, "123:abc")
        assert ok
        ok2, _ = validate_step_answer(step, "invalid")
        assert not ok2

    def test_build_config(self) -> None:
        flow = get_onboarding_flow("telegram")
        assert flow is not None
        result = build_config_from_answers(
            flow,
            {
                "token": "123456:ABC-DEF",
            },
        )
        assert result.completed
        assert result.config["type"] == "telegram"
        assert result.config["token"] == "123456:ABC-DEF"

    def test_build_config_missing_required(self) -> None:
        flow = get_onboarding_flow("slack")
        assert flow is not None
        result = build_config_from_answers(flow, {})
        assert not result.completed
        assert len(result.errors) >= 1

    def test_signal_onboarding(self) -> None:
        flow = get_onboarding_flow("signal")
        assert flow is not None
        result = build_config_from_answers(
            flow,
            {
                "phone": "+1234567890",
            },
        )
        assert result.completed


# =====================================================================
# Phase 36c: Outbound Adapters
# =====================================================================


class TestOutboundAdapters:
    def test_chunk_short_message(self) -> None:
        result = chunk_message("Hello world", 4096)
        assert not result.was_chunked
        assert len(result.chunks) == 1

    def test_chunk_long_message(self) -> None:
        text = "Line\n" * 1000
        result = chunk_message(text, 100)
        assert result.was_chunked
        assert all(len(c) <= 100 for c in result.chunks)

    def test_chunk_preserves_code_blocks(self) -> None:
        text = "Before\n```python\nfor i in range(10):\n    print(i)\n```\nAfter " + "x" * 200
        result = chunk_message(text, 150, preserve_code_blocks=True)
        assert result.was_chunked

    def test_normalize_target_telegram(self) -> None:
        assert normalize_target("telegram", "12345") == "12345"
        assert normalize_target("telegram", "@user") == "@user"

    def test_normalize_target_discord(self) -> None:
        assert normalize_target("discord", "<#123>") == "123"

    def test_normalize_target_signal(self) -> None:
        assert normalize_target("signal", "+1234567890") == "+1234567890"

    def test_outbound_configs(self) -> None:
        assert len(CHANNEL_OUTBOUND_CONFIGS) >= 6
        tg = get_outbound_config("telegram")
        assert tg.max_message_length == 4096
        assert tg.preferred_format == MessageFormat.HTML

    def test_outbound_adapter(self) -> None:
        config = get_outbound_config("discord")
        adapter = OutboundAdapter(config)
        result = adapter.prepare("Hello world")
        assert not result.was_chunked
        assert result.chunks[0] == "Hello world"

    def test_format_plain(self) -> None:
        config = OutboundConfig(channel_type="test", preferred_format=MessageFormat.PLAIN)
        adapter = OutboundAdapter(config)
        formatted = adapter.format_text("**bold** and _italic_", MessageFormat.PLAIN)
        assert "**" not in formatted

    def test_default_config(self) -> None:
        config = get_outbound_config("unknown_channel")
        assert config.channel_type == "unknown_channel"
        assert config.max_message_length == 4096


# =====================================================================
# Phase 36d: Status Issues
# =====================================================================


class TestStatusIssues:
    def test_telegram_no_token(self) -> None:
        issues = check_channel_issues("telegram", {})
        assert len(issues) >= 1
        assert issues[0].code == "telegram_no_token"

    def test_telegram_invalid_token(self) -> None:
        issues = check_channel_issues("telegram", {"token": "invalid"})
        assert any(i.code == "telegram_invalid_token" for i in issues)

    def test_telegram_valid(self) -> None:
        issues = check_channel_issues("telegram", {"token": "123:ABC"})
        assert len(issues) == 0

    def test_discord_no_token(self) -> None:
        issues = check_channel_issues("discord", {})
        assert any(i.code == "discord_no_token" for i in issues)

    def test_signal_no_phone(self) -> None:
        issues = check_channel_issues("signal", {})
        assert any(i.code == "signal_no_phone" for i in issues)

    def test_whatsapp_session_expired(self) -> None:
        issues = check_channel_issues("whatsapp", {"sessionExpired": True})
        assert any(i.code == "whatsapp_session_expired" for i in issues)

    def test_bluebubbles_issues(self) -> None:
        issues = check_channel_issues("bluebubbles", {})
        assert len(issues) >= 1

    def test_unknown_channel(self) -> None:
        issues = check_channel_issues("nonexistent", {})
        assert len(issues) == 0

    def test_check_all(self) -> None:
        result = check_all_channels(
            {
                "telegram": {},
                "discord": {"token": "valid"},
            }
        )
        assert "telegram" in result
        assert "discord" not in result

    def test_config_schema(self) -> None:
        schema = get_config_schema("telegram")
        assert schema is not None
        json_schema = schema.to_json_schema()
        assert json_schema["type"] == "object"
        assert "token" in json_schema["properties"]
        assert "token" in json_schema["required"]

    def test_config_schema_missing(self) -> None:
        assert get_config_schema("nonexistent") is None
