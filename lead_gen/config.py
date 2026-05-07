import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "")

SEARCH = {
    "query":          "plumbers",
    "location":       "Fort Lauderdale, FL",
    "max_per_source": 40,
    "max_pages":      3,
}

SOURCES = {
    "google_maps":  True,   # primary source — always run first
    "yellow_pages": True,
    "yelp":         False,
    "bbb":          True,
    "angi":         True,
    "sunbiz":       False,
    "chamber":      False,
    "bni":          False,
}

CHAMBER_URLS = []
BNI_CHAPTER_URLS = []

DEMO_MODE = not bool(SCRAPERAPI_KEY)

OUTPUT_DIR = "outputs"
