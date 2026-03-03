"""Voice Call channel -- webhook-based voice interaction.

Receives inbound calls via webhooks, uses STT (speech-to-text) to
convert speech input, processes via the agent, and responds with
TTS (text-to-speech) via the voice provider.
"""

from __future__ import annotations

import asyncio
import base64
import errno
import hashlib
import hmac
import logging
from typing import Any
from urllib.parse import urlparse

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
        auth_token: str = "",
    ) -> None:
        self._provider = provider
        self._port = port
        self._webhook_path = webhook_path
        self._on_message = on_message
        self._auth_token: str = auth_token
        self._runner: web.AppRunner | None = None
        self._active_calls: dict[str, CallInfo] = {}
        self._call_queue: asyncio.Queue[CallInfo] = asyncio.Queue()

    @property
    def id(self) -> str:
        return "voice-call"

    def _verify_twilio_signature(
        self,
        url: str,
        params: dict[str, str],
        signature: str,
    ) -> bool:
        """Verify Twilio webhook signature using HMAC-SHA1."""
        if not self._auth_token or not signature:
            return not bool(self._auth_token)
        try:
            parsed = urlparse(url)
            candidates = [url]
            if parsed.port:
                netloc_no_port = parsed.hostname or parsed.netloc.split(":")[0]
                candidates.append(f"{parsed.scheme}://{netloc_no_port}{parsed.path or ''}{parsed.query and '?' + parsed.query or ''}")
            else:
                port = 443 if parsed.scheme == "https" else 80
                candidates.append(f"{parsed.scheme}://{parsed.netloc}:{port}{parsed.path or ''}{parsed.query and '?' + parsed.query or ''}")
            for uri in candidates:
                s = uri
                if params:
                    for key in sorted(params):
                        s += key + str(params.get(key, ""))
                mac = hmac.new(
                    self._auth_token.encode("utf-8"),
                    s.encode("utf-8"),
                    hashlib.sha1,
                )
                expected = base64.b64encode(mac.digest()).decode("utf-8").strip()
                if hmac.compare_digest(expected, signature):
                    return True
            return False
        except Exception:
            return False

    async def start(self) -> None:
        app = web.Application()
        app.router.add_post(self._webhook_path, self._handle_webhook)
        app.router.add_post(f"{self._webhook_path}/gather", self._handle_gather)
        app.router.add_post(f"{self._webhook_path}/status", self._handle_status)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        try:
            await site.start()
        except OSError as e:
            if getattr(e, "errno", None) == errno.EADDRINUSE or "address already in use" in str(e).lower():
                logger.error(
                    "Port %d already in use. Another process may be listening. "
                    "Try a different port or stop the conflicting service.",
                    self._port,
                )
            raise
        logger.info("Voice Call webhook listening on port %d", self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        data = dict(await request.post())
        sig = request.headers.get("X-Twilio-Signature", "") or request.headers.get("x-twilio-signature", "")
        if not self._verify_twilio_signature(str(request.url), data, sig):
            return web.Response(status=403, text="Forbidden")
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
        sig = request.headers.get("X-Twilio-Signature", "") or request.headers.get("x-twilio-signature", "")
        if not self._verify_twilio_signature(str(request.url), data, sig):
            return web.Response(status=403, text="Forbidden")
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
            channel_id="voice-call",
            sender_id=call_info.from_number,
            sender_name=call_info.from_number,
            text=speech,
            chat_id=call_info.from_number,
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
