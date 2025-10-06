import requests
from agents import function_tool
from models import Lead
from typing import List

HUNTER_API_KEY = "your_hunter_api_key_here"

@function_tool
def scrape_hunter_leads(domains: List[str], max_results: int = 10) -> List[Lead]:
    """
    Fetch business leads (emails) from a list of company domains using Hunter.io API.
    
    Args:
        domains: List of company domains (e.g. ["openai.com", "microsoft.com"])
        max_results: Limit number of emails per domain
    
    Returns:
        List[Lead]: List of Lead objects with name, email, company, phone
    """
    leads = []

    for domain in domains:
        url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}"
        try:
            response = requests.get(url)
            if response.status_code != 200:
                leads.append(Lead(
                    name="Error",
                    email=f"API Error: {response.status_code}",
                    company=domain,
                    phone=""
                ))
                continue

            data = response.json()
            emails = data.get("data", {}).get("emails", [])[:max_results]

            for e in emails:
                leads.append(
                    Lead(
                        name=e.get("first_name", "") + " " + e.get("last_name", ""),
                        email=e.get("value", "N/A"),
                        company=domain,
                        phone=""  # Hunter usually doesn’t return phone numbers
                    )
                )
        except Exception as ex:
            leads.append(Lead(
                name="Exception",
                email=str(ex),
                company=domain,
                phone=""
            ))

    return leads
