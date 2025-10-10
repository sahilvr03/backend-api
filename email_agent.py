# email_agent.py
from agents import Agent, function_tool
from agents.extensions.models.litellm_model import LitellmModel
from models import Lead
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import random
import asyncio

# MongoDB
from motor.motor_asyncio import AsyncIOMotorClient
client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client["lead_database"]
lead_collection = db["leads"]
email_collection = db["emails"]

# SMTP Config
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "agentt609@gmail.com"
EMAIL_PASS = "ocew rzep uafq dpfi"   # Gmail App Password

# Scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# -------------------
# Save Email to DB
# -------------------
async def save_email_to_mongo(lead_dict):
    if not lead_dict.get("email"):
        return None

    subjects = [
        f"Grow your business with {lead_dict.get('company', 'our solutions')}",
        f"Partnership opportunity for {lead_dict.get('name', 'your company')}",
        f"Unlock new opportunities in {lead_dict.get('country', 'your region')}",
        f"Special solutions for {lead_dict.get('lead_type', 'businesses')}",
        "Let’s collaborate and create impact together"
    ]
    subject = random.choice(subjects)

    email_doc = {
        "name": lead_dict.get("name"),
        "email": lead_dict.get("email"),
        "subject": subject,
        "company": lead_dict.get("company"),
        "country": lead_dict.get("country"),
        "lead_type": lead_dict.get("lead_type"),
        "created_at": datetime.utcnow()
    }

    existing = await email_collection.find_one({"email": email_doc["email"]})
    if not existing:
        result = await email_collection.insert_one(email_doc)
        email_doc["_id"] = str(result.inserted_id)
        return email_doc
    return existing

# -------------------
# AI Email Writer
# -------------------
from agent import model  # Gemini model already configured

email_writer_agent = Agent(
    name="EmailWriter",
    instructions=(
        "You are a professional email writer. "
        "Given a subject and lead details (name, company, lead_type), "
        "write a short, polite business email body (under 150 words). "
        "Return ONLY the email body text, no additional formatting or explanations."
    ),
    model=model
)

from agents import Runner

runner = Runner()

async def generate_email_body(subject, lead):
    prompt = (
        f"Subject: {subject}\n"
        f"Lead Name: {lead.get('name')}\n"
        f"Company: {lead.get('company')}\n"
        f"Lead Type: {lead.get('lead_type')}\n\n"
        f"Write the email body:"
    )

    # Get the actual email body text from the agent response
    response = await Runner.run(email_writer_agent, prompt)
    return response.final_output  # Return just the text, not a dict

# -------------------
# Email Tools
# -------------------

@function_tool
def send_pitch_emails(leads: list[Lead], subject: str = "Let's Collaborate") -> str:
    """Send professional pitch emails to leads who have an email."""
    sent, failed = [], []
    for lead in leads:
        if not lead.email:
            continue
        try:
            body = f"Hi {lead.name or 'there'},\n\nI came across {lead.company or 'your company'} " \
                   f"and believe we could collaborate effectively.\n\nWould you be open to a quick chat?\n\nBest regards,\nYour Name"

            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = lead.email
            msg["Subject"] = subject
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
def schedule_email(leads: list[Lead], send_time: str, subject: str = "Let's Collaborate") -> str:
    """Schedule an email campaign to send at a specific time."""
    try:
        run_time = datetime.strptime(send_time, "%Y-%m-%d %H:%M")
        scheduler.add_job(send_pitch_emails, "date", run_date=run_time, args=[leads, subject])
        return f"Scheduled email to {len(leads)} leads at {send_time}"
    except Exception as e:
        return f"Failed to schedule email: {e}"

# -------------------
# Email Agent
# -------------------
email_agent = Agent(
    name="EmailAgent",
    instructions="You send professional pitch emails or schedule them using tools.",
    model=model,
    tools=[send_pitch_emails, schedule_email],
)
