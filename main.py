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
from email_agent import email_collection, generate_email_body, EMAIL_USER, SMTP_SERVER, SMTP_PORT, EMAIL_PASS, email_agent
from agent import lead_agent
import asyncio
from bson import ObjectId
from datetime import datetime, timedelta

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
email_collection = db["emails"]  # new collection for email leads


scraped_leads = []

def sanitize_mongo_doc(doc):
    if not doc:
        return doc
    doc["_id"] = str(doc["_id"])
    for k, v in doc.items():
        if isinstance(v, datetime):
            doc[k] = v.isoformat()  # convert datetime → "2025-10-10T12:00:00"
    return doc


def sanitize_mongo_doc2(doc: dict) -> dict:
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

import random

async def save_email_to_mongo(lead_dict):
    """
    Save only leads with email to a separate email collection.
    Generate a subject line automatically.
    """
    if not lead_dict.get("email"):
        return None

    # Auto subject line generator (simple version)
    subjects = [
        f"Grow your business with {lead_dict.get('company', 'our solutions')}",
        f"Partnership opportunity for {lead_dict.get('name', 'your company')}",
        f"Unlock new opportunities in {lead_dict.get('country', 'your region')}",
        f"Special solutions for {lead_dict.get('lead_type', 'businesses')}",
        "Let’s collaborate and create impact together"
    ]
    subject = random.choice(subjects)

    email_doc = {
        "name": lead_dict.get("name"),
        "email": lead_dict.get("email"),
        "subject": subject,
        "company": lead_dict.get("company"),
        "country": lead_dict.get("country"),
        "lead_type": lead_dict.get("lead_type"),
        "created_at": datetime.utcnow()
    }

    # Avoid duplicates (unique email constraint)
    existing = await email_collection.find_one({"email": email_doc["email"]})
    if not existing:
        result = await email_collection.insert_one(email_doc)
        email_doc["_id"] = str(result.inserted_id)
        print(f"Saved email lead: {email_doc['email']} with subject: {email_doc['subject']}")
        return email_doc
    
    return existing


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
                        # Inside your stream_leads() where you process each parsed lead:
                            for lead_dict in leads_parsed:
                                if isinstance(lead_dict, dict) and (lead_dict.get("email") or lead_dict.get("phone")):
                                    # Save to MongoDB (main leads collection)
                                    saved_doc = await save_to_mongo(lead_dict, payload.country, payload.lead_type)
                                    
                                    # --- NEW: Save only emails separately ---
                                    if lead_dict.get("email"):
                                        await save_email_to_mongo(lead_dict)

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

from fastapi.responses import JSONResponse



@app.get("/api/emails")
async def get_emails():
    try:
        cursor = email_collection.find().sort("created_at", -1)
        emails = []
        async for doc in cursor:
            emails.append(sanitize_mongo_doc2(doc))
        return JSONResponse(content=emails)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    

from email.mime.multipart import MIMEMultipart
import smtplib
from email.mime.text import MIMEText

from fastapi import Query

@app.post("/api/send-emails-eco")
async def send_emails_api(limit: int = Query(10, description="Number of emails to send")):
    cursor = email_collection.find({"status": {"$ne": "sent"}}).sort("created_at", -1).limit(limit)
    results = []
    
    async for lead in cursor:
        lead_id = lead["_id"]  # Original ObjectId rakhna hai
        subject = lead.get("subject")
        email = lead.get("email")
        name = lead.get("name", "")
        
        if not email:
            continue

        try:
            # AI generated body - ensure it returns a string
            body = await generate_email_body(subject, lead)
            
            # Validate that body is a string
            if not isinstance(body, str):
                body = str(body) if body else "Hello, I would like to connect regarding potential collaboration opportunities."

            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = email
            msg["Subject"] = subject
            
            # Personalize the email if we have a name
            if name:
                personalized_body = f"Dear {name},\n\n{body}\n\nBest regards,\nYour Team"
            else:
                personalized_body = f"Hello,\n\n{body}\n\nBest regards,\nYour Team"
                
            msg.attach(MIMEText(personalized_body, "plain"))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PASS)
                server.sendmail(EMAIL_USER, email, msg.as_string())

            # ✅ YEH IMPORTANT HAI: Database mein status update karo
            await email_collection.update_one(
                {"_id": lead_id},  # Original ObjectId use karo
                {
                    "$set": {
                        "status": "sent",
                        "sent_at": datetime.utcnow(),
                        "last_attempt": datetime.utcnow()
                    }
                }
            )
            
            results.append({"email": email, "subject": subject, "status": "sent"})
            print(f"✅ Email sent to {email} and status updated in database")
            
        except Exception as e:
            error_msg = f"failed: {str(e)}"
            print(f"❌ Failed to send email to {email}: {error_msg}")
            
            # ✅ Failed attempt bhi track karo
            await email_collection.update_one(
                {"_id": lead_id},
                {
                    "$set": {
                        "status": "failed",
                        "last_attempt": datetime.utcnow(),
                        "error": error_msg
                    }
                }
            )
            
            results.append({"email": email, "subject": subject, "status": error_msg})

        await asyncio.sleep(0.2)  # Rate limiting

    return {"results": results}
