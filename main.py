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

app = FastAPI()

# Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.post("/api/scrape-leads", response_model=LeadResponse)
async def scrape_leads_api(payload: LeadRequest):
    global scraped_leads
    try:
        # FIX: Await Runner.run since it's async
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
        return {"leads": scraped_leads}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export-csv")
async def export_csv():
    if not scraped_leads:
        raise HTTPException(status_code=400, detail="No leads to export.")
    csv_data = leads_to_csv(scraped_leads)
    buffer = io.BytesIO(csv_data.encode())
    return StreamingResponse(buffer, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=leads.csv"
    })
