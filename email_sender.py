import pytz
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# MongoDB connection
client = MongoClient("mongodb+srv://vijay:baby9271@internsportal.oswhrxp.mongodb.net/?retryWrites=true&w=majority&appName=internsPortal")
db = client["lead_dbb"]
collection = db["leadss"]

def send_email(to_email, subject, body):
    """Send an email via Gmail SMTP"""
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject.strip()

    cleaned_body = "\n".join(
        [line for line in body.splitlines() if not line.startswith("Subject:")]
    )
    msg.attach(MIMEText(cleaned_body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, to_email, msg.as_string())
            print(f"✅ Email sent to {to_email}")
            return True
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {e}")
        return False

def send_scheduled_emails():
    """Send only leads that are due"""
    now_utc = datetime.datetime.now(pytz.UTC)
    leads = collection.find({"status": "scheduled", "due_time": {"$lte": now_utc}})
    
    for lead in leads:
        email_body = lead["email_content"]
        subject_line = None
        for line in email_body.splitlines():
            if line.startswith("Subject:"):
                subject_line = line.replace("Subject:", "").strip()
                break
        if not subject_line:
            subject_line = f"Outreach to {lead['company']} ({lead['country']})"

        sent = send_email(lead["email"], subject_line, email_body)

        if sent:
            collection.update_one(
                {"_id": lead["_id"]},
                {"$set": {"status": "sent", "sent_time": now_utc}}
            )

if __name__ == "__main__":
    send_scheduled_emails()