"""Performance benchmark tests — agent loop latency and token throughput.

Measures baseline performance using mocked LLM responses.
Run with: pytest tests/test_benchmark.py -v -s
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import patch

import pytest

from pyclaw.agents.runner import run_agent
from pyclaw.agents.session import SessionManager
from pyclaw.agents.types import AgentEvent, ModelConfig


def _make_events(text: str, chunk_size: int = 5) -> list[AgentEvent]:
    """Build AgentEvent list simulating stream_llm output."""
    events: list[AgentEvent] = []
    for i in range(0, len(text), chunk_size):
        events.append(AgentEvent(type="message_update", delta=text[i : i + chunk_size]))
    events.append(
        AgentEvent(
            type="message_end",
            usage={"input_tokens": 10, "output_tokens": len(text.split())},
        )
    )
    return events


def _make_mock_stream(text: str, chunk_size: int = 5):
    """Return an async generator matching stream_llm(model, messages, tool_defs) signature."""
    evts = _make_events(text, chunk_size)

    async def _stream(model: Any, messages: Any, tool_defs: Any = None):
        for e in evts:
            yield e

    return _stream


RESPONSE_SHORT = "Hello! How can I help you today?"
RESPONSE_LONG = "Token " * 500


class TestAgentLoopLatency:
    """Measure agent loop startup and first-token latency."""

    @pytest.mark.asyncio
    async def test_single_turn_latency(self) -> None:
        session = SessionManager.in_memory()
        model = ModelConfig(provider="openai", model_id="gpt-4o", api_key="test")

        with patch("pyclaw.agents.runner.stream_llm", _make_mock_stream(RESPONSE_SHORT)):
            start = time.perf_counter()
            first_event_time = None
            event_count = 0

            async for _event in run_agent(prompt="Hello", session=session, model=model):
                if first_event_time is None:
                    first_event_time = time.perf_counter()
                event_count += 1

            total = time.perf_counter() - start
            first_token = (first_event_time or start) - start

            assert first_token < 0.1, f"First event latency too high: {first_token:.3f}s"
            assert total < 1.0, f"Total loop time too high: {total:.3f}s"
            assert event_count > 0

    @pytest.mark.asyncio
    async def test_multi_turn_latency(self) -> None:
        session = SessionManager.in_memory()
        model = ModelConfig(provider="openai", model_id="gpt-4o", api_key="test")
        turn_times: list[float] = []

        for i in range(5):
            with patch(
                "pyclaw.agents.runner.stream_llm",
                _make_mock_stream(f"Response to turn {i}"),
            ):
                start = time.perf_counter()
                async for _ in run_agent(prompt=f"Turn {i}", session=session, model=model):
                    pass
                turn_times.append(time.perf_counter() - start)

        avg = sum(turn_times) / len(turn_times)
        assert avg < 0.5, f"Average turn latency too high: {avg:.3f}s"
        assert max(turn_times) < 1.0, f"Max turn latency too high: {max(turn_times):.3f}s"


class TestTokenThroughput:
    """Measure token processing throughput."""

    @pytest.mark.asyncio
    async def test_short_response_throughput(self) -> None:
        session = SessionManager.in_memory()
        model = ModelConfig(provider="openai", model_id="gpt-4o", api_key="test")

        with patch(
            "pyclaw.agents.runner.stream_llm",
            _make_mock_stream(RESPONSE_SHORT, chunk_size=4),
        ):
            text = ""
            start = time.perf_counter()
            async for event in run_agent(prompt="Hi", session=session, model=model):
                if event.delta:
                    text += event.delta
            elapsed = time.perf_counter() - start

            tokens = len(text.split())
            tps = tokens / elapsed if elapsed > 0 else float("inf")
            assert tps > 10, f"Throughput too low: {tps:.1f} tokens/s"

    @pytest.mark.asyncio
    async def test_long_response_throughput(self) -> None:
        session = SessionManager.in_memory()
        model = ModelConfig(provider="openai", model_id="gpt-4o", api_key="test")

        with patch(
            "pyclaw.agents.runner.stream_llm",
            _make_mock_stream(RESPONSE_LONG, chunk_size=10),
        ):
            text = ""
            start = time.perf_counter()
            async for event in run_agent(prompt="Generate", session=session, model=model):
                if event.delta:
                    text += event.delta
            elapsed = time.perf_counter() - start

            tokens = len(text.split())
            tps = tokens / elapsed if elapsed > 0 else float("inf")
            assert tokens >= 400, f"Expected ~500 tokens, got {tokens}"
            assert tps > 50, f"Throughput too low for long response: {tps:.1f} tokens/s"


class TestSessionScaling:
    """Measure performance as session history grows."""

    @pytest.mark.asyncio
    async def test_session_growth_latency(self) -> None:
        session = SessionManager.in_memory()
        model = ModelConfig(provider="openai", model_id="gpt-4o", api_key="test")
        latencies: list[float] = []

        for i in range(20):
            with patch(
                "pyclaw.agents.runner.stream_llm",
                _make_mock_stream(f"Reply {i}: " + "word " * 50, chunk_size=10),
            ):
                start = time.perf_counter()
                async for _ in run_agent(prompt=f"Message {i}", session=session, model=model):
                    pass
                latencies.append(time.perf_counter() - start)

        first_5_avg = sum(latencies[:5]) / 5
        last_5_avg = sum(latencies[-5:]) / 5

        ratio = last_5_avg / first_5_avg if first_5_avg > 0 else 1.0
        assert ratio < 5.0, (
            f"Session scaling degradation: first 5 avg={first_5_avg:.4f}s, "
            f"last 5 avg={last_5_avg:.4f}s, ratio={ratio:.2f}x"
        )


class TestAbortLatency:
    """Measure how quickly abort terminates the agent loop."""

    @pytest.mark.asyncio
    async def test_abort_stops_quickly(self) -> None:
        session = SessionManager.in_memory()
        model = ModelConfig(provider="openai", model_id="gpt-4o", api_key="test")
        abort = asyncio.Event()

        async def slow_stream(model: Any, messages: Any, tool_defs: Any = None):
            for i in range(100):
                yield AgentEvent(type="message_update", delta=f"chunk{i} ")
                await asyncio.sleep(0.01)
            yield AgentEvent(type="message_end")

        with patch("pyclaw.agents.runner.stream_llm", slow_stream):
            events: list[AgentEvent] = []
            start = time.perf_counter()

            async def run():
                async for event in run_agent(prompt="Long", session=session, model=model, abort_event=abort):
                    events.append(event)

            task = asyncio.create_task(run())
            await asyncio.sleep(0.05)
            abort.set()

            await asyncio.wait_for(task, timeout=2.0)
            elapsed = time.perf_counter() - start

            assert elapsed < 2.0, f"Abort took too long: {elapsed:.3f}s"


class TestProgressTrackerPerformance:
    """Measure ProgressTracker overhead."""

    def test_emit_progress_throughput(self) -> None:
        from pyclaw.agents.progress import (
            ProgressEvent,
            ProgressStatus,
            add_progress_listener,
            emit_progress,
            remove_progress_listener,
        )

        received = 0

        def listener(e: ProgressEvent) -> None:
            nonlocal received
            received += 1

        add_progress_listener(listener)
        try:
            start = time.perf_counter()
            for i in range(10000):
                emit_progress(
                    ProgressEvent(
                        task_id="bench",
                        status=ProgressStatus.PROGRESS,
                        progress=i / 10000,
                    )
                )
            elapsed = time.perf_counter() - start

            assert received == 10000
            assert elapsed < 1.0, f"10k progress events took {elapsed:.3f}s (should be <1s)"
            rate = received / elapsed
            assert rate > 10000, f"Progress event rate too low: {rate:.0f}/s"
        finally:
            remove_progress_listener(listener)
