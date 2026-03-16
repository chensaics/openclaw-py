"""Tests for gateway method handlers -- creation and basic dispatch."""

from __future__ import annotations

from pyclaw.gateway.methods.agents import create_agents_handlers
from pyclaw.gateway.methods.channels import create_channels_handlers
from pyclaw.gateway.methods.chat import create_chat_handlers
from pyclaw.gateway.methods.config_methods import create_config_handlers
from pyclaw.gateway.methods.cron_methods import create_cron_handlers
from pyclaw.gateway.methods.device_pair import create_device_pair_handlers
from pyclaw.gateway.methods.health import create_health_handlers
from pyclaw.gateway.methods.models import create_models_handlers
from pyclaw.gateway.methods.sessions import create_session_handlers
from pyclaw.gateway.methods.tools_catalog import create_tools_handlers


class TestHandlerFactories:
    """Verify all handler factories return callables."""

    def test_config_handlers(self):
        handlers = create_config_handlers()
        assert isinstance(handlers, dict)
        assert "config.get" in handlers
        assert "config.set" in handlers
        assert callable(handlers["config.get"])

    def test_health_handlers(self):
        handlers = create_health_handlers()
        assert isinstance(handlers, dict)
        assert "health" in handlers or "status" in handlers
        for h in handlers.values():
            assert callable(h)

    def test_session_handlers(self):
        handlers = create_session_handlers()
        assert isinstance(handlers, dict)
        expected = [
            "sessions.list",
            "sessions.preview",
            "sessions.delete",
            "sessions.reset",
            "sessions.get",
            "sessions.create",
            "sessions.cleanup",
        ]
        for key in expected:
            assert key in handlers, f"Missing handler: {key}"

    def test_chat_handlers(self):
        handlers = create_chat_handlers()
        assert isinstance(handlers, dict)
        assert "chat.send" in handlers
        assert "chat.abort" in handlers

    def test_models_handlers(self):
        handlers = create_models_handlers()
        assert isinstance(handlers, dict)
        assert "models.list" in handlers

    def test_agents_handlers(self):
        handlers = create_agents_handlers()
        assert isinstance(handlers, dict)
        assert "agents.list" in handlers

    def test_channels_handlers(self):
        handlers = create_channels_handlers()
        assert isinstance(handlers, dict)
        assert "channels.list" in handlers

    def test_tools_handlers(self):
        handlers = create_tools_handlers()
        assert isinstance(handlers, dict)
        assert "tools.catalog" in handlers or "tools.list" in handlers

    def test_cron_handlers(self):
        handlers = create_cron_handlers()
        assert isinstance(handlers, dict)
        assert "cron.list" in handlers

    def test_device_pair_handlers(self):
        handlers = create_device_pair_handlers()
        assert isinstance(handlers, dict)
        assert "device.pair.list" in handlers or "device.pair.code" in handlers
