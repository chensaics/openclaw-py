"""Tests for Phase 38: TUI/Models/Wizard/Hooks/Misc."""

from __future__ import annotations

import time
from typing import Any
from pathlib import Path

import pytest

# Phase 38a: Bundled Hooks
from pyclaw.hooks.bundled.extra_hooks import (
    BootCheckItem,
    CommandLogEntry,
    CommandLogger,
    DEFAULT_EXTRA_FILES,
    ExtraFileSpec,
    format_extra_files_for_prompt,
    load_extra_files,
    parse_boot_md,
    run_boot_checks,
)

# Phase 38b: Models Deep
from pyclaw.cli.commands.models_deep import (
    AuthOverviewEntry,
    ModelDefaultConfig,
    ProbeResult,
    format_auth_table,
    format_models_table,
    get_auth_overview,
    probe_model,
    scan_providers,
    set_default_model,
)

# Phase 38c: Wizard Session
from pyclaw.wizard.session import (
    WizardSession,
    WizardState,
    StepStatus,
    create_channel_wizard,
    create_setup_wizard,
    format_completion,
    format_intro,
    format_summary,
    generate_bash_completion,
    generate_fish_completion,
    generate_zsh_completion,
    GatewaySetupGuide,
)

# Phase 38d: Misc Extras
from pyclaw.infra.misc_extras import (
    RespawnConfig,
    RespawnTracker,
    TLSFingerprint,
    VALID_CHANNEL_TYPES,
    VoiceConnection,
    VoiceConnectionState,
    VoiceManager,
    VoiceWakeConfig,
    VoiceWakeState,
    cleanup_agent_schema,
    validate_channel_type,
)

# Phase 38e: Extra Providers
from pyclaw.agents.providers.extra_providers import (
    EXTRA_PROVIDERS,
    ExtraProviderConfig,
    create_openai_config,
    get_all_extra_models,
    get_extra_provider,
    list_extra_providers,
)


# =====================================================================
# Phase 38a: Bundled Hooks
# =====================================================================

class TestBootMd:
    def test_parse(self) -> None:
        content = """
- [ ] Config file exists | file_exists | config.json
- [x] Python installed | command_available | python3
- [ ] API key set | env_set | OPENAI_API_KEY
"""
        items = parse_boot_md(content)
        assert len(items) == 3
        assert items[0].check_type == "file_exists"
        assert items[1].passed  # [x]
        assert items[2].target == "OPENAI_API_KEY"

    def test_run_checks(self, tmp_path: Any) -> None:
        (tmp_path / "exists.txt").write_text("ok")
        items = [
            BootCheckItem(description="File exists", check_type="file_exists", target="exists.txt"),
            BootCheckItem(description="Missing file", check_type="file_exists", target="nope.txt"),
        ]
        result = run_boot_checks(items, workspace_dir=str(tmp_path))
        assert result.passed_count == 1
        assert result.failed_count == 1
        assert not result.all_passed


class TestExtraFiles:
    def test_load(self, tmp_path: Any) -> None:
        (tmp_path / "README.md").write_text("# Project\nHello")
        specs = [ExtraFileSpec("README.md", "README")]
        files = load_extra_files(specs, workspace_dir=str(tmp_path))
        assert len(files) == 1
        assert files[0][0] == "README"

    def test_load_missing(self, tmp_path: Any) -> None:
        specs = [ExtraFileSpec("nope.md", "Missing", optional=True)]
        files = load_extra_files(specs, workspace_dir=str(tmp_path))
        assert len(files) == 0

    def test_format_for_prompt(self) -> None:
        files = [("README", "# Hello"), ("RULES", "Be nice")]
        result = format_extra_files_for_prompt(files)
        assert "README" in result
        assert "Hello" in result

    def test_format_empty(self) -> None:
        assert format_extra_files_for_prompt([]) == ""

    def test_default_specs(self) -> None:
        assert len(DEFAULT_EXTRA_FILES) >= 3


class TestCommandLogger:
    def test_log_and_recent(self) -> None:
        logger = CommandLogger()
        entry = CommandLogEntry(command="ls", args=["-la"], exit_code=0)
        entry.finished_at = time.time()
        logger.log(entry)
        assert logger.total_logged == 1
        recent = logger.recent(5)
        assert len(recent) == 1
        assert recent[0].command == "ls"

    def test_log_line_format(self) -> None:
        entry = CommandLogEntry(command="echo", args=["hello"], exit_code=0)
        entry.finished_at = entry.started_at + 1.5
        line = entry.to_log_line()
        assert "exit=0" in line
        assert "echo" in line

    def test_max_entries(self) -> None:
        logger = CommandLogger(max_entries=3)
        for i in range(5):
            logger.log(CommandLogEntry(command=f"cmd{i}"))
        assert logger.total_logged == 3

    def test_log_to_file(self, tmp_path: Any) -> None:
        log_file = str(tmp_path / "commands.log")
        logger = CommandLogger(log_file=log_file)
        logger.log(CommandLogEntry(command="test", exit_code=0))
        content = Path(log_file).read_text()
        assert "test" in content


