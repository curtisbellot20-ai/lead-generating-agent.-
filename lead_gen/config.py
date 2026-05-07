import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "")

SEARCH = {
    "query": "plumbers",
    "location": "Fort Lauderdale, FL",
    "max_per_source": 40,
    "max_pages": 3,
}

SOURCES = {
    "yellow_pages":  True,
    "yelp":          True,
    "google_maps":   False,
    "sunbiz":        False,
    "chamber":       False,
    "bni":           False,
}

CHAMBER_URLS = [
    # "https://members.ftlchamber.com/list",
]

BNI_CHAPTER_URLS = [
    # "https://www.bni.com/en-US/chapters/...",
]

DEMO_MODE = not bool(SCRAPERAPI_KEY)

OUTPUT_DIR = "outputs"
