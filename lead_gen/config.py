import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "")

SEARCH = {
    "query": "plumbers",
    "location": "Fort Lauderdale, FL",
    "max_per_source": 25,
}

SOURCES = {
    "yellow_pages": True,
    "yelp": True,
    "chamber": True,
    "bni": True,
}

# Add your local Chamber of Commerce member directory URLs here
CHAMBER_URLS = [
    # "https://members.ftlchamber.com/list",
    # "https://business.bocaratonchamber.com/list",
    # "https://www.tamarac.org/298/Chamber-of-Commerce",
    # "https://www.coralspr ingschamber.com/list/",
]

# Add BNI chapter member page URLs here
BNI_CHAPTER_URLS = [
    # "https://www.bni.com/en-US/chapters/...",
]

# Automatically uses demo mode when no ScraperAPI key is set
DEMO_MODE = not bool(SCRAPERAPI_KEY)

OUTPUT_DIR = "outputs"
