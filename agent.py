from agents import Agent
from agents.extensions.models.litellm_model import LitellmModel
from tools.tavily_tool import scrape_leads

# Direct Gemini API Key
GEMINI_API_KEY = "AIzaSyB0GHfF2Nm5gxBb-rrlX_g-h7FMLZAyPdQ"

# Initialize model
model = LitellmModel(model="gemini/gemini-2.0-flash", api_key=GEMINI_API_KEY)

# Tavily Agent
tavily_agent = Agent(
    name="TavilyAgent",
    instructions="You scrape general business leads from the Tavily API.",
    model=model,
    tools=[scrape_leads]
)

# Orchestrator Agent (simplified to always use Tavily)
lead_agent = Agent(
    name="LeadOrchestrator",
    instructions="Always use TavilyAgent to search for general business leads.",
    model=model,
    handoffs=[tavily_agent],
)
