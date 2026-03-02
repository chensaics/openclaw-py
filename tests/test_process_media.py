"""Tests for Phase 29 — process supervisor, command queue, media understanding, video, embeddings."""

from __future__ import annotations

import asyncio

import pytest

from pyclaw.process.supervisor import (
    ManagedProcess,
    ProcessConfig,
    ProcessInfo,
    ProcessScope,
    ProcessState,
    ProcessSupervisor,
    kill_process_tree,
)
from pyclaw.process.command_queue import (
    CommandLane,
    CommandLaneClearedError,
    CommandQueue,
    GatewayDrainingError,
    QueueState,
    QueuedCommand,
)
from pyclaw.media.understanding.extended import (
    ALL_EXTENDED_PROVIDERS,
    DeepgramConfig,
    DeepgramUnderstandingProvider,
    GroqConfig,
    GroqUnderstandingProvider,
    MediaInputType,
    MistralConfig,
    MistralUnderstandingProvider,
    UnderstandingRequest,
    XAIConfig,
    XAIUnderstandingProvider,
    select_provider,
)
from pyclaw.media.understanding.video import (
    MiniMaxVideoConfig,
    MiniMaxVideoProvider,
    MoonshotVideoConfig,
    MoonshotVideoProvider,
    VideoConcurrencyLimiter,
    VideoConfig,
    VideoFrame,
    VideoInfo,
    compute_frame_timestamps,
    should_precheck_audio,
    validate_video,
)
from pyclaw.memory.extended import (
    BatchConfig,
    BatchItem,
    BatchRunner,
    MistralEmbeddingConfig,
    MistralEmbeddingProvider,
    RemoteEmbeddingClient,
    RemoteEmbeddingConfig,
    VoyageConfig,
    VoyageEmbeddingProvider,
)


# ===== Process Supervisor =====

class TestManagedProcess:
    @pytest.mark.asyncio
    async def test_start_echo(self) -> None:
        config = ProcessConfig(command=["echo", "hello"])
        proc = ManagedProcess("p1", config)
        result = await proc.start()
        assert result is True
        assert proc.info.state == ProcessState.RUNNING
        assert proc.info.pid > 0
        # Wait for it to finish
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_stop(self) -> None:
        config = ProcessConfig(command=["sleep", "10"], kill_timeout_s=1.0)
        proc = ManagedProcess("p1", config)
        await proc.start()
        result = await proc.stop()
        assert result is True
        assert proc.info.state == ProcessState.STOPPED

    @pytest.mark.asyncio
    async def test_invalid_command(self) -> None:
        config = ProcessConfig(command=["__nonexistent_cmd__"])
        proc = ManagedProcess("p1", config)
        result = await proc.start()
        assert result is False
        assert proc.info.state == ProcessState.FAILED

    def test_process_info(self) -> None:
        info = ProcessInfo(process_id="p1", scope=ProcessScope.SESSION)
        assert info.uptime_s == 0

    def test_uptime(self) -> None:
        import time
        info = ProcessInfo(process_id="p1", started_at=time.time() - 10)
        assert info.uptime_s >= 9


class TestProcessSupervisor:
    @pytest.mark.asyncio
    async def test_spawn_and_cancel(self) -> None:
        sup = ProcessSupervisor()
        config = ProcessConfig(command=["sleep", "10"], kill_timeout_s=1.0)
        proc = await sup.spawn("p1", config)
        assert sup.active_count == 1
        await sup.cancel("p1", force=True)
        assert sup.total_count == 0

    @pytest.mark.asyncio
    async def test_cancel_by_scope(self) -> None:
        sup = ProcessSupervisor()
        await sup.spawn("s1", ProcessConfig(command=["sleep", "10"], scope=ProcessScope.SESSION, kill_timeout_s=1.0))
        await sup.spawn("g1", ProcessConfig(command=["sleep", "10"], scope=ProcessScope.GATEWAY, kill_timeout_s=1.0))
        cancelled = await sup.cancel_by_scope(ProcessScope.SESSION)
        assert cancelled == 1
        assert sup.total_count == 1
        await sup.stop_all()

    @pytest.mark.asyncio
    async def test_list_processes(self) -> None:
        sup = ProcessSupervisor()
        await sup.spawn("p1", ProcessConfig(command=["echo", "a"]))
        infos = sup.list_processes()
        assert len(infos) == 1
        assert infos[0].process_id == "p1"
        await sup.stop_all()

    def test_kill_process_tree(self) -> None:
        killed = kill_process_tree(999999)
        assert killed == []  # PID doesn't exist


