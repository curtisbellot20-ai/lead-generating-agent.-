import json
import re
import time
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from lead_gen import config

SEARCH_URL = "https://www.bbb.org/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

DEMO_DATA = [
    {"name": "AAA Plumbing Solutions",     "phone": "(954) 555-0301", "address": "100 NW 1st Ave, Fort Lauderdale, FL 33301", "website": "www.aaaplumbing.com",  "category": "Plumbing", "rating": "A+", "reviews": "", "years_in_business": "15", "source": "BBB"},
    {"name": "Reliable Electric Inc.",      "phone": "(954) 555-0302", "address": "200 Broward Blvd, Fort Lauderdale, FL 33301", "website": "",                  "category": "Electricians", "rating": "A",  "reviews": "", "years_in_business": "9",  "source": "BBB"},
    {"name": "Top Notch Roofing LLC",       "phone": "(954) 555-0303", "address": "300 Commercial Blvd, Lauderdale, FL 33309", "website": "www.topnotchroof.com","category": "Roofing",      "rating": "A+", "reviews": "", "years_in_business": "7",  "source": "BBB"},
    {"name": "Green Lawn Landscaping",      "phone": "(954) 555-0304", "address": "400 University Dr, Tamarac, FL 33321",      "website": "",                  "category": "Landscaping",  "rating": "B+", "reviews": "", "years_in_business": "4",  "source": "BBB"},
    {"name": "Premier HVAC Services",       "phone": "(954) 555-0305", "address": "500 Sample Rd, Coral Springs, FL 33065",    "website": "www.premierhvac.com", "category": "HVAC",         "rating": "A",  "reviews": "", "years_in_business": "12", "source": "BBB"},
]


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
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html, re.DOTALL
    )
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return {}


def _year_to_years(year_str: str) -> str:
    try:
        return str(datetime.now().year - int(year_str))
    except Exception:
        return ""


def _parse_json(data: dict) -> list[dict]:
    from datetime import datetime
    page_props = data.get("props", {}).get("pageProps", {})
    results = (
        page_props.get("searchResults", {}).get("results") or
        page_props.get("results") or
        page_props.get("businesses") or
        []
    )
    leads = []
    for r in results:
        if not isinstance(r, dict):
            continue
        name = r.get("businessName") or r.get("name", "")
        if not name:
            continue
        addr = r.get("primaryAddress", {})
        if isinstance(addr, dict):
            address = ", ".join(filter(None, [
                addr.get("street", ""),
                addr.get("city", ""),
                addr.get("stateProvince", ""),
                addr.get("postalCode", ""),
            ]))
        else:
            address = str(addr)
        year = str(r.get("yearStarted", r.get("yearFounded", "")))
        years = ""
        try:
            if year.isdigit():
                years = str(datetime.now().year - int(year))
        except Exception:
            pass
        leads.append({
            "name":              name,
            "phone":             r.get("phone", r.get("primaryPhone", "")),
            "address":           address,
            "website":           r.get("websiteUrl", r.get("website", "")),
            "category":          r.get("primaryCategory", r.get("category", "")),
            "rating":            r.get("ratingText", r.get("rating", "")),
            "reviews":           "",
            "years_in_business": years,
            "email":             "",
            "source":            "BBB",
        })
    return leads


def _parse_html(html: str) -> list[dict]:
    soup  = BeautifulSoup(html, "lxml")
    leads = []
    cards = (
        soup.select("[class*='result-card']") or
        soup.select("[class*='ResultCard']") or
        soup.select("[class*='SearchResultCard']") or
        soup.select("article")
    )
    for card in cards:
        name_el = card.select_one("h3, h2, [class*='businessName'], [class*='BusinessName']")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name or len(name) < 2:
            continue
        phone_el  = card.select_one("[href^='tel:'], [class*='phone']")
        addr_el   = card.select_one("[class*='address'], [class*='Address']")
        rating_el = card.select_one("[class*='rating'], [class*='Rating'], [class*='grade']")
        leads.append({
            "name":              name,
            "phone":             phone_el.get_text(strip=True) if phone_el else "",
            "address":           addr_el.get_text(strip=True) if addr_el else "",
            "website":           "",
            "category":          "",
            "rating":            rating_el.get_text(strip=True) if rating_el else "",
            "reviews":           "",
            "years_in_business": "",
            "email":             "",
            "source":            "BBB",
        })
    return leads


def scrape(query: str, location: str, max_results: int = 40, max_pages: int = 3) -> list[dict]:
    if config.DEMO_MODE:
        print("  [BBB] Demo mode — returning sample data")
        return DEMO_DATA[:max_results]

    all_leads: list[dict] = []

    for page in range(1, max_pages + 1):
        url = (
            f"{SEARCH_URL}"
            f"?find_country=USA"
            f"&find_text={quote(query)}"
            f"&find_loc={quote(location)}"
            f"&page={page}"
        )
        print(f"  [BBB] Scraping page {page}/{max_pages}...")
        html = _fetch(url)
        if not html:
            break

        data  = _next_data(html)
        leads = _parse_json(data) if data else []
        if not leads:
            leads = _parse_html(html)
        if not leads:
            print(f"  [BBB] No results on page {page} — stopping")
            break

        all_leads.extend(leads)
        print(f"  [BBB] Page {page}: +{len(leads)} leads (total: {len(all_leads)})")

        if len(all_leads) >= max_results:
            break
        time.sleep(1.5)

    print(f"  [BBB] Done — {len(all_leads)} leads collected")
    return all_leads[:max_results]
