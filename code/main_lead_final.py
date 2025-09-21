import asyncio
import pytz
import datetime
from pymongo import MongoClient

# --- Import your existing modules ---
import Email_writer   # drafts emails
import scheduler_agent   # schedules emails
import Email_sender   # sends emails


# =============================
# MongoDB Setup
# =============================
MONGO_URI = "mongodb://localhost:27017"
client = MongoClient(MONGO_URI)
db = client["lead_database"]
leads_collection = db["new_leads"]


async def run_pipeline():
    """
    Main pipeline:
    1. Draft missing emails
    2. Schedule emails (set due_time)
    3. Send emails at due time
    """

    print("\n📧 Step 1: Writing missing emails...")
    await Email_writer.process_all_leads()

    print("\n⏰ Step 2: Scheduling unscheduled leads...")
    scheduler_agent.schedule_emails()

    print("\n📨 Step 3: Sending due emails...")
    Email_sender.send_scheduled_emails()


async def main_loop(interval_minutes: int = 1):
    """
    Continuously run the pipeline every X minutes.
    Default = 1 min.
    """
    while True:
        print("\n🚀 Running pipeline...")
        await run_pipeline()
        print(f"\n⏳ Sleeping {interval_minutes} minutes...\n")
        await asyncio.sleep(interval_minutes * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
