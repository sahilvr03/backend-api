from agents import Agent, function_tool
from agents.extensions.models.litellm_model import LitellmModel

from typing import List
from models import Lead
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime


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


SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "agentt609@gmail.com"
EMAIL_PASS = "ocew rzep uafq dpfi"   # Gmail App Password

scheduler = BackgroundScheduler()
scheduler.start()


@function_tool
def send_pitch_emails(leads: List[Lead], subject: str = "Let's Collaborate") -> str:
    """Send professional pitch emails to leads who have an email."""
    sent, failed = [], []
    for lead in leads:
        if not lead.email:
            continue
        try:
            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = lead.email
            msg["Subject"] = subject
            body = f"""Hi {lead.name or 'there'},

I hope you're doing well! I came across {lead.company or 'your company'} and
believe we could collaborate effectively.

Would you be open to a quick chat this week?

Best regards,
Your Name
"""
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PASS)
                server.sendmail(EMAIL_USER, lead.email, msg.as_string())
            sent.append(lead.email)
        except Exception as e:
            logging.error(f"Failed to send email to {lead.email}: {e}")
            failed.append(lead.email)
    return f"Emails sent: {len(sent)}, failed: {len(failed)}"


@function_tool
def schedule_email(leads: List[Lead], send_time: str, subject: str = "Let's Collaborate") -> str:
    """Schedule an email campaign to send at a specific time."""
    try:
        run_time = datetime.strptime(send_time, "%Y-%m-%d %H:%M")
        scheduler.add_job(send_pitch_emails, "date", run_date=run_time, args=[leads, subject])
        return f"Scheduled email to {len(leads)} leads at {send_time}"
    except Exception as e:
        return f"Failed to schedule email: {e}"

# Load model (Gemini)
from agent import model  

email_agent = Agent(
    name="EmailAgent",
    instructions="You send professional pitch emails or schedule them using tools.",
    model=model,
    tools=[send_pitch_emails, schedule_email],
)
