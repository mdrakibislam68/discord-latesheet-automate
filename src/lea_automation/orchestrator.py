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
            user_id = message.get("user_id", "")
            content = message.get("content", "")

            if not raw_ts:
                logger.warning(
                    "message_missing_timestamp",
                    extra={"extra_fields": {"name": name}},
                )
                return

            dt = _parse_timestamp(raw_ts)
            result = self._time_checker.evaluate(dt, name, user_id)

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

            # Check specifically for "half day" request (case-insensitive)
            is_half_day = (
                message.get("matched_keyword", "").lower() == "half-day"
                or message.get("matched_keyword", "").lower() == "half day"
                or "half day" in content.lower()
                or "half-day" in content.lower()
            )

            if is_half_day:
                status = "half_day"
                self._sheets.append_half_day_entry(
                    name, result["timestamp_utc"], result["timestamp_local"]
                )
            else:
                # Check if the user entered a manual time (e.g. 'Sign in 9:50AM')
                is_manual_allowed, manual_time_str = self._check_manual_time(content, name, result["date"], user_id)
                
                if manual_time_str is not None:
                    if is_manual_allowed:
                        status = "on_time"
                        self._sheets.append_on_time_entry(
                            name, result["timestamp_utc"], result["timestamp_local"]
                        )
                    else:
                        status = "late"
                        # Parse the manual time to construct a localized timestamp so sheets_writer records it!
                        from datetime import datetime
                        local_dt = datetime.fromisoformat(result["timestamp_local"])
                        manual_hour, manual_min = map(int, manual_time_str.split(":"))
                        local_dt_manual = local_dt.replace(hour=manual_hour, minute=manual_min)
                        
                        self._sheets.append_late_entry(
                            name, result["timestamp_utc"], local_dt_manual.isoformat()
                        )
                else:
                    # Normal flow
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

    def _check_manual_time(self, content: str, user: str, local_date_str: str, user_id: str | None = None) -> tuple[bool, str | None]:
        """
        Extracts manual time from the content (e.g. 'Sign in 9:50AM') and checks if it's before cutoff.
        If before cutoff, checks if the user has used manual sign-in <= 3 times in the month.
        Returns (is_manual_before_cutoff_and_allowed, parsed_time_str).
        """
        import re
        import os
        import json
        from datetime import time
        
        # 12-hour format time regex (e.g. 9:50AM, 9:50 AM, 09:50 am)
        match = re.search(r"\b(0?[1-9]|1[0-2]):([0-5][0-9])\s*(AM|PM)\b", content, re.IGNORECASE)
        if not match:
            return False, None
            
        hour_str, minute_str, am_pm = match.groups()
        hour = int(hour_str)
        minute = int(minute_str)
        
        if am_pm.upper() == "AM":
            if hour == 12:
                hour = 0
        else: # PM
            if hour < 12:
                hour += 12
                
        manual_time = time(hour, minute)
        
        # Check if the user is in the second shift
        is_sec = False
        if user and user.lower().strip() in self._config.second_shift_users:
            is_sec = True
        elif user_id and user_id.strip() in self._config.second_shift_users:
            is_sec = True

        if is_sec:
            cutoff_time = time(self._config.second_shift_cutoff_hour, self._config.second_shift_cutoff_minute)
        else:
            cutoff_time = time(self._config.cutoff_hour, self._config.cutoff_minute)
        
        time_str = f"{hour:02d}:{minute:02d}"
        
        # If the manually entered time is AFTER the cutoff, it is always late (no grace count is consumed/used)
        if manual_time >= cutoff_time:
            return False, time_str
            
        # Parse month string from local_date_str (e.g. '2026-05-20' -> '2026-05')
        month_str = local_date_str[:7]
        
        # Load or initialize the persistent manual signins JSON file
        tracking_file = "manual_signins.json"
        data = {"month": month_str, "users": {}}
        
        if os.path.exists(tracking_file):
            try:
                with open(tracking_file, "r") as f:
                    loaded = json.load(f)
                    # Reset if new month
                    if loaded.get("month") == month_str:
                        data = loaded
            except Exception:
                logger.warning("failed_to_load_manual_signins_tracking_file", exc_info=True)
                
        user_count = data["users"].get(user, 0)
        
        if user_count < 3:
            # Increment and save count since this manual sign-in is allowed to be "On Time"!
            data["users"][user] = user_count + 1
            try:
                with open(tracking_file, "w") as f:
                    json.dump(data, f, indent=4)
            except Exception:
                logger.warning("failed_to_save_manual_signins_tracking_file", exc_info=True)
            return True, time_str
            
        return False, time_str

    async def shutdown(self) -> None:
        self._running = False
        logger.info("orchestrator_shutdown_initiated")
