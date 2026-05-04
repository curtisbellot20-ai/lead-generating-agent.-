import requests
from bs4 import BeautifulSoup
from lead_gen import config

DEMO_DATA = [
    {"name": "Broward Builders LLC", "phone": "(954) 555-0401", "address": "2500 N Andrews Ave, Wilton Manors, FL 33311", "website": "www.browardbuilders.com", "category": "Construction", "rating": "", "source": "BNI"},
    {"name": "Laser Focused Marketing", "phone": "(954) 555-0402", "address": "3400 Hillsboro Blvd, Deerfield Beach, FL 33442", "website": "www.laserfocusedmktg.com", "category": "Marketing", "rating": "", "source": "BNI"},
    {"name": "South FL Tech Solutions", "phone": "(954) 555-0403", "address": "1000 Corporate Dr, Fort Lauderdale, FL 33334", "website": "www.sfltech.io", "category": "IT Services", "rating": "", "source": "BNI"},
    {"name": "Wealth Management Partners", "phone": "(954) 555-0404", "address": "500 E Las Olas Blvd Ste 900, Fort Lauderdale, FL 33301", "website": "www.wmpfl.com", "category": "Financial Services", "rating": "", "source": "BNI"},
    {"name": "First Class Staffing", "phone": "(954) 555-0405", "address": "6750 N Andrews Ave, Fort Lauderdale, FL 33309", "website": "www.firstclassstaffing.com", "category": "Staffing", "rating": "", "source": "BNI"},
    {"name": "Doral Print & Design", "phone": "(954) 555-0406", "address": "4200 N State Rd 7, Lauderdale Lakes, FL 33319", "website": "www.doralprint.com", "category": "Printing", "rating": "", "source": "BNI"},
]


def _scrape_url(url: str, max_results: int) -> list[dict]:
    leads = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; LeadGenBot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        cards = (
            soup.select(".member-card")
            or soup.select(".member-profile")
            or soup.select(".chapter-member")
            or soup.select("[class*='member']")
        )

        for card in cards[:max_results]:
            name_el = card.select_one("h2, h3, .name, .member-name, strong")
            phone_el = card.select_one(".phone, [href^='tel:']")
            web_el = card.select_one("a[href^='http']")
            cat_el = card.select_one(".category, .profession, .specialty, [class*='category']")

            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue

            phone = ""
            if phone_el:
                phone = phone_el.get("href", "").replace("tel:", "") or phone_el.get_text(strip=True)

            leads.append({
                "name": name,
                "phone": phone,
                "address": "",
                "website": web_el["href"] if web_el else "",
                "category": cat_el.get_text(strip=True) if cat_el else "BNI Member",
                "rating": "",
                "source": "BNI",
            })
    except Exception as e:
        print(f"  [BNI] Error scraping {url}: {e}")

    return leads


def scrape(urls: list[str], max_results: int = 25) -> list[dict]:
    if not urls:
        if config.DEMO_MODE:
            print("  [BNI] No URLs configured — returning demo data")
            return DEMO_DATA[:max_results]
        print("  [BNI] No URLs configured — skipping (add URLs to BNI_CHAPTER_URLS in config.py)")
        return []

    all_leads = []
    for url in urls:
        print(f"  [BNI] Scraping {url}")
        leads = _scrape_url(url, max_results)
        all_leads.extend(leads)
        if len(all_leads) >= max_results:
            break

    print(f"  [BNI] Found {len(all_leads)} leads")
    return all_leads[:max_results]
