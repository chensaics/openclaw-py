"""Tests for configuration loading and Pydantic models."""

import json
import tempfile
from pathlib import Path

from pyclaw.config.io import load_config, save_config
from pyclaw.config.paths import resolve_state_dir
from pyclaw.config.schema import ModelProviderConfig, ModelsConfig, PyClawConfig


def test_empty_config():
    cfg = PyClawConfig()
    assert cfg.models is None
    assert cfg.gateway is None


def test_config_with_models():
    cfg = PyClawConfig(
        models=ModelsConfig(
            providers={
                "anthropic": ModelProviderConfig(
                    base_url="https://api.anthropic.com",
                    api_key="sk-test",
                    api="anthropic-messages",
                    models=[],
                ),
            }
        )
    )
    assert cfg.models is not None
    assert cfg.models.providers is not None
    assert "anthropic" in cfg.models.providers
    assert cfg.models.providers["anthropic"].base_url == "https://api.anthropic.com"


def test_config_camelcase_compat():
    """Config should parse camelCase JSON (from TypeScript version)."""
    data = {
        "models": {
            "providers": {
                "openai": {
                    "baseUrl": "https://api.openai.com/v1",
                    "apiKey": "sk-test",
                    "models": [
                        {
                            "id": "gpt-4o",
                            "name": "GPT-4o",
                            "contextWindow": 128000,
                            "maxTokens": 16384,
                        }
                    ],
                }
            }
        },
        "gateway": {
            "mode": "local",
            "port": 18789,
        },
        "session": {
            "typingMode": "thinking",
            "idleMinutes": 30,
        },
    }
    cfg = PyClawConfig.model_validate(data)
    assert cfg.models is not None
    provider = cfg.models.providers["openai"]
    assert provider.base_url == "https://api.openai.com/v1"
    assert provider.models[0].context_window == 128000
    assert cfg.gateway is not None
    assert cfg.gateway.mode == "local"
    assert cfg.session is not None
    assert cfg.session.typing_mode == "thinking"


def test_config_preserves_unknown_fields():
    """Unknown fields should be preserved (extra='allow')."""
    data = {
        "gateway": {
            "mode": "local",
            "someNewField": "value",
        },
        "brandNewSection": {"key": "val"},
    }
    cfg = PyClawConfig.model_validate(data)
    assert cfg.gateway is not None
    assert cfg.gateway.mode == "local"
    # Extra fields preserved in model_extra
    dumped = cfg.model_dump(by_alias=True, exclude_none=True)
    assert dumped["brandNewSection"] == {"key": "val"}


def test_config_roundtrip():
    """Config should survive load -> save -> load."""
    data = {
        "models": {
            "providers": {
                "test": {
                    "baseUrl": "http://localhost:11434",
                    "models": [{"id": "llama3", "name": "Llama 3"}],
                }
            }
        },
        "gateway": {"mode": "local", "port": 18789},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        tmp_path = Path(f.name)

    try:
        cfg = load_config(tmp_path)
        save_config(cfg, tmp_path)
        cfg2 = load_config(tmp_path)

        assert cfg2.models is not None
        assert "test" in cfg2.models.providers
        assert cfg2.gateway is not None
        assert cfg2.gateway.port == 18789
    finally:
        tmp_path.unlink(missing_ok=True)


def test_paths_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr("pyclaw.config.paths._homedir", lambda: tmp_path)
    state_dir = resolve_state_dir(env={})
    assert state_dir == tmp_path / ".pyclaw"
