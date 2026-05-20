from __future__ import annotations

import datetime
import re
from discord_bot.config import BotConfig


class SigninFilter:
    def __init__(self, config: BotConfig) -> None:
        self._patterns: list[tuple[re.Pattern[str], str]] = []
        for kw in config.signin_keywords:
            escaped = re.escape(kw)
            pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
            self._patterns.append((pattern, kw))
        self._patterns.sort(key=lambda x: len(x[1]), reverse=True)
        self._start_hour = config.active_start_hour
        self._start_minute = config.active_start_minute
        self._end_hour = config.active_end_hour
        self._end_minute = config.active_end_minute

    def is_signin(self, content: str) -> str | None:
        for pattern, kw in self._patterns:
            if pattern.search(content):
                return kw
        return None

    def is_within_active_hours(self, dt: datetime.datetime) -> bool:
        start = datetime.time(self._start_hour, self._start_minute)
        end = datetime.time(self._end_hour, self._end_minute)
        t = dt.time()
        return start <= t <= end
