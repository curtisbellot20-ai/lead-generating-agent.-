import requests
from bs4 import BeautifulSoup
from lead_gen import config

DEMO_DATA = [
    {"name": "Sunshine Plumbing Co.", "phone": "(954) 555-0101", "address": "123 Main St, Fort Lauderdale, FL 33301", "website": "www.sunshineplumbing.com", "category": "Plumbers", "rating": "4.5", "source": "Yellow Pages"},
    {"name": "A1 Plumbing Services", "phone": "(954) 555-0102", "address": "456 Broward Blvd, Fort Lauderdale, FL 33302", "website": "www.a1plumbing.com", "category": "Plumbers", "rating": "4.2", "source": "Yellow Pages"},
    {"name": "Premier Plumbing & Drain", "phone": "(954) 555-0103", "address": "789 Oakland Park Blvd, Fort Lauderdale, FL 33311", "website": "www.premierplumbingfl.com", "category": "Plumbers", "rating": "4.8", "source": "Yellow Pages"},
    {"name": "Quick Fix Plumbing", "phone": "(954) 555-0104", "address": "321 NW 9th Ave, Fort Lauderdale, FL 33311", "website": "", "category": "Plumbers", "rating": "3.9", "source": "Yellow Pages"},
    {"name": "South Florida Plumbing Experts", "phone": "(954) 555-0105", "address": "654 Sunrise Blvd, Fort Lauderdale, FL 33304", "website": "www.sfplumbingexperts.com", "category": "Plumbers", "rating": "4.6", "source": "Yellow Pages"},
    {"name": "Broward Pipe & Drain", "phone": "(954) 555-0106", "address": "111 Commercial Blvd, Fort Lauderdale, FL 33309", "website": "www.browardpipe.com", "category": "Plumbers", "rating": "4.3", "source": "Yellow Pages"},
    {"name": "24/7 Emergency Plumbing", "phone": "(954) 555-0107", "address": "222 State Rd 7, Fort Lauderdale, FL 33317", "website": "", "category": "Plumbers", "rating": "4.0", "source": "Yellow Pages"},
    {"name": "Green Plumbing Solutions", "phone": "(954) 555-0108", "address": "333 Federal Hwy, Fort Lauderdale, FL 33308", "website": "www.greenplumbingfl.com", "category": "Plumbers", "rating": "4.7", "source": "Yellow Pages"},
]


def scrape(query: str, location: str, max_results: int = 25) -> list[dict]:
    if config.DEMO_MODE:
        print("  [Yellow Pages] Demo mode — returning sample data")
        return DEMO_DATA[:max_results]

    leads = []
    query_slug = query.lower().replace(" ", "+")
    location_slug = location.replace(", ", "%2C+").replace(" ", "+")
    url = f"https://www.yellowpages.com/search?search_terms={query_slug}&geo_location_terms={location_slug}"
    proxy_url = f"http://api.scraperapi.com/?api_key={config.SCRAPERAPI_KEY}&url={url}&render=true"

    try:
        resp = requests.get(proxy_url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for listing in soup.select(".result")[:max_results]:
            name_el = listing.select_one(".business-name")
            if not name_el:
                continue
            phone_el = listing.select_one(".phones")
            addr_el = listing.select_one(".street-address")
            city_el = listing.select_one(".city")
            web_el = listing.select_one("a.track-visit-website")
            rating_el = listing.select_one(".ratings")
            cat_el = listing.select_one(".categories")

            address = ", ".join(
                filter(None, [
                    addr_el.get_text(strip=True) if addr_el else "",
                    city_el.get_text(strip=True) if city_el else "",
                ])
            )
            leads.append({
                "name": name_el.get_text(strip=True),
                "phone": phone_el.get_text(strip=True) if phone_el else "",
                "address": address,
                "website": web_el["href"] if web_el else "",
                "category": cat_el.get_text(strip=True) if cat_el else query,
                "rating": rating_el.get_text(strip=True) if rating_el else "",
                "source": "Yellow Pages",
            })
    except Exception as e:
        print(f"  [Yellow Pages] Error: {e}")

    print(f"  [Yellow Pages] Found {len(leads)} leads")
    return leads
