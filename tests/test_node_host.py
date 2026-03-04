"""Tests for node host -- invoke dispatch, env sanitization."""

from __future__ import annotations

import asyncio

from pyclaw.node_host.invoke import InvokeRequest, handle_invoke, sanitize_env


class TestSanitizeEnv:
    def test_removes_dangerous_vars(self):
        import os

        os.environ["LD_PRELOAD"] = "/tmp/evil.so"
        env = sanitize_env()
        assert "LD_PRELOAD" not in env
        del os.environ["LD_PRELOAD"]

    def test_adds_overrides(self):
        env = sanitize_env({"MY_CUSTOM_VAR": "value123"})
        assert env["MY_CUSTOM_VAR"] == "value123"

    def test_removes_dyld(self):
        import os

        os.environ["DYLD_INSERT_LIBRARIES"] = "/tmp/evil.dylib"
        env = sanitize_env()
        assert "DYLD_INSERT_LIBRARIES" not in env
        del os.environ["DYLD_INSERT_LIBRARIES"]


class TestHandleInvoke:
    def test_system_which(self):
        req = InvokeRequest(id="t1", command="system.which", params={"bins": ["python3", "ls"]})
        result = asyncio.run(handle_invoke(req))
        assert result.success is True
        assert isinstance(result.result, dict)
        assert "python3" in result.result or "ls" in result.result

    def test_system_run(self):
        req = InvokeRequest(id="t2", command="system.run", params={"command": "echo hello"})
        result = asyncio.run(handle_invoke(req))
        assert result.success is True
        assert "hello" in result.result["stdout"]

    def test_system_run_failure(self):
        req = InvokeRequest(id="t3", command="system.run", params={"command": "false"})
        result = asyncio.run(handle_invoke(req))
        assert result.success is False

    def test_unknown_command(self):
        req = InvokeRequest(id="t4", command="unknown.cmd")
        result = asyncio.run(handle_invoke(req))
        assert result.success is False
        assert "Unknown command" in result.error

    def test_system_run_no_command(self):
        req = InvokeRequest(id="t5", command="system.run", params={"command": ""})
        result = asyncio.run(handle_invoke(req))
        assert result.success is False
