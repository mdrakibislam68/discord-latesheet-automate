import asyncio
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from lea_automation.config import load_config
from lea_automation.orchestrator import Orchestrator

async def test():
    config = load_config()
    print("Initializing Orchestrator...")
    orchestrator = Orchestrator(config)
    
    mock_message = {
        "user": "test_user_gemini",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": "sign in",
        "matched_keyword": "sign in"
    }
    
    print("Enqueueing mock message...")
    orchestrator.enqueue_message(mock_message)
    
    # Process the message
    print("Processing message...")
    # Get the message from the queue and process it directly
    msg = await orchestrator._queue.get()
    await orchestrator._process_message(msg)
    print("Message processed successfully!")

if __name__ == "__main__":
    asyncio.run(test())
