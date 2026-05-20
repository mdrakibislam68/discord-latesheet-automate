from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from google_sheets import (
    HEADERS,
    AuthError,
    GoogleSheetsAppendError,
    NetworkError,
    QuotaError,
    append_late_entry,
)

SERVICE_ACCOUNT_JSON = json.dumps(
    {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "test-key-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----\n",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "123456",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
)
SPREADSHEET_ID = "1WQsfb0-e7AeSBTgzQc1Icf-MSi3cbyuHQDpPjYxmIuM"


@pytest.fixture(autouse=True)
def _env_setup() -> None:
    os.environ["GOOGLE_SERVICE_ACCOUNT"] = SERVICE_ACCOUNT_JSON
    os.environ["SPREADSHEET_ID"] = SPREADSHEET_ID
    yield
    os.environ.pop("GOOGLE_SERVICE_ACCOUNT", None)
    os.environ.pop("SPREADSHEET_ID", None)


@pytest.fixture
def mock_client() -> MagicMock:
    ws = MagicMock()
    ws.get_all_values.return_value = [HEADERS]
    ws.title = "Sheet1"

    sheet = MagicMock()
    sheet.sheet1 = ws
    sheet.id = SPREADSHEET_ID

    client = MagicMock()
    client.open_by_key.return_value = sheet

    return client


@pytest.fixture(autouse=True)
def _patch_gspread(mock_client: MagicMock) -> None:
    with (
        patch("google_sheets.gspread.authorize", return_value=mock_client),
        patch(
            "google_sheets.Credentials.from_service_account_info",
            return_value=MagicMock(),
        ),
    ):
        yield


class TestAppendLateEntry:
    def test_appends_new_row(self, mock_client: MagicMock) -> None:
        result = append_late_entry(user="Alice", timestamp="10:15 AM", date="2026-05-13")
        assert result is True

        ws = mock_client.open_by_key.return_value.sheet1
        ws.append_row.assert_called_once_with(
            ["2026-05-13", "Alice", "10:15 AM", "Late"]
        )

    def test_rejects_duplicate(self, mock_client: MagicMock) -> None:
        ws = mock_client.open_by_key.return_value.sheet1
        ws.get_all_values.return_value = [
            HEADERS,
            ["2026-05-13", "Alice", "10:15 AM", "Late"],
        ]

        result = append_late_entry(user="Alice", timestamp="10:20 AM", date="2026-05-13")
        assert result is False
        ws.append_row.assert_not_called()

    def test_allows_same_user_different_date(self, mock_client: MagicMock) -> None:
        ws = mock_client.open_by_key.return_value.sheet1
        ws.get_all_values.return_value = [
            HEADERS,
            ["2026-05-12", "Alice", "09:00 AM", "Late"],
        ]

        result = append_late_entry(user="Alice", timestamp="10:15 AM", date="2026-05-13")
        assert result is True
        ws.append_row.assert_called_once_with(
            ["2026-05-13", "Alice", "10:15 AM", "Late"]
        )

    def test_allows_different_user_same_date(self, mock_client: MagicMock) -> None:
        ws = mock_client.open_by_key.return_value.sheet1
        ws.get_all_values.return_value = [
            HEADERS,
            ["2026-05-13", "Alice", "10:15 AM", "Late"],
        ]

        result = append_late_entry(user="Bob", timestamp="10:30 AM", date="2026-05-13")
        assert result is True
        ws.append_row.assert_called_once_with(
            ["2026-05-13", "Bob", "10:30 AM", "Late"]
        )


class TestAuthErrors:
    def test_missing_service_account(self) -> None:
        os.environ.pop("GOOGLE_SERVICE_ACCOUNT", None)
        with pytest.raises(AuthError, match="GOOGLE_SERVICE_ACCOUNT"):
            append_late_entry(user="Alice", timestamp="10:15 AM", date="2026-05-13")

    def test_invalid_service_account_json(self) -> None:
        os.environ["GOOGLE_SERVICE_ACCOUNT"] = "not-json"
        with pytest.raises(AuthError, match="not valid JSON"):
            append_late_entry(user="Alice", timestamp="10:15 AM", date="2026-05-13")

    def test_missing_spreadsheet_id(self) -> None:
        os.environ.pop("SPREADSHEET_ID", None)
        with pytest.raises(GoogleSheetsAppendError, match="SPREADSHEET_ID"):
            append_late_entry(user="Alice", timestamp="10:15 AM", date="2026-05-13")


class TestQuotaErrors:
    def test_quota_exceeded(self, mock_client: MagicMock) -> None:
        mock_client.open_by_key.side_effect = gspread_exception(
            "Quota exceeded for this request"
        )
        with pytest.raises(QuotaError, match="quota"):
            append_late_entry(user="Alice", timestamp="10:15 AM", date="2026-05-13")

    def test_rate_limit(self, mock_client: MagicMock) -> None:
        mock_client.open_by_key.side_effect = gspread_exception(
            "Rate Limit Exceeded"
        )
        with pytest.raises(QuotaError, match="quota"):
            append_late_entry(user="Alice", timestamp="10:15 AM", date="2026-05-13")


class TestNetworkErrors:
    def test_connection_error(self, mock_client: MagicMock) -> None:
        mock_client.open_by_key.side_effect = ConnectionError("connection refused")
        with pytest.raises(NetworkError, match="connection refused"):
            append_late_entry(user="Alice", timestamp="10:15 AM", date="2026-05-13")

    def test_timeout_error(self, mock_client: MagicMock) -> None:
        mock_client.open_by_key.side_effect = TimeoutError("timed out")
        with pytest.raises(NetworkError, match="timed out"):
            append_late_entry(user="Alice", timestamp="10:15 AM", date="2026-05-13")


class TestHeadersSetup:
    def test_ensures_headers_on_empty_sheet(self, mock_client: MagicMock) -> None:
        ws = mock_client.open_by_key.return_value.sheet1
        ws.get_all_values.return_value = []

        result = append_late_entry(user="Alice", timestamp="10:15 AM", date="2026-05-13")

        assert result is True
        ws.clear.assert_called_once()
        ws.append_row.assert_any_call(HEADERS)
        ws.append_row.assert_any_call(["2026-05-13", "Alice", "10:15 AM", "Late"])

    def test_does_not_reheadered_already_headed(self, mock_client: MagicMock) -> None:
        ws = mock_client.open_by_key.return_value.sheet1

        result = append_late_entry(user="Alice", timestamp="10:15 AM", date="2026-05-13")

        assert result is True
        ws.clear.assert_not_called()


def gspread_exception(msg: str) -> Exception:
    import gspread
    mock_resp = MagicMock()
    mock_resp.text = msg
    mock_resp.json.side_effect = ValueError("not json")
    e = gspread.exceptions.APIError(mock_resp)
    return e
