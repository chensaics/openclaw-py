"""Tests for Phase 32: Cron advanced, TTS extended, Logging advanced, SSRF, Session cost."""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Phase 32a: Cron advanced
from pyclaw.cron.advanced import (
    CronTaskConfig,
    IsolatedAgentRunner,
    ReaperConfig,
    SessionEntry,
    SessionReaper,
    SkillSnapshot,
    TaskExecution,
    TaskHandler,
    TaskState,
    TimeoutPolicy,
    apply_stagger,
    build_webhook_payload,
    capture_skill_snapshot,
    compute_stagger_offsets,
)

# Phase 32b: TTS extended
from pyclaw.agents.tts_extended import (
    ElevenLabsConfig,
    ElevenLabsTTSProvider,
    OpenAITTSConfig,
    OpenAITTSProvider,
    TTSAutoMode,
    TTSConfig,
    TTSRequest,
    parse_tts_directive,
    prepare_text_for_tts,
    should_synthesize,
)

# Phase 32c: Logging advanced
from pyclaw.logging.advanced import (
    DiagnosticSessionState,
    ParsedLogLine,
    RotationConfig,
    filter_log_lines,
    parse_log_line,
    redact_api_key,
    redact_identifiers,
    rotate_log_file,
    should_rotate,
)

# Phase 32d: SSRF
from pyclaw.security.ssrf import (
    SSRFConfig,
    SSRFGuard,
    check_url,
    is_blocked_hostname,
    is_private_ip,
)

# Phase 32e: Session cost
from pyclaw.infra.session_cost import (
    ModelPricing,
    SessionCost,
    TokenUsage,
    UsageAggregator,
    format_cost,
    format_session_cost_summary,
    format_tokens,
)


# =====================================================================
# Phase 32a: Cron Advanced
# =====================================================================

class TestCronStagger:
    def test_compute_offsets(self) -> None:
        tasks = [CronTaskConfig(task_id=f"t{i}", schedule="0 * * * *") for i in range(4)]
        offsets = compute_stagger_offsets(tasks, window_s=3600.0)
        assert len(offsets) == 4
        assert offsets[0] == 0.0
        assert offsets[1] == 900.0

    def test_single_task_no_stagger(self) -> None:
        offsets = compute_stagger_offsets([CronTaskConfig(task_id="t1", schedule="*")])
        assert offsets == [0.0]

    def test_apply_stagger(self) -> None:
        tasks = [CronTaskConfig(task_id=f"t{i}", schedule="*") for i in range(3)]
        apply_stagger(tasks, window_s=600.0)
        assert tasks[0].stagger_offset_s == 0.0
        assert tasks[1].stagger_offset_s == 200.0
        assert tasks[2].stagger_offset_s == 400.0


class TestSkillSnapshot:
    def test_capture(self) -> None:
        snap = capture_skill_snapshot("task1", ["skill_a", "skill_b"])
        assert snap.task_id == "task1"
        assert len(snap.skills) == 2
        assert snap.checksum

    def test_checksum_deterministic(self) -> None:
        s1 = capture_skill_snapshot("t", ["a", "b"])
        s2 = capture_skill_snapshot("t", ["b", "a"])
        assert s1.checksum == s2.checksum


class TestIsolatedAgentRunner:
    @pytest.mark.asyncio
    async def test_successful_task(self) -> None:
        runner = IsolatedAgentRunner()
        task = CronTaskConfig(task_id="t1", schedule="*", timeout_s=5.0)

        async def handler(t: CronTaskConfig) -> str:
            return "done"

        result = await runner.run_task(task, handler)
        assert result.state == TaskState.COMPLETED
        assert result.result == "done"
        assert result.duration_s > 0

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        runner = IsolatedAgentRunner(timeout_policy=TimeoutPolicy(max_timeout_s=0.1))
        task = CronTaskConfig(task_id="t2", schedule="*", timeout_s=0.05)

        async def handler(t: CronTaskConfig) -> str:
            await asyncio.sleep(10)
            return "never"

        result = await runner.run_task(task, handler)
        assert result.state == TaskState.TIMEOUT

    @pytest.mark.asyncio
    async def test_failed_task(self) -> None:
        runner = IsolatedAgentRunner()
        task = CronTaskConfig(task_id="t3", schedule="*")

        async def handler(t: CronTaskConfig) -> str:
            raise RuntimeError("boom")

        result = await runner.run_task(task, handler)
        assert result.state == TaskState.FAILED
        assert "boom" in result.error


