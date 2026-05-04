import requests
from bs4 import BeautifulSoup
from lead_gen import config

DEMO_DATA = [
    {"name": "Fort Lauderdale Plumbing Inc.", "phone": "(954) 555-0201", "address": "500 Las Olas Blvd, Fort Lauderdale, FL 33301", "website": "www.ftlplumbing.com", "category": "Plumbing", "rating": "4.5", "source": "Yelp"},
    {"name": "Coastal Plumbing & Rooter", "phone": "(954) 555-0202", "address": "700 E Sunrise Blvd, Fort Lauderdale, FL 33304", "website": "", "category": "Plumbing", "rating": "4.1", "source": "Yelp"},
    {"name": "Tamarac Plumbing Pros", "phone": "(954) 555-0203", "address": "6000 N University Dr, Tamarac, FL 33321", "website": "www.tamaracplumbing.com", "category": "Plumbing", "rating": "4.6", "source": "Yelp"},
    {"name": "All-Star Plumbing Services", "phone": "(954) 555-0204", "address": "3200 N Federal Hwy, Fort Lauderdale, FL 33306", "website": "www.allstarplumbing.net", "category": "Plumbing", "rating": "4.4", "source": "Yelp"},
    {"name": "Broward County Plumbers", "phone": "(954) 555-0205", "address": "1900 W Broward Blvd, Fort Lauderdale, FL 33312", "website": "", "category": "Plumbing", "rating": "3.8", "source": "Yelp"},
    {"name": "Sunrise Plumbing & HVAC", "phone": "(954) 555-0206", "address": "10000 W Oakland Park Blvd, Sunrise, FL 33351", "website": "www.sunriseplumbinghvac.com", "category": "Plumbing", "rating": "4.7", "source": "Yelp"},
    {"name": "Coral Springs Drain Experts", "phone": "(954) 555-0207", "address": "3800 Coral Ridge Dr, Coral Springs, FL 33065", "website": "", "category": "Plumbing", "rating": "4.2", "source": "Yelp"},
    {"name": "Plantation Plumbing Co.", "phone": "(954) 555-0208", "address": "400 N Pine Island Rd, Plantation, FL 33324", "website": "www.plantationplumbing.com", "category": "Plumbing", "rating": "4.5", "source": "Yelp"},
]


def scrape(query: str, location: str, max_results: int = 25) -> list[dict]:
    if config.DEMO_MODE:
        print("  [Yelp] Demo mode — returning sample data")
        return DEMO_DATA[:max_results]

    leads = []
    query_slug = query.lower().replace(" ", "+")
    location_slug = location.replace(", ", ",+").replace(" ", "+")
    url = f"https://www.yelp.com/search?find_desc={query_slug}&find_loc={location_slug}"
    proxy_url = f"http://api.scraperapi.com/?api_key={config.SCRAPERAPI_KEY}&url={url}&render=true"

    try:
        resp = requests.get(proxy_url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for listing in soup.select("[class*='businessName']")[:max_results]:
            name = listing.get_text(strip=True)
            if not name:
                continue
            parent = listing.find_parent("li") or listing.find_parent("div")
            phone = ""
            address = ""
            rating = ""
            if parent:
                phone_el = parent.select_one("[class*='phone'], p.phone")
                addr_el = parent.select_one("address, [class*='secondaryAttributes']")
                rating_el = parent.select_one("[class*='rating'], [aria-label*='star']")
                phone = phone_el.get_text(strip=True) if phone_el else ""
                address = addr_el.get_text(strip=True) if addr_el else ""
                rating = rating_el.get("aria-label", "").replace(" star rating", "") if rating_el else ""

            leads.append({
                "name": name,
                "phone": phone,
                "address": address,
                "website": "",
                "category": query,
                "rating": rating,
                "source": "Yelp",
            })
    except Exception as e:
        print(f"  [Yelp] Error: {e}")

    print(f"  [Yelp] Found {len(leads)} leads")
    return leads
