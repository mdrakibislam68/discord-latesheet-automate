from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone, tzinfo

from lea_automation.config import Config
from lea_automation.logging_setup import get_logger

logger = get_logger(__name__)

try:
    from zoneinfo import ZoneInfo

    _UTC: tzinfo = timezone.utc

    def _get_tz(name: str) -> tzinfo | None:
        try:
            return ZoneInfo(name)
        except (KeyError, ValueError):
            return None

except ImportError:
    from dateutil.tz import gettz, tzutc

    _UTC = tzutc()

    def _get_tz(name: str) -> tzinfo | None:
        return gettz(name)

try:
    import dateutil.parser as _dp
except ImportError:
    _dp = None  # type: ignore[assignment]


def _parse_timestamp(raw: str) -> datetime:
    if _dp is not None:
        return _dp.isoparse(raw)
    return datetime.fromisoformat(raw)


class TimeChecker:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._tz = _get_tz(config.timezone)
        if self._tz is None:
            logger.warning(
                "unknown_timezone_falling_back_to_utc",
                extra={"extra_fields": {"configured": config.timezone}},
            )
        self._cutoff = time(config.cutoff_hour, config.cutoff_minute)
        self._second_shift_cutoff = time(config.second_shift_cutoff_hour, config.second_shift_cutoff_minute)
        
        # Robustly parse holiday date strings to support any format configured in .env (e.g. YYYY-MM-DD, D-Mmm-YYYY)
        self._holidays = set()
        from dateutil.parser import parse
        for h in config.holidays:
            try:
                self._holidays.add(parse(h).date())
            except Exception:
                logger.warning(f"failed_to_parse_holiday_date: {h}", exc_info=True)

    @property
    def timezone_name(self) -> str:
        return self._config.timezone

    def localize(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self._tz or _UTC)
        return dt.astimezone(self._tz or _UTC)

    def now_local(self) -> datetime:
        return datetime.now(self._tz or _UTC)

    def today_local(self) -> date:
        return self.now_local().date()

    def is_late(self, message_dt: datetime, user: str | None = None, user_id: str | None = None) -> bool:
        local_dt = self.localize(message_dt)
        local_time = local_dt.time()
        
        cutoff = self._cutoff
        is_sec = False
        if user and user.lower().strip() in self._config.second_shift_users:
            is_sec = True
        elif user_id and user_id.strip() in self._config.second_shift_users:
            is_sec = True

        if is_sec:
            cutoff = self._second_shift_cutoff
            
        return local_time >= cutoff

    def is_weekend(self, dt: datetime | date | None = None) -> bool:
        d = dt
        if d is None:
            d = self.today_local()
        if isinstance(d, datetime):
            d = d.date()
        return d.weekday() >= 5

    def is_holiday(self, dt: datetime | date | None = None) -> bool:
        d = dt
        if d is None:
            d = self.today_local()
        if isinstance(d, datetime):
            d = d.date()
        return d in self._holidays

    def should_process_today(self, dt: datetime | date | None = None) -> bool:
        d = dt
        if d is None:
            d = self.today_local()
        if isinstance(d, datetime):
            d = d.date()
        if self.is_weekend(d):
            logger.debug(
                "skipping_weekend", extra={"extra_fields": {"date": d.isoformat()}}
            )
            return False
        if self.is_holiday(d):
            logger.debug(
                "skipping_holiday", extra={"extra_fields": {"date": d.isoformat()}}
            )
            return False
        return True

    def evaluate(self, message_dt: datetime, user: str | None = None, user_id: str | None = None) -> dict:
        local_dt = self.localize(message_dt)
        local_date = local_dt.date()
        result = {
            "timestamp_utc": message_dt.isoformat(),
            "timestamp_local": local_dt.isoformat(),
            "date": local_date.isoformat(),
            "timezone": self.timezone_name,
            "is_weekend": self.is_weekend(local_date),
            "is_holiday": self.is_holiday(local_date),
            "is_late": False,
            "is_processed": True,
        }
        if not self.should_process_today(local_date):
            result["is_processed"] = False
            return result
        result["is_late"] = self.is_late(message_dt, user, user_id)
        return result
