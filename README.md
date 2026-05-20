# LEA Discord Late Attendance Automation

A Python application that monitors a Discord channel for sign-in messages, evaluates them against a configurable cutoff time, and records late attendance entries to Google Sheets. Designed for teams that need automated attendance tracking with timezone-aware late detection.

## Architecture

```
┌─────────────────────────┐
│       Discord API       │
│  (Gateway Intents)      │
└─────────┬───────────────┘
          │ on_message events
          ▼
┌─────────────────────────┐
│    discord_bot/         │
│  ┌───────────────────┐  │
│  │   SigninBot       │──│── receives messages from monitored channel
│  │   (bot.py)        │  │
│  └────────┬──────────┘  │
│  ┌────────┴──────────┐  │
│  │  SigninFilter     │──│── matches sign-in keywords (here, present, ...)
│  │  (filter.py)      │  │    checks active hours window
│  └───────────────────┘  │
│  ┌───────────────────┐  │
│  │  SigninHandler    │──│── abstract handler interface
│  │  (handler.py)     │  │
│  └────────┬──────────┘  │
└───────────┼─────────────┘
            │ handle_signin(data)
            ▼
┌─────────────────────────┐
│   lea_automation/       │
│  ┌───────────────────┐  │
│  │   Orchestrator    │──│── queues & processes messages asynchronously
│  │  (orchestrator.py)│  │
│  └────────┬──────────┘  │
│  ┌────────┴──────────┐  │
│  │   TimeChecker     │──│── evaluates late/on-time with timezone & holidays
│  │  (time_check.py)  │  │
│  └────────┬──────────┘  │
│  ┌────────┴──────────┐  │
│  │  SheetsWriter     │──│── appends entries to Google Sheets (daily tabs)
│  │  (sheets_writer.py)│ │
│  └───────────────────┘  │
│  ┌───────────────────┐  │
│  │  App (main.py)    │──│── entry point, health server (port 8080)
│  └───────────────────┘  │
└─────────────────────────┘
```

**Data flow:**

1. Discord sends `on_message` events for the monitored channel
2. `SigninFilter` checks if the message contains a sign-in keyword and falls within active hours
3. Matching messages are forwarded to the `Orchestrator` via the handler interface
4. `TimeChecker` evaluates the timestamp against the cutoff, timezone, holidays, and weekends
5. Late entries are appended to a daily Google Sheet worksheet; on-time entries are also recorded

## Prerequisites

- Python 3.11+
- A Discord bot token with `message_content` intent enabled
- A Google Cloud service account with Sheets API enabled
- A Google Sheet ID (shared with the service account email)

## Setup

### 1. Clone and create a virtual environment

```bash
git clone <repo-url> lea-automation
cd lea-automation
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -e .[dev]
```c

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials. At minimum you need `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `GOOGLE_SHEETS_CREDENTIALS`, and `GOOGLE_SHEET_ID`.

### 4. Run

```bash
lea-automation
```

Or directly:

```bash
python -m lea_automation.main
```

The application starts an HTTP health check on port 8080, connects to Discord via gateway, and begins monitoring the configured channel.

## Configuration

All configuration is via environment variables. See `.env.example` for a template.

| Variable | Default | Description |
|---|---|---|
| `DISCORD_BOT_TOKEN` | — | Discord bot token (required) |
| `DISCORD_CHANNEL_ID` | — | Discord channel ID to monitor (required) |
| `CUTOFF_TIME` | `10:00` | Cutoff time in 24h format; messages after this are "late" |
| `TIMEZONE` | `America/New_York` | Timezone for cutoff evaluation |
| `SIGNIN_KEYWORDS` | `here,present,checking in,check-in` | Comma-separated sign-in trigger keywords |
| `ACTIVE_HOURS_START` | `08:00` | Start of active monitoring window (24h) |
| `ACTIVE_HOURS_END` | `10:00` | End of active monitoring window (24h) |
| `GOOGLE_SHEETS_CREDENTIALS` | — | Full Google service account JSON string (escaped) |
| `GOOGLE_SHEET_ID` | — | ID from the Google Sheet URL (required) |
| `HOLIDAYS` | — | Comma-separated holiday dates (YYYY-MM-DD) |
| `POLL_INTERVAL_SECONDS` | `60` | Poll interval for the orchestrator queue |
| `LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `PORT` | `8080` | Health check HTTP server port |

## Deployment

### Docker

```bash
docker build -t lea-automation .
docker run -d \
  --name lea-automation \
  --env-file .env \
  -p 8080:8080 \
  lea-automation
```

### systemd

Copy the service unit and configure:

```bash
sudo cp deploy/lea-automation.service /etc/systemd/system/
sudo mkdir -p /opt/lea-automation
# Copy the application and .env to /opt/lea-automation
sudo systemctl daemon-reload
sudo systemctl enable --now lea-automation
```

## Testing

```bash
pip install -e .[dev]
pytest tests/ -v
```

The test suite covers time evaluation (late/on-time/weekend/holiday), keyword filtering, active hours window, config loading, and Google Sheets interactions (with mocked API calls).

## Development

The project uses a `src/` layout:

- `src/lea_automation/` — core orchestration, time checking, sheets writing, config
- `src/discord_bot/` — Discord client, message filtering, handler interface
- `src/google_sheets.py` — standalone Google Sheets append module (legacy)
- `tests/` — pytest tests
- `deploy/` — systemd service unit

## Project

Built for [LEA-1](/LEA/issues/LEA-1). See [LEA-18](/LEA/issues/LEA-18) for finalization details.
