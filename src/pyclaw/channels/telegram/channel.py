"""Telegram channel implementation using aiogram."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger("pyclaw.channels.telegram")


class TelegramChannel(ChannelPlugin):
    """Telegram messaging channel using aiogram long polling."""

    def __init__(
        self,
        *,
        token: str,
        owner_ids: list[int] | None = None,
        allowed_ids: list[int] | None = None,
    ) -> None:
        self._token = token
        self._owner_ids = set(owner_ids or [])
        self._allowed_ids = set(allowed_ids or [])
        self._running = False
        self._bot: Any = None
        self._dp: Any = None
        self._polling_task: asyncio.Task[None] | None = None

    @property
    def id(self) -> str:
        return "telegram"

    @property
    def name(self) -> str:
        return "Telegram"

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        from aiogram import Bot, Dispatcher
        from aiogram.enums import ParseMode

        from aiogram.client.default import DefaultBotProperties
        self._bot = Bot(token=self._token, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
        self._dp = Dispatcher()

        self._register_handlers()

        self._running = True
        logger.info("Telegram channel starting (long polling)")

        self._polling_task = asyncio.create_task(self._run_polling())

    async def _run_polling(self) -> None:
        try:
            await self._dp.start_polling(self._bot)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Telegram polling error")
        finally:
            self._running = False

    async def stop(self) -> None:
        self._running = False
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

        if self._bot:
            session = self._bot.session
            if session:
                await session.close()

        logger.info("Telegram channel stopped")

    async def send_reply(self, reply: ChannelReply) -> None:
        if not self._bot:
            raise RuntimeError("Telegram bot not started")

        kwargs: dict[str, Any] = {}
        if reply.reply_to_message_id:
            kwargs["reply_to_message_id"] = int(reply.reply_to_message_id)

        await self._bot.send_message(
            chat_id=int(reply.chat_id),
            text=reply.text,
            **kwargs,
        )

    def _register_handlers(self) -> None:
        from aiogram import types as tg_types
        from aiogram.filters import Command

        @self._dp.message(Command("start"))  # type: ignore[untyped-decorator]
        async def on_start(message: tg_types.Message) -> None:
            await message.reply("pyclaw is ready. Send me a message!")

        @self._dp.message()  # type: ignore[untyped-decorator]
        async def on_message(message: tg_types.Message) -> None:
            if not message.from_user:
                return

            user_id = message.from_user.id
            is_owner = user_id in self._owner_ids

            if self._allowed_ids and user_id not in self._allowed_ids and not is_owner:
                return

            text = message.text or ""

            # Voice/audio → automatic transcription
            if not text and (message.voice or message.audio):
                text = await self._transcribe_voice(message)

            if not text:
                return

            chat_id = str(message.chat.id)
            is_group = message.chat.type in ("group", "supergroup")

            msg = ChannelMessage(
                channel_id=self.id,
                sender_id=str(user_id),
                sender_name=message.from_user.full_name,
                text=text,
                chat_id=chat_id,
                message_id=str(message.message_id),
                is_group=is_group,
                is_owner=is_owner,
                raw=message,
            )

            if self.message_callback:
                await self.message_callback(msg)

    async def _transcribe_voice(self, message: Any) -> str:
        """Download voice/audio and transcribe via Whisper API."""
        import tempfile
        from pathlib import Path

        try:
            voice = message.voice or message.audio
            if not voice or not self._bot:
                return ""

            file = await self._bot.get_file(voice.file_id)
            if not file.file_path:
                return ""

            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                await self._bot.download_file(file.file_path, destination=tmp)

            transcript = await _whisper_transcribe(tmp_path)
            tmp_path.unlink(missing_ok=True)

            if transcript:
                logger.info("Voice transcribed (%d chars)", len(transcript))
            return transcript
        except Exception:
            logger.debug("Voice transcription failed", exc_info=True)
            return ""


async def _whisper_transcribe(audio_path: Any) -> str:
    """Transcribe audio file using OpenAI Whisper API (or Groq fallback)."""
    import os
    from pathlib import Path

    import httpx

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return ""

    # Try Groq first (free Whisper endpoint), then OpenAI
    providers = []
    groq_key = os.environ.get("GROQ_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    if groq_key:
        providers.append(("https://api.groq.com/openai/v1/audio/transcriptions", groq_key))
    if openai_key:
        providers.append(("https://api.openai.com/v1/audio/transcriptions", openai_key))

    if not providers:
        return ""

    for url, key in providers:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                with open(audio_path, "rb") as f:
                    resp = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {key}"},
                        files={"file": (audio_path.name, f, "audio/ogg")},
                        data={"model": "whisper-large-v3"},
                    )
                if resp.status_code == 200:
                    return cast(str, resp.json().get("text", ""))
        except httpx.HTTPError:
            continue

    return ""
