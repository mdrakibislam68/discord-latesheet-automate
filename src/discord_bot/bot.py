from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

import discord

from discord_bot.config import BotConfig
from discord_bot.filter import SigninFilter
from discord_bot.handler import SigninHandler

logger = logging.getLogger(__name__)


class SigninBot:
    def __init__(
        self,
        config: BotConfig,
        handler: SigninHandler,
    ) -> None:
        self._config = config
        self._filter = SigninFilter(config)
        self._handler = handler
        self._client: discord.Client | None = None
        self._running = False

    async def start(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True

        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_ready() -> None:
            logger.info(
                "bot_connected",
                extra={"extra_fields": {"user": str(self._client.user)}},
            )

        @self._client.event
        async def on_message(message: discord.Message) -> None:
            if message.author.bot:
                return

            if message.channel.id != self._config.channel_id:
                return

            matched_keyword = self._filter.is_signin(message.content)
            
            if not matched_keyword:
                logger.debug(
                    "message_skipped",
                    extra={
                        "extra_fields": {
                            "author": message.author.name,
                            "content_preview": message.content[:100],
                        }
                    },
                )
                return

            data: dict[str, Any] = {
                "user": message.author.name,
                "user_id": str(message.author.id),
                "timestamp": message.created_at.isoformat(),
                "content": message.content,
                "matched_keyword": matched_keyword or "",
            }
            logger.info(
                "signin_detected",
                extra={
                    "extra_fields": {
                        "user": data["user"],
                        "timestamp": data["timestamp"],
                        "matched_keyword": data["matched_keyword"],
                    }
                },
            )
            await self._handler.handle_signin(data)

        self._running = True

        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig, lambda: asyncio.create_task(self._shutdown(stop_event))
                )
            except NotImplementedError:
                pass

        try:
            async with self._client:
                await self._client.start(self._config.discord_token)
        except asyncio.CancelledError:
            logger.info("bot_cancelled")
        finally:
            self._running = False
            stop_event.set()

    async def _shutdown(self, stop_event: asyncio.Event) -> None:
        logger.info("bot_shutdown_initiated")
        self._running = False
        if self._client:
            await self._client.close()
        stop_event.set()

    async def wait_for_shutdown(self) -> None:
        while self._running:
            await asyncio.sleep(0.5)

    @property
    def is_running(self) -> bool:
        return self._running
