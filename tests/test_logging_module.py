"""Tests for logging subsystem -- subsystem logger and redact."""

from __future__ import annotations

import pytest

from pyclaw.logging.subsystem import SubsystemLogger, create_subsystem_logger, CHANNEL_SUBSYSTEM_PREFIXES
from pyclaw.logging.redact import redact_sensitive_text, redact_tool_detail, set_custom_redact_patterns


class TestSubsystemLogger:
    def test_create(self):
        logger = create_subsystem_logger("gateway")
        assert isinstance(logger, SubsystemLogger)

    def test_child_logger(self):
        parent = create_subsystem_logger("gateway")
        child = parent.child("ws")
        assert isinstance(child, SubsystemLogger)

    def test_channel_prefixes(self):
        assert isinstance(CHANNEL_SUBSYSTEM_PREFIXES, frozenset)
        assert len(CHANNEL_SUBSYSTEM_PREFIXES) > 0

    def test_log_methods_exist(self):
        logger = create_subsystem_logger("test")
        assert callable(logger.trace)
        assert callable(logger.debug)
        assert callable(logger.info)
        assert callable(logger.warn)
        assert callable(logger.error)
        assert callable(logger.fatal)


class TestRedact:
    def test_redact_api_key(self):
        key = "sk-proj-" + "a" * 30
        text = f"Key: {key}"
        result = redact_sensitive_text(text)
        assert key not in result
        assert "[REDACTED]" in result

    def test_redact_auth_header(self):
        text = "X-API-Key: mysecretkey123"
        result = redact_sensitive_text(text)
        assert "mysecretkey123" not in result
        assert "[REDACTED]" in result

    def test_no_redact_normal_text(self):
        text = "Hello world, this is a normal message"
        result = redact_sensitive_text(text)
        assert result == text

    def test_redact_tool_detail_off_mode(self):
        result = redact_tool_detail("exec", "ls -la", mode="off")
        assert result == "ls -la"

    def test_redact_tool_detail_tools_mode(self):
        result = redact_tool_detail("exec", "export API_KEY=sk-secret123", mode="tools")
        assert isinstance(result, str)

    def test_custom_redact_patterns(self):
        set_custom_redact_patterns(["secret_\\w+"])
        text = "Found secret_abc123 in config"
        result = redact_sensitive_text(text)
        assert "secret_abc123" not in result
        set_custom_redact_patterns([])
