from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BotConfig:
    discord_token: str
    channel_id: int
    signin_keywords: tuple[str, ...] = (
        "here",
        "present",
        "checking in",
        "check-in",
        "i'm here",
    )
    active_hours_start: str = "08:00"
    active_hours_end: str = "10:00"

    @classmethod
    def from_env(cls) -> BotConfig:
        token = os.environ.get("DISCORD_BOT_TOKEN")
        if not token:
            raise ValueError("DISCORD_BOT_TOKEN environment variable is required")

        channel_id_str = os.environ.get("DISCORD_CHANNEL_ID")
        if not channel_id_str:
            raise ValueError("DISCORD_CHANNEL_ID environment variable is required")

        keywords_str = os.environ.get(
            "SIGNIN_KEYWORDS", "here,present,checking in,check-in"
        )
        keywords = tuple(k.strip().lower() for k in keywords_str.split(",") if k.strip())

        return cls(
            discord_token=token,
            channel_id=int(channel_id_str),
            signin_keywords=keywords,
            active_hours_start=os.environ.get(
                "ACTIVE_HOURS_START", "08:00"
            ),
            active_hours_end=os.environ.get("ACTIVE_HOURS_END", "10:00"),
        )

    @property
    def active_start_hour(self) -> int:
        return int(self.active_hours_start.split(":")[0])

    @property
    def active_start_minute(self) -> int:
        return int(self.active_hours_start.split(":")[1])

    @property
    def active_end_hour(self) -> int:
        return int(self.active_hours_end.split(":")[0])

    @property
    def active_end_minute(self) -> int:
        return int(self.active_hours_end.split(":")[1])