class TestSessionReaper:
    def test_track_and_reap(self) -> None:
        reaper = SessionReaper(ReaperConfig(max_idle_s=1.0, max_age_s=100.0))
        reaper.track(SessionEntry(
            session_id="s1",
            created_at=time.time(),
            last_active_at=time.time() - 2.0,
        ))
        assert reaper.tracked_count == 1
        reaped = reaper.reap()
        assert "s1" in reaped

    def test_no_reap_active(self) -> None:
        reaper = SessionReaper(ReaperConfig(max_idle_s=300.0))
        reaper.track(SessionEntry(
            session_id="s2",
            created_at=time.time(),
            last_active_at=time.time(),
        ))
        reaped = reaper.reap()
        assert len(reaped) == 0


class TestWebhookPayload:
    def test_build(self) -> None:
        task = CronTaskConfig(task_id="t1", schedule="*")
        execution = TaskExecution(task_id="t1", state=TaskState.COMPLETED, result="ok")
        payload = build_webhook_payload(task, execution)
        assert payload["task_id"] == "t1"
        assert payload["state"] == "completed"


# =====================================================================
# Phase 32b: TTS Extended
# =====================================================================

class TestTTSProviders:
    def test_elevenlabs_voices(self) -> None:
        provider = ElevenLabsTTSProvider(ElevenLabsConfig(api_key="test"))
        assert "rachel" in provider.available_voices
        assert provider.validate_voice("rachel")
        assert not provider.validate_voice("nonexistent")

    def test_elevenlabs_request(self) -> None:
        provider = ElevenLabsTTSProvider(ElevenLabsConfig(api_key="test-key"))
        req = TTSRequest(text="Hello", voice="rachel")
        built = provider.build_request(req)
        assert "text-to-speech" in built["url"]
        assert built["headers"]["xi-api-key"] == "test-key"

    def test_openai_voices(self) -> None:
        provider = OpenAITTSProvider(OpenAITTSConfig(api_key="test"))
        assert "alloy" in provider.available_voices
        assert provider.validate_voice("nova")

    def test_openai_request(self) -> None:
        provider = OpenAITTSProvider(OpenAITTSConfig(api_key="sk-test"))
        req = TTSRequest(text="Hello", voice="echo", speed=1.5)
        built = provider.build_request(req)
        assert "audio/speech" in built["url"]
        assert built["body"]["voice"] == "echo"
        assert built["body"]["speed"] == 1.5


class TestTTSHelpers:
    def test_should_synthesize_off(self) -> None:
        cfg = TTSConfig(auto_mode=TTSAutoMode.OFF)
        assert not should_synthesize(cfg)

    def test_should_synthesize_always(self) -> None:
        cfg = TTSConfig(auto_mode=TTSAutoMode.ALWAYS)
        assert should_synthesize(cfg)

    def test_should_synthesize_inbound(self) -> None:
        cfg = TTSConfig(auto_mode=TTSAutoMode.INBOUND)
        assert not should_synthesize(cfg, inbound_has_audio=False)
        assert should_synthesize(cfg, inbound_has_audio=True)

    def test_should_synthesize_tagged(self) -> None:
        cfg = TTSConfig(auto_mode=TTSAutoMode.TAGGED)
        assert not should_synthesize(cfg, has_tts_directive=False)
        assert should_synthesize(cfg, has_tts_directive=True)

    def test_prepare_text_short(self) -> None:
        cfg = TTSConfig(max_text_length=100)
        assert prepare_text_for_tts("Hello", cfg) == "Hello"

    def test_prepare_text_long_truncate(self) -> None:
        cfg = TTSConfig(max_text_length=10, summarize_long_text=False)
        result = prepare_text_for_tts("A" * 50, cfg)
        assert len(result) == 10

    def test_parse_tts_directive(self) -> None:
        has, voice, text = parse_tts_directive("/tts echo Hello world")
        assert has
        assert voice == "echo"
        assert text == "Hello world"

    def test_parse_tts_no_voice(self) -> None:
        has, voice, text = parse_tts_directive("/tts Hello world")
        assert has
        # "Hello" is parsed as voice since it comes first; the rest is text
        assert "Hello" in voice or "Hello" in text

    def test_parse_at_tts(self) -> None:
        has, voice, text = parse_tts_directive("Hello @tts world")
        assert has
        assert "Hello" in text

    def test_parse_no_directive(self) -> None:
        has, voice, text = parse_tts_directive("Regular text")
        assert not has