# ===== Command Queue =====

class TestCommandLane:
    def test_enqueue_dequeue(self) -> None:
        lane = CommandLane("default")
        lane.enqueue(QueuedCommand(command_id="c1", lane="default"))
        assert lane.pending_count == 1
        cmd = lane.dequeue()
        assert cmd is not None
        assert cmd.command_id == "c1"

    def test_priority(self) -> None:
        lane = CommandLane("default")
        lane.enqueue(QueuedCommand(command_id="low", lane="default", priority=0))
        lane.enqueue(QueuedCommand(command_id="high", lane="default", priority=10))
        cmd = lane.dequeue()
        assert cmd is not None
        assert cmd.command_id == "high"

    def test_clear(self) -> None:
        lane = CommandLane("default")
        lane.enqueue(QueuedCommand(command_id="c1", lane="default"))
        lane.enqueue(QueuedCommand(command_id="c2", lane="default"))
        cleared = lane.clear()
        assert cleared == 2
        assert lane.pending_count == 0

    def test_stats(self) -> None:
        lane = CommandLane("test")
        lane.enqueue(QueuedCommand(command_id="c1", lane="test"))
        lane.record_completed()
        stats = lane.stats
        assert stats.lane == "test"
        assert stats.completed == 1


class TestCommandQueue:
    def test_enqueue(self) -> None:
        q = CommandQueue()
        q.enqueue(QueuedCommand(command_id="c1", lane="exec"))
        assert q.total_pending == 1

    def test_draining_rejects(self) -> None:
        q = CommandQueue()
        q.drain()
        with pytest.raises(GatewayDrainingError):
            q.enqueue(QueuedCommand(command_id="c1", lane="exec"))

    def test_resume(self) -> None:
        q = CommandQueue()
        q.drain()
        q.resume()
        q.enqueue(QueuedCommand(command_id="c1", lane="exec"))
        assert q.total_pending == 1

    @pytest.mark.asyncio
    async def test_process_lane(self) -> None:
        q = CommandQueue()
        results: list[str] = []

        async def handler(cmd: QueuedCommand) -> bool:
            results.append(cmd.command_id)
            return True

        q.register_handler("exec", handler)
        q.enqueue(QueuedCommand(command_id="c1", lane="exec"))
        q.enqueue(QueuedCommand(command_id="c2", lane="exec"))
        processed = await q.process_lane("exec")
        assert processed == 2
        assert results == ["c1", "c2"]

    def test_clear_lane(self) -> None:
        q = CommandQueue()
        q.enqueue(QueuedCommand(command_id="c1", lane="exec"))
        q.enqueue(QueuedCommand(command_id="c2", lane="exec"))
        cleared = q.clear_lane("exec")
        assert cleared == 2

    def test_stop(self) -> None:
        q = CommandQueue()
        q.enqueue(QueuedCommand(command_id="c1", lane="exec"))
        total = q.stop()
        assert total == 1
        assert q.state == QueueState.STOPPED

    def test_get_stats(self) -> None:
        q = CommandQueue()
        q.enqueue(QueuedCommand(command_id="c1", lane="a"))
        q.enqueue(QueuedCommand(command_id="c2", lane="b"))
        stats = q.get_stats()
        assert "a" in stats
        assert "b" in stats


# ===== Media Understanding Extended =====

class TestGroqProvider:
    def test_supported_types(self) -> None:
        p = GroqUnderstandingProvider(GroqConfig(api_key="test"))
        assert MediaInputType.IMAGE in p.supported_types
        assert MediaInputType.AUDIO in p.supported_types

    def test_build_vision_request(self) -> None:
        p = GroqUnderstandingProvider(GroqConfig(api_key="test"))
        req = UnderstandingRequest(input_type=MediaInputType.IMAGE, url="https://img.com/a.jpg")
        result = p.build_request(req)
        assert "chat/completions" in result["url"]

    def test_build_audio_request(self) -> None:
        p = GroqUnderstandingProvider(GroqConfig(api_key="test"))
        req = UnderstandingRequest(input_type=MediaInputType.AUDIO)
        result = p.build_request(req)
        assert "transcriptions" in result["url"]

    def test_parse_response(self) -> None:
        p = GroqUnderstandingProvider(GroqConfig())
        result = p.parse_response({"choices": [{"message": {"content": "A cat"}}]})
        assert result.text == "A cat"