# =====================================================================
# Phase 38b: Models Deep
# =====================================================================

class TestModelProbe:
    def test_probe_with_key(self) -> None:
        result = probe_model("gpt-4o", "openai", api_key="sk-test")
        assert result.available
        assert result.context_window == 128000
        assert result.supports_tools
        assert result.supports_vision

    def test_probe_no_key(self) -> None:
        result = probe_model("gpt-4o", "openai")
        assert not result.available
        assert "API key" in result.error

    def test_probe_ollama_no_key(self) -> None:
        result = probe_model("llama3.2", "ollama")
        assert result.available


class TestModelScan:
    def test_scan(self) -> None:
        providers = {"openai": "sk-test", "anthropic": "sk-ant-test"}
        result = scan_providers(providers)
        assert result.total_providers == 2
        assert result.available_count >= 1

    def test_scan_empty(self) -> None:
        result = scan_providers({})
        assert result.total_providers == 0


class TestAuthOverview:
    def test_overview(self) -> None:
        entries = get_auth_overview({"openai": "sk-test123456", "anthropic": ""})
        assert len(entries) == 2
        assert entries[0].configured
        assert not entries[1].configured
        assert entries[0].key_prefix.startswith("sk-test")


class TestModelDefault:
    def test_set_default(self) -> None:
        current = ModelDefaultConfig(model="gpt-4o")
        updated = set_default_model(current, model="claude-3-5-sonnet")
        assert updated.model == "claude-3-5-sonnet"

    def test_keep_existing(self) -> None:
        current = ModelDefaultConfig(model="gpt-4o", provider="openai")
        updated = set_default_model(current)
        assert updated.model == "gpt-4o"
        assert updated.provider == "openai"


class TestTableFormatting:
    def test_models_table(self) -> None:
        results = [
            ProbeResult(model="gpt-4o", provider="openai", available=True,
                        context_window=128000, supports_tools=True, supports_vision=True),
            ProbeResult(model="llama3", provider="ollama", available=False, error="no key"),
        ]
        table = format_models_table(results)
        assert "gpt-4o" in table
        assert "OK" in table
        assert "FAIL" in table

    def test_auth_table(self) -> None:
        entries = [AuthOverviewEntry(provider="openai", configured=True, auth_method="api_key")]
        table = format_auth_table(entries)
        assert "openai" in table
        assert "Configured" in table

    def test_empty_table(self) -> None:
        assert "No models" in format_models_table([])


# =====================================================================
# Phase 38c: Wizard Session
# =====================================================================

class TestWizardSession:
    def test_create_setup(self) -> None:
        wizard = create_setup_wizard()
        assert wizard.wizard_type == "setup"
        assert len(wizard.steps) >= 5
        assert wizard.progress == 0.0

    def test_start_and_advance(self) -> None:
        wizard = create_setup_wizard()
        first = wizard.start()
        assert first is not None
        assert first.status == StepStatus.ACTIVE
        assert wizard.state == WizardState.IN_PROGRESS

        wizard.set_answer("openai")
        next_step = wizard.advance()
        assert next_step is not None
        assert wizard.collected_config["provider"] == "openai"

    def test_complete(self) -> None:
        wizard = create_setup_wizard()
        wizard.start()
        while not wizard.is_complete:
            wizard.set_answer("test")
            wizard.advance()
        assert wizard.state == WizardState.COMPLETED
        assert wizard.progress == 1.0

    def test_skip(self) -> None:
        wizard = create_setup_wizard()
        wizard.start()
        # Advance to a skippable step
        while wizard.current_step and not wizard.current_step.skippable:
            wizard.set_answer("test")
            wizard.advance()

        if wizard.current_step and wizard.current_step.skippable:
            wizard.skip_current()
            assert any(s.status == StepStatus.SKIPPED for s in wizard.steps)

    def test_cancel(self) -> None:
        wizard = create_setup_wizard()
        wizard.start()
        wizard.cancel()
        assert wizard.state == WizardState.CANCELLED

    def test_channel_wizard(self) -> None:
        wizard = create_channel_wizard("telegram")
        assert "telegram" in wizard.wizard_type
        assert len(wizard.steps) >= 3


class TestPromptFormatting:
    def test_intro(self) -> None:
        result = format_intro("Setup Wizard")
        assert "Setup Wizard" in result
        assert "┌" in result

    def test_summary(self) -> None:
        config = {"provider": "openai", "model": "gpt-4o"}
        result = format_summary(config)
        assert "openai" in result
        assert "gpt-4o" in result

    def test_completion(self) -> None:
        result = format_completion("setup")
        assert "Setup" in result


