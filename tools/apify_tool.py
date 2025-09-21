# tools/apify_tool.py
import requests
from agents import function_tool
from typing import List, Dict
import re

# Apify API token (provided)
APIFY_API_TOKEN = "apify_api_vHVyOUMWeToc8EQQ4aNgYv9gVKLDak4xkgH5"

@function_tool
def scrape_apify_domain(domain: str) -> str:
    """
    Find emails associated with a domain using Apify Email Extractor API.
    Returns the first valid email found.
    """
    url = f"https://api.apify.com/v2/acts/apify~email-extractor/run-sync?token={APIFY_API_TOKEN}"

    params = {
        "domain": domain,
        "maxEmails": 1
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            return "N/A"

        data = response.json()
        emails = data.get("data", {}).get("emails", [])
        valid_emails = [email for email in emails if re.match(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', email)]
        return valid_emails[0] if valid_emails else "N/A"

    except Exception:
        return "N/A"