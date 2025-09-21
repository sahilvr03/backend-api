import requests
from agents import function_tool
from models import Lead
from typing import List

APOLLO_API_KEY = "oonqrVtMGwBkasJeoOnVzw"

@function_tool
def scrape_apollo_leads(query: str, max_results: int = 50) -> List[Lead]:
    """
    Scrape business leads using Apollo API.
    """
    url = "https://api.apollo.io/api/v1/mixed_people/search"

    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY
    }

    payload = {
        "q_keywords": query,
        "per_page": max_results,
        "page": 1
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            return [Lead(name="Error", email=f"API Error: {response.status_code}", company="", phone="")]

        data = response.json()
        leads = []

        for person in data.get("people", []):
            org = person.get("organization") or {}
            leads.append(
                Lead(
                    name=person.get("name", "Unknown"),
                    email=person.get("email", "N/A"),
                    company=org.get("name", "N/A"),
                    phone=person.get("phone_numbers", [{}])[0].get("raw_number", "")
                )
            )
        return leads

    except Exception as e:
        return [Lead(name="Exception", email=str(e), company="", phone="")]
