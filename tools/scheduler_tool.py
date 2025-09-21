from agents import function_tool
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from typing import List
from models import Lead
from tools.email_tool import send_pitch_emails

scheduler = BackgroundScheduler()
scheduler.start()

@function_tool
def schedule_email(leads: List[Lead], send_time: str, subject: str = "Let's Collaborate") -> str:
    """
    Schedule an email campaign to send at a specific time.
    send_time format: 'YYYY-MM-DD HH:MM'
    """

    try:
        run_time = datetime.strptime(send_time, "%Y-%m-%d %H:%M")

        scheduler.add_job(
            send_pitch_emails,
            "date",
            run_date=run_time,
            args=[leads, subject],
        )
        return f"Scheduled email to {len(leads)} leads at {send_time}"
    except Exception as e:
        return f"Failed to schedule email: {e}"
