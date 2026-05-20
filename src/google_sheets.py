from __future__ import annotations

import json
import logging
import os

import gspread
from google.oauth2.service_account import Credentials
from gspread import Worksheet

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

HEADERS = ["Date", "Name", "Sign-In Time", "Status"]


class GoogleSheetsAppendError(Exception):
    """Base error for Google Sheets append operations."""


class AuthError(GoogleSheetsAppendError):
    """Raised when authentication with Google Sheets fails."""


class QuotaError(GoogleSheetsAppendError):
    """Raised when Google API quota is exceeded."""


class NetworkError(GoogleSheetsAppendError):
    """Raised when a network issue prevents the API call."""


def _build_client() -> gspread.Client:
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
    if not creds_json:
        raise AuthError("GOOGLE_SERVICE_ACCOUNT environment variable is not set")
    try:
        creds_data = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
        return gspread.authorize(creds)
    except json.JSONDecodeError as e:
        raise AuthError("GOOGLE_SERVICE_ACCOUNT is not valid JSON") from e
    except Exception as e:
        raise AuthError(f"Authentication failed: {e}") from e


def _get_sheet_id() -> str:
    sheet_id = os.environ.get("SPREADSHEET_ID")
    if not sheet_id:
        raise GoogleSheetsAppendError("SPREADSHEET_ID environment variable is not set")
    return sheet_id


def _ensure_headers(ws: Worksheet) -> None:
    existing = ws.get_all_values()
    if not existing or existing[0] != HEADERS:
        ws.clear()
        ws.append_row(HEADERS)


def _is_duplicate(ws: Worksheet, user: str, date: str) -> bool:
    try:
        existing = ws.get_all_values()
        for row in existing[1:]:
            if len(row) >= 2 and row[0] == date and row[1] == user:
                return True
    except Exception:
        logger.warning("could_not_check_duplicates", exc_info=True)
    return False


def append_late_entry(user: str, timestamp: str, date: str) -> bool:
    """Append a late attendance entry to the Google Sheet.

    Args:
        user: The name of the late attendee.
        timestamp: The sign-in time (e.g. "10:15 AM").
        date: The date string (e.g. "2026-05-13").

    Returns:
        True if the entry was appended, False if a duplicate was skipped.

    Raises:
        AuthError: If GOOGLE_SERVICE_ACCOUNT is missing or invalid.
        QuotaError: If Google API quota or rate limit is exceeded.
        NetworkError: If a connection or timeout error occurs.
    """
    try:
        client = _build_client()
        sheet_id = _get_sheet_id()
        sheet = client.open_by_key(sheet_id)
        ws = sheet.sheet1

        _ensure_headers(ws)

        if _is_duplicate(ws, user, date):
            logger.info(
                "duplicate_entry_skipped",
                extra={"extra_fields": {"user": user, "date": date}},
            )
            return False

        ws.append_row([date, user, timestamp, "Late"])
        logger.info(
            "late_entry_appended",
            extra={
                "extra_fields": {
                    "user": user,
                    "date": date,
                    "timestamp": timestamp,
                    "sheet_id": sheet_id,
                }
            },
        )
        return True

    except gspread.exceptions.APIError as e:
        if "quota" in str(e).lower() or "rate" in str(e).lower():
            raise QuotaError(f"API quota exceeded: {e}") from e
        raise GoogleSheetsAppendError(f"Google API error: {e}") from e
    except (ConnectionError, TimeoutError) as e:
        raise NetworkError(f"Network error: {e}") from e
    except AuthError:
        raise
    except GoogleSheetsAppendError:
        raise
    except Exception as e:
        raise GoogleSheetsAppendError(f"Unexpected error: {e}") from e
