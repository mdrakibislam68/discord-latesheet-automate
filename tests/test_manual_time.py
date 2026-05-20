from __future__ import annotations

import os
import json
import pytest
from unittest.mock import MagicMock

from lea_automation.config import load_config
from lea_automation.orchestrator import Orchestrator

@pytest.fixture
def clean_manual_json():
    # Make sure we clean up the tracking file before and after tests
    tracking_file = "manual_signins.json"
    if os.path.exists(tracking_file):
        try:
            os.remove(tracking_file)
        except Exception:
            pass
    yield
    if os.path.exists(tracking_file):
        try:
            os.remove(tracking_file)
        except Exception:
            pass

def test_check_manual_time_limits(clean_manual_json):
    os.environ["CUTOFF_TIME"] = "10:00"
    os.environ["DISCORD_BOT_TOKEN"] = "fake"
    os.environ["DISCORD_CHANNEL_ID"] = "1"
    os.environ["GOOGLE_SHEETS_CREDENTIALS"] = "{}"
    os.environ["GOOGLE_SHEET_ID"] = "fake"
    config = load_config()
    
    # Patch SheetsWriter creation inside Orchestrator
    Orchestrator._init_sheets = MagicMock(return_value=MagicMock())
    
    orch = Orchestrator(config)
    
    # 1. First manual entry before cutoff (9:50 AM) - Allowed!
    allowed, time_str = orch._check_manual_time("Sign in 9:50AM", "test_user", "2026-05-20")
    assert allowed is True
    assert time_str == "09:50"
    
    # 2. Second manual entry before cutoff (9:45 AM) - Allowed!
    allowed, time_str = orch._check_manual_time("Sign in 9:45AM", "test_user", "2026-05-21")
    assert allowed is True
    assert time_str == "09:45"
    
    # 3. Third manual entry before cutoff (9:30 AM) - Allowed!
    allowed, time_str = orch._check_manual_time("Sign in 9:30AM", "test_user", "2026-05-22")
    assert allowed is True
    assert time_str == "09:30"
    
    # 4. Fourth manual entry before cutoff (9:55 AM) - Rejected (exceeded 3 times)!
    allowed, time_str = orch._check_manual_time("Sign in 9:55AM", "test_user", "2026-05-23")
    assert allowed is False
    assert time_str == "09:55"
    
    # 5. Different user manual entry before cutoff - Allowed (separate counts per user)!
    allowed, time_str = orch._check_manual_time("Sign in 9:50AM", "another_user", "2026-05-20")
    assert allowed is True
    assert time_str == "09:50"

def test_check_manual_time_after_cutoff(clean_manual_json):
    os.environ["CUTOFF_TIME"] = "10:00"
    os.environ["DISCORD_BOT_TOKEN"] = "fake"
    os.environ["DISCORD_CHANNEL_ID"] = "1"
    os.environ["GOOGLE_SHEETS_CREDENTIALS"] = "{}"
    os.environ["GOOGLE_SHEET_ID"] = "fake"
    config = load_config()
    Orchestrator._init_sheets = MagicMock(return_value=MagicMock())
    orch = Orchestrator(config)
    
    # Manual entry after cutoff (e.g. 10:15 AM) - Rejected (always late, does not consume grace count)!
    allowed, time_str = orch._check_manual_time("Sign in 10:15AM", "test_user", "2026-05-20")
    assert allowed is False
    assert time_str == "10:15"
    
    # Verify it did not consume any grace count
    tracking_file = "manual_signins.json"
    if os.path.exists(tracking_file):
        with open(tracking_file, "r") as f:
            data = json.load(f)
        assert data["users"].get("test_user", 0) == 0
