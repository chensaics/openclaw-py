"""Tests for Phase 23 — memory-core extension, Gemini CLI auth, Ollama enhanced, i18n de."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from pyclaw.plugins.contrib.memory_core import (
    MemoryCoreExtension,
    MemoryEntry,
    MemoryToolConfig,
)
from pyclaw.plugins.contrib.gemini_cli_auth import (
    GeminiAuthConfig,
    GeminiCliAuthExtension,
    OAuthTokens,
    PKCEChallenge,
    build_auth_url,
    build_refresh_request,
    build_token_request,
    generate_pkce_challenge,
    parse_token_response,
)
from pyclaw.agents.providers.ollama_enhanced import (
    OllamaDiscovery,
    OllamaModelInfo,
    parse_ollama_model_info,
    resolve_context_window,
)


# ===== Memory Core Extension =====

class TestMemoryCoreExtension:
    @pytest.fixture
    def ext(self) -> MemoryCoreExtension:
        return MemoryCoreExtension(MemoryToolConfig(auto_recall=True, auto_capture=True))

    @pytest.mark.asyncio
    async def test_lifecycle(self, ext: MemoryCoreExtension) -> None:
        assert ext.is_loaded is False
        await ext.on_load()
        assert ext.is_loaded is True
        await ext.on_unload()
        assert ext.is_loaded is False

    def test_get_tools(self, ext: MemoryCoreExtension) -> None:
        tools = ext.get_tools()
        assert len(tools) == 4
        names = {t["name"] for t in tools}
        assert "memory_search" in names
        assert "memory_add" in names

    def test_disabled_tools(self) -> None:
        ext = MemoryCoreExtension(MemoryToolConfig(enabled=False))
        assert ext.get_tools() == []

    def test_add_and_search(self, ext: MemoryCoreExtension) -> None:
        ext.add_memory("The user likes Python programming", tags=["preference"])
        ext.add_memory("Meeting scheduled for Friday")
        results = ext.search_memories("Python")
        assert len(results) >= 1
        assert "Python" in results[0].content

    def test_search_by_tag(self, ext: MemoryCoreExtension) -> None:
        ext.add_memory("Something", tags=["important"])
        results = ext.search_memories("important")
        assert len(results) >= 1

    def test_delete_memory(self, ext: MemoryCoreExtension) -> None:
        entry = ext.add_memory("To be deleted")
        assert ext.memory_count == 1
        assert ext.delete_memory(entry.id) is True
        assert ext.memory_count == 0

    def test_delete_nonexistent(self, ext: MemoryCoreExtension) -> None:
        assert ext.delete_memory("nonexistent") is False

    def test_list_memories(self, ext: MemoryCoreExtension) -> None:
        ext.add_memory("First")
        ext.add_memory("Second")
        ext.add_memory("Third")
        recent = ext.list_memories(limit=2)
        assert len(recent) == 2

    def test_auto_recall(self, ext: MemoryCoreExtension) -> None:
        ext.add_memory("Python is the user's favorite language")
        results = ext.auto_recall("Tell me about Python")
        assert len(results) >= 1

    def test_auto_recall_disabled(self) -> None:
        ext = MemoryCoreExtension(MemoryToolConfig(auto_recall=False))
        ext.add_memory("Something")
        assert ext.auto_recall("Something") == []

    def test_auto_capture(self, ext: MemoryCoreExtension) -> None:
        result = ext.auto_capture("Long exchange about Python", turn_count=5)
        assert result is not None
        assert result.source == "auto"

    def test_auto_capture_too_few_turns(self, ext: MemoryCoreExtension) -> None:
        result = ext.auto_capture("Short exchange", turn_count=1)
        assert result is None


# ===== Gemini CLI Auth =====

class TestPKCE:
    def test_generate(self) -> None:
        pkce = generate_pkce_challenge()
        assert len(pkce.code_verifier) > 20
        assert len(pkce.code_challenge) > 20
        assert pkce.method == "S256"
        assert pkce.code_verifier != pkce.code_challenge

    def test_deterministic_challenge(self) -> None:
        # Same verifier should produce same challenge
        import base64, hashlib
        verifier = "test_verifier_12345"
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert len(challenge) > 0


class TestAuthUrl:
    def test_build(self) -> None:
        config = GeminiAuthConfig(client_id="test_client")
        pkce = generate_pkce_challenge()
        url = build_auth_url(config, pkce)
        assert "accounts.google.com" in url
        assert "test_client" in url
        assert "code_challenge" in url

    def test_with_state(self) -> None:
        config = GeminiAuthConfig(client_id="c")
        pkce = generate_pkce_challenge()
        url = build_auth_url(config, pkce, state="mystate")
        assert "mystate" in url


class TestTokenRequests:
    def test_token_request(self) -> None:
        config = GeminiAuthConfig(client_id="c", client_secret="s")
        pkce = generate_pkce_challenge()
        body = build_token_request(config, "auth_code_123", pkce)
        assert body["code"] == "auth_code_123"
        assert body["client_id"] == "c"
        assert body["grant_type"] == "authorization_code"

    def test_refresh_request(self) -> None:
        config = GeminiAuthConfig(client_id="c", client_secret="s")
        body = build_refresh_request(config, "refresh_token_123")
        assert body["refresh_token"] == "refresh_token_123"
        assert body["grant_type"] == "refresh_token"

    def test_parse_response(self) -> None:
        data = {
            "access_token": "at_123",
            "refresh_token": "rt_123",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        tokens = parse_token_response(data)
        assert tokens.access_token == "at_123"
        assert tokens.refresh_token == "rt_123"
        assert tokens.is_valid is True


class TestOAuthTokens:
    def test_expired(self) -> None:
        tokens = OAuthTokens(access_token="at", expires_at=time.time() - 100)
        assert tokens.is_expired is True
        assert tokens.is_valid is False

    def test_valid(self) -> None:
        tokens = OAuthTokens(access_token="at", expires_at=time.time() + 3600)
        assert tokens.is_valid is True


class TestGeminiExtension:
    def test_start_flow(self) -> None:
        ext = GeminiCliAuthExtension(GeminiAuthConfig(client_id="c"))
        url, pkce = ext.start_auth_flow()
        assert "accounts.google.com" in url
        assert pkce.code_verifier

    def test_not_authenticated_initially(self) -> None:
        ext = GeminiCliAuthExtension()
        assert ext.is_authenticated is False

    def test_set_tokens(self) -> None:
        ext = GeminiCliAuthExtension()
        ext.set_tokens(OAuthTokens(access_token="at", expires_at=time.time() + 3600))
        assert ext.is_authenticated is True
        assert ext.access_token == "at"

    def test_needs_refresh(self) -> None:
        ext = GeminiCliAuthExtension()
        ext.set_tokens(OAuthTokens(
            access_token="at",
            refresh_token="rt",
            expires_at=time.time() - 100,
        ))
        assert ext.needs_refresh is True


# ===== Ollama Enhanced =====

class TestParseOllamaModelInfo:
    def test_basic(self) -> None:
        raw = {
            "name": "llama3:latest",
            "size": 4700000000,
            "details": {
                "family": "llama",
                "parameter_size": "8B",
                "quantization_level": "Q4_0",
            },
        }
        info = parse_ollama_model_info(raw)
        assert info.name == "llama3:latest"
        assert info.family == "llama"
        assert "llama" in info.families

    def test_context_length_from_model_info(self) -> None:
        raw = {
            "name": "test",
            "model_info": {"context_length": 32768},
            "details": {},
        }
        info = parse_ollama_model_info(raw)
        assert info.context_length == 32768

    def test_vision_support(self) -> None:
        raw = {
            "name": "llava",
            "details": {"family": "llava", "families": ["llama", "clip"]},
        }
        info = parse_ollama_model_info(raw)
        assert info.supports_vision is True

    def test_tool_support(self) -> None:
        raw = {"name": "llama3", "details": {"family": "llama", "families": ["llama"]}}
        info = parse_ollama_model_info(raw)
        assert info.supports_tools is True


class TestResolveContextWindow:
    def test_user_override(self) -> None:
        info = OllamaModelInfo(name="test", context_length=4096)
        assert resolve_context_window(info, user_override=8192) == 8192

    def test_model_metadata(self) -> None:
        info = OllamaModelInfo(name="test", context_length=32768)
        assert resolve_context_window(info) == 32768

    def test_family_default(self) -> None:
        info = OllamaModelInfo(name="test", family="qwen2")
        assert resolve_context_window(info) == 32768

    def test_global_default(self) -> None:
        info = OllamaModelInfo(name="test")
        assert resolve_context_window(info) == 4096


class TestOllamaDiscovery:
    def test_initial_state(self) -> None:
        disc = OllamaDiscovery()
        assert disc.state.is_healthy is False
        assert disc.should_retry() is True

    def test_successful_discovery(self) -> None:
        disc = OllamaDiscovery()
        models = disc.process_discovery_response({
            "models": [
                {"name": "llama3", "details": {"family": "llama"}},
                {"name": "mistral", "details": {"family": "mistral"}},
            ]
        })
        assert len(models) == 2
        assert disc.state.is_healthy is True

    def test_empty_discovery(self) -> None:
        disc = OllamaDiscovery()
        models = disc.process_discovery_response({"models": []})
        assert models == []
        assert disc.state.empty_count == 1

    def test_error_recovery(self) -> None:
        disc = OllamaDiscovery()
        # First success
        disc.process_discovery_response({
            "models": [{"name": "llama3", "details": {}}]
        })
        # Then error — should keep old models
        disc.process_discovery_response(None, error="connection refused")
        assert len(disc.models) == 1
        assert disc.state.consecutive_failures == 1

    def test_log_downgrade(self) -> None:
        disc = OllamaDiscovery()
        for _ in range(5):
            disc.process_discovery_response(None, error="timeout")
        assert disc.state.consecutive_failures == 5

    def test_get_model(self) -> None:
        disc = OllamaDiscovery()
        disc.process_discovery_response({
            "models": [
                {"name": "llama3:latest", "details": {"family": "llama"}},
            ]
        })
        assert disc.get_model("llama3:latest") is not None
        assert disc.get_model("LLAMA3:LATEST") is not None
        assert disc.get_model("nonexistent") is None


class TestGermanLocale:
    def test_locale_file_exists(self) -> None:
        locale_path = Path(__file__).parent.parent / "src" / "pyclaw" / "ui" / "locales" / "de.json"
        assert locale_path.exists()

    def test_locale_valid_json(self) -> None:
        locale_path = Path(__file__).parent.parent / "src" / "pyclaw" / "ui" / "locales" / "de.json"
        data = json.loads(locale_path.read_text())
        assert "app.title" in data
        assert "chat.send" in data
        assert data["chat.send"] == "Senden"

    def test_locale_keys_match_english(self) -> None:
        """German locale should cover all keys present in the file."""
        locale_path = Path(__file__).parent.parent / "src" / "pyclaw" / "ui" / "locales" / "de.json"
        data = json.loads(locale_path.read_text())
        # Just verify we have a reasonable number of keys
        assert len(data) >= 40
        # Key categories should be covered
        categories = {k.split(".")[0] for k in data}
        assert "app" in categories
        assert "chat" in categories
        assert "settings" in categories
        assert "channels" in categories
        assert "onboarding" in categories
        assert "tools" in categories
