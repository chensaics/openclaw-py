"""Twilio voice call provider.

Implements the VoiceProvider interface using the Twilio REST API
and TwiML for call control.
"""

from __future__ import annotations

import logging
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

import aiohttp

from pyclaw.channels.voice_call.types import CallInfo, CallState, VoiceProvider, VoiceResponse

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01/Accounts"


class TwilioProvider(VoiceProvider):
    """Twilio voice call provider."""

    def __init__(self, account_sid: str, auth_token: str) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token

    def _auth(self) -> aiohttp.BasicAuth:
        return aiohttp.BasicAuth(self._account_sid, self._auth_token)

    def _calls_url(self) -> str:
        return f"{TWILIO_API_BASE}/{self._account_sid}/Calls"

    async def make_call(self, to: str, from_: str, url: str) -> CallInfo:
        async with (
            aiohttp.ClientSession(auth=self._auth()) as session,
            session.post(
                f"{self._calls_url()}.json",
                data={"To": to, "From": from_, "Url": url},
            ) as resp,
        ):
            data = await resp.json()
            return CallInfo(
                call_sid=data.get("sid", ""),
                from_number=from_,
                to_number=to,
                state=_map_twilio_status(data.get("status", "")),
                direction=data.get("direction", "outbound-api"),
            )

    async def answer_call(self, call_sid: str, response: VoiceResponse) -> None:
        twiml = _build_twiml(response)
        async with aiohttp.ClientSession(auth=self._auth()) as session:
            await session.post(
                f"{self._calls_url()}/{call_sid}.json",
                data={"Twiml": twiml},
            )

    async def hang_up(self, call_sid: str) -> None:
        async with aiohttp.ClientSession(auth=self._auth()) as session:
            await session.post(
                f"{self._calls_url()}/{call_sid}.json",
                data={"Status": "completed"},
            )

    async def get_call(self, call_sid: str) -> CallInfo | None:
        async with aiohttp.ClientSession(auth=self._auth()) as session:
            async with session.get(f"{self._calls_url()}/{call_sid}.json") as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return CallInfo(
                    call_sid=data.get("sid", call_sid),
                    from_number=data.get("from_formatted", data.get("from", "")),
                    to_number=data.get("to_formatted", data.get("to", "")),
                    state=_map_twilio_status(data.get("status", "")),
                    direction=data.get("direction", ""),
                    duration_s=int(data.get("duration", 0) or 0),
                )

    def parse_webhook(self, data: dict[str, Any]) -> CallInfo:
        return CallInfo(
            call_sid=data.get("CallSid", ""),
            from_number=data.get("From", ""),
            to_number=data.get("To", ""),
            state=_map_twilio_status(data.get("CallStatus", "")),
            direction=data.get("Direction", "inbound"),
            metadata={
                "speech_result": data.get("SpeechResult", ""),
                "digits": data.get("Digits", ""),
                "recording_url": data.get("RecordingUrl", ""),
            },
        )


def _map_twilio_status(status: str) -> CallState:
    mapping: dict[str, CallState] = {
        "queued": CallState.RINGING,
        "ringing": CallState.RINGING,
        "in-progress": CallState.IN_PROGRESS,
        "completed": CallState.COMPLETED,
        "busy": CallState.BUSY,
        "failed": CallState.FAILED,
        "no-answer": CallState.NO_ANSWER,
        "canceled": CallState.CANCELED,
    }
    return mapping.get(status, CallState.RINGING)


def _build_twiml(response: VoiceResponse) -> str:
    """Convert VoiceResponse actions to TwiML XML string."""
    root = Element("Response")
    for action in response.actions:
        action_type = action.get("type", "")
        if action_type == "say":
            elem = SubElement(root, "Say")
            elem.text = action.get("text", "")
            elem.set("voice", action.get("voice", "alice"))
            elem.set("language", action.get("language", "en-US"))
        elif action_type == "gather":
            elem = SubElement(root, "Gather")
            elem.set("input", action.get("input", "speech"))
            elem.set("timeout", str(action.get("timeout", 5)))
            if action.get("action"):
                elem.set("action", action["action"])
        elif action_type == "play":
            elem = SubElement(root, "Play")
            elem.text = action.get("url", "")
        elif action_type == "hangup":
            SubElement(root, "Hangup")
        elif action_type == "pause":
            elem = SubElement(root, "Pause")
            elem.set("length", str(action.get("length", 1)))
        elif action_type == "redirect":
            elem = SubElement(root, "Redirect")
            elem.text = action.get("url", "")
    return tostring(root, encoding="unicode")
