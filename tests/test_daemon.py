"""Tests for daemon/service — plist generation, unit file, service abstraction."""

from __future__ import annotations

import platform

import pytest

from pyclaw.daemon.launchd import build_launch_agent_plist
from pyclaw.daemon.service import GatewayServiceInstallArgs, resolve_gateway_service


class TestBuildLaunchAgentPlist:
    def test_basic_plist(self):
        args = GatewayServiceInstallArgs(
            label="ai.pyclaw.gateway",
            program="/usr/bin/python3",
            arguments=["-m", "pyclaw", "gateway", "--port", "18789"],
            working_directory="/Users/test",
        )
        plist = build_launch_agent_plist(args)

        assert plist["Label"] == "ai.pyclaw.gateway"
        assert plist["ProgramArguments"][0] == "/usr/bin/python3"
        assert plist["ProgramArguments"][1] == "-m"
        assert plist["RunAtLoad"] is True
        assert plist["KeepAlive"] is True
        assert plist["ThrottleInterval"] == 10
        assert plist["WorkingDirectory"] == "/Users/test"

    def test_environment_variables(self):
        args = GatewayServiceInstallArgs(
            label="test",
            program="python3",
            environment={"PYCLAW_ENV": "production", "PATH": "/usr/bin"},
        )
        plist = build_launch_agent_plist(args)
        assert plist["EnvironmentVariables"]["PYCLAW_ENV"] == "production"
        assert plist["EnvironmentVariables"]["PATH"] == "/usr/bin"

    def test_log_paths(self):
        args = GatewayServiceInstallArgs(label="test", program="python3", log_dir="/tmp/logs")
        plist = build_launch_agent_plist(args)
        assert plist["StandardOutPath"] == "/tmp/logs/gateway.stdout.log"
        assert plist["StandardErrorPath"] == "/tmp/logs/gateway.stderr.log"

    def test_default_log_dir(self):
        args = GatewayServiceInstallArgs(label="test", program="python3")
        plist = build_launch_agent_plist(args)
        assert "gateway.stdout.log" in plist["StandardOutPath"]


class TestSystemdUnit:
    def test_build_unit(self):
        from pyclaw.daemon.systemd import _build_unit

        args = GatewayServiceInstallArgs(
            label="ai.pyclaw.gateway",
            program="/usr/bin/python3",
            arguments=["-m", "pyclaw", "gateway"],
            environment={"NODE_ENV": "production"},
        )
        unit = _build_unit(args)
        assert "[Unit]" in unit
        assert "[Service]" in unit
        assert "[Install]" in unit
        assert "ExecStart=/usr/bin/python3 -m pyclaw gateway" in unit
        assert "Environment=NODE_ENV=production" in unit
        assert "Restart=on-failure" in unit


class TestResolveGatewayService:
    def test_returns_service(self):
        svc = resolve_gateway_service()
        assert svc is not None

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    def test_macos_returns_launchd(self):
        from pyclaw.daemon.launchd import LaunchdService

        svc = resolve_gateway_service()
        assert isinstance(svc, LaunchdService)
