from __future__ import annotations

from datetime import datetime
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
        self._current_month: str | None = None
        self._worksheet: Worksheet | None = None
        
        # Robustly parse holiday dates configured in .env for sheet shading & labeling
        self._holidays = set()
        from dateutil.parser import parse
        for h in config.holidays:
            try:
                self._holidays.add(parse(h).date())
            except Exception:
                logger.warning(f"failed_to_parse_holiday_in_sheets: {h}", exc_info=True)

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

    @staticmethod
    def _col_to_letter(col: int) -> str:
        letter = ""
        while col > 0:
            col, remainder = divmod(col - 1, 26)
            letter = chr(65 + remainder) + letter
        return letter

    def _ensure_worksheet(self, local_dt: datetime) -> Worksheet:
        import calendar
        sheet_name = local_dt.strftime("%B %Y")
        if self._current_month != sheet_name:
            try:
                self._worksheet = self._sheet.worksheet(sheet_name)
                # Check if it has the grid layout. If not, recreate it!
                headers = self._worksheet.row_values(1)
                if len(headers) < 28 or "Name" not in headers[0] or "1-" not in headers[1]:
                    logger.info("recreating_sheet_with_grid_layout", extra={"extra_fields": {"sheet_name": sheet_name}})
                    try:
                        self._sheet.del_worksheet(self._worksheet)
                    except Exception:
                        pass
                    raise gspread.WorksheetNotFound()
            except gspread.WorksheetNotFound:
                # Create a grid-sheet for the month
                num_days = calendar.monthrange(local_dt.year, local_dt.month)[1]
                self._worksheet = self._sheet.add_worksheet(
                    title=sheet_name, rows=1000, cols=40
                )
                
                headers = ["Name"]
                for day in range(1, num_days + 1):
                    headers.append(f"{day}-{local_dt.strftime('%b-%Y')}")
                
                self._worksheet.append_row(headers)

            # Shade weekend and holiday columns with soft gray background, and reset other columns to white!
            # This ensures only the exact current holidays in .env are applied, and cleans up any old/mock ones automatically!
            num_days = calendar.monthrange(local_dt.year, local_dt.month)[1]
            for day in range(1, num_days + 1):
                from datetime import date
                day_date = date(local_dt.year, local_dt.month, day)
                is_weekend = calendar.weekday(local_dt.year, local_dt.month, day) >= 5
                is_holiday = day_date in self._holidays
                
                col_letter = self._col_to_letter(day + 1)
                try:
                    if is_weekend or is_holiday:
                        self._worksheet.format(f"{col_letter}2:{col_letter}1000", {
                            "backgroundColor": {
                                "red": 0.95,
                                "green": 0.96,
                                "blue": 0.96
                            },
                            "textFormat": {
                                "italic": True,
                                "foregroundColor": {
                                    "red": 0.5,
                                    "green": 0.5,
                                    "blue": 0.5
                                }
                            },
                            "horizontalAlignment": "CENTER"
                        })
                    else:
                        # Revert background to clean white for standard workdays!
                        self._worksheet.format(f"{col_letter}2:{col_letter}1000", {
                            "backgroundColor": {
                                "red": 1.0,
                                "green": 1.0,
                                "blue": 1.0
                            },
                            "textFormat": {
                                "italic": False,
                                "foregroundColor": {
                                    "red": 0.0,
                                    "green": 0.0,
                                    "blue": 0.0
                                }
                            }
                        })
                except Exception:
                    logger.warning(f"could_not_format_col_{col_letter}", exc_info=True)

            # Auto-clear any stray 'Holiday' or 'Weekend' text labels from non-disabled weekday cells
            try:
                rows_data = self._worksheet.get_all_values()
                if len(rows_data) > 1:
                    for r_idx in range(1, len(rows_data)):
                        row = rows_data[r_idx]
                        row_updated = False
                        for day in range(1, num_days + 1):
                            from datetime import date
                            day_date = date(local_dt.year, local_dt.month, day)
                            is_weekend = calendar.weekday(local_dt.year, local_dt.month, day) >= 5
                            is_holiday = day_date in self._holidays
                            
                            col_idx = day + 1
                            if col_idx <= len(row):
                                cell_val = row[col_idx - 1]
                                if not is_weekend and not is_holiday and cell_val in ("Holiday", "Weekend"):
                                    row[col_idx - 1] = ""
                                    row_updated = True
                        if row_updated:
                            self._worksheet.update(f"A{r_idx + 1}", [row])
            except Exception:
                logger.warning("failed_to_heal_holiday_row_values", exc_info=True)

            # Format headers to look clean, white-background, and bold black text
            # This runs for both brand new and already existing worksheets to guarantee correct styling!
            try:
                self._worksheet.format("A1:AN1", {
                    "textFormat": {
                        "bold": True,
                        "fontSize": 12,
                        "foregroundColor": {"red": 0.0, "green": 0.0, "blue": 0.0}
                    },
                    "backgroundColor": {
                        "red": 1.0,
                        "green": 1.0,
                        "blue": 1.0
                    },
                    "horizontalAlignment": "CENTER"
                })
            except Exception:
                logger.warning("could_not_format_headers", exc_info=True)
                            
            self._current_month = sheet_name
            logger.info(
                "monthly_sheet_ready",
                extra={
                    "extra_fields": {
                        "sheet_name": sheet_name,
                        "sheet_id": self._config.google_sheet_id,
                    }
                },
            )
        assert self._worksheet is not None
        return self._worksheet

    def _find_or_create_user_row(self, ws: Worksheet, name: str, local_dt: datetime) -> int:
        import calendar
        names = ws.col_values(1)
        if name in names:
            return names.index(name) + 1
            
        # Create a new row for this user
        num_days = calendar.monthrange(local_dt.year, local_dt.month)[1]
        new_row = [name]
        for day in range(1, num_days + 1):
            from datetime import date
            day_date = date(local_dt.year, local_dt.month, day)
            is_weekend = calendar.weekday(local_dt.year, local_dt.month, day) >= 5
            is_holiday = day_date in self._holidays
            
            if is_weekend:
                new_row.append("Weekend")
            elif is_holiday:
                new_row.append("Holiday")
            else:
                new_row.append("")
                
        ws.append_row(new_row)
        return len(names) + 1

    def append_late_entry(
        self, name: str, timestamp_utc: str, timestamp_local: str
    ) -> None:
        from datetime import datetime
        local_dt = datetime.fromisoformat(timestamp_local)
        ws = self._ensure_worksheet(local_dt)
        row = self._find_or_create_user_row(ws, name, local_dt)
        
        col = local_dt.day + 1
        time_str = local_dt.strftime("%H:%M")
        value = f"Late-{time_str}"
        
        ws.update_cell(row, col, value)
        
        try:
            col_letter = self._col_to_letter(col)
            ws.format(f"{col_letter}{row}", {
                "backgroundColor": {
                    "red": 1.0,
                    "green": 0.8,
                    "blue": 0.8
                },
                "textFormat": {
                    "bold": True,
                    "foregroundColor": {
                        "red": 0.8,
                        "green": 0.0,
                        "blue": 0.0
                    }
                },
                "horizontalAlignment": "CENTER"
            })
        except Exception:
            logger.warning("could_not_format_late_cell", exc_info=True)

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
        from datetime import datetime
        local_dt = datetime.fromisoformat(timestamp_local)
        ws = self._ensure_worksheet(local_dt)
        row = self._find_or_create_user_row(ws, name, local_dt)
        
        col = local_dt.day + 1
        
        ws.update_cell(row, col, "On Time")
        
        try:
            col_letter = self._col_to_letter(col)
            ws.format(f"{col_letter}{row}", {
                "backgroundColor": {
                    "red": 0.82,
                    "green": 0.98,
                    "blue": 0.90
                },
                "textFormat": {
                    "bold": True,
                    "foregroundColor": {
                        "red": 0.06,
                        "green": 0.48,
                        "blue": 0.28
                    }
                },
                "horizontalAlignment": "CENTER"
            })
        except Exception:
            logger.warning("could_not_format_ontime_cell", exc_info=True)

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
