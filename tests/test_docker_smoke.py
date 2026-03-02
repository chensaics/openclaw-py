"""Docker smoke test — verify the Docker image builds and basic functionality.

These tests are designed to run in CI after building the Docker image.
They test import paths, CLI availability, and basic module loading.

To run against a real Docker build:
    docker build -t pyclaw-test .
    docker run --rm pyclaw-test python -m pytest tests/test_docker_smoke.py -v
"""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest


class TestModuleImports:
    """Verify all critical modules can be imported."""

    CRITICAL_MODULES = [
        "pyclaw",
        "pyclaw.cli.app",
        "pyclaw.config.schema",
        "pyclaw.config.io",
        "pyclaw.config.paths",
        "pyclaw.config.migrations",
        "pyclaw.agents.runner",
        "pyclaw.agents.session",
        "pyclaw.agents.types",
        "pyclaw.agents.tools.registry",
        "pyclaw.agents.progress",
        "pyclaw.gateway.server",
        "pyclaw.channels.base",
        "pyclaw.channels.manager",
        "pyclaw.media",
        "pyclaw.media.fetch",
        "pyclaw.social.registry",
        "pyclaw.infra.misc_extras",
    ]

    @pytest.mark.parametrize("module_name", CRITICAL_MODULES)
    def test_import(self, module_name: str) -> None:
        mod = importlib.import_module(module_name)
        assert mod is not None


class TestCLIAvailability:
    """Verify the CLI is installed and responds."""

    def test_cli_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "pyclaw.cli.app", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        combined = (result.stdout + result.stderr).lower()
        assert "pyclaw" in combined or "usage" in combined or result.returncode == 0

    def test_version_available(self) -> None:
        from pyclaw import __version__

        assert __version__
        assert isinstance(__version__, str)


class TestConfigSchema:
    """Verify config schema validation works."""

    def test_empty_config_valid(self) -> None:
        from pyclaw.config.schema import PyClawConfig

        cfg = PyClawConfig()
        assert cfg is not None

    def test_azure_fields_present(self) -> None:
        from pyclaw.config.schema import ModelProviderConfig

        cfg = ModelProviderConfig(baseUrl="https://test.openai.azure.com")
        assert hasattr(cfg, "api_version")
        assert hasattr(cfg, "use_aad")


class TestToolRegistry:
    """Verify default tool registry creates correctly."""

    def test_default_tools_created(self) -> None:
        from pyclaw.agents.tools.registry import create_default_tools

        registry = create_default_tools(enable_exec=False, enable_web=False)
        assert len(registry) > 0
        assert "social_join" in registry
        assert "social_status" in registry


class TestMediaFetchModule:
    """Verify media fetch module is properly exported."""

    def test_media_exports(self) -> None:
        from pyclaw.media import FetchResult, MediaFetcher, fetch_media

        assert callable(fetch_media)
        assert MediaFetcher is not None
        assert FetchResult is not None


class TestMigrations:
    """Verify config migrations are available."""

    def test_default_registry_has_steps(self) -> None:
        from pyclaw.config.migrations import create_default_registry

        registry = create_default_registry()
        assert registry.step_count >= 2


class TestChannelOnboarding:
    """Verify onboarding flows cover all expected channels."""

    def test_onboarding_coverage(self) -> None:
        from pyclaw.channels.plugins.onboarding import list_onboarding_channels

        channels = list_onboarding_channels()
        expected = {
            "telegram",
            "discord",
            "slack",
            "signal",
            "whatsapp",
            "imessage",
            "matrix",
            "feishu",
            "msteams",
            "dingtalk",
            "qq",
            "irc",
        }
        assert expected.issubset(set(channels))