# =====================================================================
# Phase 32c: Logging Advanced
# =====================================================================

class TestRedaction:
    def test_redact_email(self) -> None:
        result = redact_identifiers("Contact user@example.com for info")
        assert "[REDACTED_EMAIL]" in result
        assert "user@example.com" not in result

    def test_redact_ip(self) -> None:
        result = redact_identifiers("Server at 192.168.1.100")
        assert "[REDACTED_IP]" in result

    def test_redact_api_key_full(self) -> None:
        result = redact_identifiers("Key: sk-abc1234567890xyz")
        assert "[REDACTED_KEY]" in result

    def test_redact_api_key_mask(self) -> None:
        assert redact_api_key("sk-abc123456789") == "sk-a...6789"

    def test_redact_api_key_short(self) -> None:
        assert redact_api_key("ab") == "****"


class TestLogRotation:
    def test_should_rotate_small(self, tmp_path: Path) -> None:
        log = tmp_path / "test.log"
        log.write_text("small")
        assert not should_rotate(log, RotationConfig(max_size_bytes=1000))

    def test_should_rotate_large(self, tmp_path: Path) -> None:
        log = tmp_path / "test.log"
        log.write_text("x" * 2000)
        assert should_rotate(log, RotationConfig(max_size_bytes=1000))

    def test_rotate_file(self, tmp_path: Path) -> None:
        log = tmp_path / "test.log"
        log.write_text("x" * 2000)
        result = rotate_log_file(log, RotationConfig(max_size_bytes=1000))
        assert result.rotated
        assert not log.exists()  # Original renamed


class TestLogParsing:
    def test_parse_structured_line(self) -> None:
        line = "2026-02-28T10:30:00.123 INFO [gateway] Server started"
        parsed = parse_log_line(line)
        assert parsed.level == "INFO"
        assert parsed.subsystem == "gateway"
        assert "Server started" in parsed.message

    def test_parse_no_subsystem(self) -> None:
        line = "2026-02-28T10:30:00 ERROR Something failed"
        parsed = parse_log_line(line)
        assert parsed.level == "ERROR"
        assert parsed.is_error

    def test_parse_unstructured(self) -> None:
        parsed = parse_log_line("random text")
        assert parsed.raw == "random text"

    def test_filter_by_level(self) -> None:
        lines = [
            "2026-02-28T10:00:00 INFO ok",
            "2026-02-28T10:00:01 ERROR fail",
            "2026-02-28T10:00:02 INFO fine",
        ]
        errors = filter_log_lines(lines, level="ERROR")
        assert len(errors) == 1

    def test_filter_by_pattern(self) -> None:
        lines = [
            "2026-02-28T10:00:00 INFO connected",
            "2026-02-28T10:00:01 INFO disconnected",
        ]
        result = filter_log_lines(lines, pattern="disconnect")
        assert len(result) == 1


class TestDiagnosticState:
    def test_to_log_dict(self) -> None:
        state = DiagnosticSessionState(
            session_id="s1", agent_id="a1", model="gpt-4o",
            turn_count=5, tool_call_count=3,
            started_at=1000.0, last_activity_at=1060.0,
        )
        d = state.to_log_dict()
        assert d["session_id"] == "s1"
        assert d["uptime_s"] == 60.0


# =====================================================================
# Phase 32d: SSRF
# =====================================================================

