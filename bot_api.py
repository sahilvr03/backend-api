import os
import asyncio
from datetime import datetime
from pymongo import MongoClient
from fastapi import FastAPI, Query
from dotenv import load_dotenv
from agents import (
    Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel,
    ModelSettings, function_tool, StopAtTools
)

# ======================================
# Environment Setup
# ======================================
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = MongoClient(MONGO_URI)
db = client["lead_db"]
collection = db["leads"]

external_client = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

model = OpenAIChatCompletionsModel(
    model="gemini-2.5-flash",
    openai_client=external_client,
)

# ======================================
# Function Tools
# ======================================

@function_tool
async def show_leads(query: str = "last 10") -> str:
    """Fetch lead information based on user query."""
    try:
        if "last" in query.lower():
            n = [int(s) for s in query.split() if s.isdigit()]
            limit = n[0] if n else 10
            leads = list(collection.find().sort("_id", -1).limit(limit))
        elif "today" in query.lower():
            today = datetime.utcnow().date()
            leads = list(collection.find({
                "createdAt": {"$gte": datetime(today.year, today.month, today.day)}
            }))
        elif "pending" in query.lower():
            leads = list(collection.find({"status": {"$regex": "pending", "$options": "i"}}))
        else:
            leads = list(collection.find().sort("_id", -1).limit(5))

        if not leads:
            return "No leads found."

        response = []
        for lead in leads:
            response.append({
                "name": lead.get("name", "N/A"),
                "email": lead.get("email", "N/A"),
                "status": lead.get("status", "N/A"),
                "source": lead.get("source", "N/A"),
            })
        return response
    except Exception as e:
        return {"error": str(e)}

@function_tool
async def count_leads() -> str:
    """Return total number of leads."""
    total = collection.count_documents({})
    return f"📊 Total leads: {total}"

@function_tool
async def get_email_stats() -> str:
    """Return number of emails sent and pending."""
    today = datetime.now().date()
    sent_today = collection.count_documents({
        "status": "sent",
        "due_time": {"$gte": datetime(today.year, today.month, today.day)}
    })
    pending = collection.count_documents({"status": "scheduled"})
    total = collection.count_documents({})
    return {
        "total": total,
        "sent_today": sent_today,
        "pending": pending
    }

@function_tool
async def get_emails_sent_today() -> str:
    """Return count of emails sent today."""
    today = datetime.now().strftime("%Y-%m-%d")
    count = collection.count_documents({"sent_date": today})
    return f"📤 {count} emails sent today."

@function_tool
async def list_scheduled_emails() -> str:
    """List scheduled emails."""
    leads = list(collection.find({"status": "scheduled"}).limit(10))
    if not leads:
        return "✅ No scheduled emails found."
    return [
        {
            "email": l.get("email"),
            "due_time": str(l.get("due_time")),
            "timezone": l.get("timezone", "Unknown"),
        }
        for l in leads
    ]

@function_tool
async def draft_email_template(industry: str, tone: str = "professional") -> str:
    """Generate AI-written email draft for a specific industry."""
    prompt = f"Write a {tone} cold email template pitching AI-based lead automation for the {industry} industry."
    agent = Agent(
        name="EmailDrafter",
        instructions="You write clear, persuasive cold emails that sound human.",
        tools=[],
        model=model,
        model_settings=ModelSettings(temperature=0.7),
    )
    result = await Runner.run(agent, prompt, max_turns=1)
    return result.final_output

# ======================================
# Lead Agent
# ======================================

lead_agent = Agent(
    name="LeadManagerAI",
    instructions="""
    You are an AI Lead Management Assistant.
    - Fetch, count, and summarize leads.
    - Draft email templates.
    - Analyze database stats conversationally.
    """,
    tools=[count_leads, get_email_stats, list_scheduled_emails,
           get_emails_sent_today, draft_email_template, show_leads],
    model=model,
    model_settings=ModelSettings(temperature=0.4),
    tool_use_behavior=StopAtTools(
        stop_at_tool_names=["get_email_stats", "list_scheduled_emails", "draft_email_template"]
    )
)

# ======================================
# FastAPI Setup
# ======================================

app = FastAPI(
    title="Lead Management AI API",
    description="AI-powered API for managing leads, drafting emails, and fetching stats.",
    version="1.0.0"
)

@app.get("/")
def root():
    return {"message": "🚀 Lead Management AI API is live!"}

@app.get("/leads")
async def get_leads(limit: int = 10):
    data = await show_leads(f"last {limit}")
    return {"status": "success", "data": data}

@app.get("/count")
async def get_count():
    data = await count_leads()
    return {"status": "success", "data": data}

@app.get("/stats")
async def get_stats():
    data = await get_email_stats()
    return {"status": "success", "data": data}

@app.get("/scheduled")
async def get_scheduled():
    data = await list_scheduled_emails()
    return {"status": "success", "data": data}

@app.post("/draft_email")
async def draft_email(industry: str, tone: str = "professional"):
    email_text = await draft_email_template(industry, tone)
    return {"status": "success", "industry": industry, "tone": tone, "draft": email_text}

@app.post("/chat")
async def chat(query: str = Query(..., description="Chat query for AI Lead Assistant")):
    """Chat with the AI Lead Assistant."""
    result = await Runner.run(lead_agent, input=query, max_turns=3)
    return {"status": "success", "query": query, "response": result.final_output}

