from agents import function_tool
from typing import List
from models import Lead
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "agentt609@gmail.com"   # replace
EMAIL_PASS = "ocew rzep uafq dpfi"      # use App Password

@function_tool
def send_pitch_emails(leads: List[Lead], subject: str = "Let's Collaborate") -> str:
    """
    Send professional pitch emails to leads who have an email.
    """
    sent = []
    failed = []

    for lead in leads:
        if not lead.email:
            continue
        try:
            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = lead.email
            msg["Subject"] = subject

            body = f"""
            Hi {lead.name or 'there'},

            I hope you're doing well! I came across {lead.company or 'your company'} and
            I believe we could collaborate effectively.

            We specialize in innovative solutions that can help businesses like yours
            grow faster and achieve better results.

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
