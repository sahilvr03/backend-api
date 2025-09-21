from agents import function_tool
from models import Lead
from typing import List
from tavily import TavilyClient

# Direct API key
TAVILY_API_KEY = "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"

# Initialize Tavily client
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

@function_tool
def scrape_leads(query: str, max_results: int = 100) -> List[Lead]:
    """
    Search for business leads using Tavily API.
    Returns a list of leads with name, email, company, and phone.
    """
    response = tavily_client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results
    )

    leads = []
    for item in response.get("results", []):
        leads.append(
            Lead(
                name=item.get("title", "Unknown"),
                email=item.get("email", None),
                company=item.get("source", None),
                phone=item.get("phone", None)
            )
        )
    return leads
