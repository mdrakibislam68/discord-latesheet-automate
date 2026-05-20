from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lea_automation.config import Config
from lea_automation.time_check import TimeChecker


def make_config(**kwargs) -> Config:
    defaults = dict(
        cutoff_time="10:00",
        timezone="America/New_York",
        log_level="INFO",
        holidays=frozenset(),
        poll_interval_seconds=60.0,
        port=8080,
        discord_bot_token="",
        discord_channel_id="",
        google_sheets_credentials="",
        google_sheet_id="",
    )
    defaults.update(kwargs)
    return Config(**defaults)


def test_is_late_after_cutoff():
    config = make_config()
    checker = TimeChecker(config)
    dt = datetime(2026, 5, 12, 14, 30, 0, tzinfo=timezone.utc)
    assert checker.is_late(dt), "2:30 PM UTC should be late for NY (10:30 AM ET)"


def test_is_late_before_cutoff():
    config = make_config()
    checker = TimeChecker(config)
    dt = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)
    assert not checker.is_late(dt), "12:00 PM UTC should be on time for NY (8:00 AM ET)"


def test_is_late_edge_exact_cutoff():
    config = make_config(cutoff_time="10:00")
    checker = TimeChecker(config)
    dt = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)
    assert checker.is_late(dt), "10:00 AM ET exactly should be late"


def test_is_weekend_saturday():
    config = make_config()
    checker = TimeChecker(config)
    sat = date(2026, 5, 9)
    assert checker.is_weekend(sat)


def test_is_weekend_sunday():
    config = make_config()
    checker = TimeChecker(config)
    sun = date(2026, 5, 10)
    assert checker.is_weekend(sun)


def test_is_weekday():
    config = make_config()
    checker = TimeChecker(config)
    mon = date(2026, 5, 11)
    assert not checker.is_weekend(mon)


def test_is_holiday():
    config = make_config(holidays=frozenset(["2026-12-25"]))
    checker = TimeChecker(config)
    xmas = date(2026, 12, 25)
    assert checker.is_holiday(xmas)


def test_is_not_holiday():
    config = make_config(holidays=frozenset(["2026-12-25"]))
    checker = TimeChecker(config)
    normal = date(2026, 5, 12)
    assert not checker.is_holiday(normal)


def test_should_process_weekday():
    config = make_config()
    checker = TimeChecker(config)
    mon = date(2026, 5, 11)
    assert checker.should_process_today(mon)


def test_should_skip_weekend():
    config = make_config()
    checker = TimeChecker(config)
    sat = date(2026, 5, 9)
    assert not checker.should_process_today(sat)


def test_should_skip_holiday():
    config = make_config(holidays=frozenset(["2026-12-25"]))
    checker = TimeChecker(config)
    xmas = date(2026, 12, 25)
    assert not checker.should_process_today(xmas)


def test_evaluate_late():
    config = make_config()
    checker = TimeChecker(config)
    dt = datetime(2026, 5, 12, 14, 30, 0, tzinfo=timezone.utc)
    result = checker.evaluate(dt)
    assert result["is_late"] is True
    assert result["is_processed"] is True
    assert result["date"] == "2026-05-12"
    assert result["timezone"] == "America/New_York"


def test_evaluate_on_time():
    config = make_config()
    checker = TimeChecker(config)
    dt = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)
    result = checker.evaluate(dt)
    assert result["is_late"] is False
    assert result["is_processed"] is True


def test_evaluate_weekend_no_process():
    config = make_config()
    checker = TimeChecker(config)
    sat_noon = datetime(2026, 5, 9, 14, 0, 0, tzinfo=timezone.utc)
    result = checker.evaluate(sat_noon)
    assert result["is_processed"] is False
    assert result["is_late"] is False


def test_evaluate_holiday_no_process():
    config = make_config(holidays=frozenset(["2026-12-25"]))
    checker = TimeChecker(config)
    xmas = datetime(2026, 12, 25, 14, 0, 0, tzinfo=timezone.utc)
    result = checker.evaluate(xmas)
    assert result["is_processed"] is False
    assert result["is_late"] is False


def test_localize_naive():
    config = make_config(timezone="America/New_York")
    checker = TimeChecker(config)
    naive = datetime(2026, 5, 12, 14, 0, 0)
    localized = checker.localize(naive)
    assert localized.tzinfo is not None


def test_different_cutoff():
    config = make_config(cutoff_time="09:00")
    checker = TimeChecker(config)
    dt = datetime(2026, 5, 12, 13, 30, 0, tzinfo=timezone.utc)
    assert checker.is_late(dt), "9:00 AM ET should flag 9:30 AM ET as late"


def test_evaluate_edge_midnight():
    config = make_config()
    checker = TimeChecker(config)
    dt = datetime(2026, 5, 12, 4, 0, 0, tzinfo=timezone.utc)
    result = checker.evaluate(dt)
    assert result["is_late"] is False
    assert result["is_processed"] is True


if __name__ == "__main__":
    tests = [
        test_is_late_after_cutoff,
        test_is_late_before_cutoff,
        test_is_late_edge_exact_cutoff,
        test_is_weekend_saturday,
        test_is_weekend_sunday,
        test_is_weekday,
        test_is_holiday,
        test_is_not_holiday,
        test_should_process_weekday,
        test_should_skip_weekend,
        test_should_skip_holiday,
        test_evaluate_late,
        test_evaluate_on_time,
        test_evaluate_weekend_no_process,
        test_evaluate_holiday_no_process,
        test_localize_naive,
        test_different_cutoff,
        test_evaluate_edge_midnight,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failures += 1
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
