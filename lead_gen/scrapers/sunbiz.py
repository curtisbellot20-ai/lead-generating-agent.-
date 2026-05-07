import time
from datetime import datetime
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from lead_gen import config

SEARCH_URL = "https://search.sunbiz.org/Inquiry/CorporationSearch/ByName"
DETAIL_BASE = "https://search.sunbiz.org"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

DEMO_DATA = [
    {"name": "SUNSHINE ELECTRICAL SERVICES LLC",  "phone": "", "address": "123 NW 5th Ave, Fort Lauderdale, FL 33311", "website": "", "category": "Electricians", "owner_name": "James Rivera",  "years_in_business": "6",  "source": "SunBiz", "rating": "", "reviews": ""},
    {"name": "BROWARD ELECTRIC INC",               "phone": "", "address": "456 Sunrise Blvd, Fort Lauderdale, FL 33304", "website": "", "category": "Electricians", "owner_name": "Maria Santos", "years_in_business": "11", "source": "SunBiz", "rating": "", "reviews": ""},
    {"name": "POWER UP ELECTRICAL SOLUTIONS LLC",  "phone": "", "address": "789 Federal Hwy, Pompano Beach, FL 33060",   "website": "", "category": "Electricians", "owner_name": "Owner",        "years_in_business": "3",  "source": "SunBiz", "rating": "", "reviews": ""},
    {"name": "SOUTH FLORIDA WIRING PROS LLC",      "phone": "", "address": "321 Sample Rd, Coral Springs, FL 33065",    "website": "", "category": "Electricians", "owner_name": "David Chen",   "years_in_business": "8",  "source": "SunBiz", "rating": "", "reviews": ""},
    {"name": "VOLTEX ELECTRICAL CONTRACTORS INC",  "phone": "", "address": "654 University Dr, Tamarac, FL 33321",      "website": "", "category": "Electricians", "owner_name": "Owner",        "years_in_business": "14", "source": "SunBiz", "rating": "", "reviews": ""},
]


def _scraper_url(target: str) -> str:
    if config.SCRAPERAPI_KEY:
        return (
            f"http://api.scraperapi.com/"
            f"?api_key={config.SCRAPERAPI_KEY}"
            f"&url={quote(target, safe=':/?=&')}"
            f"&render=true"
        )
    return target


def _fetch(url: str) -> str:
    try:
        resp = requests.get(_scraper_url(url), headers=HEADERS, timeout=45)
        if resp.ok:
            return resp.text
    except Exception:
        pass
    return ""


def _years_from_date(date_str: str) -> str:
    """Convert 'MM/DD/YYYY' filing date to years in business."""
    try:
        filed = datetime.strptime(date_str.strip(), "%m/%d/%Y")
        years = (datetime.now() - filed).days // 365
        return str(years) if years >= 0 else ""
    except Exception:
        return ""


def _parse_detail(path: str) -> dict:
    url = DETAIL_BASE + path
    html = _fetch(url)
    if not html:
        return {}

    soup = BeautifulSoup(html, "lxml")
    data = {"address": "", "owner_name": "Owner"}

    # Each section is a <div class="detailSection">
    for section in soup.select(".detailSection"):
        label_el = section.select_one(".label")
        if not label_el:
            continue
        label = label_el.get_text(strip=True).upper()

        if "PRINCIPAL ADDRESS" in label:
            parts = [s.get_text(" ", strip=True) for s in section.select("span") if s.get_text(strip=True)]
            parts = [p for p in parts if p and "Principal" not in p]
            data["address"] = ", ".join(parts)

        elif "REGISTERED AGENT" in label:
            name_el = section.select_one(".registered-agent-name span, span")
            if name_el:
                name = name_el.get_text(strip=True)
                if name and name.upper() not in ("REGISTERED AGENT NAME & ADDRESS", ""):
                    data["owner_name"] = name.title()

        elif "OFFICER" in label or "AUTHORIZED" in label:
            name_el = section.select_one("span")
            if name_el and not data.get("owner_name") or data.get("owner_name") == "Owner":
                name = name_el.get_text(strip=True)
                if name:
                    data["owner_name"] = name.title()

    return data


def _parse_results(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    leads = []

    table = soup.find("table", {"id": "search-results"})
    if not table:
        # fallback: try any table with the right columns
        table = soup.find("table")
    if not table:
        return leads

    for row in table.select("tr")[1:]:  # skip header row
        cols = row.find_all("td")
        if len(cols) < 4:
            continue

        name_el = cols[0].find("a")
        if not name_el:
            continue

        name = name_el.get_text(strip=True)
        link = name_el.get("href", "")
        doc_num = cols[1].get_text(strip=True) if len(cols) > 1 else ""
        date_filed = cols[3].get_text(strip=True) if len(cols) > 3 else ""
        status = cols[5].get_text(strip=True).upper() if len(cols) > 5 else ""

        if status and status != "ACTIVE":
            continue

        leads.append({
            "name": name,
            "doc_number": doc_num,
            "detail_path": link,
            "years_in_business": _years_from_date(date_filed),
            "phone": "",
            "email": "",
            "website": "",
            "address": "",
            "category": "",
            "rating": "",
            "reviews": "",
            "owner_name": "Owner",
            "source": "SunBiz",
        })

    return leads


def scrape(query: str, location: str, max_results: int = 40, max_pages: int = 3) -> list[dict]:
    if config.DEMO_MODE:
        print("  [SunBiz] Demo mode — returning sample data")
        return DEMO_DATA[:max_results]

    all_leads: list[dict] = []
    per_page = 20

    for page in range(max_pages):
        offset = page * per_page
        url = (
            f"{SEARCH_URL}"
            f"?SearchTerm={quote(query)}"
            f"&SearchType=EntityName"
            f"&SearchNameOrder=CONTAINS"
            f"&ActiveCorporationsOnly=Y"
            f"&State=FL"
            f"&offset={offset}"
        )

        print(f"  [SunBiz] Scraping page {page + 1}/{max_pages}...")
        html = _fetch(url)
        if not html:
            print(f"  [SunBiz] Page {page + 1} fetch failed — stopping")
            break

        rows = _parse_results(html)
        if not rows:
            print(f"  [SunBiz] No results on page {page + 1} — stopping")
            break

        for lead in rows:
            detail = _parse_detail(lead.pop("detail_path", ""))
            lead.update(detail)
            lead["category"] = query
            all_leads.append(lead)
            time.sleep(0.5)

            if len(all_leads) >= max_results:
                break

        print(f"  [SunBiz] Page {page + 1}: +{len(rows)} leads (total: {len(all_leads)})")

        if len(all_leads) >= max_results:
            break

        time.sleep(1.5)

    print(f"  [SunBiz] Done — {len(all_leads)} leads collected")
    return all_leads
