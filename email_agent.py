from agents import Agent
from agents.extensions.models.litellm_model import LitellmModel
from tools.email_tool import send_pitch_emails
from tools.scheduler_tool import schedule_email

# Load model (Gemini)
from agent import model  

email_agent = Agent(
    name="EmailAgent",
    instructions="You send professional pitch emails or schedule them using tools.",
    model=model,
    tools=[send_pitch_emails, schedule_email],
)
