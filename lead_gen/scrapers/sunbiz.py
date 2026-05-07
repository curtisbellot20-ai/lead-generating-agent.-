import re
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

# Florida county → cities mapping for county-based filtering
FL_COUNTY_CITIES = {
    "broward":      ["fort lauderdale", "hollywood", "pompano beach", "miramar", "coral springs", "pembroke pines", "sunrise", "plantation", "davie", "deerfield beach", "tamarac", "north lauderdale", "margate", "coconut creek", "lauderhill", "weston", "hallandale beach", "oakland park", "wilton manors", "dania beach", "cooper city", "lighthouse point", "lauderdale lakes", "parkland"],
    "miami-dade":   ["miami", "hialeah", "miami gardens", "homestead", "miami beach", "north miami", "coral gables", "doral", "north miami beach", "aventura", "miami lakes", "cutler bay", "opa-locka", "florida city", "south miami", "sweetwater", "medley"],
    "palm beach":   ["west palm beach", "boca raton", "delray beach", "boynton beach", "lake worth", "wellington", "palm beach gardens", "jupiter", "greenacres", "royal palm beach", "riviera beach", "belle glade", "palm springs", "pahokee", "lake park"],
    "orange":       ["orlando", "kissimmee", "apopka", "ocoee", "winter garden", "winter park", "maitland", "edgewood", "belle isle", "eatonville", "windermere"],
    "hillsborough": ["tampa", "brandon", "temple terrace", "plant city", "riverview", "valrico", "ruskin", "sun city center", "apollo beach"],
    "pinellas":     ["st. petersburg", "saint petersburg", "clearwater", "largo", "dunedin", "tarpon springs", "pinellas park", "safety harbor", "oldsmar", "seminole", "belleair"],
    "duval":        ["jacksonville", "jacksonville beach", "neptune beach", "atlantic beach", "baldwin"],
    "seminole":     ["sanford", "altamonte springs", "casselberry", "longwood", "oviedo", "lake mary", "winter springs"],
    "volusia":      ["daytona beach", "deltona", "port orange", "ormond beach", "deland", "edgewater", "new smyrna beach", "holly hill", "south daytona"],
    "brevard":      ["melbourne", "palm bay", "titusville", "rockledge", "cocoa", "cocoa beach", "merritt island", "viera"],
    "lee":          ["cape coral", "fort myers", "bonita springs", "sanibel", "estero", "lehigh acres"],
    "collier":      ["naples", "marco island", "immokalee", "everglades city", "golden gate"],
    "sarasota":     ["sarasota", "venice", "north port", "englewood"],
    "manatee":      ["bradenton", "palmetto", "ellenton", "anna maria", "holmes beach", "longboat key"],
    "alachua":      ["gainesville", "archer", "hawthorne", "high springs", "newberry"],
    "leon":         ["tallahassee", "havana", "midway"],
    "escambia":     ["pensacola", "pensacola beach", "century"],
    "pasco":        ["new port richey", "dade city", "zephyrhills", "holiday", "land o lakes"],
    "polk":         ["lakeland", "winter haven", "bartow", "auburndale", "haines city", "lake wales"],
    "marion":       ["ocala", "belleview", "dunnellon", "silver springs"],
    "osceola":      ["kissimmee", "st. cloud", "saint cloud", "poinciana"],
    "st. lucie":    ["port st. lucie", "fort pierce", "port saint lucie"],
    "martin":       ["stuart", "hobe sound", "jensen beach", "palm city"],
    "indian river": ["vero beach", "sebastian", "fellsmere"],
}

ZIP_RE = re.compile(r"\b(\d{5})\b")

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
    try:
        filed = datetime.strptime(date_str.strip(), "%m/%d/%Y")
        years = (datetime.now() - filed).days // 365
        return str(years) if years >= 0 else ""
    except Exception:
        return ""


def _matches_location(address: str, location: str) -> bool:
    """Return True if the address belongs to the requested location."""
    if not address:
        return False

    addr_lower = address.lower()
    loc_lower  = location.lower().strip()

    # Zip code: 5 digits anywhere in location string
    zip_match = ZIP_RE.search(loc_lower)
    if zip_match:
        return zip_match.group(1) in address

    # County: location contains the word "county"
    if "county" in loc_lower:
        county_name = loc_lower.replace("county", "").replace(",", "").replace("fl", "").strip()
        cities = FL_COUNTY_CITIES.get(county_name, [])
        if cities:
            return any(city in addr_lower for city in cities)
        # Fallback: check if county name itself appears in address (rare but possible)
        return county_name in addr_lower

    # City: take everything before the first comma
    city = loc_lower.split(",")[0].strip()
    return city in addr_lower


def _parse_detail(path: str) -> dict:
    url = DETAIL_BASE + path
    html = _fetch(url)
    if not html:
        return {}

    soup = BeautifulSoup(html, "lxml")
    data = {"address": "", "owner_name": "Owner"}

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
            if name_el and (not data.get("owner_name") or data.get("owner_name") == "Owner"):
                name = name_el.get_text(strip=True)
                if name:
                    data["owner_name"] = name.title()

    return data


def _parse_results(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    leads = []

    table = soup.find("table", {"id": "search-results"}) or soup.find("table")
    if not table:
        return leads

    for row in table.select("tr")[1:]:
        cols = row.find_all("td")
        if len(cols) < 4:
            continue

        name_el = cols[0].find("a")
        if not name_el:
            continue

        status = cols[5].get_text(strip=True).upper() if len(cols) > 5 else ""
        if status and status != "ACTIVE":
            continue

        leads.append({
            "name":              name_el.get_text(strip=True),
            "detail_path":       name_el.get("href", ""),
            "doc_number":        cols[1].get_text(strip=True) if len(cols) > 1 else "",
            "years_in_business": _years_from_date(cols[3].get_text(strip=True) if len(cols) > 3 else ""),
            "phone": "", "email": "", "website": "", "address": "",
            "category": "", "rating": "", "reviews": "",
            "owner_name": "Owner",
            "source": "SunBiz",
        })

    return leads


def scrape(query: str, location: str, max_results: int = 40, max_pages: int = 3) -> list[dict]:
    if config.DEMO_MODE:
        print("  [SunBiz] Demo mode — returning sample data")
        return DEMO_DATA[:max_results]

    all_leads: list[dict] = []
    scanned = 0
    per_page = 20
    # Scan extra pages to compensate for filtered-out non-local results
    extended_pages = max_pages * 3

    print(f"  [SunBiz] Filtering results to: {location}")

    for page in range(extended_pages):
        if len(all_leads) >= max_results:
            break

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

        print(f"  [SunBiz] Scraping page {page + 1}...")
        html = _fetch(url)
        if not html:
            break

        rows = _parse_results(html)
        if not rows:
            break

        for lead in rows:
            detail = _parse_detail(lead.pop("detail_path", ""))
            lead.update(detail)
            lead["category"] = query
            scanned += 1

            if _matches_location(lead.get("address", ""), location):
                all_leads.append(lead)

            time.sleep(0.5)
            if len(all_leads) >= max_results:
                break

        time.sleep(1.5)

    print(f"  [SunBiz] Done — {len(all_leads)} local leads from {scanned} records scanned")
    return all_leads
