"""Voice Call channel -- webhook-based voice interaction.

Receives inbound calls via webhooks, uses STT (speech-to-text) to
convert speech input, processes via the agent, and responds with
TTS (text-to-speech) via the voice provider.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import web

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply
from pyclaw.channels.voice_call.types import CallInfo, CallState, VoiceProvider, VoiceResponse

logger = logging.getLogger(__name__)


class VoiceCallChannel(ChannelPlugin):
    """Voice call channel using a pluggable VoiceProvider."""

    def __init__(
        self,
        provider: VoiceProvider,
        *,
        port: int = 8070,
        webhook_path: str = "/voice",
        on_message: Any = None,
    ) -> None:
        self._provider = provider
        self._port = port
        self._webhook_path = webhook_path
        self._on_message = on_message
        self._runner: web.AppRunner | None = None
        self._active_calls: dict[str, CallInfo] = {}

    @property
    def id(self) -> str:
        return "voice-call"

    async def start(self) -> None:
        app = web.Application()
        app.router.add_post(self._webhook_path, self._handle_webhook)
        app.router.add_post(f"{self._webhook_path}/gather", self._handle_gather)
        app.router.add_post(f"{self._webhook_path}/status", self._handle_status)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        logger.info("Voice Call webhook listening on port %d", self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        data = dict(await request.post())
        call_info = self._provider.parse_webhook(data)
        self._active_calls[call_info.call_sid] = call_info

        response = VoiceResponse()
        response.say("Hello, this is pyclaw. How can I help you?")
        response.gather(
            input_type="speech",
            timeout=5,
            action_url=f"{self._webhook_path}/gather",
        )
        response.say("I didn't hear anything. Goodbye.")
        response.hangup()

        await self._provider.answer_call(call_info.call_sid, response)
        return web.Response(
            text=_voice_response_to_twiml(response),
            content_type="application/xml",
        )

    async def _handle_gather(self, request: web.Request) -> web.Response:
        data = dict(await request.post())
        call_info = self._provider.parse_webhook(data)
        speech = call_info.metadata.get("speech_result", "")

        if not speech:
            response = VoiceResponse()
            response.say("I didn't catch that. Could you repeat?")
            response.gather(
                input_type="speech",
                timeout=5,
                action_url=f"{self._webhook_path}/gather",
            )
            return web.Response(
                text=_voice_response_to_twiml(response),
                content_type="application/xml",
            )

        msg = ChannelMessage(
            channel="voice-call",
            sender_id=call_info.from_number,
            text=speech,
            raw={"call_sid": call_info.call_sid, "from": call_info.from_number},
        )

        if self._on_message:
            result = self._on_message(msg)
            if asyncio.iscoroutine(result):
                await result

        response = VoiceResponse()
        response.say("Let me think about that...")
        response.pause(length=2)
        response.gather(
            input_type="speech",
            timeout=10,
            action_url=f"{self._webhook_path}/gather",
        )
        return web.Response(
            text=_voice_response_to_twiml(response),
            content_type="application/xml",
        )

    async def _handle_status(self, request: web.Request) -> web.Response:
        data = dict(await request.post())
        call_info = self._provider.parse_webhook(data)
        if call_info.state in (CallState.COMPLETED, CallState.FAILED, CallState.CANCELED):
            self._active_calls.pop(call_info.call_sid, None)
        return web.Response(status=200, text="ok")

    async def send_reply(self, reply: ChannelReply) -> None:
        call_sid = reply.raw.get("call_sid", "") if reply.raw else ""
        if not call_sid:
            logger.warning("No call_sid for voice reply")
            return

        response = VoiceResponse()
        response.say(reply.text)
        response.gather(
            input_type="speech",
            timeout=10,
            action_url=f"{self._webhook_path}/gather",
        )
        await self._provider.answer_call(call_sid, response)


def _voice_response_to_twiml(response: VoiceResponse) -> str:
    from pyclaw.channels.voice_call.twilio_provider import _build_twiml

    return _build_twiml(response)
