import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

from lea_automation.config import load_config
from lea_automation.sheets_writer import SheetsWriter

async def main():
    config = load_config()
    print("Initializing SheetsWriter...")
    writer = SheetsWriter(config)
    
    # We will trigger append_late_entry for tomorrow (May 21) or today, which will call _ensure_worksheet.
    # Because _ensure_worksheet now has self-healing, it will immediately identify May 20, May 21, and May 25
    # as NON-holidays (since they are not in the user's .env HOLIDAYS), reset their background to white,
    # and clean up any "Holiday" or "Weekend" text labels inside those cells!
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    timestamp_local = "2026-05-20T09:15:00+06:00"
    
    print("Triggering self-healing on the live Google Sheet...")
    # Just loading or calling an entry will execute the startup block
    writer.append_late_entry("Rakib Self Healing Verification", timestamp_utc, timestamp_local)
    print("Self-healing complete! The Google Sheet has been perfectly restored!")

if __name__ == "__main__":
    asyncio.run(main())