class TestSSRF:
    def test_private_ip(self) -> None:
        assert is_private_ip("127.0.0.1")
        assert is_private_ip("192.168.1.1")
        assert is_private_ip("10.0.0.1")
        assert not is_private_ip("8.8.8.8")

    def test_blocked_hostname(self) -> None:
        assert is_blocked_hostname("localhost")
        assert is_blocked_hostname("169.254.169.254")
        assert not is_blocked_hostname("example.com")

    def test_check_url_localhost(self) -> None:
        result = check_url("http://localhost:8080/api")
        assert not result.allowed
        assert "Blocked hostname" in result.reason

    def test_check_url_private_ip(self) -> None:
        result = check_url("http://192.168.1.1/admin", SSRFConfig(resolve_dns=False))
        assert not result.allowed

    def test_check_url_allowed_domain(self) -> None:
        config = SSRFConfig(allowed_domains=["api.example.com"], resolve_dns=False)
        result = check_url("https://api.example.com/v1", config)
        assert result.allowed

    def test_check_url_not_in_allowlist(self) -> None:
        config = SSRFConfig(allowed_domains=["safe.com"], resolve_dns=False)
        result = check_url("https://evil.com/steal", config)
        assert not result.allowed

    def test_check_url_blocked_scheme(self) -> None:
        result = check_url("ftp://example.com/file")
        assert not result.allowed

    def test_check_url_disabled(self) -> None:
        result = check_url("http://localhost", SSRFConfig(enabled=False))
        assert result.allowed

    def test_guard_counts_blocks(self) -> None:
        guard = SSRFGuard()
        guard.check("http://localhost/admin")
        guard.check("http://localhost/secret")
        assert guard.blocked_count == 2


# =====================================================================
# Phase 32e: Session Cost
# =====================================================================

class TestSessionCost:
    def test_basic_cost(self) -> None:
        sc = SessionCost(session_id="s1")
        sc.add_usage(TokenUsage(input_tokens=1_000_000, output_tokens=500_000, model="gpt-4o"))
        cost = sc.compute_cost()
        assert cost > 0
        assert sc.total_input_tokens == 1_000_000
        assert sc.total_output_tokens == 500_000

    def test_by_model(self) -> None:
        sc = SessionCost(session_id="s1")
        sc.add_usage(TokenUsage(input_tokens=100, output_tokens=50, model="gpt-4o"))
        sc.add_usage(TokenUsage(input_tokens=200, output_tokens=100, model="gpt-4o-mini"))
        by_model = sc.by_model()
        assert "gpt-4o" in by_model
        assert "gpt-4o-mini" in by_model
        assert by_model["gpt-4o"]["calls"] == 1

    def test_unknown_model_zero_cost(self) -> None:
        sc = SessionCost(session_id="s1")
        sc.add_usage(TokenUsage(input_tokens=1000, output_tokens=500, model="unknown-model"))
        assert sc.compute_cost() == 0.0


class TestCostFormatting:
    def test_format_cost(self) -> None:
        assert format_cost(0.001) == "$0.0010"
        assert format_cost(0.15) == "$0.150"
        assert format_cost(5.50) == "$5.50"

    def test_format_tokens(self) -> None:
        assert format_tokens(500) == "500"
        assert format_tokens(1500) == "1.5K"
        assert format_tokens(2_500_000) == "2.50M"


class TestUsageAggregator:
    def test_aggregate(self) -> None:
        agg = UsageAggregator()
        agg.record("s1", TokenUsage(input_tokens=100, output_tokens=50, model="gpt-4o"))
        agg.record("s2", TokenUsage(input_tokens=200, output_tokens=100, model="gpt-4o"))
        assert agg.session_count == 2
        assert agg.total_tokens() == 450

    def test_summary(self) -> None:
        agg = UsageAggregator()
        agg.record("s1", TokenUsage(input_tokens=100, output_tokens=50, model="gpt-4o"))
        summary = agg.summary()
        assert summary["sessions"] == 1
        assert summary["total_tokens"] == 150

    def test_format_session_summary(self) -> None:
        sc = SessionCost(session_id="test-session")
        sc.add_usage(TokenUsage(input_tokens=1000, output_tokens=500, model="gpt-4o"))
        text = format_session_cost_summary(sc)
        assert "test-session" in text
        assert "gpt-4o" in text
