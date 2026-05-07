import json
import re
import time
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from lead_gen import config

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

CATEGORY_MAP = {
    "plumbers":      "plumbing",
    "electricians":  "electricians",
    "roofers":       "roofing",
    "landscapers":   "landscaping",
    "painters":      "painting",
    "hvac":          "heating-cooling",
    "contractors":   "general-contractors",
    "cleaners":      "house-cleaning",
    "movers":        "moving",
    "handymen":      "handyman",
    "pest control":  "pest-control",
    "pool service":  "pool-cleaning",
    "plumbing":      "plumbing",
    "electrical":    "electricians",
    "electric":      "electricians",
    "roofing":       "roofing",
    "landscaping":   "landscaping",
    "painting":      "painting",
    "cleaning":      "house-cleaning",
    "handyman":      "handyman",
}

COUNTY_CITY_SLUG = {
    "broward":      "fort-lauderdale",
    "miami-dade":   "miami",
    "palm beach":   "west-palm-beach",
    "orange":       "orlando",
    "hillsborough": "tampa",
    "pinellas":     "clearwater",
    "duval":        "jacksonville",
    "seminole":     "sanford",
    "volusia":      "daytona-beach",
    "brevard":      "melbourne",
    "lee":          "fort-myers",
    "collier":      "naples",
    "sarasota":     "sarasota",
    "manatee":      "bradenton",
    "alachua":      "gainesville",
    "leon":         "tallahassee",
    "escambia":     "pensacola",
    "polk":         "lakeland",
    "marion":       "ocala",
    "osceola":      "kissimmee",
}

DEMO_DATA = [
    {"name": "FastFix Plumbing",       "phone": "(954) 555-0401", "address": "Fort Lauderdale, FL", "website": "",                     "category": "Plumbing",    "rating": "4.7", "reviews": "94",  "years_in_business": "", "source": "Angi"},
    {"name": "Bright Spark Electric",  "phone": "(954) 555-0402", "address": "Pompano Beach, FL",   "website": "www.brightspark.com",  "category": "Electrical",  "rating": "4.5", "reviews": "61",  "years_in_business": "", "source": "Angi"},
    {"name": "SoFlo Roofing Experts",  "phone": "(954) 555-0403", "address": "Coral Springs, FL",   "website": "",                     "category": "Roofing",     "rating": "4.8", "reviews": "130", "years_in_business": "", "source": "Angi"},
    {"name": "Green Cut Landscaping",  "phone": "(954) 555-0404", "address": "Sunrise, FL",          "website": "www.greencut.com",    "category": "Landscaping", "rating": "4.3", "reviews": "47",  "years_in_business": "", "source": "Angi"},
    {"name": "CoolAir HVAC Services",  "phone": "(954) 555-0405", "address": "Plantation, FL",       "website": "",                     "category": "HVAC",        "rating": "4.6", "reviews": "78",  "years_in_business": "", "source": "Angi"},
]


def _build_url(query: str, location: str) -> str:
    category = CATEGORY_MAP.get(query.lower().strip(), query.lower().replace(" ", "-"))
    loc = location.strip()

    # Zip code
    zip_match = re.match(r'^(\d{5})', loc)
    if zip_match:
        return f"https://www.angi.com/nearme/{category}/?zipCode={zip_match.group(1)}"

    # County
    if "county" in loc.lower():
        county = loc.lower().replace("county", "").replace(",", "").replace("fl", "").strip()
        city_slug = COUNTY_CITY_SLUG.get(county, county.replace(" ", "-"))
        return f"https://www.angi.com/companylist/us/fl/{city_slug}/{category}.htm"

    # City, State
    parts = loc.split(",")
    if len(parts) >= 2:
        city  = parts[0].strip().lower().replace(" ", "-").replace(".", "").replace("'", "")
        state = parts[1].strip().lower()[:2]
        return f"https://www.angi.com/companylist/us/{state}/{city}/{category}.htm"

    return f"https://www.angi.com/nearme/{category}/"


def _fetch(url: str) -> str:
    try:
        proxy = (
            f"http://api.scraperapi.com/"
            f"?api_key={config.SCRAPERAPI_KEY}"
            f"&url={quote(url, safe=':/?=&')}"
            f"&render=true"
        )
        resp = requests.get(proxy, headers=HEADERS, timeout=60)
        if resp.ok:
            return resp.text
    except Exception:
        pass
    return ""


def _next_data(html: str) -> dict:
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return {}


def _find_providers(data: dict) -> list:
    page = data.get("props", {}).get("pageProps", {})
    for key in ["providers", "companyList", "businesses", "results", "companies", "listings"]:
        val = page.get(key)
        if isinstance(val, list) and val:
            return val
        if isinstance(val, dict):
            for sub in ["results", "items", "data"]:
                if isinstance(val.get(sub), list) and val[sub]:
                    return val[sub]
    return []


def _parse_providers(providers: list, query: str) -> list[dict]:
    leads = []
    for p in providers:
        if not isinstance(p, dict):
            continue
        name = (p.get("businessName") or p.get("name") or
                p.get("companyName") or p.get("providerName", "")).strip()
        if not name:
            continue
        addr = p.get("address", p.get("city", ""))
        if isinstance(addr, dict):
            addr = ", ".join(filter(None, [addr.get("city", ""), addr.get("state", "")]))
        rating  = p.get("rating", p.get("starRating", p.get("overallRating", "")))
        reviews = p.get("reviewCount", p.get("numReviews", p.get("totalReviews", "")))
        leads.append({
            "name":              name,
            "phone":             p.get("phone", p.get("phoneNumber", "")),
            "address":           addr,
            "website":           p.get("website", p.get("websiteUrl", "")),
            "category":          p.get("category", p.get("serviceCategory", query)),
            "rating":            str(rating) if rating else "",
            "reviews":           str(reviews) if reviews else "",
            "years_in_business": "",
            "email":             "",
            "source":            "Angi",
        })
    return leads


def _parse_html(html: str, query: str) -> list[dict]:
    soup  = BeautifulSoup(html, "lxml")
    leads = []
    cards = (
        soup.select("[class*='companyCard']") or
        soup.select("[class*='provider']") or
        soup.select("[class*='ProviderCard']") or
        soup.select("article")
    )
    for card in cards:
        name_el = card.select_one("h2, h3, [class*='name'], [class*='title']")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name or len(name) < 2:
            continue
        rating_el = card.select_one("[class*='rating'], [class*='star']")
        phone_el  = card.select_one("[href^='tel:']")
        leads.append({
            "name":              name,
            "phone":             phone_el.get("href", "").replace("tel:", "") if phone_el else "",
            "address":           "",
            "website":           "",
            "category":          query,
            "rating":            rating_el.get_text(strip=True) if rating_el else "",
            "reviews":           "",
            "years_in_business": "",
            "email":             "",
            "source":            "Angi",
        })
    return leads


def scrape(query: str, location: str, max_results: int = 40, max_pages: int = 3) -> list[dict]:
    if config.DEMO_MODE:
        print("  [Angi] Demo mode — returning sample data")
        return DEMO_DATA[:max_results]

    url = _build_url(query, location)
    print(f"  [Angi] Fetching: {url}")

    html = _fetch(url)
    if not html:
        print("  [Angi] Failed to fetch page")
        return []

    data      = _next_data(html)
    providers = _find_providers(data)
    leads     = _parse_providers(providers, query) if providers else _parse_html(html, query)

    print(f"  [Angi] Done — {len(leads)} leads collected")
    return leads[:max_results]
