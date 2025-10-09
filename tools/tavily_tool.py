from typing import Optional
from agents import function_tool
from models import Lead
from tavily import TavilyClient
import requests
import re
import asyncio
import json

# API keys
TAVILY_API_KEY = "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"
GOOGLE_API_KEY = "AIzaSyD97k49aW_hPx87_BpHauUy2-6H38tJnz0"
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# Regex for emails and UAE phones
EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', re.I)
INVALID_EMAIL_RE = re.compile(r'@(select2|bootstrap|icon|intl-segmenter|slick-carousel|lc-lightbox-lite|streamline|jquery|fontawesome|wp-content|cdn|assets|png|svg|js|css)\b', re.I)
PHONE_RE = re.compile(r'(\+971|00?971)?[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})')

@function_tool
async def scrape_leads(query: str, country: Optional[str] = None, lead_type: Optional[str] = None, max_results: int = 100) -> str:
    """
    Search for business leads using Tavily + Google Places API.
    Returns a JSON string of leads array.
    """
    leads = []
    search_query = f"{lead_type or ''} {query} {country or ''}".strip()
    
    def is_valid_email(email):
        if not email:
            return False
        if INVALID_EMAIL_RE.search(email):
            return False
        if any(generic in email.lower() for generic in ["info@", "contact@", "support@", "sales@", "hello@"]):
            return True
        return EMAIL_RE.match(email) and "@" in email and len(email.split('.')[-1]) >= 2

    async def fetch_tavily():
        try:
            tavily_resp = tavily_client.search(
                query=search_query,
                search_depth="advanced",
                max_results=max_results // 2
            )
            print(f"Tavily found {len(tavily_resp.get('results', []))} raw results for '{search_query}'")
            for item in tavily_resp.get("results", []):
                content = item.get("content", "") + " " + item.get("description", "")
                title = item.get("title", "Unknown")
                
                emails = EMAIL_RE.findall(content)
                email = None
                for e in emails[:1]:
                    if is_valid_email(e):
                        email = e
                        break
                
                phones = PHONE_RE.findall(content)
                phone = None
                if phones:
                    phone = f"+971-{phones[0][1]}-{phones[0][2]}-{phones[0][3]}" if len(phones[0]) == 4 else None
                
                if not email and "uae" in search_query.lower() and item.get("source"):
                    domain = re.sub(r'[^\w\s-]', '', item.get("source").replace("www.", "").split("/")[0].lower().replace(" ", ""))
                    if not domain.endswith(".ae"):
                        domain += ".ae"
                    email = f"info@{domain} (guessed)"
                
                if email or phone:
                    lead = {
                        "name": title,
                        "email": email if is_valid_email(email) else None,
                        "company": item.get("source", "Unknown"),
                        "phone": phone,
                        "source": item.get("url"),
                        "country": country,
                        "lead_type": lead_type
                    }
                    leads.append(lead)
                    print(f"Extracted Tavily lead: {lead['name']} ({lead['email'] or 'No email'})")
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Tavily error: {e}")

    async def fetch_google():
        try:
            next_page_token = None
            fetched = 0
            while fetched < max_results // 2:
                params = {"query": search_query, "key": GOOGLE_API_KEY}
                if next_page_token:
                    params["pagetoken"] = next_page_token
                    await asyncio.sleep(2)
                
                url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
                resp = requests.get(url, params=params)
                data = resp.json()
                print(f"Google found {len(data.get('results', []))} raw results")
                
                if "results" not in data:
                    break
                
                for place in data["results"][:max_results // 2 - fetched]:
                    name = place.get("name", "Unknown")
                    address = place.get("formatted_address", "Unknown")
                    place_id = place.get("place_id")
                    
                    detail_params = {"place_id": place_id, "fields": "website,formatted_phone_number", "key": GOOGLE_API_KEY}
                    detail_url = "https://maps.googleapis.com/maps/api/place/details/json"
                    detail_resp = requests.get(detail_url, params=detail_params).json()
                    website = detail_resp.get("result", {}).get("website")
                    phone = detail_resp.get("result", {}).get("formatted_phone_number")
                    
                    email = None
                    if website:
                        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                        try:
                            site_resp = requests.get(website, headers=headers, timeout=10)
                            emails = EMAIL_RE.findall(site_resp.text)
                            for e in emails[:1]:
                                if is_valid_email(e):
                                    email = e
                                    break
                        except Exception as site_e:
                            print(f"Website scrape error: {site_e}")
                    
                    if not email and "uae" in search_query.lower():
                        domain = re.sub(r'[^\w\s-]', '', name.lower()).replace(" ", "") + ".ae"
                        email = f"info@{domain} (guessed)"
                    
                    if email or phone:
                        lead = {
                            "name": name,
                            "email": email if is_valid_email(email) else None,
                            "company": address,
                            "phone": phone,
                            "source": website,
                            "country": country,
                            "lead_type": lead_type
                        }
                        leads.append(lead)
                        print(f"Extracted Google lead: {lead['name']} {lead['phone']} ({lead['email'] or 'No email'})")
                    
                    fetched += 1
                    await asyncio.sleep(0.1)
                
                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break
        except Exception as e:
            print(f"Google error: {e}")

    await asyncio.gather(fetch_tavily(), fetch_google())
    print(f"Returning {len(leads)} leads from scrape_leads")
    return json.dumps(leads, ensure_ascii=False)