"""Tests for Phase 31 — CLI enhanced: doctor, auth providers, onboarding, status, models, channels."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from pyclaw.cli.commands.doctor_flows import (
    BUILTIN_CHECKS,
    DiagnosticRegistry,
    DiagnosticResult,
    DiagnosticReport,
    Severity,
    check_config,
    check_platform,
    create_default_registry,
    run_doctor,
)
from pyclaw.cli.commands.auth_providers import (
    AuthCredential,
    AuthMethod,
    AuthResult,
    CredentialStore,
    PROVIDER_SPECS,
    apply_api_key_auth,
    get_provider_auth_info,
    list_available_providers,
    validate_api_key,
)
from pyclaw.cli.commands.onboarding_enhanced import (
    OnboardingMode,
    OnboardingState,
    OnboardingStep,
    handle_risk_ack,
    handle_gateway_config,
    handle_auth_select,
    handle_provider_auth,
    handle_skills_install,
    handle_finalize,
    run_non_interactive,
)
from pyclaw.cli.commands.status_enhanced import (
    StatusLevel,
    StatusReport,
    SubsystemStatus,
    collect_config_status,
    collect_daemon_status,
    collect_sessions_status,
    generate_status_report,
)
from pyclaw.cli.commands.models_cmd import (
    BUILTIN_MODELS,
    DEFAULT_ALIASES,
    FallbackChain,
    ModelCapability,
    ModelInfo,
    ModelRegistry,
)
from pyclaw.cli.commands.channels_enhanced import (
    CHANNEL_SPECS,
    ChannelCapability,
    channel_summary,
    get_channel_capabilities,
    list_channels,
    transform_channel_config,
    validate_channel_config,
)


# ===== Doctor Flows =====

class TestDiagnosticResult:
    def test_ok(self) -> None:
        r = DiagnosticResult(check_name="test", category="test", severity=Severity.OK, message="OK")
        assert r.severity == Severity.OK

    def test_error(self) -> None:
        r = DiagnosticResult(check_name="test", category="test", severity=Severity.ERROR, message="fail")
        assert r.severity == Severity.ERROR


class TestDiagnosticReport:
    def test_has_errors(self) -> None:
        report = DiagnosticReport(results=[
            DiagnosticResult(check_name="a", category="c", severity=Severity.OK),
            DiagnosticResult(check_name="b", category="c", severity=Severity.ERROR),
        ])
        assert report.has_errors
        assert report.error_count == 1

    def test_by_category(self) -> None:
        report = DiagnosticReport(results=[
            DiagnosticResult(check_name="a", category="config"),
            DiagnosticResult(check_name="b", category="auth"),
        ])
        cats = report.by_category()
        assert "config" in cats
        assert "auth" in cats

    def test_summary_text(self) -> None:
        report = DiagnosticReport(results=[
            DiagnosticResult(check_name="test", category="config", severity=Severity.OK, message="OK"),
        ], platform="darwin", python_version="3.14")
        text = report.summary_text()
        assert "Doctor Report" in text
        assert "darwin" in text


class TestDiagnosticRegistry:
    def test_register_and_run(self) -> None:
        reg = DiagnosticRegistry()
        reg.register(lambda: DiagnosticResult(check_name="t", category="c", severity=Severity.OK, message="ok"))
        report = reg.run_all()
        assert len(report.results) == 1

    def test_exception_handling(self) -> None:
        reg = DiagnosticRegistry()

        def bad_check() -> DiagnosticResult:
            raise RuntimeError("boom")

        reg.register(bad_check)
        report = reg.run_all()
        assert report.results[0].severity == Severity.ERROR


class TestBuiltinChecks:
    def test_check_platform(self) -> None:
        result = check_platform()
        assert result.category == "platform"

    def test_builtin_count(self) -> None:
        assert len(BUILTIN_CHECKS) >= 9

    def test_run_doctor(self) -> None:
        report = run_doctor()
        assert len(report.results) >= 1


# ===== Auth Providers =====

class TestProviderSpecs:
    def test_count(self) -> None:
        assert len(PROVIDER_SPECS) >= 25

    def test_openai(self) -> None:
        spec = PROVIDER_SPECS["openai"]
        assert spec.display_name == "OpenAI"
        assert spec.auth_method == AuthMethod.API_KEY

    def test_bedrock(self) -> None:
        spec = PROVIDER_SPECS["bedrock"]
        assert spec.auth_method == AuthMethod.AWS_IAM

    def test_ollama(self) -> None:
        spec = PROVIDER_SPECS["ollama"]
        assert spec.auth_method == AuthMethod.NONE


class TestValidateApiKey:
    def test_valid(self) -> None:
        assert validate_api_key("sk-test123456789", PROVIDER_SPECS["openai"])

    def test_wrong_prefix(self) -> None:
        assert not validate_api_key("wrong-prefix", PROVIDER_SPECS["openai"])

    def test_empty(self) -> None:
        assert not validate_api_key("", PROVIDER_SPECS["openai"])

    def test_too_short(self) -> None:
        assert not validate_api_key("sk-", PROVIDER_SPECS["openai"])


class TestApplyApiKeyAuth:
    def test_success(self) -> None:
        result = apply_api_key_auth("anthropic", "sk-ant-test123456")
        assert result.success
        assert result.credential is not None

    def test_unknown_provider(self) -> None:
        result = apply_api_key_auth("unknown", "key")
        assert not result.success

    def test_invalid_key(self) -> None:
        result = apply_api_key_auth("openai", "bad")
        assert not result.success


class TestCredentialStore:
    def test_save_load(self, tmp_path: Path) -> None:
        store = CredentialStore(tmp_path)
        cred = AuthCredential(provider_id="test", auth_method=AuthMethod.API_KEY, api_key="k")
        store.save(cred)

        loaded = store.load("test")
        assert loaded is not None
        assert loaded.api_key == "k"

    def test_delete(self, tmp_path: Path) -> None:
        store = CredentialStore(tmp_path)
        cred = AuthCredential(provider_id="test", auth_method=AuthMethod.API_KEY)
        store.save(cred)
        assert store.delete("test")
        assert store.load("test") is None

    def test_list(self, tmp_path: Path) -> None:
        store = CredentialStore(tmp_path)
        store.save(AuthCredential(provider_id="a", auth_method=AuthMethod.API_KEY))
        store.save(AuthCredential(provider_id="b", auth_method=AuthMethod.API_KEY))
        assert sorted(store.list_providers()) == ["a", "b"]


class TestAuthHelpers:
    def test_get_info(self) -> None:
        info = get_provider_auth_info("openai")
        assert info is not None
        assert info["display_name"] == "OpenAI"

    def test_get_info_unknown(self) -> None:
        assert get_provider_auth_info("nonexistent") is None

    def test_list_providers(self) -> None:
        providers = list_available_providers()
        assert len(providers) >= 25


class TestAuthCredential:
    def test_expired(self) -> None:
        cred = AuthCredential(provider_id="t", auth_method=AuthMethod.OAUTH, expires_at=1.0)
        assert cred.is_expired

    def test_not_expired(self) -> None:
        import time
        cred = AuthCredential(provider_id="t", auth_method=AuthMethod.OAUTH, expires_at=time.time() + 9999)
        assert not cred.is_expired

    def test_serialize(self) -> None:
        cred = AuthCredential(provider_id="t", auth_method=AuthMethod.API_KEY, api_key="k")
        d = cred.to_dict()
        restored = AuthCredential.from_dict(d)
        assert restored.api_key == "k"


# ===== Onboarding Enhanced =====

class TestOnboardingSteps:
    def test_risk_ack_denied(self) -> None:
        state = OnboardingState()
        result = handle_risk_ack(state, acknowledged=False)
        assert not result.success

    def test_risk_ack_accepted(self) -> None:
        state = OnboardingState()
        result = handle_risk_ack(state, acknowledged=True)
        assert result.success
        assert state.risk_acknowledged

    def test_gateway_config(self) -> None:
        state = OnboardingState()
        result = handle_gateway_config(state, port=9090, bind="0.0.0.0")
        assert result.success
        assert state.gateway_port == 9090

    def test_auth_select_empty(self) -> None:
        state = OnboardingState()
        result = handle_auth_select(state, provider="")
        assert not result.success

    def test_auth_select(self) -> None:
        state = OnboardingState()
        result = handle_auth_select(state, provider="openai")
        assert result.success
        assert state.selected_provider == "openai"

    def test_provider_auth(self) -> None:
        state = OnboardingState(selected_provider="anthropic")
        result = handle_provider_auth(state, api_key="sk-ant-test123456")
        assert result.success

    def test_skills_skip(self) -> None:
        state = OnboardingState()
        result = handle_skills_install(state, skip=True)
        assert result.success

    def test_finalize(self) -> None:
        state = OnboardingState(selected_provider="openai")
        result = handle_finalize(state)
        assert result.success
        assert state.is_complete


class TestNonInteractive:
    def test_full_flow(self) -> None:
        state = run_non_interactive(
            provider="anthropic",
            api_key="sk-ant-test123456",
            port=9090,
        )
        assert state.is_complete
        assert state.gateway_port == 9090

    def test_bad_key(self) -> None:
        state = run_non_interactive(provider="openai", api_key="bad")
        assert not state.is_complete
        assert len(state.errors) > 0


class TestOnboardingState:
    def test_progress(self) -> None:
        state = OnboardingState(current_step=OnboardingStep.FINALIZE)
        assert state.progress_pct > 50


# ===== Status Enhanced =====

class TestStatusReport:
    def test_overall_ok(self) -> None:
        report = StatusReport(subsystems=[
            SubsystemStatus(name="a", level=StatusLevel.OK),
        ])
        assert report.overall_level == StatusLevel.OK

    def test_overall_error(self) -> None:
        report = StatusReport(subsystems=[
            SubsystemStatus(name="a", level=StatusLevel.OK),
            SubsystemStatus(name="b", level=StatusLevel.ERROR),
        ])
        assert report.overall_level == StatusLevel.ERROR

    def test_format(self) -> None:
        report = StatusReport(
            subsystems=[SubsystemStatus(name="test", level=StatusLevel.OK, message="good")],
            mode="summary",
        )
        text = report.format_text()
        assert "test" in text
        assert "good" in text


class TestStatusCollectors:
    def test_config_status(self) -> None:
        result = collect_config_status()
        assert result.name == "Config"

    def test_daemon_status(self) -> None:
        result = collect_daemon_status()
        assert result.name == "Daemon"

    def test_sessions_status(self) -> None:
        result = collect_sessions_status()
        assert result.name == "Sessions"


class TestGenerateReport:
    def test_generate(self) -> None:
        report = generate_status_report(mode="summary")
        assert len(report.subsystems) >= 1


# ===== Models CLI =====

class TestModelRegistry:
    def test_list_all(self) -> None:
        reg = ModelRegistry()
        models = reg.list_models()
        assert len(models) >= 10

    def test_filter_provider(self) -> None:
        reg = ModelRegistry()
        models = reg.list_models(provider="openai")
        assert all(m.provider == "openai" for m in models)

    def test_filter_capability(self) -> None:
        reg = ModelRegistry()
        models = reg.list_models(capability=ModelCapability.VISION)
        assert all(ModelCapability.VISION in m.capabilities for m in models)

    def test_get_model(self) -> None:
        reg = ModelRegistry()
        m = reg.get_model("gpt-4o")
        assert m is not None
        assert m.provider == "openai"

    def test_alias(self) -> None:
        reg = ModelRegistry()
        resolved = reg.resolve_alias("default")
        assert resolved == "gpt-4o"

    def test_set_alias(self) -> None:
        reg = ModelRegistry()
        reg.set_alias("custom", "gemini-2.0-flash")
        assert reg.resolve_alias("custom") == "gemini-2.0-flash"

    def test_remove_alias(self) -> None:
        reg = ModelRegistry()
        reg.set_alias("temp", "x")
        assert reg.remove_alias("temp")
        assert reg.resolve_alias("temp") == "temp"

    def test_fallbacks(self) -> None:
        reg = ModelRegistry()
        fb = reg.get_fallbacks("gpt-4o")
        assert len(fb) >= 1

    def test_image_fallback(self) -> None:
        reg = ModelRegistry()
        fb = reg.resolve_image_fallback("o3-mini")
        assert fb is not None

    def test_list_providers(self) -> None:
        reg = ModelRegistry()
        providers = reg.list_providers()
        assert "openai" in providers
        assert "anthropic" in providers


# ===== Channels Enhanced =====

class TestChannelSpecs:
    def test_count(self) -> None:
        assert len(CHANNEL_SPECS) >= 9

    def test_telegram_caps(self) -> None:
        caps = get_channel_capabilities("telegram")
        assert ChannelCapability.TEXT in caps
        assert ChannelCapability.GROUPS in caps

    def test_unknown_channel(self) -> None:
        assert get_channel_capabilities("nonexistent") == []


class TestValidateConfig:
    def test_valid(self) -> None:
        result = validate_channel_config("telegram", {"token": "123:ABC"})
        assert result.valid

    def test_missing_field(self) -> None:
        result = validate_channel_config("telegram", {})
        assert not result.valid
        assert "token" in result.missing_fields

    def test_unknown(self) -> None:
        result = validate_channel_config("nonexistent", {})
        assert not result.valid


class TestTransformConfig:
    def test_defaults(self) -> None:
        result = transform_channel_config("telegram", {"token": "t"})
        assert result["enabled"] is True

    def test_normalize_token(self) -> None:
        result = transform_channel_config("telegram", {"bot_token": "t"})
        assert result.get("token") == "t"


class TestListChannels:
    def test_all(self) -> None:
        channels = list_channels()
        assert len(channels) >= 9

    def test_filter_category(self) -> None:
        extensions = list_channels(category="extension")
        assert all(c.category == "extension" for c in extensions)


class TestChannelSummary:
    def test_summary(self) -> None:
        s = channel_summary("telegram", {"enabled": True})
        assert "Telegram" in s
        assert "enabled" in s
