from agents import Agent
from agents.extensions.models.litellm_model import LitellmModel
from tools.tavily_tool import scrape_leads
from tools.hunteremail_tool import scrape_hunter_leads

# Gemini API key
GEMINI_API_KEY = "AIzaSyDyUverBS7o0HkMWlBVUKcOfi3xq1N1Nmk"
model = LitellmModel(model="gemini/gemini-2.0-flash", api_key=GEMINI_API_KEY)

# Tavily Agent
tavily_agent = Agent(
    name="TavilyAgent",
    instructions=(
        "You are a business lead scraping agent. "
        "Call the scrape_leads tool with the provided query, country, and lead_type. "
        "Return a JSON array of valid leads: "
        '[{\"name\": \"John Doe\", \"email\": \"john@company.com\", \"company\": \"CompanyX\", \"phone\": \"+971-xxx-xxx\", \"source\": \"https://...\", \"country\": \"UAE\", \"lead_type\": \"Real Estate\"}]. '
        "Include leads with email OR phone. Skip generic emails (info@, contact@, support@, noreply@). "
        "For UAE queries, prioritize .ae domains and +971 phones. "
        "Return [] if no leads."
    ),
    model=model,
    tools=[scrape_leads],
)

# Orchestrator Agent
lead_agent = Agent(
    name="LeadOrchestrator",
    instructions=(
        "Orchestrate lead scraping. Handoff to TavilyAgent. "
        "Instruct it to call scrape_leads with query, country, lead_type and return a JSON array of leads. "
        "Stream the leads as received. Return [] if empty."
    ),
    model=model,
    handoffs=[tavily_agent],
)

# Email Agent
email_agent = Agent(
    name="EmailAgent",
    instructions=(
        "You are an email-finding assistant. "
        "Use the Hunter.io API via scrape_hunter_leads to fetch verified email addresses. "
        "Return a structured list of leads with emails, names, and companies, without duplicates."
    ),
    model=model,
    tools=[scrape_hunter_leads],
)