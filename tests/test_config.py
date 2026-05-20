from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lea_automation.config import load_config, Config


def test_default_config():
    os.environ.pop("CUTOFF_TIME", None)
    os.environ.pop("TIMEZONE", None)
    os.environ.pop("LOG_LEVEL", None)
    os.environ.pop("HOLIDAYS", None)
    os.environ.pop("POLL_INTERVAL_SECONDS", None)
    os.environ.pop("PORT", None)

    cfg = load_config()
    assert cfg.cutoff_time == "10:00"
    assert cfg.timezone == "America/New_York"
    assert cfg.log_level == "INFO"
    assert cfg.cutoff_hour == 10
    assert cfg.cutoff_minute == 0
    assert cfg.holidays == frozenset()
    assert cfg.poll_interval_seconds == 60.0
    assert cfg.port == 8080
    print("  PASS  test_default_config")


def test_custom_config():
    os.environ["CUTOFF_TIME"] = "09:30"
    os.environ["TIMEZONE"] = "Europe/London"
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["HOLIDAYS"] = "2026-12-25,2026-01-01"
    os.environ["POLL_INTERVAL_SECONDS"] = "30"
    os.environ["PORT"] = "9090"

    cfg = load_config()
    assert cfg.cutoff_time == "09:30"
    assert cfg.timezone == "Europe/London"
    assert cfg.log_level == "DEBUG"
    assert cfg.cutoff_hour == 9
    assert cfg.cutoff_minute == 30
    assert cfg.holidays == frozenset(["2026-12-25", "2026-01-01"])
    assert cfg.poll_interval_seconds == 30.0
    assert cfg.port == 9090
    print("  PASS  test_custom_config")


if __name__ == "__main__":
    test_default_config()
    test_custom_config()
    print("\n2/2 passed")
