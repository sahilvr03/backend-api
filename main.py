from fastapi import FastAPI, HTTPException,APIRouter
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
from pinecone import Pinecone
from pydantic import BaseModel
from typing import List, Optional, Union

app = FastAPI()

router = APIRouter()
# Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB setup
MONGO_URI = "mongodb+srv://vijay:baby9271@internsportal.oswhrxp.mongodb.net/?retryWrites=true&w=majority&appName=internsPortal"
client = AsyncIOMotorClient(MONGO_URI)
db = client["lead_db"]
lead_collection = db["leads"]

# Pinecone setup
PINECONE_API_KEY = "pcsk_3283KK_5MT1uResLEU4VJryL89LhzEJ45xibXNesXJ91uBhLRjBWCFG9DTPz97icRrmVqF"
INDEX_NAME = "lead-context"

@app.on_event("startup")
async def init_pinecone():
    pc = Pinecone(api_key=PINECONE_API_KEY)
    if not pc.has_index(INDEX_NAME):
        pc.create_index_for_model(
            name=INDEX_NAME,
            cloud="aws",
            region="us-east-1",
            embed={
                "model": "llama-text-embed-v2",
                "field_map": {"text": "chunk_text"}
            }
        )

# In-memory leads
scraped_leads = []

# --- Safe JSON extractor ---
def extract_json(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
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
        if "email" in lead and lead["email"]:
            existing = await lead_collection.find_one({"email": lead["email"]})
            if not existing:
                lead["created_at"] = datetime.utcnow()
                await lead_collection.insert_one(lead)
        else:
            lead["created_at"] = datetime.utcnow()
            await lead_collection.insert_one(lead)

# Extended response model for chatbot
class EmailResponse(BaseModel):
    subject: str
    body: str
    to: str

class StrategyResponse(BaseModel):
    strategy: str
    communication_style: str
    value_proposition: str
    follow_up_plan: str

class ChatbotResponse(BaseModel):
    leads: Optional[List[Lead]] = None
    email: Optional[EmailResponse] = None
    strategy: Optional[StrategyResponse] = None
    message: Optional[str] = None
    error: Optional[str] = None

@app.get("/")
async def check():
    return {"status": "ok", "message": "API is running!"}

@app.post("/api/scrape-leads", response_model=LeadResponse)
async def scrape_leads_api(payload: LeadRequest):
    global scraped_leads
    try:
        result = await Runner.run(
            starting_agent=lead_agent,
            input=f"Find business leads for: {payload.query}. "
                  f"Return ONLY JSON array of leads with keys: name, email, company, phone, source."
        )
        print("=== RAW AI OUTPUT ===")
        print(result.final_output)
        try:
            leads_data = extract_json(result.final_output)
        except Exception as parse_error:
            print("JSON PARSE ERROR:", str(parse_error))
            raise HTTPException(status_code=500, detail=f"Failed to parse AI output. Error: {str(parse_error)}")
        if not leads_data:
            raise HTTPException(status_code=404, detail="No leads returned by the AI agent.")
        print("=== LEADS DATA BEFORE MODEL ===")
        print(leads_data)
        try:
            scraped_leads = [Lead(**lead) for lead in leads_data]
        except Exception as model_error:
            print("MODEL VALIDATION ERROR:", str(model_error))
            raise HTTPException(status_code=500, detail=f"Invalid lead format. Error: {str(model_error)}")
        try:
            await save_to_mongo([lead.dict() for lead in scraped_leads])
        except Exception as mongo_error:
            print("MONGO SAVE ERROR:", str(mongo_error))
            raise HTTPException(status_code=500, detail=f"Failed to save to MongoDB. Error: {str(mongo_error)}")
        try:
            pc = Pinecone(api_key=PINECONE_API_KEY)
            dense_index = pc.Index(INDEX_NAME)
            records = [
                {
                    "_id": str(lead.email),
                    "chunk_text": f"{lead.name or 'Unknown'} from {lead.company or 'Unknown'} "
                                  f"with email {lead.email or 'None'} and phone {lead.phone or 'None'}",
                    "category": "lead",
                    "metadata": {
                        "name": lead.name or "Unknown",
                        "email": lead.email,
                        "company": lead.company,
                        "phone": lead.phone,
                        "source": lead.source
                    }
                }
                for lead in scraped_leads
            ]
            dense_index.upsert_records("lead-namespace", records)
        except Exception as pinecone_error:
            print("PINECONE UPSERT ERROR:", str(pinecone_error))
            raise HTTPException(status_code=500, detail=f"Failed to upsert to Pinecone. Error: {str(pinecone_error)}")
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

class Lead(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None


class EmailDraft(BaseModel):
    to: str
    subject: str
    body: str


class ApproachStrategy(BaseModel):
    strategy: str
    communication_style: str
    value_proposition: str
    follow_up_plan: str


class ChatbotResponse(BaseModel):
    message: Optional[str] = None
    leads: Optional[List[Lead]] = []
    email: Optional[EmailDraft] = None
    strategy: Optional[ApproachStrategy] = None
    error: Optional[str] = None


# =============================
# API Endpoint
# =============================
@app.post("/api/query-leads")
async def query_leads(request: dict):
    try:
        query = request.get("query")
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")

        # Run agent with Runner (Agent doesn’t have .run())
        run_result = await Runner.run(starting_agent=query_agent, input=query)

        print("=== RUNNER RESULT ===")
        print(run_result)

        # Extract raw output safely
        if hasattr(run_result, "final_output"):
            raw_response = run_result.final_output
        elif hasattr(run_result, "output"):
            raw_response = run_result.output
        else:
            raw_response = str(run_result)

        print("=== RAW AGENT OUTPUT ===")
        print(raw_response)

        # Try parsing as JSON
        try:
            response_data = json.loads(raw_response)
        except Exception:
            # If plain text, return as message
            return ChatbotResponse(message=raw_response)

        # Normalize dict or list
        if isinstance(response_data, dict):
            return ChatbotResponse(
                message=response_data.get("message") or response_data.get("response"),
                leads=response_data.get("leads", []),
                email=response_data.get("email"),
                strategy=response_data.get("strategy"),
                error=response_data.get("error"),
            )
        elif isinstance(response_data, list):  # sometimes agent returns list of leads
            return ChatbotResponse(leads=response_data)
        else:
            return ChatbotResponse(message=str(response_data))

    except HTTPException:
        raise
    except Exception as e:
        print("Backend error:", e)
        return ChatbotResponse(error=str(e))