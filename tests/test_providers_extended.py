"""Tests for Phase 26 — OpenAI-compat adapter, Chinese providers, OAuth flows, Bedrock."""

from __future__ import annotations

import pytest

from pyclaw.agents.providers.bedrock import (
    BEDROCK_MODELS,
    BedrockConfig,
    BedrockProvider,
    ConverseMessage,
)
from pyclaw.agents.providers.cn_providers import (
    ALL_CN_PROVIDERS,
    MOONSHOT_SPEC,
    build_cn_config,
    get_cn_provider_models,
    list_cn_providers,
)
from pyclaw.agents.providers.oauth_providers import (
    CopilotDeviceFlow,
    MiniMaxOAuthConfig,
    MiniMaxOAuthFlow,
    QwenOAuthConfig,
    QwenOAuthFlow,
    generate_code_challenge,
    generate_code_verifier,
)
from pyclaw.agents.providers.openai_compat import (
    PRECONFIGURED_PROVIDERS,
    ChatMessage,
    ModelMapping,
    OpenAICompatConfig,
    OpenAICompatProvider,
    fireworks_config,
    groq_config,
    openrouter_config,
    perplexity_config,
    together_config,
)
from pyclaw.agents.providers.registry import (
    ProviderRegistry,
    activate_provider,
    create_default_registry,
)

# ===== OpenAI-Compat Provider =====


