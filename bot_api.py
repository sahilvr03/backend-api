import os
import asyncio
from datetime import datetime
from pymongo import MongoClient
from openai import OpenAI
from fastapi import FastAPI, Query
from dotenv import load_dotenv
from agents import (
    Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel,
    ModelSettings, function_tool, StopAtTools
)
from datetime import datetime, timedelta


# ----------------------------
# Setup
# ----------------------------
load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["lead_dbb"]
collection = db["leadss"]

# Gemini/OpenAI model
api_key = os.getenv("GEMINI_API_KEY")
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
external_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

model = OpenAIChatCompletionsModel(
    model="gemini-2.5-flash",
    openai_client=external_client,
)
 
@function_tool
async def show_leads(query: str = "last 60 days") -> str:
    """Fetch lead information based on user query."""
    try:
        q = query.lower().strip()

        if "all" in q:
            leads = list(collection.find().sort("_id", -1))  # no limit 🚀

        elif "last" in q:
            n = [int(s) for s in q.split() if s.isdigit()]
            limit = n[0] if n else 10
            leads = list(collection.find().sort("_id", -1).limit(limit))

        elif "today" in q:
            today = datetime.utcnow().date()
            leads = list(collection.find({
                "createdAt": {"$gte": datetime(today.year, today.month, today.day)}
            }))

        elif "pending" in q:
            leads = list(collection.find({"status": {"$regex": "pending", "$options": "i"}}))

        else:
            leads = list(collection.find().sort("_id", -1).limit(10))

        if not leads:
            return "No leads found."

        response = [
            {"name": l.get("name", "N/A"), "email": l.get("email", "N/A")}
            for l in leads
        ]
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
    """Generate AI-written email draft. Creates the gernal email not necessarily related to lead , drafting email should be based on user query."""
    prompt = f"Write a {tone} cold email template pitching AI-based lead automation for the {industry} industry."
    agent = Agent(
        name="EmailDrafter",
        instructions="You write clear, natural, and human-like email drafts based on user input.",
        tools=[],
        model=model,
        model_settings=ModelSettings(temperature=0.7),
    )
    result = await Runner.run(agent, prompt, max_turns=1)
    return result.final_output

# ======================================
# Lead Agent
# ======================================

lead_agent2 = Agent(
    name="LeadManagerAI",
    instructions="""You are an AI Lead Management Assistant.
    - Fetch, count, and summarize leads.
    - Analyze database stats conversationally.
    - If the user asks for an email draft, detect whether it's a general email or lead-related.
      • If it is **lead-related**, use your business/lead context.
      • If it is **general (e.g., personal, formal, professional, or unrelated to leads)**, write a
        clear, properly formatted, human-like email without including any sales or lead-assistant tone.
    """,
    tools=[count_leads, get_email_stats, list_scheduled_emails,
           get_emails_sent_today, draft_email_template, show_leads],
    model=model,
    model_settings=ModelSettings(temperature=0.4),
    tool_use_behavior=StopAtTools(
        stop_at_tool_names=["get_email_stats", "list_scheduled_emails", "draft_email_template"]
    )
)
# ----------------------------
# Chat Loop with Memory
# ----------------------------


async def main():
    print("💼 Lead Management Chatbot is ready! Type 'exit' to quit.\n")

    # Simple list to store conversation history
    history = []

    while True:
        user_input = input("🧠 You: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            break

        # Add the user's message to memory
        history.append({"role": "user", "content": user_input})

        print("🤖 Thinking...\n")

        # Combine history into a single string for context
        full_context = "\n".join(
            [f"{msg['role'].capitalize()}: {msg['content']}" for msg in history]
        )

        # Run the agent using the context as input
        result = await Runner.run(
            lead_agent2,
            input=full_context,
            max_turns=3
        )

        # Save assistant’s response in history
        response_text = result.final_output
        history.append({"role": "assistant", "content": response_text})

        print(response_text)
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())