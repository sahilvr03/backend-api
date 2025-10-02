from agents import function_tool
from models import Lead
from typing import List
from tavily import TavilyClient
import requests
import re

# Tavily + Google API keys
TAVILY_API_KEY = "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"
GOOGLE_API_KEY = "AIzaSyD97k49aW_hPx87_BpHauUy2-6H38tJnz0"

tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# Regex for extracting emails
EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', re.I)

@function_tool
def scrape_leads(query: str, max_results: int = 20) -> List[Lead]:
    """
    Search for business leads using Tavily + Google Places API.
    Returns a list of leads with name, email, company, and phone.
    """
    leads: List[Lead] = []

    # -------- Tavily API Search --------
    try:
        tavily_resp = tavily_client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results
        )

        for item in tavily_resp.get("results", []):
            leads.append(
                Lead(
                    name=item.get("title", "Unknown"),
                    email=item.get("email", None),
                    company=item.get("source", None),
                    phone=item.get("phone", None),
                )
            )
    except Exception as e:
        print("Tavily error:", e)

    # -------- Google Places Search --------
    try:
        url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={query}&key={GOOGLE_API_KEY}"
        resp = requests.get(url)
        data = resp.json()

        if "results" in data:
            for place in data["results"][:max_results]:
                name = place.get("name")
                address = place.get("formatted_address")
                place_id = place.get("place_id")

                # Place Details: website + phone
                detail_url = (
                    f"https://maps.googleapis.com/maps/api/place/details/json?"
                    f"place_id={place_id}&fields=website,formatted_phone_number&key={GOOGLE_API_KEY}"
                )
                detail_resp = requests.get(detail_url).json()
                website = detail_resp.get("result", {}).get("website")
                phone = detail_resp.get("result", {}).get("formatted_phone_number")

                # Try extracting emails from website
                emails = []
                if website:
                    try:
                        site_html = requests.get(website, timeout=5).text
                        emails = EMAIL_RE.findall(site_html)
                    except Exception:
                        pass

                leads.append(
                    Lead(
                        name=name,
                        email=emails[0] if emails else None,
                        company=address,
                        phone=phone,
                    )
                )
    except Exception as e:
        print("Google Places error:", e)

    return leads
