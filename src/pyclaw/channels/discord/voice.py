"""Discord voice channel — join/leave/speak in voice channels.

Uses discord.py voice support (requires PyNaCl + FFmpeg).
Provides voice connection management, TTS playback, and STT recording.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("pyclaw.channels.discord.voice")


class DiscordVoiceManager:
    """Manage Discord voice connections for a bot client."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._connections: dict[int, Any] = {}  # guild_id → VoiceClient

    @property
    def active_connections(self) -> int:
        return sum(1 for vc in self._connections.values() if vc.is_connected())

    async def join(self, channel_id: int) -> bool:
        """Join a voice channel by ID."""
        try:
            channel = self._client.get_channel(channel_id)
            if channel is None:
                channel = await self._client.fetch_channel(channel_id)

            if not hasattr(channel, "guild"):
                logger.warning("Channel %d is not a guild voice channel", channel_id)
                return False

            guild_id = channel.guild.id

            existing = self._connections.get(guild_id)
            if existing and existing.is_connected():
                await existing.move_to(channel)
                return True

            vc = await channel.connect()
            self._connections[guild_id] = vc
            logger.info("Joined voice channel %d (guild %d)", channel_id, guild_id)
            return True
        except Exception:
            logger.exception("Failed to join voice channel %d", channel_id)
            return False

    async def leave(self, guild_id: int) -> bool:
        """Leave the voice channel in a guild."""
        vc = self._connections.pop(guild_id, None)
        if vc and vc.is_connected():
            await vc.disconnect()
            logger.info("Left voice in guild %d", guild_id)
            return True
        return False

    async def leave_all(self) -> None:
        """Disconnect from all voice channels."""
        for guild_id in list(self._connections.keys()):
            await self.leave(guild_id)

    async def speak_tts(
        self,
        guild_id: int,
        text: str,
        voice: str = "en-US-AriaNeural",
    ) -> bool:
        """Synthesize text with edge-tts and play in the voice channel."""
        vc = self._connections.get(guild_id)
        if not vc or not vc.is_connected():
            logger.warning("Not connected to voice in guild %d", guild_id)
            return False

        try:
            from pyclaw.ui.voice import synthesize_speech

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                audio_path = Path(tmp.name)

            await synthesize_speech(text, voice=voice, output_path=str(audio_path))

            import discord

            source = discord.FFmpegPCMAudio(str(audio_path))
            if vc.is_playing():
                vc.stop()

            done = asyncio.Event()
            vc.play(source, after=lambda e: done.set())
            await done.wait()

            audio_path.unlink(missing_ok=True)
            return True

        except ImportError:
            logger.warning("edge-tts or FFmpeg not available for voice TTS")
            return False
        except Exception:
            logger.exception("Voice TTS playback failed")
            return False

    async def record_and_transcribe(
        self,
        guild_id: int,
        duration_s: float = 10.0,
    ) -> str:
        """Record audio from the voice channel and transcribe.

        Note: discord.py receive audio requires additional setup.
        This is a simplified implementation that records for a fixed duration.
        """
        vc = self._connections.get(guild_id)
        if not vc or not vc.is_connected():
            return ""

        try:
            sink = _PCMSink()
            vc.start_recording(sink, _on_recording_done)
            await asyncio.sleep(duration_s)
            vc.stop_recording()

            if not sink.audio_data:
                return ""

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav_path = Path(tmp.name)
                _write_wav(wav_path, sink.audio_data)

            from pyclaw.ui.voice import transcribe_audio

            text = await transcribe_audio(str(wav_path))
            wav_path.unlink(missing_ok=True)
            return text

        except Exception:
            logger.debug("Voice recording/transcription failed", exc_info=True)
            return ""

    def get_connection(self, guild_id: int) -> Any | None:
        vc = self._connections.get(guild_id)
        if vc and vc.is_connected():
            return vc
        return None

    def status(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for guild_id, vc in self._connections.items():
            result.append(
                {
                    "guildId": guild_id,
                    "connected": vc.is_connected() if vc else False,
                    "channelId": vc.channel.id if vc and vc.channel else None,
                }
            )
        return result


class _PCMSink:
    """Simple PCM audio accumulator for discord.py recording."""

    def __init__(self) -> None:
        self.audio_data = bytearray()

    def write(self, data: bytes) -> None:
        self.audio_data.extend(data)

    def cleanup(self) -> None:
        self.audio_data.clear()


def _on_recording_done(sink: Any, *args: Any) -> None:
    pass


def _write_wav(path: Path, pcm_data: bytes | bytearray, sample_rate: int = 48000) -> None:
    """Write raw PCM data as a WAV file."""
    import struct

    channels = 2
    bits_per_sample = 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm_data)

    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))
        f.write(struct.pack("<H", 1))  # PCM
        f.write(struct.pack("<H", channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits_per_sample))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(pcm_data)