class TestMistralProvider:
    def test_supported_types(self) -> None:
        p = MistralUnderstandingProvider(MistralConfig())
        assert p.supported_types == [MediaInputType.IMAGE]

    def test_parse(self) -> None:
        p = MistralUnderstandingProvider(MistralConfig())
        result = p.parse_response({
            "choices": [{"message": {"content": "dog"}}],
            "usage": {"total_tokens": 100},
        })
        assert result.text == "dog"
        assert result.tokens_used == 100


class TestDeepgramProvider:
    def test_supported_types(self) -> None:
        p = DeepgramUnderstandingProvider(DeepgramConfig())
        assert p.supported_types == [MediaInputType.AUDIO]

    def test_parse(self) -> None:
        p = DeepgramUnderstandingProvider(DeepgramConfig())
        result = p.parse_response({
            "results": {"channels": [{"alternatives": [{"transcript": "hello world", "confidence": 0.95}]}]},
        })
        assert result.text == "hello world"
        assert result.confidence == 0.95


class TestXAIProvider:
    def test_name(self) -> None:
        p = XAIUnderstandingProvider(XAIConfig())
        assert p.name == "xai"

    def test_build(self) -> None:
        p = XAIUnderstandingProvider(XAIConfig(api_key="k"))
        req = UnderstandingRequest(input_type=MediaInputType.IMAGE, url="https://img.com/a.jpg")
        result = p.build_request(req)
        assert result["body"]["model"] == "grok-2-vision-1212"


class TestProviderSelection:
    def test_select_image(self) -> None:
        providers = [
            DeepgramUnderstandingProvider(DeepgramConfig()),
            GroqUnderstandingProvider(GroqConfig()),
        ]
        p = select_provider(providers, MediaInputType.IMAGE)
        assert p is not None
        assert p.name == "groq"

    def test_select_audio(self) -> None:
        providers = [
            MistralUnderstandingProvider(MistralConfig()),
            DeepgramUnderstandingProvider(DeepgramConfig()),
        ]
        p = select_provider(providers, MediaInputType.AUDIO)
        assert p is not None
        assert p.name == "deepgram"

    def test_select_none(self) -> None:
        providers = [MistralUnderstandingProvider(MistralConfig())]
        assert select_provider(providers, MediaInputType.VIDEO) is None

    def test_all_providers(self) -> None:
        assert len(ALL_EXTENDED_PROVIDERS) == 4


# ===== Video Understanding =====

class TestVideoUtils:
    def test_compute_timestamps(self) -> None:
        ts = compute_frame_timestamps(30.0, max_frames=5, interval_s=10.0)
        assert ts == [0.0, 10.0, 20.0]

    def test_compute_short_video(self) -> None:
        ts = compute_frame_timestamps(3.0, max_frames=10, interval_s=5.0)
        assert ts == [0.0]

    def test_compute_zero(self) -> None:
        ts = compute_frame_timestamps(0.0)
        assert ts == [0.0]

    def test_validate_ok(self) -> None:
        info = VideoInfo(duration_s=60, file_size_bytes=10 * 1024 * 1024)
        issues = validate_video(info, VideoConfig())
        assert issues == []

    def test_validate_too_long(self) -> None:
        info = VideoInfo(duration_s=600)
        issues = validate_video(info, VideoConfig(max_duration_s=300))
        assert len(issues) == 1

    def test_validate_too_large(self) -> None:
        info = VideoInfo(file_size_bytes=200 * 1024 * 1024)
        issues = validate_video(info, VideoConfig(max_file_size_mb=100))
        assert len(issues) == 1

    def test_precheck_audio(self) -> None:
        info = VideoInfo(has_audio=True)
        assert should_precheck_audio(info, VideoConfig(audio_precheck=True))
        assert not should_precheck_audio(info, VideoConfig(audio_precheck=False))


class TestVideoProviders:
    def test_moonshot_build(self) -> None:
        p = MoonshotVideoProvider(MoonshotVideoConfig(api_key="k"))
        frames = [VideoFrame(index=0, timestamp_s=0, url="https://img.com/f0.jpg")]
        req = p.build_frame_request(frames, "Describe")
        assert "moonshot" in req["body"]["model"]

    def test_minimax_build(self) -> None:
        p = MiniMaxVideoProvider(MiniMaxVideoConfig(api_key="k"))
        frames = [VideoFrame(index=0, timestamp_s=0, url="https://img.com/f0.jpg")]
        req = p.build_frame_request(frames, "Describe")
        assert req["body"]["model"] == "abab6.5s-chat"

    def test_parse_response(self) -> None:
        p = MoonshotVideoProvider(MoonshotVideoConfig())
        text = p.parse_response({"choices": [{"message": {"content": "A video"}}]})
        assert text == "A video"


