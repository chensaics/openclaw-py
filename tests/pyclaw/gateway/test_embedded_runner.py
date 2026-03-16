"""Tests for Phase 35: Pi Embedded Runner."""

from __future__ import annotations

import time

# Phase 35e: Helpers
from pyclaw.agents.embedded_runner.helpers import (
    BootstrapConfig,
    build_anthropic_turns,
    build_bootstrap,
    build_google_turns,
    build_openai_turns,
    clean_schema_for_gemini,
    deduplicate_messages,
    map_provider_error,
)

# Phase 35a: Run
from pyclaw.agents.embedded_runner.run import (
    ImageContent,
    Message,
    RunConfig,
    RunRecord,
    RunState,
    RunTracker,
    build_request_payload,
    inject_images,
    prune_images,
)

# Phase 35b: Session Manager
from pyclaw.agents.embedded_runner.session_manager import (
    EmbeddedSessionManager,
    SessionConfig,
    SessionLane,
    SessionState,
    resolve_lane,
    should_wait_for_idle,
)

# Phase 35c: Thinking
from pyclaw.agents.embedded_runner.thinking import (
    AbortSignal,
    CompactionGuardConfig,
    ThinkingConfig,
    ThinkingMode,
    build_thinking_param,
    extract_thinking_blocks,
    is_compaction_safe,
    process_thinking_response,
    strip_thinking_tags,
)

# Phase 35d: Tool Guards
from pyclaw.agents.embedded_runner.tool_guards import (
    AllowlistConfig,
    SchemaSplitConfig,
    ToolCacheManager,
    TruncationConfig,
    filter_tools,
    guard_tool_context,
    should_split_schema,
    split_schema,
    truncate_tool_result,
)

# =====================================================================
# Phase 35a: Run
# =====================================================================


class TestRunConfig:
    def test_build_payload(self) -> None:
        config = RunConfig(model="gpt-4o", max_tokens=2048, temperature=0.5)
        messages = [Message(role="user", content="Hello")]
        payload = build_request_payload(messages, config, system_prompt="You are helpful")
        assert payload["model"] == "gpt-4o"
        assert payload["max_tokens"] == 2048
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"

    def test_build_payload_with_tools(self) -> None:
        config = RunConfig(model="claude-3-5-sonnet")
        tools = [{"type": "function", "function": {"name": "search"}}]
        payload = build_request_payload([], config, tools=tools)
        assert "tools" in payload
        assert len(payload["tools"]) == 1

    def test_build_payload_with_thinking(self) -> None:
        config = RunConfig(model="o3", enable_thinking=True, thinking_budget=5000)
        payload = build_request_payload([], config)
        assert payload["thinking"]["budget_tokens"] == 5000


class TestImageHandling:
    def test_inject_images(self) -> None:
        messages = [Message(role="user", content="What is this?")]
        images = [ImageContent(url="https://img.example.com/photo.png")]
        inject_images(messages, images)
        assert isinstance(messages[0].content, list)
        assert len(messages[0].content) == 2
        assert messages[0].content[0]["type"] == "text"
        assert messages[0].content[1]["type"] == "image_url"

    def test_inject_base64_image(self) -> None:
        messages = [Message(role="user", content="Describe")]
        images = [ImageContent(base64_data="abc123", media_type="image/jpeg")]
        inject_images(messages, images)
        assert isinstance(messages[0].content, list)
        img_block = messages[0].content[1]
        assert "data:image/jpeg;base64," in img_block["image_url"]["url"]

    def test_prune_images(self) -> None:
        messages = [
            Message(
                role="user",
                content=[
                    {"type": "text", "text": "First"},
                    {"type": "image_url", "image_url": {"url": "img1"}},
                ],
            ),
            Message(
                role="user",
                content=[
                    {"type": "text", "text": "Second"},
                    {"type": "image_url", "image_url": {"url": "img2"}},
                ],
            ),
            Message(
                role="user",
                content=[
                    {"type": "text", "text": "Third"},
                    {"type": "image_url", "image_url": {"url": "img3"}},
                ],
            ),
        ]
        pruned = prune_images(messages, keep_last_n=2)
        assert pruned == 1
        # First message should have images removed, converted back to string
        assert isinstance(messages[0].content, str)
        assert messages[0].content == "First"

    def test_inject_empty(self) -> None:
        messages = [Message(role="user", content="Hi")]
        inject_images(messages, [])
        assert messages[0].content == "Hi"


class TestRunTracker:
    def test_start_and_finish(self) -> None:
        tracker = RunTracker()
        record = tracker.start_run(model="gpt-4o")
        assert record.state == RunState.RUNNING
        assert tracker.total_runs == 1
        assert len(tracker.active_runs) == 1

        tracker.finish_run(record.run_id, state=RunState.COMPLETED)
        assert tracker.get_run(record.run_id).state == RunState.COMPLETED
        assert len(tracker.active_runs) == 0

    def test_duration(self) -> None:
        record = RunRecord(run_id="r1", started_at=time.time() - 5, finished_at=time.time())
        assert record.duration_s >= 4


