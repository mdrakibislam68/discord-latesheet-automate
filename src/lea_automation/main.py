from __future__ import annotations

import asyncio
import os
import signal

from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

from lea_automation.config import load_config
from lea_automation.logging_setup import get_logger, setup_logging
from lea_automation.orchestrator import Orchestrator

from discord_bot import SigninBot, BotConfig

logger = get_logger(__name__)


class Application:
    def __init__(self) -> None:
        self._config = load_config()
        self._orchestrator = Orchestrator(self._config)
        
        bot_config = BotConfig.from_env()
        self._bot = SigninBot(bot_config, self._orchestrator)
        
        self._http_server: asyncio.AbstractServer | None = None

    async def _health_handler(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Connection: close\r\n"
            f"Content-Length: 25\r\n"
            "\r\n"
            '{"status":"healthy"}\n'
        )
        writer.write(response.encode())
        await writer.drain()
        writer.close()

    async def start(self) -> None:
        setup_logging(self._config.log_level)
        logger.info(
            "application_starting",
            extra={
                "extra_fields": {
                    "cutoff_time": self._config.cutoff_time,
                    "timezone": self._config.timezone,
                    "log_level": self._config.log_level,
                }
            },
        )

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        self._http_server = await asyncio.start_server(
            self._health_handler,
            host="0.0.0.0",
            port=self._config.port,
        )
        logger.info(
            "health_server_started",
            extra={"extra_fields": {"port": self._config.port}},
        )

        # Run both the Orchestrator and the Discord Bot concurrently
        await asyncio.gather(
            self._orchestrator.run(),
            self._bot.start()
        )

    async def stop(self) -> None:
        logger.info("application_shutdown_initiated")
        await self._orchestrator.shutdown()
        if self._http_server:
            self._http_server.close()
            await self._http_server.wait_closed()
        logger.info("application_shutdown_complete")

        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    app = Application()
    try:
        asyncio.run(app.start())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
