from __future__ import annotations

import os
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from lea_automation.config import load_config
from lea_automation.time_check import TimeChecker
from lea_automation.orchestrator import Orchestrator

def test_regular_sign_in_shifts():
    # 1. Setup config with second shift users: "rakib" and "john"
    os.environ["CUTOFF_TIME"] = "10:00"
    os.environ["TIMEZONE"] = "Asia/Dhaka"
    os.environ["DISCORD_BOT_TOKEN"] = "fake"
    os.environ["DISCORD_CHANNEL_ID"] = "1"
    os.environ["GOOGLE_SHEETS_CREDENTIALS"] = "{}"
    os.environ["GOOGLE_SHEET_ID"] = "fake"
    os.environ["SECOND_SHIFT_USERS"] = "rakib, john"
    os.environ["SECOND_SHIFT_CUTOFF_TIME"] = "14:00"
    
    config = load_config()
    tc = TimeChecker(config)
    
    # --- TEST SHIFT 1 (Default: cutoff is 10:00 AM) ---
    # User "alice" is NOT in SECOND_SHIFT_USERS
    
    # 09:59 AM should be ON TIME
    dt_on_time = datetime(2026, 5, 20, 9, 59, 0)
    res_alice = tc.evaluate(dt_on_time, "alice")
    assert res_alice["is_late"] is False
    
    # 10:00 AM should be LATE
    dt_late = datetime(2026, 5, 20, 10, 0, 0)
    res_alice_late = tc.evaluate(dt_late, "alice")
    assert res_alice_late["is_late"] is True
    
    # --- TEST SHIFT 2 (Cutoff is 02:00 PM / 14:00) ---
    # User "rakib" IS in SECOND_SHIFT_USERS
    
    # 10:15 AM (which is late for Shift 1) should be ON TIME for "rakib" (Shift 2)
    dt_shift2_early = datetime(2026, 5, 20, 10, 15, 0)
    res_rakib = tc.evaluate(dt_shift2_early, "rakib")
    assert res_rakib["is_late"] is False
    
    # 01:59 PM should be ON TIME for "rakib"
    dt_shift2_on_time = datetime(2026, 5, 20, 13, 59, 0)
    res_rakib_on = tc.evaluate(dt_shift2_on_time, "rakib")
    assert res_rakib_on["is_late"] is False
    
    # 02:00 PM should be LATE for "rakib"
    dt_shift2_late = datetime(2026, 5, 20, 14, 0, 0)
    res_rakib_late = tc.evaluate(dt_shift2_late, "rakib")
    assert res_rakib_late["is_late"] is True

    # --- TEST SHIFT 2 BY USER ID ---
    os.environ["SECOND_SHIFT_USERS"] = "12345"
    config_by_id = load_config()
    tc_by_id = TimeChecker(config_by_id)
    res_rakib_by_id = tc_by_id.evaluate(dt_shift2_early, "unknown_name", "12345")
    assert res_rakib_by_id["is_late"] is False

def test_manual_time_sign_in_shifts():
    os.environ["CUTOFF_TIME"] = "10:00"
    os.environ["TIMEZONE"] = "Asia/Dhaka"
    os.environ["DISCORD_BOT_TOKEN"] = "fake"
    os.environ["DISCORD_CHANNEL_ID"] = "1"
    os.environ["GOOGLE_SHEETS_CREDENTIALS"] = "{}"
    os.environ["GOOGLE_SHEET_ID"] = "fake"
    os.environ["SECOND_SHIFT_USERS"] = "rakib, john"
    os.environ["SECOND_SHIFT_CUTOFF_TIME"] = "14:00"
    
    config = load_config()
    
    # Mock SheetsWriter creation
    Orchestrator._init_sheets = MagicMock(return_value=MagicMock())
    orch = Orchestrator(config)
    
    # --- TEST SHIFT 1 MANUAL ---
    # "alice" (Shift 1) enters manual time 9:50 AM - Allowed (before 10:00 cutoff)
    allowed, time_str = orch._check_manual_time("Sign in 9:50AM", "alice", "2026-05-20")
    assert allowed is True
    assert time_str == "09:50"
    
    # "alice" (Shift 1) enters manual time 10:15 AM - Rejected (after 10:00 cutoff)
    allowed, time_str = orch._check_manual_time("Sign in 10:15AM", "alice", "2026-05-20")
    assert allowed is False
    assert time_str == "10:15"
    
    # --- TEST SHIFT 2 MANUAL ---
    # "rakib" (Shift 2) enters manual time 10:15 AM - Allowed! (before 14:00 cutoff)
    allowed, time_str = orch._check_manual_time("Sign in 10:15AM", "rakib", "2026-05-20")
    assert allowed is True
    assert time_str == "10:15"
    
    # "rakib" (Shift 2) enters manual time 01:50 PM - Allowed! (before 14:00 cutoff)
    allowed, time_str = orch._check_manual_time("Sign in 1:50PM", "rakib", "2026-05-20")
    assert allowed is True
    assert time_str == "13:50"
    
    # "rakib" (Shift 2) enters manual time 02:15 PM - Rejected! (after 14:00 cutoff)
    allowed, time_str = orch._check_manual_time("Sign in 2:15PM", "rakib", "2026-05-20")
    assert allowed is False
    assert time_str == "14:15"
