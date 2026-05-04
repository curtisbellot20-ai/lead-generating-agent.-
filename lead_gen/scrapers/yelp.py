import time
import requests
from bs4 import BeautifulSoup
from lead_gen import config

BASE_URL = "https://www.yelp.com/search"
RESULTS_PER_PAGE = 10

DEMO_DATA = [
    {"name": "Fort Lauderdale Plumbing Inc.",  "phone": "(954) 555-0201", "address": "500 Las Olas Blvd, Fort Lauderdale, FL 33301",       "website": "www.ftlplumbing.com",          "category": "Plumbing", "rating": "4.5", "reviews": "112", "years_in_business": "",   "source": "Yelp"},
    {"name": "Coastal Plumbing & Rooter",      "phone": "(954) 555-0202", "address": "700 E Sunrise Blvd, Fort Lauderdale, FL 33304",      "website": "",                             "category": "Plumbing", "rating": "4.1", "reviews": "47",  "years_in_business": "",   "source": "Yelp"},
    {"name": "Tamarac Plumbing Pros",          "phone": "(954) 555-0203", "address": "6000 N University Dr, Tamarac, FL 33321",           "website": "www.tamaracplumbing.com",      "category": "Plumbing", "rating": "4.6", "reviews": "88",  "years_in_business": "",   "source": "Yelp"},
    {"name": "All-Star Plumbing Services",     "phone": "(954) 555-0204", "address": "3200 N Federal Hwy, Fort Lauderdale, FL 33306",    "website": "www.allstarplumbing.net",      "category": "Plumbing", "rating": "4.4", "reviews": "63",  "years_in_business": "",   "source": "Yelp"},
    {"name": "Broward County Plumbers",        "phone": "(954) 555-0205", "address": "1900 W Broward Blvd, Fort Lauderdale, FL 33312",   "website": "",                             "category": "Plumbing", "rating": "3.8", "reviews": "29",  "years_in_business": "",   "source": "Yelp"},
    {"name": "Sunrise Plumbing & HVAC",        "phone": "(954) 555-0206", "address": "10000 W Oakland Park Blvd, Sunrise, FL 33351",    "website": "www.sunriseplumbinghvac.com",  "category": "Plumbing", "rating": "4.7", "reviews": "95",  "years_in_business": "",   "source": "Yelp"},
    {"name": "Coral Springs Drain Experts",    "phone": "(954) 555-0207", "address": "3800 Coral Ridge Dr, Coral Springs, FL 33065",    "website": "",                             "category": "Plumbing", "rating": "4.2", "reviews": "38",  "years_in_business": "",   "source": "Yelp"},
    {"name": "Plantation Plumbing Co.",        "phone": "(954) 555-0208", "address": "400 N Pine Island Rd, Plantation, FL 33324",      "website": "www.plantationplumbing.com",   "category": "Plumbing", "rating": "4.5", "reviews": "71",  "years_in_business": "",   "source": "Yelp"},
    {"name": "Deerfield Beach Plumbing",       "phone": "(954) 555-0209", "address": "1200 S Military Trail, Deerfield Beach, FL 33442", "website": "www.deerfieldplumbing.com",    "category": "Plumbing", "rating": "4.3", "reviews": "52",  "years_in_business": "",   "source": "Yelp"},
    {"name": "Pompano Beach Plumbing Pros",    "phone": "(954) 555-0210", "address": "2100 N Federal Hwy, Pompano Beach, FL 33064",     "website": "www.pompanoplumbing.com",      "category": "Plumbing", "rating": "4.0", "reviews": "34",  "years_in_business": "",   "source": "Yelp"},
]


def _get_page(query: str, location: str, offset: int) -> str | None:
    target = (
        f"{BASE_URL}"
        f"?find_desc={requests.utils.quote(query)}"
        f"&find_loc={requests.utils.quote(location)}"
        f"&start={offset}"
    )
    proxy = (
        f"http://api.scraperapi.com/"
        f"?api_key={config.SCRAPERAPI_KEY}"
        f"&url={requests.utils.quote(target, safe=':/?=&')}"
        f"&render=true"
        f"&country_code=us"
    )
    try:
        resp = requests.get(proxy, timeout=60)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  [Yelp] Offset {offset} error: {e}")
        return None


def _parse_listings(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    leads = []

    # Yelp renders results in <li> blocks inside the main results container
    # We look for any block that contains a business name anchor
    containers = soup.select("li.css-1q2nwpv, li[class*='businessListItem'], [class*='mainAttributes']")
    if not containers:
        # Fallback: find all h3/h4 that look like business names
        containers = soup.select("[data-testid='serp-ia-card'], [class*='arrange-unit']")

    for block in containers:
        # Name — Yelp wraps business names in an anchor inside an h3/h4
        name_el = (
            block.select_one("h3 a, h4 a, [class*='businessName'] a, a[name]")
            or block.select_one("h3, h4")
        )
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        # Strip leading index numbers like "1. "
        if name and name[0].isdigit() and ". " in name[:4]:
            name = name.split(". ", 1)[1]
        if not name:
            continue

        # Phone
        phone_el = block.select_one("[class*='phone'], p.phone, [href^='tel:']")
        phone = ""
        if phone_el:
            phone = phone_el.get("href", "").replace("tel:", "") or phone_el.get_text(strip=True)

        # Address
        addr_el = block.select_one("address, [class*='secondaryAttributes'] p, [class*='address']")
        address = addr_el.get_text(strip=True) if addr_el else ""

        # Category
        cat_el = block.select_one("[class*='tag'], [class*='category'], span.tagLabel")
        category = cat_el.get_text(strip=True) if cat_el else ""

        # Rating — Yelp uses aria-label="X star rating" on the star graphic
        rating = ""
        rating_el = block.select_one("[aria-label*='star'], [class*='rating']")
        if rating_el:
            aria = rating_el.get("aria-label", "")
            rating = aria.replace(" star rating", "").strip() if aria else rating_el.get_text(strip=True)

        # Review count
        review_el = block.select_one("[class*='reviewCount'], span[class*='count']")
        reviews = review_el.get_text(strip=True).strip("()") if review_el else ""

        leads.append({
            "name": name,
            "phone": phone,
            "address": address,
            "website": "",  # Yelp hides direct website links on search results
            "category": category,
            "rating": rating,
            "reviews": reviews,
            "years_in_business": "",
            "source": "Yelp",
        })

    return leads


def scrape(query: str, location: str, max_results: int = 40, max_pages: int = 3) -> list[dict]:
    if config.DEMO_MODE:
        print("  [Yelp] Demo mode — returning sample data")
        return DEMO_DATA[:max_results]

    all_leads: list[dict] = []

    for page in range(max_pages):
        offset = page * RESULTS_PER_PAGE
        print(f"  [Yelp] Scraping page {page + 1}/{max_pages} (offset {offset})...")
        html = _get_page(query, location, offset)
        if not html:
            break

        leads = _parse_listings(html)
        if not leads:
            print(f"  [Yelp] No results on page {page + 1} — stopping")
            break

        all_leads.extend(leads)
        print(f"  [Yelp] Page {page + 1}: +{len(leads)} leads (total: {len(all_leads)})")

        if len(all_leads) >= max_results:
            break

        if page < max_pages - 1:
            time.sleep(2)  # Yelp is stricter — wait a bit between pages

    all_leads = all_leads[:max_results]
    print(f"  [Yelp] Done — {len(all_leads)} leads collected")
    return all_leads
