from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from agents import Runner
from models import LeadRequest, LeadResponse, Lead
from agent import lead_agent
from query_agent import query_agent
from utils import leads_to_csv
from email_agent import email_agent
import io
import json
import re
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

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
MONGO_URI = "mongodb+srv://vijay:baby9271@internsportal.oswhrxp.mongodb.net/?retryWrites=true&w=majority&appName=internsPortal"
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
    """Insert leads into MongoDB (skip duplicates by email)."""
    if not isinstance(leads, list):
        leads = [leads]

    for lead in leads:
        if "email" in lead:
            existing = await lead_collection.find_one({"email": lead["email"]})
            if not existing:
                lead["created_at"] = datetime.utcnow()
                await lead_collection.insert_one(lead)
        else:
            lead["created_at"] = datetime.utcnow()
            await lead_collection.insert_one(lead)

@app.get("/")
async def check():
    return {"status": "ok", "message": "API is running!"}

@app.post("/api/scrape-leads", response_model=LeadResponse)
async def scrape_leads_api(payload: LeadRequest):
    global scraped_leads
    try:
        # Step 1: Call AI Agent
        result = await Runner.run(
            starting_agent=lead_agent,
            input=f"Find business leads for: {payload.query}. "
                  f"Return ONLY JSON array of leads with keys: name, email, company, phone."
        )

        print("=== RAW AI OUTPUT ===")
        print(result.final_output)

        # Step 2: Try to parse JSON
        try:
            leads_data = extract_json(result.final_output)
        except Exception as parse_error:
            print("JSON PARSE ERROR:", str(parse_error))
            raise HTTPException(status_code=500, detail=f"Failed to parse AI output. Error: {str(parse_error)}")

        # Step 3: Validate leads
        if not leads_data:
            raise HTTPException(
                status_code=404,
                detail="No leads returned by the AI agent."
            )

        print("=== LEADS DATA BEFORE MODEL ===")
        print(leads_data)

        try:
            scraped_leads = [Lead(**lead) for lead in leads_data]
        except Exception as model_error:
            print("MODEL VALIDATION ERROR:", str(model_error))
            raise HTTPException(status_code=500, detail=f"Invalid lead format. Error: {str(model_error)}")

        # Step 4: Save to MongoDB
        try:
            await save_to_mongo([lead.dict() for lead in scraped_leads])
        except Exception as mongo_error:
            print("MONGO SAVE ERROR:", str(mongo_error))
            raise HTTPException(status_code=500, detail=f"Failed to save to MongoDB. Error: {str(mongo_error)}")

        # Step 5: Return leads
        return {"leads": scraped_leads}

    except HTTPException:
        raise
    except Exception as e:
        print("GENERAL ERROR:", str(e))
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

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
        input=f"Schedule an email to these leads: {leads} at {send_time}."
    )
    return {"result": result.final_output}

@app.post("/api/query-leads", response_model=LeadResponse)
async def query_leads_api(payload: LeadRequest):
    try:
        # Call QueryAgent
        result = await Runner.run(
            starting_agent=query_agent,
            input=f"Query leads: {payload.query}. Return JSON array of leads with keys: name, email, company, phone, source."
        )

        print("=== RAW AI OUTPUT ===")
        print(result.final_output)

        # Parse JSON
        try:
            leads_data = extract_json(result.final_output)
        except Exception as parse_error:
            print("JSON PARSE ERROR:", str(parse_error))
            raise HTTPException(status_code=500, detail=f"Failed to parse AI output. Error: {str(parse_error)}")

        # Validate leads
        if not leads_data:
            return {"leads": []}

        print("=== LEADS DATA ===")
        print(leads_data)

        return {"leads": leads_data}
    except HTTPException:
        raise
    except Exception as e:
        print("GENERAL ERROR:", str(e))
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")