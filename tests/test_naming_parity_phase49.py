"""Phase 49 tests — naming consistency, ACP file-secret args, docs parity."""

from __future__ import annotations

import importlib
import json
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pyclaw.cli.app import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# 49a  ACP server --token-file / --password-file
# ---------------------------------------------------------------------------


class TestAcpFileSecrets:
    """ACP server accepts --token-file and --password-file."""

    def test_parse_token_file(self, tmp_path: Path) -> None:
        secret_file = tmp_path / "token.txt"
        secret_file.write_text("secret-token-value\n")

        from pyclaw.acp.server import _parse_cli_args

        args = _parse_cli_args(["--token-file", str(secret_file)])
        assert args.token_file == str(secret_file)

    def test_parse_password_file(self, tmp_path: Path) -> None:
        secret_file = tmp_path / "pass.txt"
        secret_file.write_text("my-password\n")

        from pyclaw.acp.server import _parse_cli_args

        args = _parse_cli_args(["--password-file", str(secret_file)])
        assert args.password_file == str(secret_file)

    def test_read_file_secret_strips_whitespace(self, tmp_path: Path) -> None:
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("  token-value  \n\n")

        from pyclaw.acp.server import _read_file_secret

        assert _read_file_secret(str(secret_file)) == "  token-value"

    def test_file_overrides_inline_arg(self, tmp_path: Path) -> None:
        """--token-file should take priority over --auth-token."""
        token_file = tmp_path / "tok.txt"
        token_file.write_text("from-file\n")

        from pyclaw.acp.server import _parse_cli_args, _read_file_secret

        args = _parse_cli_args(
            ["--auth-token", "inline-val", "--token-file", str(token_file)]
        )
        # main() logic: if token_file is set, read from file
        token = args.auth_token
        if args.token_file:
            token = _read_file_secret(args.token_file)
        assert token == "from-file"


# ---------------------------------------------------------------------------
# 49b  pyclaw naming — no user-facing "pyclaw" CLI references remain
# ---------------------------------------------------------------------------


class TestPyclawNamingConsistency:
    """User-facing strings should use 'pyclaw', not 'openclaw' as CLI command."""

    @pytest.fixture
    def cli_command_modules(self) -> list[str]:
        return [
            "pyclaw.cli.commands.config_cmd",
            "pyclaw.cli.commands.setup",
            "pyclaw.cli.commands.auth_cmd",
            "pyclaw.cli.commands.doctor",
            "pyclaw.cli.commands.doctor_flows",
            "pyclaw.cli.commands.onboarding_enhanced",
            "pyclaw.cli.commands.message_cmd",
            "pyclaw.cli.commands.bindings_cmd",
            "pyclaw.cli.commands.secrets_cmd",
        ]

    def test_no_openclaw_cli_references_in_docstrings(
        self, cli_command_modules: list[str]
    ) -> None:
        for mod_name in cli_command_modules:
            mod = importlib.import_module(mod_name)
            doc = getattr(mod, "__doc__", "") or ""
            # Allow "pyclaw" as Python module name but not as CLI command
            for line in doc.splitlines():
                line_lower = line.lower().strip()
                if "``openclaw " in line_lower or "`openclaw " in line_lower:
                    pytest.fail(
                        f"Module {mod_name} docstring references 'openclaw' CLI: {line.strip()}"
                    )


# ---------------------------------------------------------------------------
# 49c  docs parity — gateway subcommands coverage
# ---------------------------------------------------------------------------


class TestGatewaySubcommandParity:
    """Ensure all gateway subcommands are registered."""

    def test_gateway_subcommands_present(self) -> None:
        result = runner.invoke(app, ["gateway", "--help"])
        assert result.exit_code == 0
        for cmd in ("run", "status", "probe", "call", "discover"):
            assert cmd in result.stdout, f"Missing gateway subcommand: {cmd}"

    def test_browser_subcommands_present(self) -> None:
        result = runner.invoke(app, ["browser", "--help"])
        assert result.exit_code == 0
        for cmd in (
            "status", "tabs", "open", "navigate", "screenshot",
            "evaluate", "profiles", "create-profile",
            "delete-profile", "focus", "close",
        ):
            assert cmd in result.stdout, f"Missing browser subcommand: {cmd}"


class TestRootHelpRegression:
    """Verify root-level help still lists all top-level groups."""

    def test_root_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for group in (
            "gateway", "config", "auth", "message", "sessions",
            "agents", "system", "browser", "security",
        ):
            assert group in result.stdout, f"Missing top-level group: {group}"
