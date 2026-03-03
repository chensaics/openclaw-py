"""Microsoft Teams channel plugin — Bot Framework webhook + Graph API.

Ported from ``extensions/msteams/``.
Requires ``botbuilder-core`` and ``aiohttp``.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


class MSTeamsChannel(ChannelPlugin):
    """Microsoft Teams channel using Bot Framework webhook."""

    name = "msteams"

    def __init__(
        self,
        *,
        app_id: str = "",
        app_password: str = "",
        webhook_port: int = 3978,
        allow_from: list[str] | None = None,
        tenant_id: str = "",
    ) -> None:
        self._app_id = app_id
        self._app_password = app_password
        self._webhook_port = webhook_port
        self._allow_from = set(allow_from) if allow_from else None
        self._tenant_id = tenant_id
        self._handler: Any = None
        self._server: Any = None

    async def start(self) -> None:
        try:
            from aiohttp import web
        except ImportError:
            raise RuntimeError("aiohttp required: pip install aiohttp")

        app = web.Application()
        app.router.add_post("/api/messages", self._handle_webhook)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._webhook_port)
        await site.start()
        self._server = runner
        logger.info("MS Teams webhook listening on port %d", self._webhook_port)

    async def stop(self) -> None:
        if self._server:
            await self._server.cleanup()
            self._server = None

    async def send(self, reply: ChannelReply) -> None:
        """Send a reply via Graph API or Bot Framework."""
        await self._send_via_graph(reply)

    def on_message(self, handler: Any) -> None:
        self._handler = handler

    async def _handle_webhook(self, request: Any) -> Any:
        from aiohttp import web

        try:
            body = await request.json()
        except Exception:
            return web.Response(status=400, text="Bad request")

        activity_type = body.get("type", "")
        if activity_type != "message":
            return web.Response(status=200)

        sender_id = body.get("from", {}).get("id", "")
        sender_name = body.get("from", {}).get("name", "")
        text = body.get("text", "").strip()

        # Remove @mention prefix
        if body.get("entities"):
            for entity in body["entities"]:
                if entity.get("type") == "mention":
                    mention_text = entity.get("text", "")
                    text = text.replace(mention_text, "").strip()

        if self._allow_from and sender_id not in self._allow_from:
            return web.Response(status=200)

        conversation = body.get("conversation", {})
        is_group = conversation.get("conversationType") in ("groupChat", "channel")

        msg = ChannelMessage(
            channel_id="msteams",
            sender_id=sender_id,
            sender_name=sender_name or sender_id,
            text=text,
            chat_id=conversation.get("id", "") or sender_id,
            raw=body,
            is_group=is_group,
            group_id=conversation.get("id", ""),
            display_name=sender_name,
        )

        if self._handler:
            await self._handler(msg)

        return web.Response(status=200)

    async def _send_via_graph(self, reply: ChannelReply) -> None:
        """Send message via Microsoft Graph API."""
        try:
            import aiohttp
        except ImportError:
            logger.error("aiohttp required for MS Teams send")
            return

        token = await self._get_bot_token()
        if not token:
            logger.error("Failed to get bot token")
            return

        url = f"https://graph.microsoft.com/v1.0/chats/{reply.recipient}/messages"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"body": {"content": reply.text}}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status >= 400:
                    logger.error("Teams send error: %d", resp.status)

    async def _get_bot_token(self) -> str | None:
        """Get an OAuth token for the bot."""
        try:
            import aiohttp
        except ImportError:
            return None

        url = f"https://login.microsoftonline.com/{self._tenant_id or 'botframework.com'}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self._app_id,
            "client_secret": self._app_password,
            "scope": "https://api.botframework.com/.default",
        }

        async with aiohttp.ClientSession() as session, session.post(url, data=data) as resp:
            if resp.status == 200:
                result = await resp.json()
                return cast(str | None, result.get("access_token"))
        return None