class TestOpenAICompatProvider:
    def test_create_provider(self) -> None:
        config = OpenAICompatConfig(
            name="test",
            base_url="https://api.example.com",
            api_key="sk-test",
            models=[ModelMapping("gpt-4o", "gpt-4o-2024-08-06", context_window=128000)],
        )
        provider = OpenAICompatProvider(config)
        assert provider.name == "test"
        assert provider.base_url == "https://api.example.com"

    def test_resolve_model_alias(self) -> None:
        config = OpenAICompatConfig(
            name="test",
            base_url="https://api.example.com",
            models=[ModelMapping("fast", "gpt-4o-mini", context_window=128000)],
        )
        provider = OpenAICompatProvider(config)
        assert provider.resolve_model("fast") == "gpt-4o-mini"

    def test_resolve_unknown_model(self) -> None:
        config = OpenAICompatConfig(name="test", base_url="https://api.example.com")
        provider = OpenAICompatProvider(config)
        assert provider.resolve_model("unknown-model") == "unknown-model"

    def test_build_headers(self) -> None:
        config = OpenAICompatConfig(
            name="test",
            base_url="https://api.example.com",
            api_key="sk-test",
            extra_headers={"X-Custom": "value"},
        )
        provider = OpenAICompatProvider(config)
        headers = provider.build_headers()
        assert headers["Authorization"] == "Bearer sk-test"
        assert headers["X-Custom"] == "value"

    def test_build_request_body(self) -> None:
        config = OpenAICompatConfig(name="test", base_url="https://api.example.com")
        provider = OpenAICompatProvider(config)
        messages = [ChatMessage(role="user", content="Hello")]
        body = provider.build_request_body(messages, "gpt-4o", stream=True, temperature=0.7)
        assert body["model"] == "gpt-4o"
        assert body["stream"] is True
        assert body["temperature"] == 0.7
        assert len(body["messages"]) == 1

    def test_system_role_conversion(self) -> None:
        config = OpenAICompatConfig(
            name="test",
            base_url="https://api.example.com",
            supports_system_role=False,
        )
        provider = OpenAICompatProvider(config)
        messages = [ChatMessage(role="system", content="Be helpful")]
        body = provider.build_request_body(messages, "model")
        assert body["messages"][0]["role"] == "user"

    def test_parse_sse_chunk(self) -> None:
        config = OpenAICompatConfig(name="test", base_url="https://api.example.com")
        provider = OpenAICompatProvider(config)

        line = 'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}],"model":"gpt-4o"}'
        chunk = provider.parse_sse_chunk(line)
        assert chunk is not None
        assert chunk.delta_content == "Hello"
        assert chunk.model == "gpt-4o"

    def test_parse_sse_done(self) -> None:
        config = OpenAICompatConfig(name="test", base_url="https://api.example.com")
        provider = OpenAICompatProvider(config)
        chunk = provider.parse_sse_chunk("data: [DONE]")
        assert chunk is not None
        assert chunk.finish_reason == "stop"

    def test_parse_sse_non_data(self) -> None:
        config = OpenAICompatConfig(name="test", base_url="https://api.example.com")
        provider = OpenAICompatProvider(config)
        assert provider.parse_sse_chunk("event: ping") is None

    def test_parse_completion(self) -> None:
        config = OpenAICompatConfig(name="test", base_url="https://api.example.com")
        provider = OpenAICompatProvider(config)
        response = {
            "choices": [{"message": {"content": "Hi there"}, "finish_reason": "stop"}],
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        result = provider.parse_completion(response)
        assert result.content == "Hi there"
        assert result.finish_reason == "stop"

    def test_get_endpoint(self) -> None:
        config = OpenAICompatConfig(name="test", base_url="https://api.example.com")
        provider = OpenAICompatProvider(config)
        assert provider.get_endpoint() == "https://api.example.com/v1/chat/completions"

    def test_list_models(self) -> None:
        config = OpenAICompatConfig(
            name="test",
            base_url="https://api.example.com",
            models=[
                ModelMapping("model-a", "real-a"),
                ModelMapping("model-b", "real-b"),
            ],
        )
        provider = OpenAICompatProvider(config)
        assert provider.list_models() == ["model-a", "model-b"]


class TestPreconfiguredProviders:
    def test_together(self) -> None:
        config = together_config("sk-test")
        assert config.name == "together"
        assert len(config.models) >= 3

    def test_openrouter(self) -> None:
        config = openrouter_config("sk-test")
        assert config.name == "openrouter"
        assert "HTTP-Referer" in config.extra_headers

    def test_fireworks(self) -> None:
        config = fireworks_config("sk-test")
        assert config.name == "fireworks"

    def test_groq(self) -> None:
        config = groq_config("sk-test")
        assert config.name == "groq"
        assert len(config.models) >= 3

    def test_perplexity(self) -> None:
        config = perplexity_config("sk-test")
        assert config.supports_tool_choice is False

    def test_all_preconfigured(self) -> None:
        assert len(PRECONFIGURED_PROVIDERS) >= 5


# ===== Chinese Providers =====


class TestCNProviders:
    def test_all_specs_exist(self) -> None:
        assert len(ALL_CN_PROVIDERS) >= 9
        names = set(ALL_CN_PROVIDERS.keys())
        for expected in ("moonshot", "volcengine", "deepseek", "qwen", "zhipu", "minimax"):
            assert expected in names

    def test_moonshot_models(self) -> None:
        models = get_cn_provider_models("moonshot")
        assert "moonshot-v1-128k" in models

    def test_deepseek_models(self) -> None:
        models = get_cn_provider_models("deepseek")
        assert "deepseek-chat" in models
        assert "deepseek-reasoner" in models

    def test_qwen_models(self) -> None:
        models = get_cn_provider_models("qwen")
        assert "qwen-max" in models
        assert "qwen-vl-max" in models

    def test_zhipu_models(self) -> None:
        models = get_cn_provider_models("zhipu")
        assert "glm-4-plus" in models

    def test_build_config(self) -> None:
        config = build_cn_config(MOONSHOT_SPEC, "sk-moon-test")
        assert config.name == "moonshot"
        assert config.api_key == "sk-moon-test"
        assert config.base_url == "https://api.moonshot.cn"

    def test_list_providers(self) -> None:
        providers = list_cn_providers()
        assert len(providers) >= 9
        names = {p["name"] for p in providers}
        assert "deepseek" in names

    def test_unknown_provider(self) -> None:
        assert get_cn_provider_models("nonexistent") == []


# ===== OAuth Providers =====


class TestPKCE:
    def test_verifier_length(self) -> None:
        v = generate_code_verifier(64)
        assert len(v) == 64

    def test_challenge_deterministic(self) -> None:
        v = "test_verifier_12345678901234567890123456789012345"
        c1 = generate_code_challenge(v)
        c2 = generate_code_challenge(v)
        assert c1 == c2
        assert len(c1) > 10


class TestMiniMaxOAuth:
    def test_start_flow(self) -> None:
        config = MiniMaxOAuthConfig(client_id="test-client")
        flow = MiniMaxOAuthFlow(config)
        url = flow.start()
        assert "client_id=test-client" in url
        assert "code_challenge=" in url
        assert "S256" in url

    def test_build_token_request(self) -> None:
        config = MiniMaxOAuthConfig(client_id="test-client")
        flow = MiniMaxOAuthFlow(config)
        flow.start()
        req = flow.build_token_request("auth-code-123")
        assert req["code"] == "auth-code-123"
        assert req["grant_type"] == "authorization_code"
        assert "code_verifier" in req

    def test_parse_token(self) -> None:
        config = MiniMaxOAuthConfig(client_id="test")
        flow = MiniMaxOAuthFlow(config)
        tokens = flow.parse_token_response(
            {
                "access_token": "at-123",
                "refresh_token": "rt-456",
                "expires_in": 3600,
            }
        )
        assert tokens.access_token == "at-123"
        assert tokens.refresh_token == "rt-456"
        assert not tokens.is_expired

    def test_token_not_started(self) -> None:
        config = MiniMaxOAuthConfig(client_id="test")
        flow = MiniMaxOAuthFlow(config)
        with pytest.raises(RuntimeError, match="not started"):
            flow.build_token_request("code")


class TestQwenOAuth:
    def test_start_flow(self) -> None:
        config = QwenOAuthConfig(client_id="qwen-client")
        flow = QwenOAuthFlow(config)
        url = flow.start()
        assert "client_id=qwen-client" in url
        assert "code_challenge=" in url

    def test_build_token_request(self) -> None:
        config = QwenOAuthConfig(client_id="qwen-client")
        flow = QwenOAuthFlow(config)
        flow.start()
        req = flow.build_token_request("code-789")
        assert req["code"] == "code-789"


class TestCopilotDeviceFlow:
    def test_device_code_request(self) -> None:
        flow = CopilotDeviceFlow()
        req = flow.build_device_code_request()
        assert "client_id" in req

    def test_parse_device_code(self) -> None:
        flow = CopilotDeviceFlow()
        resp = flow.parse_device_code_response(
            {
                "device_code": "dc-123",
                "user_code": "ABCD-1234",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 5,
            }
        )
        assert resp.user_code == "ABCD-1234"
        assert resp.device_code == "dc-123"

    def test_poll_request(self) -> None:
        flow = CopilotDeviceFlow()
        flow.parse_device_code_response(
            {
                "device_code": "dc-123",
                "user_code": "ABCD",
                "verification_uri": "https://github.com/login/device",
            }
        )
        req = flow.build_token_poll_request()
        assert req["device_code"] == "dc-123"
        assert req["grant_type"] == "urn:ietf:params:oauth:grant-type:device_code"

    def test_parse_pending(self) -> None:
        flow = CopilotDeviceFlow()
        result = flow.parse_token_response({"error": "authorization_pending"})
        assert result is None

    def test_parse_success(self) -> None:
        flow = CopilotDeviceFlow()
        tokens = flow.parse_token_response({"access_token": "ghu_abc123", "token_type": "bearer"})
        assert tokens is not None
        assert tokens.access_token == "ghu_abc123"

    def test_parse_error(self) -> None:
        flow = CopilotDeviceFlow()
        with pytest.raises(RuntimeError, match="OAuth error"):
            flow.parse_token_response({"error": "access_denied", "error_description": "denied"})

    def test_copilot_headers(self) -> None:
        flow = CopilotDeviceFlow()
        headers = flow.build_copilot_chat_headers("token-123")
        assert headers["Authorization"] == "Bearer token-123"
        assert "Editor-Version" in headers


# ===== Provider Registry =====


class TestProviderRegistry:
    def test_register_and_get(self) -> None:
        registry = ProviderRegistry()
        config = OpenAICompatConfig(name="test", base_url="https://api.test.com")
        provider = OpenAICompatProvider(config)
        registry.register(provider)
        assert registry.get("test") is not None
        assert registry.provider_count == 1

    def test_list_providers(self) -> None:
        registry = create_default_registry()
        all_providers = registry.list_providers()
        assert len(all_providers) >= 10

    def test_list_by_category(self) -> None:
        registry = create_default_registry()
        cn = registry.list_providers(category="cn")
        assert len(cn) >= 9

    def test_resolve_qualified_model(self) -> None:
        registry = ProviderRegistry()
        config = together_config("sk-test")
        provider = OpenAICompatProvider(config)
        registry.register(provider)

        prov_name, model_id = registry.resolve_model("together/llama-3.3-70b")
        assert prov_name == "together"
        assert "Llama" in model_id

    def test_activate_provider(self) -> None:
        registry = ProviderRegistry()
        provider = activate_provider(registry, "together", "sk-test")
        assert provider is not None
        assert provider.name == "together"
        assert registry.get("together") is not None

    def test_activate_cn_provider(self) -> None:
        registry = ProviderRegistry()
        provider = activate_provider(registry, "deepseek", "sk-ds")
        assert provider is not None
        assert provider.name == "deepseek"

    def test_activate_unknown(self) -> None:
        registry = ProviderRegistry()
        assert activate_provider(registry, "nonexistent", "key") is None

    def test_unregister(self) -> None:
        registry = ProviderRegistry()
        config = OpenAICompatConfig(name="temp", base_url="https://api.test.com")
        registry.register(OpenAICompatProvider(config))
        assert registry.unregister("temp") is True
        assert registry.get("temp") is None


# ===== Bedrock Provider =====


class TestBedrockProvider:
    def test_models_exist(self) -> None:
        assert len(BEDROCK_MODELS) >= 7

    def test_resolve_model(self) -> None:
        provider = BedrockProvider()
        model_id = provider.resolve_model("claude-3.5-sonnet")
        assert "anthropic" in model_id
        assert "claude" in model_id

    def test_resolve_unknown(self) -> None:
        provider = BedrockProvider()
        assert provider.resolve_model("custom-model") == "custom-model"

    def test_build_request(self) -> None:
        provider = BedrockProvider()
        messages = [ConverseMessage(role="user", content=[{"text": "Hello"}])]
        body = provider.build_converse_request(
            messages,
            "claude-3.5-sonnet",
            system_prompt="Be helpful",
            max_tokens=1024,
            temperature=0.5,
        )
        assert "anthropic" in body["modelId"]
        assert body["system"] == [{"text": "Be helpful"}]
        assert body["inferenceConfig"]["maxTokens"] == 1024

    def test_build_request_with_tools(self) -> None:
        provider = BedrockProvider()
        messages = [ConverseMessage(role="user", content=[{"text": "Run code"}])]
        tools = [{"function": {"name": "exec", "description": "Execute", "parameters": {"type": "object"}}}]
        body = provider.build_converse_request(messages, "claude-3.5-sonnet", tools=tools)
        assert "toolConfig" in body
        assert body["toolConfig"]["tools"][0]["toolSpec"]["name"] == "exec"

    def test_parse_content_delta(self) -> None:
        provider = BedrockProvider()
        event = {"contentBlockDelta": {"delta": {"text": "Hi there"}}}
        chunk = provider.parse_stream_event(event)
        assert chunk.type == "contentBlockDelta"
        assert chunk.delta_text == "Hi there"

    def test_parse_message_stop(self) -> None:
        provider = BedrockProvider()
        event = {"messageStop": {"stopReason": "end_turn"}}
        chunk = provider.parse_stream_event(event)
        assert chunk.type == "messageStop"
        assert chunk.stop_reason == "end_turn"

    def test_parse_metadata(self) -> None:
        provider = BedrockProvider()
        event = {"metadata": {"usage": {"inputTokens": 100, "outputTokens": 50}}}
        chunk = provider.parse_stream_event(event)
        assert chunk.usage is not None
        assert chunk.usage["input_tokens"] == 100

    def test_parse_tool_use_start(self) -> None:
        provider = BedrockProvider()
        event = {"contentBlockStart": {"start": {"toolUse": {"name": "exec", "toolUseId": "t1"}}}}
        chunk = provider.parse_stream_event(event)
        assert chunk.type == "contentBlockStart"
        assert chunk.tool_use is not None

    def test_list_models(self) -> None:
        provider = BedrockProvider()
        models = provider.list_models()
        assert "claude-3.5-sonnet" in models
        assert "llama-3.1-70b" in models

    def test_list_by_provider(self) -> None:
        provider = BedrockProvider()
        anthropic = provider.list_models_by_provider("anthropic")
        assert all("claude" in m or "opus" in m for m in anthropic)

    def test_boto3_config(self) -> None:
        provider = BedrockProvider(
            BedrockConfig(
                region="us-west-2",
                access_key_id="AKIA...",
                secret_access_key="secret",
            )
        )
        cfg = provider.get_boto3_config()
        assert cfg["region_name"] == "us-west-2"
        assert cfg["aws_access_key_id"] == "AKIA..."

    def test_endpoint_url(self) -> None:
        provider = BedrockProvider(BedrockConfig(region="eu-west-1"))
        assert "eu-west-1" in provider.get_endpoint_url()

    def test_custom_endpoint(self) -> None:
        provider = BedrockProvider(BedrockConfig(endpoint_url="https://custom.endpoint.com"))
        assert provider.get_endpoint_url() == "https://custom.endpoint.com"
