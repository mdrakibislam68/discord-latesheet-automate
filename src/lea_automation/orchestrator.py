from __future__ import annotations

import asyncio
from typing import Callable

from lea_automation.config import Config
from lea_automation.logging_setup import get_logger
from lea_automation.time_check import TimeChecker, _parse_timestamp

logger = get_logger(__name__)

MessageCallback = Callable[["dict"], None]


from discord_bot.handler import SigninHandler
from typing import Any

class Orchestrator(SigninHandler):
    def __init__(self, config: Config) -> None:
        self._config = config
        self._time_checker = TimeChecker(config)
        self._sheets = self._init_sheets(config)
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self._running = False
        self._last_processed_date: str | None = None

    async def handle_signin(self, data: dict[str, Any]) -> None:
        self.enqueue_message(data)

    @staticmethod
    def _init_sheets(config: Config) -> object:
        from lea_automation.sheets_writer import SheetsWriter as _SW
        return _SW(config)

    @property
    def time_checker(self) -> TimeChecker:
        return self._time_checker

    @property
    def sheets(self) -> SheetsWriter:
        return self._sheets

    def enqueue_message(self, message: dict) -> None:
        self._queue.put_nowait(message)

    async def run(self) -> None:
        self._running = True
        logger.info("orchestrator_started")
        try:
            while self._running:
                try:
                    message = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                    await self._process_message(message)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.info("orchestrator_cancelled")
            raise
        finally:
            self._running = False
            logger.info("orchestrator_stopped")

    async def _process_message(self, message: dict) -> None:
        try:
            raw_ts = message.get("timestamp", "")
            name = message.get("user", message.get("author", message.get("name", "unknown")))
            content = message.get("content", "")

            if not raw_ts:
                logger.warning(
                    "message_missing_timestamp",
                    extra={"extra_fields": {"name": name}},
                )
                return

            dt = _parse_timestamp(raw_ts)
            result = self._time_checker.evaluate(dt)

            log_extra = {
                "extra_fields": {
                    "name": name,
                    "result": result,
                    "content_preview": content[:100],
                }
            }

            if not result["is_processed"]:
                logger.info("message_skipped_not_processing_day", extra=log_extra)
                return

            status = "late" if result["is_late"] else "on_time"

            if result["is_late"]:
                self._sheets.append_late_entry(
                    name, result["timestamp_utc"], result["timestamp_local"]
                )
            else:
                self._sheets.append_on_time_entry(
                    name, result["timestamp_utc"], result["timestamp_local"]
                )

            logger.info(
                f"message_{status}",
                extra={
                    "extra_fields": {
                        "name": name,
                        "date": result["date"],
                        "local_time": result["timestamp_local"],
                        "status": status,
                    }
                },
            )

            if (
                self._last_processed_date is not None
                and result["date"] != self._last_processed_date
            ):
                logger.info(
                    "new_day_detected",
                    extra={
                        "extra_fields": {
                            "previous_date": self._last_processed_date,
                            "new_date": result["date"],
                        }
                    },
                )
            self._last_processed_date = result["date"]

        except Exception:
            logger.exception(
                "message_processing_failed",
                extra={"extra_fields": {"message": message}},
            )

    async def shutdown(self) -> None:
        self._running = False
        logger.info("orchestrator_shutdown_initiated")
