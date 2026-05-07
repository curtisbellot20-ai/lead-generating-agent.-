import requests
from lead_gen import config

API_URL = "https://api.scraperapi.com/structured/google/maps"

DEMO_DATA = [
    {"name": "Sunrise Electric Co.",        "phone": "(954) 555-0201", "address": "100 Sunrise Blvd, Fort Lauderdale, FL 33304", "website": "www.sunriseelectric.com",  "category": "Electrician", "rating": "4.8", "reviews": "112", "years_in_business": "", "source": "Google Maps"},
    {"name": "Pro Power Electric LLC",       "phone": "(954) 555-0202", "address": "200 Federal Hwy, Pompano Beach, FL 33060",    "website": "www.propowerfl.com",     "category": "Electrician", "rating": "4.6", "reviews": "87",  "years_in_business": "", "source": "Google Maps"},
    {"name": "Elite Electrical Services",    "phone": "(954) 555-0203", "address": "300 Sample Rd, Coral Springs, FL 33065",      "website": "",                       "category": "Electrician", "rating": "4.4", "reviews": "54",  "years_in_business": "", "source": "Google Maps"},
    {"name": "Broward Master Electric",      "phone": "(954) 555-0204", "address": "400 University Dr, Tamarac, FL 33321",        "website": "www.browardmaster.com",  "category": "Electrician", "rating": "4.7", "reviews": "203", "years_in_business": "", "source": "Google Maps"},
    {"name": "Voltage Kings Electric",       "phone": "(954) 555-0205", "address": "500 Oakland Park Blvd, Oakland Park, FL 33334","website": "",                       "category": "Electrician", "rating": "4.2", "reviews": "31",  "years_in_business": "", "source": "Google Maps"},
]


def scrape(query: str, location: str, max_results: int = 40, max_pages: int = 3) -> list[dict]:
    if config.DEMO_MODE:
        print("  [Google Maps] Demo mode — returning sample data")
        return DEMO_DATA[:max_results]

    all_leads: list[dict] = []
    search_query = f"{query} near {location}"

    try:
        resp = requests.get(
            API_URL,
            params={
                "api_key": config.SCRAPERAPI_KEY,
                "query":   search_query,
                "country": "us",
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [Google Maps] Error: {e}")
        return []

    places = data if isinstance(data, list) else data.get("results", data.get("local_results", []))

    for place in places:
        if not isinstance(place, dict):
            continue

        name = place.get("name", "").strip()
        if not name:
            continue

        rating  = place.get("rating", "")
        reviews = place.get("reviews", place.get("reviews_count", ""))

        all_leads.append({
            "name":              name,
            "phone":             place.get("phone", ""),
            "address":           place.get("address", ""),
            "website":           place.get("website", ""),
            "category":          place.get("type", query),
            "rating":            str(rating) if rating else "",
            "reviews":           str(reviews) if reviews else "",
            "years_in_business": "",
            "email":             "",
            "source":            "Google Maps",
        })

        if len(all_leads) >= max_results:
            break

    print(f"  [Google Maps] Done — {len(all_leads)} leads collected")
    return all_leads