class TestMessage:
    def test_to_dict(self) -> None:
        msg = Message(role="user", content="Hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"

    def test_to_dict_with_tool(self) -> None:
        msg = Message(role="tool", content="result", tool_call_id="tc1")
        d = msg.to_dict()
        assert d["tool_call_id"] == "tc1"


# =====================================================================
# Phase 35b: Session Manager
# =====================================================================


class TestEmbeddedSessionManager:
    def test_get_or_create(self) -> None:
        mgr = EmbeddedSessionManager()
        session = mgr.get_or_create("s1", agent_id="a1", model="gpt-4o")
        assert session.session_id == "s1"
        assert session.agent_id == "a1"
        assert mgr.cached_count == 1

        # Second call returns same session
        session2 = mgr.get_or_create("s1")
        assert session2 is session

    def test_append_message(self) -> None:
        mgr = EmbeddedSessionManager()
        mgr.get_or_create("s1")
        mgr.append_message("s1", Message(role="user", content="Hello"))
        session = mgr.get("s1")
        assert session is not None
        assert session.message_count == 1

    def test_history_limits(self) -> None:
        mgr = EmbeddedSessionManager(SessionConfig(max_history_messages=5))
        mgr.get_or_create("s1")
        for i in range(10):
            mgr.append_message("s1", Message(role="user", content=f"msg {i}"))
        session = mgr.get("s1")
        assert session is not None
        assert session.message_count <= 5

    def test_eviction(self) -> None:
        mgr = EmbeddedSessionManager(SessionConfig(max_cached_sessions=2, session_ttl_s=0.01))
        mgr.get_or_create("s1")
        time.sleep(0.02)
        mgr.get_or_create("s2")
        mgr.get_or_create("s3")
        # s1 should be evicted (expired)
        assert mgr.get("s1") is None

    def test_remove(self) -> None:
        mgr = EmbeddedSessionManager()
        mgr.get_or_create("s1")
        assert mgr.remove("s1")
        assert mgr.cached_count == 0

    def test_estimated_tokens(self) -> None:
        state = SessionState(session_id="s1")
        state.messages.append(Message(role="user", content="Hello world"))
        assert state.estimated_tokens > 0


class TestLaneResolution:
    def test_default(self) -> None:
        assert resolve_lane() == SessionLane.DEFAULT

    def test_cron(self) -> None:
        assert resolve_lane(is_cron=True) == SessionLane.CRON

    def test_priority(self) -> None:
        assert resolve_lane(is_priority=True) == SessionLane.PRIORITY

    def test_background(self) -> None:
        assert resolve_lane(is_background=True) == SessionLane.BACKGROUND

    def test_priority_wins(self) -> None:
        assert resolve_lane(is_priority=True, is_cron=True) == SessionLane.PRIORITY

    def test_wait_for_idle(self) -> None:
        assert should_wait_for_idle(SessionLane.DEFAULT)
        assert should_wait_for_idle(SessionLane.PRIORITY)
        assert not should_wait_for_idle(SessionLane.CRON)
        assert not should_wait_for_idle(SessionLane.BACKGROUND)


# =====================================================================
# Phase 35c: Thinking
# =====================================================================


class TestThinking:
    def test_extract_blocks(self) -> None:
        text = "Hello <thinking>I should analyze this</thinking> World"
        blocks = extract_thinking_blocks(text)
        assert len(blocks) == 1
        assert "analyze" in blocks[0].content

    def test_strip_tags(self) -> None:
        text = "Hello <thinking>internal</thinking> World"
        result = strip_thinking_tags(text)
        assert "internal" not in result
        assert "Hello" in result

    def test_process_response_strip(self) -> None:
        config = ThinkingConfig(strip_from_output=True)
        cleaned, blocks = process_thinking_response(
            "Reply <reasoning>step 1</reasoning> done",
            config,
        )
        assert "step 1" not in cleaned
        assert len(blocks) == 1

    def test_process_response_keep(self) -> None:
        config = ThinkingConfig(strip_from_output=False)
        text, blocks = process_thinking_response(
            "Reply <thinking>thought</thinking> done",
            config,
        )
        assert "<thinking>" in text
        assert len(blocks) == 1

    def test_build_thinking_param_disabled(self) -> None:
        assert build_thinking_param(ThinkingConfig()) is None

    def test_build_thinking_param_enabled(self) -> None:
        config = ThinkingConfig(mode=ThinkingMode.ENABLED, budget_tokens=8000)
        param = build_thinking_param(config)
        assert param is not None
        assert param["budget_tokens"] == 8000

    def test_parse_thinking_content_block(self) -> None:
        from pyclaw.agents.embedded_runner.thinking import parse_thinking_content_block

        block = parse_thinking_content_block({"type": "thinking", "thinking": "deep thought"})
        assert block is not None
        assert block.content == "deep thought"
        assert parse_thinking_content_block({"type": "text", "text": "hi"}) is None


class TestAbortSignal:
    def test_abort(self) -> None:
        signal = AbortSignal()
        assert not signal.is_aborted
        signal.abort("timeout")
        assert signal.is_aborted
        assert signal.reason == "timeout"

    def test_reset(self) -> None:
        signal = AbortSignal()
        signal.abort()
        signal.reset()
        assert not signal.is_aborted


class TestCompactionSafety:
    def test_safe(self) -> None:
        messages = [{"role": "user"}, {"role": "assistant"}, {"role": "user"}, {"role": "assistant"}, {"role": "user"}]
        safe, reason = is_compaction_safe(messages, 4, CompactionGuardConfig())
        assert safe

    def test_too_few_messages(self) -> None:
        messages = [{"role": "user"}] * 10
        safe, reason = is_compaction_safe(messages, 2, CompactionGuardConfig(min_messages_after=4))
        assert not safe
        assert "only 2" in reason

    def test_too_aggressive(self) -> None:
        messages = [{"role": "user"}] * 20
        safe, reason = is_compaction_safe(messages, 5, CompactionGuardConfig(max_compaction_ratio=0.5))
        assert not safe
        assert "aggressive" in reason


# =====================================================================
# Phase 35d: Tool Guards
# =====================================================================


class TestToolAllowlist:
    def test_filter_all(self) -> None:
        tools = [
            {"function": {"name": "search"}},
            {"function": {"name": "bash"}},
        ]
        result = filter_tools(tools, AllowlistConfig(mode="all"))
        assert len(result) == 2

    def test_filter_blocklist(self) -> None:
        tools = [
            {"function": {"name": "search"}},
            {"function": {"name": "dangerous_tool"}},
        ]
        config = AllowlistConfig(mode="blocklist", blocked_tools=["dangerous_tool"])
        result = filter_tools(tools, config)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "search"

    def test_filter_allowlist(self) -> None:
        tools = [
            {"function": {"name": "search"}},
            {"function": {"name": "bash"}},
            {"function": {"name": "unknown"}},
        ]
        config = AllowlistConfig(mode="allowlist", allowed_tools=["search"])
        result = filter_tools(tools, config)
        names = {t["function"]["name"] for t in result}
        assert "search" in names
        assert "bash" in names  # always_allowed
        assert "unknown" not in names


class TestContextGuard:
    def test_redact_sensitive(self) -> None:
        args = {"query": "hello", "api_key": "sk-secret123", "data": "normal"}
        guarded = guard_tool_context("search", args)
        assert guarded["api_key"] == "[REDACTED]"
        assert guarded["query"] == "hello"

    def test_no_redact(self) -> None:
        args = {"api_key": "sk-secret"}
        guarded = guard_tool_context("test", args, redact_sensitive=False)
        assert guarded["api_key"] == "sk-secret"

    def test_truncate_long_value(self) -> None:
        args = {"data": "x" * 20000}
        guarded = guard_tool_context("test", args)
        assert len(guarded["data"]) < 20000


class TestResultTruncation:
    def test_short_result(self) -> None:
        assert truncate_tool_result("hello") == "hello"

    def test_long_result(self) -> None:
        long = "x" * 100000
        result = truncate_tool_result(long, TruncationConfig(max_result_chars=1000))
        assert len(result) < 1100
        assert "truncated" in result

    def test_line_limit(self) -> None:
        lines = "\n".join(f"line {i}" for i in range(1000))
        result = truncate_tool_result(lines, TruncationConfig(max_result_lines=10))
        assert result.count("\n") <= 11


class TestSchemaSplitting:
    def test_no_split_needed(self) -> None:
        tools = [{"function": {"name": f"t{i}"}} for i in range(5)]
        assert not should_split_schema(tools, SchemaSplitConfig())

    def test_split_by_count(self) -> None:
        tools = [{"function": {"name": f"t{i}"}} for i in range(200)]
        assert should_split_schema(tools, SchemaSplitConfig(max_tools_per_request=100))

    def test_split_chunks(self) -> None:
        tools = [{"function": {"name": f"t{i}"}} for i in range(10)]
        chunks = split_schema(tools, SchemaSplitConfig(max_tools_per_request=3))
        assert len(chunks) >= 3
        total = sum(len(c) for c in chunks)
        assert total == 10


class TestToolCache:
    def test_set_get(self) -> None:
        cache = ToolCacheManager()
        cache.set("k1", "value1", ttl_s=10.0)
        assert cache.get("k1") == "value1"
        assert cache.size == 1

    def test_expired(self) -> None:
        cache = ToolCacheManager()
        cache.set("k1", "value1", ttl_s=0.01)
        time.sleep(0.02)
        assert cache.get("k1") is None

    def test_compute_key(self) -> None:
        cache = ToolCacheManager()
        k1 = cache.compute_key("search", {"q": "hello"})
        k2 = cache.compute_key("search", {"q": "hello"})
        k3 = cache.compute_key("search", {"q": "world"})
        assert k1 == k2
        assert k1 != k3

    def test_cleanup(self) -> None:
        cache = ToolCacheManager()
        cache.set("k1", "v1", ttl_s=0.01)
        cache.set("k2", "v2", ttl_s=100.0)
        time.sleep(0.02)
        cleaned = cache.cleanup_expired()
        assert cleaned == 1
        assert cache.size == 1

    def test_provider_ttl(self) -> None:
        cache = ToolCacheManager()
        assert cache.get_ttl("openai") == 300.0
        assert cache.get_ttl("ollama") == 0.0


# =====================================================================
# Phase 35e: Helpers
# =====================================================================


class TestErrorMapping:
    def test_rate_limit(self) -> None:
        err = map_provider_error("Rate limit exceeded, please retry after 30s")
        assert err.code == "rate_limit"
        assert err.retryable

    def test_auth_error(self) -> None:
        err = map_provider_error("Invalid API key provided", provider="openai")
        assert err.code == "auth_error"
        assert not err.retryable

    def test_context_overflow(self) -> None:
        err = map_provider_error("This model's maximum context length is 128000")
        assert err.code == "context_overflow"

    def test_unknown(self) -> None:
        err = map_provider_error("Something weird happened")
        assert err.code == "unknown"

    def test_content_filter(self) -> None:
        err = map_provider_error("Content was blocked by safety filters")
        assert err.code == "content_filtered"


class TestTurnBuilding:
    def test_openai_turns(self) -> None:
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = build_openai_turns(messages)
        assert len(result) == 3
        assert result[0]["role"] == "system"

    def test_anthropic_turns(self) -> None:
        messages = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hello"},
        ]
        system, turns = build_anthropic_turns(messages)
        assert system == "Be helpful"
        assert len(turns) == 1
        assert turns[0]["role"] == "user"

    def test_google_turns(self) -> None:
        messages = [
            {"role": "system", "content": "Ignored"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = build_google_turns(messages)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "model"
        assert result[0]["parts"][0]["text"] == "Hello"


class TestDeduplication:
    def test_deduplicate(self) -> None:
        messages = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A1"},  # duplicate
        ]
        result, removed = deduplicate_messages(messages, window=5)
        assert removed == 1
        assert len(result) == 3

    def test_no_dedup_different(self) -> None:
        messages = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "assistant", "content": "A2"},
        ]
        result, removed = deduplicate_messages(messages)
        assert removed == 0