@app.get("/api/email-send-status")
async def get_email_send_status():
    """
    Get detailed statistics about email sending status
    """
    try:
        total_emails = await email_collection.count_documents({})
        sent_emails = await email_collection.count_documents({"status": "sent"})
        failed_emails = await email_collection.count_documents({"status": "failed"})
        pending_emails = await email_collection.count_documents({"status": {"$exists": False}})
        
        return {
            "total_emails": total_emails,
            "sent_emails": sent_emails,
            "failed_emails": failed_emails,
            "pending_emails": pending_emails,
            "success_rate": round((sent_emails / total_emails * 100), 2) if total_emails > 0 else 0
        }
    except Exception as e:
        return {"error": str(e)}
 


@app.get("/api/sent-emails")
async def get_sent_emails(
    limit: int = Query(50, description="Number of emails to return"),
    page: int = Query(1, description="Page number"),
    sort_by: str = Query("sent_at", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc")
):
    """
    Get all emails with status 'sent'
    """
    try:
        # Calculate skip for pagination
        skip = (page - 1) * limit
        
        # Sort order
        sort_direction = -1 if sort_order == "desc" else 1
        
        cursor = email_collection.find({"status": "sent"}).sort(sort_by, sort_direction).skip(skip).limit(limit)
        
        sent_emails = []
        async for doc in cursor:
            email_data = sanitize_mongo_doc2(doc)
            
            # Add formatted date for better display
            if doc.get("sent_at"):
                email_data["sent_at_formatted"] = doc["sent_at"].strftime("%Y-%m-%d %H:%M:%S")
            
            sent_emails.append(email_data)
        
        # Get total count for pagination info
        total_sent = await email_collection.count_documents({"status": "sent"})
        total_pages = (total_sent + limit - 1) // limit  # Ceiling division
        
        return {
            "emails": sent_emails,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_emails": total_sent,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        
    except Exception as e:
        return {"error": str(e)}



@app.get("/api/sent-emails-by-date")
async def get_sent_emails_by_date(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, description="Number of emails to return")
):
    """
    Get sent emails within a date range
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        
        cursor = email_collection.find({
            "status": "sent",
            "sent_at": {
                "$gte": start_dt,
                "$lte": end_dt
            }
        }).sort("sent_at", -1).limit(limit)
        
        sent_emails = []
        async for doc in cursor:
            email_data = sanitize_mongo_doc2(doc)
            email_data["sent_at_formatted"] = doc["sent_at"].strftime("%Y-%m-%d %H:%M:%S")
            sent_emails.append(email_data)
        
        return {
            "emails": sent_emails,
            "date_range": {
                "start_date": start_date,
                "end_date": end_date,
                "total_emails": len(sent_emails)
            }
        }
        
    except Exception as e:
        return {"error": str(e)}
    


@app.get("/api/recent-sent-emails")
async def get_recent_sent_emails(
    hours: int = Query(24, description="Last N hours"),
    limit: int = Query(50, description="Number of emails to return")
):
    """
    Get emails sent in the last N hours
    """
    try:
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        
        cursor = email_collection.find({
            "status": "sent",
            "sent_at": {"$gte": time_threshold}
        }).sort("sent_at", -1).limit(limit)
        
        recent_emails = []
        async for doc in cursor:
            email_data = sanitize_mongo_doc2(doc)
            email_data["sent_at_formatted"] = doc["sent_at"].strftime("%Y-%m-%d %H:%M:%S")
            
            # Calculate how long ago it was sent
            time_diff = datetime.utcnow() - doc["sent_at"]
            email_data["sent_ago"] = f"{time_diff.seconds // 3600}h {(time_diff.seconds % 3600) // 60}m ago"
            
            recent_emails.append(email_data)
        
        return {
            "emails": recent_emails,
            "time_period": f"last_{hours}_hours",
            "total_emails": len(recent_emails)
        }
        
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/search-sent-emails")
async def search_sent_emails(
    query: str = Query(..., description="Search in email, name, company or subject"),
    limit: int = Query(50, description="Number of emails to return")
):
    """
    Search within sent emails
    """
    try:
        # Case-insensitive search across multiple fields
        cursor = email_collection.find({
            "status": "sent",
            "$or": [
                {"email": {"$regex": query, "$options": "i"}},
                {"name": {"$regex": query, "$options": "i"}},
                {"company": {"$regex": query, "$options": "i"}},
                {"subject": {"$regex": query, "$options": "i"}}
            ]
        }).sort("sent_at", -1).limit(limit)
        
        search_results = []
        async for doc in cursor:
            email_data = sanitize_mongo_doc2(doc)
            email_data["sent_at_formatted"] = doc["sent_at"].strftime("%Y-%m-%d %H:%M:%S")
            search_results.append(email_data)
        
        return {
            "results": search_results,
            "search_query": query,
            "total_found": len(search_results)
        }
        
    except Exception as e:
        return {"error": str(e)}




