import os
from dataclasses import dataclass, field
from typing import FrozenSet


@dataclass(frozen=True)
class Config:
    cutoff_time: str = "10:00"
    timezone: str = "America/New_York"
    log_level: str = "INFO"
    discord_bot_token: str = ""
    discord_channel_id: str = ""
    google_sheets_credentials: str = ""
    google_sheet_id: str = ""
    holidays: FrozenSet[str] = field(default_factory=frozenset)
    second_shift_users: FrozenSet[str] = field(default_factory=frozenset)
    second_shift_cutoff_time: str = "14:00"
    poll_interval_seconds: float = 60.0
    port: int = 8080

    @property
    def cutoff_hour(self) -> int:
        return int(self.cutoff_time.split(":")[0])

    @property
    def cutoff_minute(self) -> int:
        return int(self.cutoff_time.split(":")[1])

    @property
    def second_shift_cutoff_hour(self) -> int:
        return int(self.second_shift_cutoff_time.split(":")[0])

    @property
    def second_shift_cutoff_minute(self) -> int:
        return int(self.second_shift_cutoff_time.split(":")[1])


def load_config() -> Config:
    holidays_raw = os.environ.get("HOLIDAYS", "")
    holidays = frozenset(
        d.strip() for d in holidays_raw.split(",") if d.strip()
    )
    second_shift_raw = os.environ.get("SECOND_SHIFT_USERS", "")
    second_shift_users = frozenset(
        u.strip().lower() for u in second_shift_raw.split(",") if u.strip()
    )
    return Config(
        cutoff_time=os.environ.get("CUTOFF_TIME", "10:00"),
        timezone=os.environ.get("TIMEZONE", "America/New_York"),
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        discord_bot_token=os.environ.get("DISCORD_BOT_TOKEN", ""),
        discord_channel_id=os.environ.get("DISCORD_CHANNEL_ID", ""),
        google_sheets_credentials=os.environ.get(
            "GOOGLE_SHEETS_CREDENTIALS", ""
        ),
        google_sheet_id=os.environ.get("GOOGLE_SHEET_ID", ""),
        holidays=holidays,
        second_shift_users=second_shift_users,
        second_shift_cutoff_time=os.environ.get("SECOND_SHIFT_CUTOFF_TIME", "14:00"),
        poll_interval_seconds=float(
            os.environ.get("POLL_INTERVAL_SECONDS", "60")
        ),
        port=int(os.environ.get("PORT", "8080")),
    )
