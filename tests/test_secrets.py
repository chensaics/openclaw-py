"""Tests for secrets module — audit, resolve, plan, apply, runtime."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pyclaw.config.secrets import SecretRef
from pyclaw.secrets.audit import _looks_like_plaintext_key, run_secrets_audit
from pyclaw.secrets.plan import SecretProviderSetup, SecretsApplyPlan, SecretsPlanTarget
from pyclaw.secrets.resolve import SecretRefResolveCache, resolve_secret_ref_value
from pyclaw.secrets.runtime import SecretsRuntime

# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------


class TestResolveSecretRef:
    def test_env_ref(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_API_KEY", "sk-test-123")
        ref = SecretRef(source="env", provider="default", id="MY_API_KEY")
        result = resolve_secret_ref_value(ref)
        assert result == "sk-test-123"

    def test_env_ref_missing(self) -> None:
        ref = SecretRef(source="env", provider="default", id="NONEXISTENT_VAR_12345")
        result = resolve_secret_ref_value(ref)
        assert result is None

    def test_file_ref(self, tmp_path: Path) -> None:
        secret_file = tmp_path / "api_key.txt"
        secret_file.write_text("sk-file-secret\n")
        ref = SecretRef(source="file", provider="default", id=str(secret_file))
        result = resolve_secret_ref_value(ref)
        assert result == "sk-file-secret"

    def test_file_ref_missing(self) -> None:
        ref = SecretRef(source="file", provider="default", id="/nonexistent/path")
        result = resolve_secret_ref_value(ref)
        assert result is None

    def test_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CACHED_KEY", "cached-value")
        cache = SecretRefResolveCache()
        ref = SecretRef(source="env", provider="default", id="CACHED_KEY")

        result1 = resolve_secret_ref_value(ref, cache=cache)
        assert result1 == "cached-value"
        assert cache.has(ref)

        # Change env, cache should still return old value
        monkeypatch.setenv("CACHED_KEY", "new-value")
        result2 = resolve_secret_ref_value(ref, cache=cache)
        assert result2 == "cached-value"


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


class TestSecretsApplyPlan:
    def test_roundtrip(self) -> None:
        plan = SecretsApplyPlan(
            targets=[
                SecretsPlanTarget(
                    path="models.providers.openai.apiKey",
                    ref=SecretRef(source="env", provider="default", id="OPENAI_API_KEY"),
                )
            ],
            providers={"default": SecretProviderSetup(kind="env")},
            scrub_legacy=True,
        )
        data = plan.to_dict()
        restored = SecretsApplyPlan.from_dict(data)
        assert len(restored.targets) == 1
        assert restored.targets[0].path == "models.providers.openai.apiKey"
        assert restored.targets[0].ref.source == "env"
        assert restored.scrub_legacy is True

    def test_empty_plan(self) -> None:
        plan = SecretsApplyPlan.from_dict({})
        assert plan.targets == []
        assert plan.providers == {}


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class TestLooksLikePlaintext:
    def test_openai_key(self) -> None:
        assert _looks_like_plaintext_key("sk-1234567890abcdef") is True

    def test_anthropic_key(self) -> None:
        assert _looks_like_plaintext_key("sk-ant-api-key-here") is True

    def test_short_string(self) -> None:
        assert _looks_like_plaintext_key("short") is False

    def test_not_a_key(self) -> None:
        assert _looks_like_plaintext_key("just a regular string value") is False


class TestSecretsAudit:
    def test_audit_empty_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "pyclaw.json"
        config_path.write_text("{}")
        report = run_secrets_audit(state_dir=tmp_path, config_path=config_path)
        assert report.status == "clean"
        assert len(report.findings) == 0

    def test_audit_detects_plaintext(self, tmp_path: Path) -> None:
        config_path = tmp_path / "pyclaw.json"
        config_data = {
            "models": {
                "providers": {
                    "openai": {
                        "baseUrl": "https://api.openai.com/v1",
                        "apiKey": "sk-1234567890abcdef1234567890abcdef",
                    }
                }
            }
        }
        config_path.write_text(json.dumps(config_data))
        report = run_secrets_audit(state_dir=tmp_path, config_path=config_path)
        assert report.status != "clean"
        assert report.summary["plaintext_count"] > 0


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------


class TestSecretsRuntime:
    def test_resolve_string(self) -> None:
        rt = SecretsRuntime()
        assert rt.resolve_from_config_value("plain-value") == "plain-value"

    def test_resolve_empty_string(self) -> None:
        rt = SecretsRuntime()
        assert rt.resolve_from_config_value("") is None

    def test_reload(self) -> None:
        rt = SecretsRuntime()
        rt.reload()
        assert rt.last_reload > 0
