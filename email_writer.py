import os
import json
import asyncio
from dotenv import load_dotenv
from pymongo import MongoClient

# Agents & Tools
from agents import (
    Agent,
    Runner,
    AsyncOpenAI,
    OpenAIChatCompletionsModel,
    set_tracing_export_api_key,
    ModelSettings
)

# =============================
# Context: env, clients, model
# =============================
class Context:
    def __init__(self):
        load_dotenv()
        tracing_api_key = os.getenv("OPENAI_API_KEY")
        if tracing_api_key:
            set_tracing_export_api_key(tracing_api_key)

        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

        self.external_client = AsyncOpenAI(api_key=self.gemini_api_key, base_url=self.base_url)

        self.model = OpenAIChatCompletionsModel(
            MODEL="gemini-2.5-flash",
            openai_client=self.external_client,
        )

ctx = Context()

# =============================
# MongoDB Setup
# =============================
MONGO_URI = ("mongodb+srv://vijay:baby9271@internsportal.oswhrxp.mongodb.net/?retryWrites=true&w=majority&appName=internsPortal")
client = MongoClient(MONGO_URI)
db = client["lead_dbb"]
leads_collection = db["leadss"]

# =============================
# Writer Agent
# =============================
writer_agent = Agent(
    name="WriterAgent",
    instructions="""
    You are a professional outreach email writer.
    Write a concise, polite, and personalized email for a company lead.
    - Use the provided company information, role, and country context.
    - Keep it professional but approachable.
    - Avoid being too long; 4–6 sentences max.
    """,
    model=ctx.model,
    model_settings=ModelSettings(temperature=0.4)
)

# =============================
# Your Contact Information
# =============================
MY_SIGNATURE = """
Best regards,

Aleema Saleem  
CEO  
Crop2x Private Limited  
📧 aleema@example.com | 🌐 www.crop2x.com
"""

async def draft_email(lead: dict) -> str:
    """Generate email for a single lead using WriterAgent"""
    prompt = f"""
    Draft an outreach email for:
    - Name: {lead.get("name")}
    - Role: {lead.get("role")}
    - Company: {lead.get("company")}
    - Country: {lead.get("country")}
    - Company Info: {lead.get("company_info")}

    Make the email professional and relevant.
    Do not add placeholders like [Your Name] — the signature will be appended automatically.
    """

    result = await Runner.run(writer_agent, prompt, max_turns=2)
    email_body = result.final_output.strip()

    # Append your actual signature
    full_email = f"{email_body}\n\n{MY_SIGNATURE}"
    return full_email


async def process_all_leads():
    leads = list(leads_collection.find({"email_content": {"$exists": False}}))  # only new leads
    if not leads:
        print("⚠️ No new leads found in MongoDB.")
        return

    for lead in leads:
        print(f"✍️ Drafting email for {lead['company']} ({lead['country']})...")
        email_text = await draft_email(lead)

        # Update document with email + country tag
        leads_collection.update_one(
            {"_id": lead["_id"]},
            {"$set": {
                "email_content": email_text,
                "country": lead.get("country", "Unknown")
            }}
        )
        print(f"✅ Stored email for {lead['company']} in {lead['country']}")

# =============================
# Run Writer Agent
# =============================
async def main():
    print("📧 Writer Agent ready! Generating emails for leads...\n")
    await process_all_leads()
    print("\n🎉 All emails drafted and stored in MongoDB.")


if __name__ == "__main__":
    asyncio.run(main())