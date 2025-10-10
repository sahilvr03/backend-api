from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from agents import Runner, ItemHelpers
from models import LeadRequest, LeadResponse, Lead
from bot_api import lead_agent2, show_leads, count_leads, get_email_stats, list_scheduled_emails, draft_email_template
from utils import leads_to_csv
import io
import json
import re
import html
from motor.motor_asyncio import AsyncIOMotorClient
from email_agent import email_agent
from agent import lead_agent
import asyncio
from bson import ObjectId

app = FastAPI(
    title="Lead Management AI API",
    description="AI-powered API for managing leads, drafting emails, and fetching stats.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True, 
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_URI = "mongodb+srv://vijay:baby9271@internsportal.oswhrxp.mongodb.net/?retryWrites=true&w=majority&appName=internsPortal"
client = AsyncIOMotorClient(MONGO_URI)
db = client["lead_dbb"]
lead_collection = db["leadss"]

scraped_leads = []

def sanitize_mongo_doc(doc: dict) -> dict:
    """Remove _id, convert ObjectId to str, remove None values, ensure JSON serializable."""
    safe_doc = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, ObjectId):
            safe_doc[k] = str(v)
        elif v is not None:
            safe_doc[k] = v
    return safe_doc

def extract_json(raw: str):
    try:
        raw = html.unescape(raw)
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        dict_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if dict_match:
            try:
                return [json.loads(dict_match.group(0))]
            except json.JSONDecodeError:
                pass
        return []

async def save_to_mongo(lead, country=None, lead_type=None):
    lead_copy = {k: v for k, v in lead.items() if k != "_id" and v is not None}
    lead_copy["country"] = country or lead_copy.get("country")
    lead_copy["lead_type"] = lead_type or lead_copy.get("lead_type")
    if "email" in lead_copy and lead_copy["email"]:
        existing = await lead_collection.find_one({"email": lead_copy["email"]})
        if not existing:
            await lead_collection.insert_one(lead_copy)
    else:
        await lead_collection.insert_one(lead_copy)
    return lead_copy

@app.on_event("shutdown")
async def shutdown():
    client.close()  # ✅ Correct
    print("MongoDB connection closed.")

@app.get("/")
async def check():
    return {"status": "ok", "message": "Lead Management AI API is running!"}

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
async def chat(data: dict):
    query = data.get("query")
    agent_type = data.get("agent", "email")  # default = email

    if agent_type == "lead":
        result = await Runner.run(lead_agent2, input=query)
    else:
        result = await Runner.run(email_agent, input=query)
    print(f"Agent result: {result.final_output[:200]}...")
    return {"status": "success", "response": result.final_output}


@app.post("/api/scrape-leads")
async def scrape_leads_api(payload: LeadRequest):
    global scraped_leads
    scraped_leads = []
    max_results = 100

    async def stream_leads():
        count = 0
        try:
            # First, stream from DB if country and lead_type provided
            if payload.country and payload.lead_type:
                print(f"Fetching existing leads for {payload.lead_type} in {payload.country}")
                cursor = lead_collection.find({
                    "country": payload.country,
                    "lead_type": payload.lead_type
                }).sort("_id", -1).limit(max_results)
                
                async for doc in cursor:
                    lead_dict = sanitize_mongo_doc(doc)
                    # Add display fields for frontend
                    lead_dict["display_contact"] = lead_dict.get("email") or lead_dict.get("phone", "")
                    lead_dict["has_email"] = bool(lead_dict.get("email"))
                    
                    yield json.dumps(lead_dict, ensure_ascii=False) + "\n"
                    scraped_leads.append(Lead(**lead_dict))
                    count += 1
                    await asyncio.sleep(0.05)

            max_scrape = max_results - count
            if max_scrape > 0:
                print(f"Starting streamed scrape for: {payload.query}, country: {payload.country}, lead_type: {payload.lead_type}")
                result = Runner.run_streamed(
                    lead_agent,
                    input=(
                        f"Find business leads for query: {payload.query}. "
                        f"Country: {payload.country or 'any'}. Lead type: {payload.lead_type or 'any'}. "
                        f"Call scrape_leads tool with max_results={max_scrape} and return JSON array."
                    )
                )

                async for event in result.stream_events():
                    if event.type == "run_item_stream_event" and hasattr(event, "item") and event.item:
                        item = event.item
                        leads_parsed = []

                        # --- Tool output ---
                        if getattr(item, "type", None) == "tool_call_output_item":
                            output_str = str(item.output)
                            print(f"Tool output: {output_str[:200]}...")
                            leads_parsed = extract_json(output_str)
                            if not isinstance(leads_parsed, list):
                                leads_parsed = [leads_parsed] if isinstance(leads_parsed, dict) else []

                        # --- Agent message ---
                        elif getattr(item, "type", None) == "message_output_item":
                            text = ItemHelpers.text_message_output(item)
                            print(f"Agent message: {text[:200]}...")
                            leads_parsed = extract_json(text)
                            if not isinstance(leads_parsed, list):
                                leads_parsed = [leads_parsed] if isinstance(leads_parsed, dict) else []

                        # --- Process parsed leads ---
                        for lead_dict in leads_parsed:
                            if isinstance(lead_dict, dict) and (lead_dict.get("email") or lead_dict.get("phone")):
                                # Save to MongoDB
                                saved_doc = await save_to_mongo(lead_dict, payload.country, payload.lead_type)
                                
                                # Sanitize the saved document
                                safe_doc = sanitize_mongo_doc(saved_doc)
                                
                                # Add display fields for frontend
                                safe_doc["display_contact"] = safe_doc.get("email") or safe_doc.get("phone", "")
                                safe_doc["has_email"] = bool(safe_doc.get("email"))
                                
                                # Yield as JSON line
                                yield json.dumps(safe_doc, ensure_ascii=False) + "\n"
                                
                                scraped_leads.append(Lead(**safe_doc))
                                count += 1
                                await asyncio.sleep(0.05)

            print(f"Total leads streamed: {count}")
            if count == 0:
                yield json.dumps({"warning": "No valid leads found. Try a different query."}) + "\n"

        except Exception as e:
            print(f"Stream error: {e}")
            import traceback
            traceback.print_exc()
            yield json.dumps({"error": str(e)}) + "\n"

    # Stream response with headers that force no buffering
    return StreamingResponse(
        stream_leads(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disables proxy buffering (important)
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked"
        },
    )

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
    leads = [Lead(**{k: v for k, v in doc.items() if k != "_id" and not isinstance(v, ObjectId)}) async for doc in leads_cursor]
    result = await Runner.run(
        starting_agent=email_agent,
        input=f"Send a professional email to these leads: {leads}. "
              f"Use subject '{payload.get('subject', 'Collaboration Opportunity')}'."
    )
    return {"result": result.final_output}

@app.post("/api/schedule-emails")
async def schedule_emails(payload: dict):
    leads_cursor = lead_collection.find({})
    leads = [Lead(**{k: v for k, v in doc.items() if k != "_id" and not isinstance(v, ObjectId)}) async for doc in leads_cursor]
    send_time = payload.get("send_time", "2025-09-22 10:00")
    result = await Runner.run(
        starting_agent=email_agent,
        input=f"Schedule an email to these leads: {leads} at {send_time}."
    )
    return {"result": result.final_output}