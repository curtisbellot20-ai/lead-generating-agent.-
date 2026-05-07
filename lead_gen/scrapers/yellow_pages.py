import time
import requests
from bs4 import BeautifulSoup
from lead_gen import config

BASE_URL = "https://www.yellowpages.com/search"

DEMO_DATA = [
    {"name": "Sunshine Plumbing Co.",        "phone": "(954) 555-0101", "address": "123 Main St, Fort Lauderdale, FL 33301",          "website": "www.sunshineplumbing.com",    "category": "Plumbers", "rating": "4.5", "reviews": "38",  "years_in_business": "12", "source": "Yellow Pages"},
    {"name": "A1 Plumbing Services",          "phone": "(954) 555-0102", "address": "456 Broward Blvd, Fort Lauderdale, FL 33302",      "website": "www.a1plumbing.com",        "category": "Plumbers", "rating": "4.2", "reviews": "21",  "years_in_business": "8",  "source": "Yellow Pages"},
    {"name": "Premier Plumbing & Drain",       "phone": "(954) 555-0103", "address": "789 Oakland Park Blvd, Fort Lauderdale, FL 33311", "website": "www.premierplumbingfl.com",  "category": "Plumbers", "rating": "4.8", "reviews": "74",  "years_in_business": "20", "source": "Yellow Pages"},
    {"name": "Quick Fix Plumbing",             "phone": "(954) 555-0104", "address": "321 NW 9th Ave, Fort Lauderdale, FL 33311",        "website": "",                         "category": "Plumbers", "rating": "3.9", "reviews": "12",  "years_in_business": "",   "source": "Yellow Pages"},
    {"name": "South Florida Plumbing Experts", "phone": "(954) 555-0105", "address": "654 Sunrise Blvd, Fort Lauderdale, FL 33304",       "website": "www.sfplumbingexperts.com", "category": "Plumbers", "rating": "4.6", "reviews": "55",  "years_in_business": "15", "source": "Yellow Pages"},
    {"name": "Broward Pipe & Drain",           "phone": "(954) 555-0106", "address": "111 Commercial Blvd, Fort Lauderdale, FL 33309",   "website": "www.browardpipe.com",      "category": "Plumbers", "rating": "4.3", "reviews": "29",  "years_in_business": "10", "source": "Yellow Pages"},
    {"name": "24/7 Emergency Plumbing",        "phone": "(954) 555-0107", "address": "222 State Rd 7, Fort Lauderdale, FL 33317",         "website": "",                         "category": "Plumbers", "rating": "4.0", "reviews": "17",  "years_in_business": "",   "source": "Yellow Pages"},
    {"name": "Green Plumbing Solutions",       "phone": "(954) 555-0108", "address": "333 Federal Hwy, Fort Lauderdale, FL 33308",        "website": "www.greenplumbingfl.com",  "category": "Plumbers", "rating": "4.7", "reviews": "61",  "years_in_business": "18", "source": "Yellow Pages"},
    {"name": "Tamarac Plumbing LLC",           "phone": "(954) 555-0109", "address": "6100 N University Dr, Tamarac, FL 33321",           "website": "www.tamaracplumbing.net",  "category": "Plumbers", "rating": "4.4", "reviews": "33",  "years_in_business": "9",  "source": "Yellow Pages"},
    {"name": "Coral Springs Plumbing",         "phone": "(954) 555-0110", "address": "9800 W Sample Rd, Coral Springs, FL 33065",         "website": "www.csplumbing.com",       "category": "Plumbers", "rating": "4.5", "reviews": "44",  "years_in_business": "14", "source": "Yellow Pages"},
]


def _get_page(query: str, location: str, page: int) -> str | None:
    params = {
        "search_terms": query,
        "geo_location_terms": location,
        "page": page,
    }
    param_str = "&".join(f"{k}={str(v).replace(' ', '+')}" for k, v in params.items())
    target = f"{BASE_URL}?{param_str}"
    proxy = (
        f"http://api.scraperapi.com/"
        f"?api_key={config.SCRAPERAPI_KEY}"
        f"&url={requests.utils.quote(target, safe=':/?=&')}"
        f"&render=true"
    )
    try:
        resp = requests.get(proxy, timeout=90)   # 90s — YP pages can be slow
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  [Yellow Pages] Page {page} error: {e}")
        return None


def _parse_listings(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    leads = []

    for listing in soup.select(".result, .organic, [class*='result']"):
        if listing.select_one(".sponsored-label, .ad-label"):
            continue

        name_el   = listing.select_one(".business-name span, .business-name, h2 a")
        phone_el  = listing.select_one(".phones.phone.primary, .phones")
        addr_el   = listing.select_one(".street-address")
        city_el   = listing.select_one(".city")
        web_el    = listing.select_one("a.track-visit-website, a[href*='yellowpages.com/url']")
        rating_el = listing.select_one(".ratings .count, [class*='rating']")
        review_el = listing.select_one(".rating-count, .count")
        years_el  = listing.select_one(".years-in-business .count, [class*='years']")
        cat_el    = listing.select_one(".categories a, .categories")

        name = name_el.get_text(strip=True) if name_el else ""
        if not name:
            continue

        address = ", ".join(filter(None, [
            addr_el.get_text(strip=True) if addr_el else "",
            city_el.get_text(strip=True) if city_el else "",
        ]))

        website = ""
        if web_el:
            href = web_el.get("href", "")
            website = href if href.startswith("http") else ""

        leads.append({
            "name":             name,
            "phone":            phone_el.get_text(strip=True) if phone_el else "",
            "address":          address,
            "website":          website,
            "category":         cat_el.get_text(strip=True) if cat_el else "",
            "rating":           rating_el.get_text(strip=True) if rating_el else "",
            "reviews":          review_el.get_text(strip=True).strip("()") if review_el else "",
            "years_in_business": years_el.get_text(strip=True) if years_el else "",
            "source":           "Yellow Pages",
        })

    return leads


def scrape(query: str, location: str, max_results: int = 40, max_pages: int = 3) -> list[dict]:
    if config.DEMO_MODE:
        print("  [Yellow Pages] Demo mode — returning sample data")
        return DEMO_DATA[:max_results]

    all_leads: list[dict] = []

    for page in range(1, max_pages + 1):
        print(f"  [Yellow Pages] Scraping page {page}/{max_pages}...")
        html = _get_page(query, location, page)
        if not html:
            break

        leads = _parse_listings(html)
        if not leads:
            print(f"  [Yellow Pages] No results on page {page} — stopping")
            break

        all_leads.extend(leads)
        print(f"  [Yellow Pages] Page {page}: +{len(leads)} leads (total: {len(all_leads)})")

        if len(all_leads) >= max_results:
            break

        if page < max_pages:
            time.sleep(1.5)

    all_leads = all_leads[:max_results]
    print(f"  [Yellow Pages] Done — {len(all_leads)} leads collected")
    return all_leads
