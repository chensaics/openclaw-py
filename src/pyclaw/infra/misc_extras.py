"""Miscellaneous extras — Discord voice, TLS fingerprint, VoiceWake, process respawn, clipboard, etc.

Ported from various small modules across the TypeScript codebase.

Provides:
- Discord voice basics (join/leave/state)
- TLS fingerprint for connection verification
- VoiceWake state management
- Process respawn with backoff
- Clipboard read/write helpers
- Config channel type validation
- Agent schema cleanup
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import platform
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Discord Voice Basics
# ---------------------------------------------------------------------------


class VoiceConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class VoiceConnection:
    """Represents a Discord voice connection."""

    guild_id: str
    channel_id: str
    state: VoiceConnectionState = VoiceConnectionState.DISCONNECTED
    connected_at: float = 0.0
    user_count: int = 0

    def connect(self) -> None:
        self.state = VoiceConnectionState.CONNECTED
        self.connected_at = time.time()

    def disconnect(self) -> None:
        self.state = VoiceConnectionState.DISCONNECTED
        self.connected_at = 0.0

    @property
    def is_connected(self) -> bool:
        return self.state in (VoiceConnectionState.CONNECTED, VoiceConnectionState.SPEAKING)


class VoiceManager:
    """Manage Discord voice connections."""

    def __init__(self) -> None:
        self._connections: dict[str, VoiceConnection] = {}

    def join(self, guild_id: str, channel_id: str) -> VoiceConnection:
        conn = VoiceConnection(guild_id=guild_id, channel_id=channel_id)
        conn.connect()
        self._connections[guild_id] = conn
        return conn

    def leave(self, guild_id: str) -> bool:
        conn = self._connections.pop(guild_id, None)
        if conn:
            conn.disconnect()
            return True
        return False

    def get(self, guild_id: str) -> VoiceConnection | None:
        return self._connections.get(guild_id)

    @property
    def active_count(self) -> int:
        return sum(1 for c in self._connections.values() if c.is_connected)


# ---------------------------------------------------------------------------
# TLS Fingerprint
# ---------------------------------------------------------------------------


@dataclass
class TLSFingerprint:
    """TLS certificate fingerprint for connection verification."""

    sha256: str = ""
    common_name: str = ""
    issuer: str = ""
    valid_from: str = ""
    valid_to: str = ""

    @property
    def short_hash(self) -> str:
        return self.sha256[:16] if self.sha256 else ""


def compute_tls_fingerprint(cert_pem: str) -> TLSFingerprint:
    """Compute SHA-256 fingerprint from PEM certificate data."""
    import base64

    lines = [l for l in cert_pem.splitlines() if not l.startswith("-----")]
    der_bytes = base64.b64decode("".join(lines))
    sha256 = hashlib.sha256(der_bytes).hexdigest()
    return TLSFingerprint(sha256=sha256)


# ---------------------------------------------------------------------------
# VoiceWake
# ---------------------------------------------------------------------------


@dataclass
class VoiceWakeConfig:
    """VoiceWake configuration."""

    enabled: bool = False
    wake_word: str = "hey pyclaw"
    command_template: str = 'pyclaw-mac agent --message "${text}" --thinking low'
    sensitivity: float = 0.5
    continuous: bool = True


class VoiceWakeState:
    """Track VoiceWake state with optional audio listener.

    When ``start_listening_async`` is called, a background task uses
    ``sounddevice`` to capture microphone audio and ``vosk`` to detect
    the configured wake word.  Falls back to state-only tracking when
    the audio libraries are unavailable.
    """

    def __init__(self, config: VoiceWakeConfig | None = None) -> None:
        self._config = config or VoiceWakeConfig()
        self._listening = False
        self._last_wake: float = 0.0
        self._wake_count: int = 0
        self._task: Any = None
        self._on_wake_callback: Any = None

    def start_listening(self) -> None:
        self._listening = True

    def stop_listening(self) -> None:
        self._listening = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None

    def on_wake(self) -> None:
        self._last_wake = time.time()
        self._wake_count += 1
        if self._on_wake_callback:
            self._on_wake_callback()

    @property
    def is_listening(self) -> bool:
        return self._listening and self._config.enabled

    @property
    def wake_count(self) -> int:
        return self._wake_count

    @property
    def config(self) -> VoiceWakeConfig:
        return self._config

    async def start_listening_async(
        self,
        on_wake: Any = None,
        model_path: str | None = None,
    ) -> bool:
        """Start background mic → vosk wake-word detection.

        Returns True if the listener started successfully, False if
        the required libraries (sounddevice, vosk) are not installed.
        """
        import asyncio

        try:
            import sounddevice  # noqa: F401
            import vosk  # noqa: F401
        except ImportError:
            logger.warning("Voice wake requires 'sounddevice' and 'vosk' packages")
            return False

        self._on_wake_callback = on_wake
        self._listening = True

        async def _listen_loop() -> None:
            import json as _json
            import queue

            import sounddevice as sd
            import vosk

            vosk.SetLogLevel(-1)
            sample_rate = 16000

            effective_model_path = model_path or os.environ.get("VOSK_MODEL_PATH", "")
            if not effective_model_path:
                logger.error("VOSK_MODEL_PATH not set — cannot start wake-word detection")
                return

            model = vosk.Model(effective_model_path)
            rec = vosk.KaldiRecognizer(model, sample_rate)
            audio_queue: queue.Queue[bytes] = queue.Queue()

            def _audio_cb(indata: Any, frames: int, time_info: Any, status: Any) -> None:
                audio_queue.put(bytes(indata))

            wake_lower = self._config.wake_word.lower()

            with sd.RawInputStream(
                samplerate=sample_rate,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=_audio_cb,
            ):
                while self._listening:
                    try:
                        data = audio_queue.get(timeout=0.5)
                    except queue.Empty:
                        await asyncio.sleep(0.1)
                        continue

                    if rec.AcceptWaveform(data):
                        result = _json.loads(rec.Result())
                        text = result.get("text", "").lower()
                        if wake_lower in text:
                            self.on_wake()
                            logger.info("Wake word detected: '%s'", text)

                    await asyncio.sleep(0)

        self._task = asyncio.create_task(_listen_loop())
        return True


# ---------------------------------------------------------------------------
# Process Respawn
# ---------------------------------------------------------------------------


@dataclass
class RespawnConfig:
    """Configuration for process respawn."""

    max_respawns: int = 5
    initial_delay_s: float = 1.0
    max_delay_s: float = 60.0
    reset_after_s: float = 300.0


class RespawnTracker:
    """Track respawn attempts with exponential backoff."""

    def __init__(self, config: RespawnConfig | None = None) -> None:
        self._config = config or RespawnConfig()
        self._count = 0
        self._first_respawn: float = 0.0
        self._last_respawn: float = 0.0

    def should_respawn(self) -> bool:
        if self._count >= self._config.max_respawns:
            if self._first_respawn and (time.time() - self._first_respawn) > self._config.reset_after_s:
                self.reset()
                return True
            return False
        return True

    def record_respawn(self) -> float:
        """Record a respawn and return the delay to wait."""
        now = time.time()
        if self._count == 0:
            self._first_respawn = now
        self._count += 1
        self._last_respawn = now

        delay = min(
            self._config.initial_delay_s * (2 ** (self._count - 1)),
            self._config.max_delay_s,
        )
        return cast(float, delay)

    def reset(self) -> None:
        self._count = 0
        self._first_respawn = 0.0

    @property
    def respawn_count(self) -> int:
        return self._count


class ProcessRespawner:
    """Auto-restart a subprocess with backoff on failure.

    Wraps ``RespawnTracker`` with actual ``asyncio.subprocess`` management.
    """

    def __init__(
        self,
        cmd: list[str],
        *,
        config: RespawnConfig | None = None,
        env: dict[str, str] | None = None,
        on_exit: Any = None,
    ) -> None:
        self._cmd = cmd
        self._env = {**os.environ, **(env or {})}
        self._tracker = RespawnTracker(config)
        self._proc: Any = None
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._on_exit = on_exit

    async def start(self) -> None:
        """Launch the managed process and start the watchdog loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._supervise())

    async def stop(self) -> None:
        """Terminate the managed process and stop the watchdog."""
        self._running = False
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=10)
            except (TimeoutError, Exception):
                self._proc.kill()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _supervise(self) -> None:
        while self._running:
            try:
                self._proc = await asyncio.create_subprocess_exec(
                    *self._cmd,
                    env=self._env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                logger.info("Process started: pid=%s cmd=%s", self._proc.pid, self._cmd[0])
                await self._proc.wait()
                exit_code = self._proc.returncode
                logger.warning("Process exited: pid=%s code=%s", self._proc.pid, exit_code)
            except Exception as exc:
                exit_code = -1
                logger.error("Process spawn failed: %s", exc)

            if self._on_exit:
                try:
                    self._on_exit(exit_code)
                except Exception:
                    pass

            if not self._running:
                break
            if exit_code == 0:
                logger.info("Process exited cleanly, not respawning")
                break
            if not self._tracker.should_respawn():
                logger.error("Max respawns (%d) reached", self._tracker._config.max_respawns)
                break

            delay = self._tracker.record_respawn()
            logger.info("Respawning in %.1fs (attempt %d)", delay, self._tracker.respawn_count)
            await asyncio.sleep(delay)

    @property
    def is_running(self) -> bool:
        return self._running and self._proc is not None and self._proc.returncode is None

    @property
    def respawn_count(self) -> int:
        return self._tracker.respawn_count


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------


def clipboard_read() -> str:
    """Read from system clipboard. Returns empty string on failure."""
    try:
        if platform.system() == "Darwin":
            return subprocess.check_output(["pbpaste"], text=True, timeout=5)
        if platform.system() == "Linux":
            return subprocess.check_output(
                ["xclip", "-selection", "clipboard", "-o"],
                text=True,
                timeout=5,
            )
        if platform.system() == "Windows":
            return subprocess.check_output(
                ["powershell", "-Command", "Get-Clipboard"],
                text=True,
                timeout=5,
            )
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return ""


def clipboard_write(text: str) -> bool:
    """Write to system clipboard. Returns True on success."""
    try:
        if platform.system() == "Darwin":
            subprocess.run(["pbcopy"], input=text, text=True, check=True, timeout=5)
            return True
        if platform.system() == "Linux":
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                text=True,
                check=True,
                timeout=5,
            )
            return True
        if platform.system() == "Windows":
            subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{text}'"],
                check=True,
                timeout=5,
            )
            return True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return False


# ---------------------------------------------------------------------------
# Config Channel Type Validation
# ---------------------------------------------------------------------------

VALID_CHANNEL_TYPES = frozenset(
    {
        "telegram",
        "discord",
        "slack",
        "whatsapp",
        "signal",
        "imessage",
        "irc",
        "msteams",
        "matrix",
        "feishu",
        "twitch",
        "bluebubbles",
        "googlechat",
        "synology",
        "mattermost",
        "nextcloud",
        "tlon",
        "zalo",
        "zalouser",
        "nostr",
        "line",
        "voicecall",
        "web",
    }
)


def validate_channel_type(channel_type: str) -> bool:
    return channel_type.lower() in VALID_CHANNEL_TYPES


# ---------------------------------------------------------------------------
# Agent Schema Cleanup
# ---------------------------------------------------------------------------


def cleanup_agent_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Clean up an agent configuration schema, removing deprecated fields."""
    deprecated = {"legacy_mode", "v1_compat", "old_format", "__internal__"}
    return {k: v for k, v in schema.items() if k not in deprecated}