class TestBootstrap:
    def test_basic(self) -> None:
        result = build_bootstrap("You are a helpful assistant.", BootstrapConfig())
        assert "helpful assistant" in result
        assert "Current date" in result

    def test_with_model(self) -> None:
        result = build_bootstrap("Base", BootstrapConfig(include_model_info=True), model="gpt-4o")
        assert "gpt-4o" in result

    def test_with_tools(self) -> None:
        result = build_bootstrap(
            "Base",
            BootstrapConfig(include_tool_hints=True),
            tool_names=["search", "bash"],
        )
        assert "search" in result

    def test_no_extras(self) -> None:
        config = BootstrapConfig(
            include_datetime=False,
            include_model_info=False,
            include_tool_hints=False,
        )
        result = build_bootstrap("Only this", config)
        assert result == "Only this"


class TestGeminiSchema:
    def test_remove_anyof(self) -> None:
        schema = {"type": "object", "anyOf": [{"type": "string"}, {"type": "number"}]}
        cleaned = clean_schema_for_gemini(schema)
        assert "anyOf" not in cleaned
        assert cleaned["type"] == "string"  # Takes first option

    def test_remove_format(self) -> None:
        schema = {"type": "string", "format": "date-time"}
        cleaned = clean_schema_for_gemini(schema)
        assert "format" not in cleaned

    def test_nested_cleaning(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "date": {"type": "string", "format": "date"},
                "value": {"oneOf": [{"type": "string"}, {"type": "number"}]},
            },
        }
        cleaned = clean_schema_for_gemini(schema)
        assert "format" not in cleaned["properties"]["date"]
        assert "oneOf" not in cleaned["properties"]["value"]
