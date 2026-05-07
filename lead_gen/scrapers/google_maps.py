import re
import time
import requests
from lead_gen import config

API_URL = "https://api.scraperapi.com/structured/google/search"

DEMO_DATA = [
    {"name": "Sunrise Electric Co.",        "phone": "(954) 555-0201", "address": "100 Sunrise Blvd, Fort Lauderdale, FL 33304", "website": "www.sunriseelectric.com",  "category": "Electrician", "rating": "4.8", "reviews": "112", "years_in_business": "", "source": "Google Maps"},
    {"name": "Pro Power Electric LLC",       "phone": "(954) 555-0202", "address": "200 Federal Hwy, Pompano Beach, FL 33060",    "website": "www.propowerfl.com",     "category": "Electrician", "rating": "4.6", "reviews": "87",  "years_in_business": "", "source": "Google Maps"},
    {"name": "Elite Electrical Services",    "phone": "(954) 555-0203", "address": "300 Sample Rd, Coral Springs, FL 33065",      "website": "",                       "category": "Electrician", "rating": "4.4", "reviews": "54",  "years_in_business": "", "source": "Google Maps"},
    {"name": "Broward Master Electric",      "phone": "(954) 555-0204", "address": "400 University Dr, Tamarac, FL 33321",        "website": "www.browardmaster.com",  "category": "Electrician", "rating": "4.7", "reviews": "203", "years_in_business": "", "source": "Google Maps"},
    {"name": "Voltage Kings Electric",       "phone": "(954) 555-0205", "address": "500 Oakland Park Blvd, Oakland Park, FL 33334","website": "",                       "category": "Electrician", "rating": "4.2", "reviews": "31",  "years_in_business": "", "source": "Google Maps"},
]

_STRIP_WORDS = {
    "inc", "llc", "ltd", "corp", "co", "company", "group",
    "services", "service", "solutions", "and", "the",
}


def _normalize(name: str) -> str:
    name = name.lower()
    name = re.sub(r'[^\w\s]', ' ', name)
    return " ".join(w for w in name.split() if w not in _STRIP_WORDS).strip()


def _parse_place(place: dict, query: str) -> dict | None:
    name = (place.get("title") or place.get("name") or "").strip()
    if not name:
        return None
    rating  = place.get("rating", "")
    reviews = place.get("reviews", place.get("reviews_count", place.get("rating_count", "")))
    website = (
        place.get("website")
        or (place.get("links", {}).get("website", "") if isinstance(place.get("links"), dict) else "")
        or ""
    )
    return {
        "name":              name,
        "phone":             place.get("phone", place.get("phoneNumber", "")),
        "address":           place.get("address", place.get("full_address", "")),
        "website":           website,
        "category":          place.get("type", place.get("category", query)),
        "rating":            str(rating)  if rating  else "",
        "reviews":           str(reviews) if reviews else "",
        "years_in_business": "",
        "email":             "",
        "source":            "Google Maps",
    }


def _search_one(search_query: str, location: str) -> list[dict]:
    """Run a single Google structured search and return parsed leads."""
    full_query = f"{search_query} near {location}"
    try:
        resp = requests.get(
            API_URL,
            params={
                "api_key":      config.SCRAPERAPI_KEY,
                "query":        full_query,
                "country_code": "us",
                "num":          20,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [Google Maps] Error for '{search_query}': {e}")
        return []

    results: list[dict] = []
    for key in ("local_results", "organic_results", "results"):
        places = data.get(key, [])
        if not isinstance(places, list):
            continue
        for place in places:
            if not isinstance(place, dict):
                continue
            parsed = _parse_place(place, search_query)
            if parsed:
                results.append(parsed)
        if results:
            break
    return results


def scrape(
    query: str,
    location: str,
    max_results: int = 40,
    max_pages: int = 3,
    extra_queries: list[str] | None = None,
) -> list[dict]:
    """Scrape Google Maps using the primary query plus any AI-expanded queries."""
    if config.DEMO_MODE:
        print("  [Google Maps] Demo mode — returning sample data")
        return DEMO_DATA[:max_results]

    queries = [query]
    if extra_queries:
        # Add expanded queries, skipping duplicates of the primary
        for q in extra_queries:
            if q.lower() != query.lower():
                queries.append(q)

    all_leads: list[dict] = []
    seen_names: set[str] = set()  # deduplicate within this scraper

    for i, q in enumerate(queries):
        if len(all_leads) >= max_results:
            break
        if i > 0:
            time.sleep(0.5)  # small delay between queries
        batch = _search_one(q, location)
        added = 0
        for lead in batch:
            key = _normalize(lead["name"])
            if key and key not in seen_names:
                seen_names.add(key)
                all_leads.append(lead)
                added += 1
        if added:
            print(f"  [Google Maps] '{q}': +{added} leads (total: {len(all_leads)})")

    all_leads = all_leads[:max_results]
    print(f"  [Google Maps] Done — {len(all_leads)} leads from {len(queries)} queries")
    return all_leads
