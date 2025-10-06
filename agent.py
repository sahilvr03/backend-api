from agents import Agent
from agents.extensions.models.litellm_model import LitellmModel
from tools.tavily_tool import scrape_leads
from tools.hunteremail_tool import scrape_hunter_leads

# Gemini API key
GEMINI_API_KEY = "AIzaSyDyUverBS7o0HkMWlBVUKcOfi3xq1N1Nmk"

# Initialize Gemini model
model = LitellmModel(model="gemini/gemini-2.0-flash", api_key=GEMINI_API_KEY)

# Tavily Agent
tavily_agent = Agent(
    name="TavilyAgent",
    instructions=(
        "You are a verified business lead scraping agent. "
        "Use Tavily + Google Places ONLY. "
        "STRICT RULES:\n"
        "1. Collect only leads that have a VALID email address matching regex: "
        "   ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$ .\n"
        "2. Skip leads with NO email.\n"
        "3. Skip GENERIC emails (info@, contact@, support@, noreply@).\n"
        "4. NEVER invent or guess missing details.\n"
        "5. Phone numbers must be real; skip if missing.\n"
        "6. Always include source URL where the lead was found.\n\n"
        "[name, email, company, phone, source].\n"
        "Example:\n"
        "[{\"name\": \"John Doe\", \"email\": \"john@company.com\", \"company\": \"CompanyX\", \"phone\": \"+1-234-567-890\", \"source\": \"https://...\"}]\n"
        "If no valid results, return [] only."
    ),
    model=model,
    tools=[scrape_leads],
)

# Orchestrator Agent
lead_agent = Agent(
    name="LeadOrchestrator",
    instructions=(
        "You orchestrate lead scraping. "
        "Always delegate search to TavilyAgent. "
        "Only collect leads that pass strict email + phone validation rules. "
        "Reject any lead with fake, missing, or generic emails. "
        "If zero valid leads are found, return []."
    ),
    model=model,
    handoffs=[tavily_agent],
)

# Hunter.io Email Agent
email_agent = Agent(
    name="EmailAgent",
    instructions=(
        "You are an email-finding assistant. "
        "Your role is to fetch and return verified email addresses of business leads "
        "by using the Hunter.io API. "
        "You take a list of company domains (e.g. 'openai.com', 'microsoft.com') "
        "and return a structured list of leads with their emails, names (if available), "
        "and associated company. "
        "Use the 'scrape_hunter_leads' tool to perform the actual data fetching. "
        "Always return leads in a clean structured format without duplicates."
    ),
    model=model,
    tools=[scrape_hunter_leads],
)