class TestShellCompletion:
    def test_bash(self) -> None:
        script = generate_bash_completion()
        assert "pyclaw" in script
        assert "COMPREPLY" in script

    def test_zsh(self) -> None:
        script = generate_zsh_completion()
        assert "compdef" in script

    def test_fish(self) -> None:
        script = generate_fish_completion()
        assert "complete -c" in script


class TestGatewayGuide:
    def test_config(self) -> None:
        guide = GatewaySetupGuide(mode="local", port=18789)
        config = guide.to_config_dict()
        assert config["gateway"]["mode"] == "local"
        assert config["gateway"]["port"] == 18789

    def test_run_command(self) -> None:
        guide = GatewaySetupGuide()
        cmd = guide.to_run_command()
        assert "pyclaw gateway run" in cmd


# =====================================================================
# Phase 38d: Misc Extras
# =====================================================================

class TestVoiceManager:
    def test_join_and_leave(self) -> None:
        mgr = VoiceManager()
        conn = mgr.join("guild1", "channel1")
        assert conn.is_connected
        assert mgr.active_count == 1

        assert mgr.leave("guild1")
        assert mgr.active_count == 0

    def test_leave_nonexistent(self) -> None:
        mgr = VoiceManager()
        assert not mgr.leave("nonexistent")


class TestTLSFingerprint:
    def test_short_hash(self) -> None:
        fp = TLSFingerprint(sha256="abcdef1234567890" * 4)
        assert len(fp.short_hash) == 16


class TestVoiceWake:
    def test_state(self) -> None:
        state = VoiceWakeState(VoiceWakeConfig(enabled=True))
        assert not state.is_listening
        state.start_listening()
        assert state.is_listening
        state.on_wake()
        assert state.wake_count == 1
        state.stop_listening()
        assert not state.is_listening


class TestRespawnTracker:
    def test_respawn(self) -> None:
        tracker = RespawnTracker(RespawnConfig(max_respawns=3))
        assert tracker.should_respawn()
        delay = tracker.record_respawn()
        assert delay > 0
        assert tracker.respawn_count == 1

    def test_max_respawns(self) -> None:
        tracker = RespawnTracker(RespawnConfig(max_respawns=2))
        tracker.record_respawn()
        tracker.record_respawn()
        assert not tracker.should_respawn()

    def test_reset(self) -> None:
        tracker = RespawnTracker(RespawnConfig(max_respawns=2))
        tracker.record_respawn()
        tracker.record_respawn()
        tracker.reset()
        assert tracker.should_respawn()


class TestChannelValidation:
    def test_valid(self) -> None:
        assert validate_channel_type("telegram")
        assert validate_channel_type("discord")

    def test_invalid(self) -> None:
        assert not validate_channel_type("nonexistent")

    def test_case_insensitive(self) -> None:
        assert validate_channel_type("Telegram")


class TestAgentSchemaCleanup:
    def test_cleanup(self) -> None:
        schema = {"model": "gpt-4o", "legacy_mode": True, "name": "agent1"}
        cleaned = cleanup_agent_schema(schema)
        assert "model" in cleaned
        assert "name" in cleaned
        assert "legacy_mode" not in cleaned


# =====================================================================
# Phase 38e: Extra Providers
# =====================================================================

class TestExtraProviders:
    def test_providers_registered(self) -> None:
        assert len(EXTRA_PROVIDERS) >= 6
        assert "venice" in EXTRA_PROVIDERS
        assert "huggingface" in EXTRA_PROVIDERS
        assert "nvidia-nim" in EXTRA_PROVIDERS
        assert "vllm" in EXTRA_PROVIDERS
        assert "litellm" in EXTRA_PROVIDERS
        assert "kimi-coding" in EXTRA_PROVIDERS

    def test_get_provider(self) -> None:
        p = get_extra_provider("venice")
        assert p is not None
        assert p.display_name == "Venice AI"
        assert p.base_url.startswith("https://")

    def test_get_missing(self) -> None:
        assert get_extra_provider("nonexistent") is None

    def test_list_providers(self) -> None:
        providers = list_extra_providers()
        assert len(providers) >= 6

    def test_get_all_models(self) -> None:
        models = get_all_extra_models()
        assert "venice" in models
        assert len(models["venice"]) >= 1

    def test_create_openai_config(self) -> None:
        config = create_openai_config("venice", api_key="test-key")
        assert config is not None
        assert config["base_url"] == "https://api.venice.ai/api/v1"
        assert config["api_key"] == "test-key"

    def test_create_openai_config_missing(self) -> None:
        assert create_openai_config("nonexistent") is None

    def test_to_openai_config(self) -> None:
        p = get_extra_provider("kimi-coding")
        assert p is not None
        config = p.to_openai_config("key123")
        assert config["api_key"] == "key123"
        assert "moonshot" in config["base_url"]

    def test_provider_capabilities(self) -> None:
        venice = get_extra_provider("venice")
        assert venice is not None
        assert venice.supports_streaming
        assert venice.supports_tools

        hf = get_extra_provider("huggingface")
        assert hf is not None
        assert not hf.supports_tools