class TestConcurrencyLimiter:
    @pytest.mark.asyncio
    async def test_acquire_release(self) -> None:
        limiter = VideoConcurrencyLimiter(max_concurrent=2)
        await limiter.acquire()
        assert limiter.active_count == 1
        limiter.release()
        assert limiter.active_count == 0


# ===== Memory Extended =====

class TestVoyageProvider:
    def test_name(self) -> None:
        p = VoyageEmbeddingProvider(VoyageConfig())
        assert p.name == "voyage"

    def test_dimension(self) -> None:
        p = VoyageEmbeddingProvider(VoyageConfig(dimension=1024))
        assert p.dimension == 1024

    def test_build_request(self) -> None:
        p = VoyageEmbeddingProvider(VoyageConfig(api_key="k"))
        req = p.build_request(["hello", "world"])
        assert req["body"]["input"] == ["hello", "world"]
        assert "voyage" in req["body"]["model"]

    def test_parse_response(self) -> None:
        p = VoyageEmbeddingProvider(VoyageConfig())
        result = p.parse_response({"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]})
        assert len(result) == 2
        assert result[0] == [0.1, 0.2]


class TestMistralEmbedding:
    def test_build(self) -> None:
        p = MistralEmbeddingProvider(MistralEmbeddingConfig(api_key="k"))
        req = p.build_request(["test"])
        assert "mistral" in req["body"]["model"]

    def test_parse(self) -> None:
        p = MistralEmbeddingProvider(MistralEmbeddingConfig())
        result = p.parse_response({"data": [{"embedding": [1.0, 2.0]}]})
        assert result == [[1.0, 2.0]]


class TestBatchRunner:
    def test_create_batches(self) -> None:
        runner = BatchRunner(BatchConfig(batch_size=2))
        items = [BatchItem(item_id=str(i), text=f"text {i}") for i in range(5)]
        batches = runner.create_batches(items)
        assert len(batches) == 3
        assert len(batches[0]) == 2
        assert len(batches[2]) == 1

    def test_process_batch(self) -> None:
        runner = BatchRunner()
        items = [BatchItem(item_id="1", text="hello")]
        result = runner.process_batch_sync(items, embed_fn=lambda texts: texts)
        assert result.succeeded == 1
        assert result.failed == 0

    def test_process_batch_failure(self) -> None:
        runner = BatchRunner()
        items = [BatchItem(item_id="1", text="hello")]

        def bad_fn(texts: list[str]) -> None:
            raise RuntimeError("fail")

        result = runner.process_batch_sync(items, embed_fn=bad_fn)
        assert result.failed == 1

    def test_total_processed(self) -> None:
        runner = BatchRunner()
        items = [BatchItem(item_id="1", text="a"), BatchItem(item_id="2", text="b")]
        runner.process_batch_sync(items, embed_fn=lambda t: t)
        assert runner.total_processed == 2
        runner.reset()
        assert runner.total_processed == 0


class TestRemoteEmbeddingClient:
    def test_build_request(self) -> None:
        client = RemoteEmbeddingClient(RemoteEmbeddingConfig(
            url="https://embed.example.com/v1/embeddings",
            api_key="k",
            model="custom-embed",
        ))
        req = client.build_request(["hello"])
        assert req["url"] == "https://embed.example.com/v1/embeddings"
        assert req["body"]["model"] == "custom-embed"

    def test_validate_batch_size(self) -> None:
        client = RemoteEmbeddingClient(RemoteEmbeddingConfig(url="u", max_batch_size=10))
        assert client.validate_batch_size(["a"] * 10)
        assert not client.validate_batch_size(["a"] * 11)

    def test_split_batches(self) -> None:
        client = RemoteEmbeddingClient(RemoteEmbeddingConfig(url="u", max_batch_size=3))
        batches = client.split_batches(["a", "b", "c", "d", "e"])
        assert len(batches) == 2
        assert len(batches[0]) == 3
        assert len(batches[1]) == 2
