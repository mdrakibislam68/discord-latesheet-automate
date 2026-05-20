from __future__ import annotations

import json
from datetime import date
from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from gspread import Worksheet

from lea_automation.config import Config
from lea_automation.logging_setup import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


class SheetsWriter:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._client = self._build_client(config)
        self._sheet = self._client.open_by_key(config.google_sheet_id)
        self._current_day: date | None = None
        self._worksheet: Worksheet | None = None
        self._ensure_worksheet()

    @staticmethod
    def _build_client(config: Config) -> gspread.Client:
        import os
        creds_data = json.loads(config.google_sheets_credentials)
        if "type" in creds_data and creds_data["type"] == "service_account":
            creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
        elif os.path.exists(".gspread_token.json"):
            from google.oauth2.credentials import Credentials as UserCredentials
            with open(".gspread_token.json", "r") as f:
                token_data = json.load(f)
            creds = UserCredentials.from_authorized_user_info(token_data, scopes=SCOPES)
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_config(creds_data, scopes=SCOPES)
            print("\n*** GOOGLE SHEETS OAUTH FLOW ***")
            print("Please follow the instructions in your browser to authorize the application.")
            creds = flow.run_local_server(port=0)
            with open(".gspread_token.json", "w") as f:
                f.write(creds.to_json())
            print("Success! Google Sheets authorization complete and token saved.\n")
        return gspread.authorize(creds)

    def _ensure_worksheet(self) -> Worksheet:
        today = date.today()
        sheet_name = today.isoformat()
        if self._current_day != today:
            try:
                self._worksheet = self._sheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                self._worksheet = self._sheet.add_worksheet(
                    title=sheet_name, rows=500, cols=10
                )
                self._worksheet.append_row(
                    ["Name", "Timestamp (UTC)", "Timestamp (Local)", "Status"]
                )
            self._current_day = today
            logger.info(
                "daily_sheet_ready",
                extra={
                    "extra_fields": {
                        "sheet_name": sheet_name,
                        "sheet_id": self._config.google_sheet_id,
                    }
                },
            )
        assert self._worksheet is not None
        return self._worksheet

    def append_late_entry(
        self, name: str, timestamp_utc: str, timestamp_local: str
    ) -> None:
        ws = self._ensure_worksheet()
        ws.append_row([name, timestamp_utc, timestamp_local, "Late"])
        logger.info(
            "late_entry_written",
            extra={
                "extra_fields": {
                    "name": name,
                    "timestamp_utc": timestamp_utc,
                    "sheet_name": ws.title,
                }
            },
        )

    def append_on_time_entry(
        self, name: str, timestamp_utc: str, timestamp_local: str
    ) -> None:
        ws = self._ensure_worksheet()
        ws.append_row([name, timestamp_utc, timestamp_local, "On Time"])
        logger.info(
            "on_time_entry_written",
            extra={
                "extra_fields": {
                    "name": name,
                    "timestamp_utc": timestamp_utc,
                    "sheet_name": ws.title,
                }
            },
        )
