import requests
from bs4 import BeautifulSoup
from lead_gen import config

DEMO_DATA = [
    {"name": "Broward Business Consulting", "phone": "(954) 555-0301", "address": "100 E Broward Blvd Ste 1200, Fort Lauderdale, FL 33301", "website": "www.browardbiz.com", "category": "Business Consulting", "rating": "", "source": "Chamber of Commerce"},
    {"name": "FTL Marketing Group", "phone": "(954) 555-0302", "address": "200 SE 1st St, Fort Lauderdale, FL 33301", "website": "www.ftlmarketing.com", "category": "Marketing", "rating": "", "source": "Chamber of Commerce"},
    {"name": "Tamarac Insurance Agency", "phone": "(954) 555-0303", "address": "7525 N University Dr, Tamarac, FL 33321", "website": "www.tamaracinsurance.com", "category": "Insurance", "rating": "", "source": "Chamber of Commerce"},
    {"name": "Coral Springs Realty", "phone": "(954) 555-0304", "address": "9721 W Sample Rd, Coral Springs, FL 33065", "website": "www.csrealty.com", "category": "Real Estate", "rating": "", "source": "Chamber of Commerce"},
    {"name": "Sunrise Accounting Services", "phone": "(954) 555-0305", "address": "1600 N University Dr, Sunrise, FL 33322", "website": "www.sunriseaccounting.com", "category": "Accounting", "rating": "", "source": "Chamber of Commerce"},
    {"name": "Plantation Financial Advisors", "phone": "(954) 555-0306", "address": "8000 W Broward Blvd, Plantation, FL 33324", "website": "www.plantationfinancial.com", "category": "Financial Services", "rating": "", "source": "Chamber of Commerce"},
]


def _scrape_url(url: str, max_results: int) -> list[dict]:
    leads = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; LeadGenBot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Generic selectors that work across most chamber directory themes
        cards = (
            soup.select(".member-listing")
            or soup.select(".business-card")
            or soup.select(".directory-item")
            or soup.select("[class*='member']")[:max_results]
        )

        for card in cards[:max_results]:
            name_el = card.select_one("h2, h3, .business-name, .member-name, strong")
            phone_el = card.select_one(".phone, [href^='tel:'], [class*='phone']")
            addr_el = card.select_one(".address, [class*='address'], address")
            web_el = card.select_one("a[href^='http']:not([href*='chamber'])")
            cat_el = card.select_one(".category, [class*='category'], .tag")

            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue

            phone = ""
            if phone_el:
                phone = phone_el.get("href", "").replace("tel:", "") or phone_el.get_text(strip=True)

            leads.append({
                "name": name,
                "phone": phone,
                "address": addr_el.get_text(strip=True) if addr_el else "",
                "website": web_el["href"] if web_el else "",
                "category": cat_el.get_text(strip=True) if cat_el else "Chamber Member",
                "rating": "",
                "source": "Chamber of Commerce",
            })
    except Exception as e:
        print(f"  [Chamber] Error scraping {url}: {e}")

    return leads


def scrape(urls: list[str], max_results: int = 25) -> list[dict]:
    if not urls:
        if config.DEMO_MODE:
            print("  [Chamber] No URLs configured — returning demo data")
            return DEMO_DATA[:max_results]
        print("  [Chamber] No URLs configured — skipping (add URLs to CHAMBER_URLS in config.py)")
        return []

    all_leads = []
    for url in urls:
        print(f"  [Chamber] Scraping {url}")
        leads = _scrape_url(url, max_results)
        all_leads.extend(leads)
        if len(all_leads) >= max_results:
            break

    print(f"  [Chamber] Found {len(all_leads)} leads")
    return all_leads[:max_results]
