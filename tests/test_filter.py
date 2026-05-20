from __future__ import annotations

import datetime

import pytest

from discord_bot.config import BotConfig
from discord_bot.filter import SigninFilter


@pytest.fixture
def config() -> BotConfig:
    return BotConfig(
        discord_token="fake-token",
        channel_id=123456789,
        signin_keywords=("here", "present", "checking in", "check-in", "i'm here"),
        active_hours_start="08:00",
        active_hours_end="10:00",
    )


@pytest.fixture
def filter_instance(config: BotConfig) -> SigninFilter:
    return SigninFilter(config)


class TestIsSignin:
    def test_exact_keyword_match(self, filter_instance: SigninFilter) -> None:
        assert filter_instance.is_signin("here") == "here"

    def test_keyword_in_sentence(self, filter_instance: SigninFilter) -> None:
        assert filter_instance.is_signin("I'm here") == "i'm here"

    def test_case_insensitive(self, filter_instance: SigninFilter) -> None:
        assert filter_instance.is_signin("HERE") == "here"
        assert filter_instance.is_signin("Present") == "present"
        assert filter_instance.is_signin("Checking In") == "checking in"

    def test_keyword_with_punctuation(self, filter_instance: SigninFilter) -> None:
        assert filter_instance.is_signin("here!") == "here"
        assert filter_instance.is_signin("check-in!") == "check-in"

    def test_mixed_keyword_in_sentence(self, filter_instance: SigninFilter) -> None:
        assert filter_instance.is_signin("Good morning, I'm here!") == "i'm here"
        assert filter_instance.is_signin("Just checking in for the day") == "checking in"
        assert filter_instance.is_signin("I am present today") == "present"

    def test_no_match(self, filter_instance: SigninFilter) -> None:
        assert filter_instance.is_signin("Hello everyone") is None
        assert filter_instance.is_signin("Running late today") is None
        assert filter_instance.is_signin("") is None

    def test_whitespace_only(self, filter_instance: SigninFilter) -> None:
        assert filter_instance.is_signin("   ") is None
        assert filter_instance.is_signin("\t\n") is None

    def test_partial_word_no_match(self, filter_instance: SigninFilter) -> None:
        assert filter_instance.is_signin("therefore") is None
        assert filter_instance.is_signin("heritage") is None

    def test_default_keywords_empty(self) -> None:
        c = BotConfig(
            discord_token="t",
            channel_id=1,
            signin_keywords=(),
        )
        f = SigninFilter(c)
        assert f.is_signin("here") is None


class TestIsWithinActiveHours:
    def test_within_window(self, filter_instance: SigninFilter) -> None:
        dt = datetime.datetime(2026, 5, 12, 9, 15, 0)
        assert filter_instance.is_within_active_hours(dt) is True

    def test_exactly_at_start(self, filter_instance: SigninFilter) -> None:
        dt = datetime.datetime(2026, 5, 12, 8, 0, 0)
        assert filter_instance.is_within_active_hours(dt) is True

    def test_exactly_at_end(self, filter_instance: SigninFilter) -> None:
        dt = datetime.datetime(2026, 5, 12, 10, 0, 0)
        assert filter_instance.is_within_active_hours(dt) is True

    def test_before_window(self, filter_instance: SigninFilter) -> None:
        dt = datetime.datetime(2026, 5, 12, 7, 59, 59)
        assert filter_instance.is_within_active_hours(dt) is False

    def test_after_window(self, filter_instance: SigninFilter) -> None:
        dt = datetime.datetime(2026, 5, 12, 10, 0, 1)
        assert filter_instance.is_within_active_hours(dt) is False

    def test_late_night(self, filter_instance: SigninFilter) -> None:
        dt = datetime.datetime(2026, 5, 12, 23, 30, 0)
        assert filter_instance.is_within_active_hours(dt) is False

    def test_custom_window(self) -> None:
        c = BotConfig(
            discord_token="t",
            channel_id=1,
            active_hours_start="14:00",
            active_hours_end="16:00",
        )
        f = SigninFilter(c)
        assert f.is_within_active_hours(
            datetime.datetime(2026, 5, 12, 14, 0, 0)
        ) is True
        assert f.is_within_active_hours(
            datetime.datetime(2026, 5, 12, 15, 30, 0)
        ) is True
        assert f.is_within_active_hours(
            datetime.datetime(2026, 5, 12, 16, 0, 0)
        ) is True
        assert f.is_within_active_hours(
            datetime.datetime(2026, 5, 12, 13, 59, 59)
        ) is False
        assert f.is_within_active_hours(
            datetime.datetime(2026, 5, 12, 16, 0, 1)
        ) is False
