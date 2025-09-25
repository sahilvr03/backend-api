from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from agents import Runner
from models import LeadRequest, LeadResponse, Lead
from agent import lead_agent
from utils import leads_to_csv
import io
import json
import re
from motor.motor_asyncio import AsyncIOMotorClient
from email_agent import email_agent

app = FastAPI()

# Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB setup
MONGO_URI = "mongodb+srv://vijay:baby9271@internsportal.oswhrxp.mongodb.net/?retryWrites=true&w=majority&appName=internsPortal"   # change if remote
client = AsyncIOMotorClient(MONGO_URI)
db = client["lead_db"]
lead_collection = db["leads"]

# In-memory leads
scraped_leads = []

# --- Safe JSON extractor ---
def extract_json(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise HTTPException(
            status_code=500,
            detail="Model did not return valid JSON. Raw output: " + raw
        )

async def save_to_mongo(leads):
    """Insert leads into MongoDB (skip duplicates by emmail)."""
    if not isinstance(leads, list):
        leads = [leads]

    for lead in leads:
        if "email" in lead:
            existing = await lead_collection.find_one({"email": lead["email"]})
            if not existing:
                await lead_collection.insert_one(lead)
        else:
            await lead_collection.insert_one(lead)

@app.post("/api/scrape-leads", response_model=LeadResponse)
async def scrape_leads_api(payload: LeadRequest):
    global scraped_leads
    try:
        # AI Agent call
        result = await Runner.run(
            starting_agent=lead_agent,
            input=f"Find business leads for: {payload.query}. "
                  f"Return ONLY JSON array of leads with keys: name, email, company, phone."
        )

        leads_data = extract_json(result.final_output)

        if not leads_data:
            raise HTTPException(
                status_code=500,
                detail="No leads returned by the AI agent."
            )

        scraped_leads = [Lead(**lead) for lead in leads_data]

        # Save to MongoDB
        await save_to_mongo([lead.dict() for lead in scraped_leads])

        return {"leads": scraped_leads}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export-csv")
async def export_csv():
    if not scraped_leads:
        raise HTTPException(status_code=400, detail="No leads to export.")
    csv_data = leads_to_csv(scraped_leads)
    buffer = io.BytesIO(csv_data.encode())
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"}
    )

@app.post("/api/send-emails")
async def send_emails(payload: dict):
    query = payload.get("query", "business leads")
    leads_cursor = lead_collection.find({})
    leads = [Lead(**doc) async for doc in leads_cursor]

    result = await Runner.run(
        starting_agent=email_agent,
        input=f"Send a professional email to these leads: {leads}. "
              f"Use subject '{payload.get('subject', 'Collaboration Opportunity')}'."
    )
    return {"result": result.final_output}

@app.post("/api/schedule-emails")
async def schedule_emails(payload: dict):
    leads_cursor = lead_collection.find({})
    leads = [Lead(**doc) async for doc in leads_cursor]

    send_time = payload.get("send_time", "2025-09-22 10:00")

    result = await Runner.run(
        starting_agent=email_agent,
        input=f"Schedule an email to these leaads: {leads} at {send_time}."
    )
    return {"result": result.final_output}
