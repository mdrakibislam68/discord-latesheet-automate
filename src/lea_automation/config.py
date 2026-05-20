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
    poll_interval_seconds: float = 60.0
    port: int = 8080

    @property
    def cutoff_hour(self) -> int:
        return int(self.cutoff_time.split(":")[0])

    @property
    def cutoff_minute(self) -> int:
        return int(self.cutoff_time.split(":")[1])


def load_config() -> Config:
    holidays_raw = os.environ.get("HOLIDAYS", "")
    holidays = frozenset(
        d.strip() for d in holidays_raw.split(",") if d.strip()
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
        poll_interval_seconds=float(
            os.environ.get("POLL_INTERVAL_SECONDS", "60")
        ),
        port=int(os.environ.get("PORT", "8080")),
    )
