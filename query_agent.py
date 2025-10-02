from agents import Agent
from agents.extensions.models.litellm_model import LitellmModel
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from typing import List
from models import Lead
import json
import re

# MongoDB setup
MONGO_URI = "mongodb+srv://vijay:baby9271@internsportal.oswhrxp.mongodb.net/?retryWrites=true&w=majority&appName=internsPortal"
client = AsyncIOMotorClient(MONGO_URI)
db = client["lead_db"]
lead_collection = db["leads"]

# Gemini API key
GEMINI_API_KEY = "AIzaSyDyUverBS7o0HkMWlBVUKcOfi3xq1N1Nmk"

# Initialize Gemini model
model = LitellmModel(model="gemini/gemini-2.0-flash", api_key=GEMINI_API_KEY)

# Function to query MongoDB for leads
async def fetch_leads_from_db(query: str) -> List[dict]:
    """
    Fetch leads from MongoDB based on the natural language query.
    Supports time-based queries (e.g., last 10 days) and keyword filtering.
    """
    leads = []
    try:
        # Parse query for time range or keywords
        time_range_match = re.search(r"last (\d+) days", query, re.I)
        days = int(time_range_match.group(1)) if time_range_match else None
        now = datetime.utcnow()

        # Build MongoDB query
        mongo_query = {}
        if days:
            mongo_query["created_at"] = {
                "$gte": now - timedelta(days=days),
                "$lte": now
            }

        # Add keyword filtering if present
        keywords = [word.lower() for word in query.split() if word.lower() not in ["last", "days", "leads", "show", "past"]]
        if keywords:
            mongo_query["$or"] = [
                {"name": {"$regex": keyword, "$options": "i"}}
                for keyword in keywords
            ] + [
                {"company": {"$regex": keyword, "$options": "i"}}
                for keyword in keywords
            ] + [
                {"email": {"$regex": keyword, "$options": "i"}}
                for keyword in keywords
            ]

        # Fetch leads from MongoDB
        cursor = lead_collection.find(mongo_query)
        leads = [doc async for doc in cursor]

        # Convert MongoDB documents to Lead model-compatible dicts
        formatted_leads = []
        for lead in leads:
            lead_dict = {
                "name": lead.get("name", "Unknown"),
                "email": lead.get("email", None),
                "company": lead.get("company", None),
                "phone": lead.get("phone", None),
                "source": lead.get("source", None)
            }
            formatted_leads.append(lead_dict)

        return formatted_leads
    except Exception as e:
        print(f"Error fetching leads from MongoDB: {str(e)}")
        return []

# Query Agent
query_agent = Agent(
    name="QueryAgent",
    instructions=(
        "You are a conversational AI agent that helps users query their past leads stored in a MongoDB database. "
        "Users can ask questions in natural language, such as 'show me the past leads' or 'find leads from the last 10 days'. "
        "You can filter leads by time range (e.g., last X days) or by keywords in name, company, or email. "
        "Always return results in a JSON array of objects with keys: name, email, company, phone, source. "
        "If no leads match the query, return []. "
        "Use the fetch_leads_from_db tool to query the database. "
        "Do not invent or guess missing details. "
        "Ensure the response is strictly JSON formatted."
    ),
    model=model,
    tools=[fetch_leads_from_db],
)