from agents import Agent, function_tool
from agents.extensions.models.litellm_model import LitellmModel
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from typing import List
from fastapi import HTTPException
from pinecone import Pinecone
import json, re

# ==========================
# MongoDB setup
# ==========================
MONGO_URI = "mongodb+srv://vijay:baby9271@internsportal.oswhrxp.mongodb.net/?retryWrites=true&w=majority&appName=internsPortal"
client = AsyncIOMotorClient(MONGO_URI)
db = client["lead_db"]
lead_collection = db["leads"]

# ==========================
# Pinecone setup
# ==========================
PINECONE_API_KEY = "pcsk_3283KK_5MT1uResLEU4VJryL89LhzEJ45xibXNesXJ91uBhLRjBWCFG9DTPz97icRrmVqF"
pc = Pinecone(api_key=PINECONE_API_KEY)
INDEX_NAME = "lead-context"

# ==========================
# Gemini model setup
# ==========================
GEMINI_API_KEY = "AIzaSyDyUverBS7o0HkMWlBVUKcOfi3xq1N1Nmk"
model = LitellmModel(model="gemini/gemini-2.0-flash", api_key=GEMINI_API_KEY)


# --------------------------------
# Fetch Leads from MongoDB
# --------------------------------
@function_tool
async def fetch_leads_from_db(query: str) -> List[dict]:
    """
    Fetch leads from MongoDB based on natural language query.
    Supports time-based queries (e.g., 'last 10 days') and keyword filtering.
    """
    try:
        # Check for time range (last N days)
        time_match = re.search(r"last (\d+) days", query, re.I)
        days = int(time_match.group(1)) if time_match else None
        now = datetime.utcnow()

        mongo_query = {}
        if days:
            mongo_query["created_at"] = {
                "$gte": now - timedelta(days=days),
                "$lte": now
            }

        # Extract keywords (skip stop words)
        keywords = [
            word.lower()
            for word in query.split()
            if word.lower() not in ["last", "days", "leads", "show", "past", "from"]
        ]

        if keywords:
            mongo_query["$or"] = (
                [{"name": {"$regex": kw, "$options": "i"}} for kw in keywords]
                + [{"company": {"$regex": kw, "$options": "i"}} for kw in keywords]
                + [{"email": {"$regex": kw, "$options": "i"}} for kw in keywords]
            )

        cursor = lead_collection.find(mongo_query)
        leads = [doc async for doc in cursor]

        formatted = [
            {
                "name": lead.get("name", "Unknown"),
                "email": lead.get("email"),
                "company": lead.get("company"),
                "phone": lead.get("phone"),
                "source": lead.get("source"),
                "created_at": lead.get("created_at"),
            }
            for lead in leads
        ]
        return formatted
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {str(e)}")


# --------------------------------
# Fetch Leads from Pinecone (semantic)
# --------------------------------
@function_tool
async def fetch_leads_from_pinecone(query: str) -> List[dict]:
    """
    Semantic search leads using Pinecone.
    """
    try:
        cursor = lead_collection.find({})
        leads = [doc async for doc in cursor]

        records = [
            {
                "_id": str(lead["_id"]),
                "chunk_text": f"{lead.get('name','Unknown')} from {lead.get('company','Unknown')} "
                              f"email {lead.get('email','')} phone {lead.get('phone','')}",
                "category": "lead",
                "metadata": {
                    "name": lead.get("name"),
                    "email": lead.get("email"),
                    "company": lead.get("company"),
                    "phone": lead.get("phone"),
                    "source": lead.get("source"),
                },
            }
            for lead in leads
        ]

        # Upsert into Pinecone
        dense_index = pc.Index(INDEX_NAME)
        dense_index.upsert_records("lead-namespace", records)

        results = dense_index.search(
            namespace="lead-namespace",
            query={"top_k": 10, "inputs": {"text": query}},
            rerank={"model": "bge-reranker-v2-m3", "top_n": 10, "rank_fields": ["chunk_text"]},
        )

        formatted = [
            {
                "name": hit.get("metadata", {}).get("name", "Unknown"),
                "email": hit.get("metadata", {}).get("email"),
                "company": hit.get("metadata", {}).get("company"),
                "phone": hit.get("metadata", {}).get("phone"),
                "source": hit.get("metadata", {}).get("source"),
            }
            for hit in results["result"]["hits"]
        ]
        return formatted
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pinecone error: {str(e)}")


# --------------------------------
# Draft Email
# --------------------------------
@function_tool
async def draft_email(query: str, lead_email: str = None, subject: str = "Collaboration Opportunity") -> dict:
    """
    Drafts a professional email. Returns JSON with: subject, body, to.
    """
    try:
        lead = None
        if lead_email:
            lead = await lead_collection.find_one({"email": lead_email})

        prompt = f"Draft a professional email: '{query}'. "
        if lead:
            prompt += f"Address to {lead.get('name')} at {lead.get('company')} ({lead.get('email')}). "
        prompt += f"Subject: '{subject}'. Return JSON with keys: subject, body, to."

        result = await model.generate(prompt=prompt)

        try:
            data = json.loads(result)
            return {
                "subject": data.get("subject", subject),
                "body": data.get("body", ""),
                "to": data.get("to", lead_email or "recipient@example.com"),
            }
        except json.JSONDecodeError:
            return {"subject": subject, "body": result, "to": lead_email or "recipient@example.com"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email error: {str(e)}")


# --------------------------------
# Suggest Client Approach Strategy
# --------------------------------
@function_tool
async def suggest_approach_strategy(query: str) -> dict:
    """
    Suggests strategy JSON: strategy, communication_style, value_proposition, follow_up_plan.
    """
    try:
        prompt = (
            f"Suggest a client approach strategy for: '{query}'. "
            "Return JSON with keys: strategy, communication_style, value_proposition, follow_up_plan."
        )
        result = await model.generate(prompt=prompt)

        try:
            data = json.loads(result)
            return {
                "strategy": data.get("strategy", ""),
                "communication_style": data.get("communication_style", ""),
                "value_proposition": data.get("value_proposition", ""),
                "follow_up_plan": data.get("follow_up_plan", ""),
            }
        except json.JSONDecodeError:
            return {
                "strategy": result,
                "communication_style": "Professional",
                "value_proposition": "Highlight unique offerings",
                "follow_up_plan": "Follow up within 3-5 days",
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Strategy error: {str(e)}")


# --------------------------------
# Query Agent
# --------------------------------
query_agent = Agent(
    name="QueryAgent",
    instructions=(
        "You are a lead assistant AI. Users can:\n"
        "1. Query MongoDB/Pinecone for leads (e.g., 'show leads from last 10 days').\n"
        "2. Draft emails (e.g., 'write an email to john@company.com').\n"
        "3. Suggest client approach strategies.\n\n"
        "Use tools appropriately. Always return JSON:\n"
        "- For leads: { 'leads': [ {name, email, company, phone, source} ] }\n"
        "- For email: { 'email': {to, subject, body} }\n"
        "- For strategy: { 'strategy': {...} }\n"
        "- For errors: { 'error': 'message' }\n"
    ),
    model=model,
    tools=[fetch_leads_from_db, fetch_leads_from_pinecone, draft_email, suggest_approach_strategy],
)
