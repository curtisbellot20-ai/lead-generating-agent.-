import re
import time
from datetime import datetime
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from lead_gen import config

SEARCH_URL  = "https://search.sunbiz.org/Inquiry/CorporationSearch/ByName"
DETAIL_BASE = "https://search.sunbiz.org"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

KEYWORD_MAP = {
    "plumbers":      ["plumbing"],
    "electricians":  ["electrical", "electric"],
    "roofers":       ["roofing"],
    "landscapers":   ["landscaping", "lawn"],
    "painters":      ["painting"],
    "cleaners":      ["cleaning", "janitorial"],
    "movers":        ["moving", "transport"],
    "mechanics":     ["automotive", "auto repair"],
    "dentists":      ["dental"],
    "lawyers":       ["law", "legal"],
    "accountants":   ["accounting", "cpa"],
    "contractors":   ["contracting", "construction"],
    "handymen":      ["handyman", "home repair"],
    "pest control":  ["pest", "exterminating"],
    "pool service":  ["pool", "pool cleaning"],
    "hvac":          ["air conditioning", "cooling", "heating"],
    "photographers": ["photography"],
    "caterers":      ["catering"],
    "florists":      ["floral"],
    "therapists":    ["therapy", "counseling"],
    "event planners":["events", "event management", "event planning"],
    "wedding planners":["weddings", "wedding"],
}

FL_COUNTY_CITIES = {
    "broward":      ["fort lauderdale","hollywood","pompano beach","miramar","coral springs","pembroke pines","sunrise","plantation","davie","deerfield beach","tamarac","north lauderdale","margate","coconut creek","lauderhill","weston","hallandale beach","oakland park","wilton manors","dania beach","cooper city","lighthouse point","lauderdale lakes","parkland"],
    "miami-dade":   ["miami","hialeah","miami gardens","homestead","miami beach","north miami","coral gables","doral","north miami beach","aventura","miami lakes","cutler bay","opa-locka","florida city","south miami","sweetwater","medley"],
    "palm beach":   ["west palm beach","boca raton","delray beach","boynton beach","lake worth","wellington","palm beach gardens","jupiter","greenacres","royal palm beach","riviera beach","belle glade","palm springs","pahokee","lake park"],
    "orange":       ["orlando","kissimmee","apopka","ocoee","winter garden","winter park","maitland","edgewood","belle isle","eatonville","windermere"],
    "hillsborough": ["tampa","brandon","temple terrace","plant city","riverview","valrico","ruskin","sun city center","apollo beach"],
    "pinellas":     ["st. petersburg","saint petersburg","clearwater","largo","dunedin","tarpon springs","pinellas park","safety harbor","oldsmar","seminole","belleair"],
    "duval":        ["jacksonville","jacksonville beach","neptune beach","atlantic beach","baldwin"],
    "seminole":     ["sanford","altamonte springs","casselberry","longwood","oviedo","lake mary","winter springs"],
    "volusia":      ["daytona beach","deltona","port orange","ormond beach","deland","edgewater","new smyrna beach","holly hill","south daytona"],
    "brevard":      ["melbourne","palm bay","titusville","rockledge","cocoa","cocoa beach","merritt island","viera"],
    "lee":          ["cape coral","fort myers","bonita springs","sanibel","estero","lehigh acres"],
    "collier":      ["naples","marco island","immokalee","everglades city","golden gate"],
    "sarasota":     ["sarasota","venice","north port","englewood"],
    "manatee":      ["bradenton","palmetto","ellenton","anna maria","holmes beach","longboat key"],
    "alachua":      ["gainesville","archer","hawthorne","high springs","newberry"],
    "leon":         ["tallahassee","havana","midway"],
    "escambia":     ["pensacola","pensacola beach","century"],
    "pasco":        ["new port richey","dade city","zephyrhills","holiday","land o lakes"],
    "polk":         ["lakeland","winter haven","bartow","auburndale","haines city","lake wales"],
    "marion":       ["ocala","belleview","dunnellon","silver springs"],
    "osceola":      ["kissimmee","st. cloud","saint cloud","poinciana"],
    "st. lucie":    ["port st. lucie","fort pierce","port saint lucie"],
    "martin":       ["stuart","hobe sound","jensen beach","palm city"],
    "indian river": ["vero beach","sebastian","fellsmere"],
}

ZIP_RE = re.compile(r"\b(\d{5})\b")
_STRIP_ENTITY = re.compile(r'\b(LLC|INC|CORP|LTD|CO|COMPANY|THE|AND|L\.L\.C|INC\.)\b', re.I)

DEMO_DATA = [
    {"name":"SUNSHINE PLUMBING LLC","phone":"","address":"123 NW 5th Ave, Fort Lauderdale, FL 33311","website":"","category":"Plumbers","owner_name":"James Rivera","years_in_business":"6","source":"SunBiz","rating":"","reviews":""},
    {"name":"BROWARD ELECTRICAL INC","phone":"","address":"456 Sunrise Blvd, Fort Lauderdale, FL 33304","website":"","category":"Electricians","owner_name":"Maria Santos","years_in_business":"11","source":"SunBiz","rating":"","reviews":""},
]


def _get_queries(query: str) -> list[str]:
    q = query.lower().strip()
    variations = [query] + KEYWORD_MAP.get(q, [])
    seen: set[str] = set()
    result: list[str] = []
    for v in variations:
        if v.lower() not in seen:
            seen.add(v.lower())
            result.append(v)
    return result


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
    if not address:
        return False
    addr_lower = address.lower()
    loc_lower  = location.lower().strip()
    zip_match  = ZIP_RE.search(loc_lower)
    if zip_match:
        return zip_match.group(1) in address
    if "county" in loc_lower:
        county_name = loc_lower.replace("county","").replace(",","").replace("fl","").strip()
        cities = FL_COUNTY_CITIES.get(county_name, [])
        if cities:
            return any(city in addr_lower for city in cities)
        return county_name in addr_lower
    city = loc_lower.split(",")[0].strip()
    return city in addr_lower


def _parse_detail(path: str) -> dict:
    """Parse a SunBiz detail page for address and primary contact name."""
    url  = DETAIL_BASE + path
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
            if name_el and (not data.get("owner_name") or data["owner_name"] == "Owner"):
                name = name_el.get_text(strip=True)
                if name:
                    data["owner_name"] = name.title()
    return data


def _parse_results(html: str) -> list[dict]:
    soup  = BeautifulSoup(html, "lxml")
    table = soup.find("table", {"id": "search-results"}) or soup.find("table")
    if not table:
        return []
    rows = []
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
        rows.append({
            "name":              name_el.get_text(strip=True),
            "detail_path":       name_el.get("href", ""),
            "years_in_business": _years_from_date(cols[3].get_text(strip=True) if len(cols) > 3 else ""),
            "phone":"","email":"","website":"","address":"",
            "category":"","rating":"","reviews":"",
            "owner_name":"Owner","source":"SunBiz",
        })
    return rows


def _scrape_one_query(query: str, location: str, max_results: int, max_pages: int, seen_names: set) -> list[dict]:
    leads: list[dict] = []
    per_page = 20
    extended = max_pages * 3
    for page in range(extended):
        if len(leads) >= max_results:
            break
        url = (
            f"{SEARCH_URL}"
            f"?SearchTerm={quote(query)}"
            f"&SearchType=EntityName&SearchNameOrder=CONTAINS"
            f"&ActiveCorporationsOnly=Y&State=FL&offset={page * per_page}"
        )
        html = _fetch(url)
        if not html:
            break
        rows = _parse_results(html)
        if not rows:
            break
        for row in rows:
            detail = _parse_detail(row.pop("detail_path", ""))
            row.update(detail)
            row["category"] = query
            name_key = row.get("name", "").lower()
            if _matches_location(row.get("address", ""), location) and name_key not in seen_names:
                seen_names.add(name_key)
                leads.append(row)
            time.sleep(0.5)
            if len(leads) >= max_results:
                break
        time.sleep(1.5)
    return leads


def scrape(query: str, location: str, max_results: int = 40, max_pages: int = 3) -> list[dict]:
    if config.DEMO_MODE:
        print("  [SunBiz] Demo mode -- returning sample data")
        return DEMO_DATA[:max_results]

    queries    = _get_queries(query)
    all_leads: list[dict] = []
    seen_names: set[str]  = set()

    print(f"  [SunBiz] Searching with keywords: {', '.join(queries)}")
    print(f"  [SunBiz] Filtering to: {location}")

    for q in queries:
        if len(all_leads) >= max_results:
            break
        remaining = max_results - len(all_leads)
        leads = _scrape_one_query(q, location, remaining, max_pages, seen_names)
        all_leads.extend(leads)
        print(f"  [SunBiz] '{q}' -> {len(leads)} leads")

    print(f"  [SunBiz] Done -- {len(all_leads)} total local leads")
    return all_leads


# ---------------------------------------------------------------------------
# Registry lookup by business name (separate from keyword scraping)
# ---------------------------------------------------------------------------

def _norm_biz(name: str) -> str:
    n = _STRIP_ENTITY.sub("", name.upper())
    n = re.sub(r'[^\w\s]', ' ', n)
    return re.sub(r'\s+', ' ', n).strip()


def _parse_registry_detail(path: str) -> dict:
    """Extract registered agent and managing member from a SunBiz detail page."""
    if not path:
        return {}
    html = _fetch(DETAIL_BASE + path)
    if not html:
        return {}
    soup   = BeautifulSoup(html, "lxml")
    result = {"registered_agent": "", "managing_member": "", "entity_type": ""}

    for section in soup.select(".detailSection"):
        lbl_el = section.select_one(".label")
        label  = lbl_el.get_text(strip=True).upper() if lbl_el else ""

        if "REGISTERED AGENT" in label:
            spans = [
                s.get_text(strip=True) for s in section.select("span")
                if s.get_text(strip=True)
                and "REGISTERED" not in s.get_text(strip=True).upper()
                and "ADDRESS" not in s.get_text(strip=True).upper()
            ]
            if spans:
                result["registered_agent"] = spans[0].title()

        elif any(k in label for k in ("OFFICER","DIRECTOR","MANAGER","MEMBER","AUTHORIZED")):
            # Find name rows in the table within this section
            for row in section.select("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    lbl = cells[0].get_text(strip=True).upper().rstrip(":")
                    val = cells[1].get_text(strip=True)
                    if lbl == "NAME" and val and not result["managing_member"]:
                        result["managing_member"] = val.title()

    return result


def lookup_by_name(business_name: str) -> dict:
    """Search SunBiz for a specific business by name and return registry data."""
    norm = _norm_biz(business_name)
    url  = (
        f"{SEARCH_URL}"
        f"?SearchTerm={quote(norm)}"
        f"&SearchType=EntityName&SearchNameOrder=CONTAINS"
        f"&ActiveCorporationsOnly=N&State=FL&offset=0"
    )
    html = _fetch(url)
    if not html:
        return {}

    soup  = BeautifulSoup(html, "lxml")
    table = soup.find("table", {"id": "search-results"}) or soup.find("table")
    if not table:
        return {}

    best_score = 0
    best_path  = ""
    best_meta: dict = {}

    for row in table.select("tr")[1:]:
        cols    = row.find_all("td")
        name_el = cols[0].find("a") if cols else None
        if not name_el:
            continue
        entity_name = name_el.get_text(strip=True)
        norm_entity = _norm_biz(entity_name)
        wa = set(norm.split())
        wb = set(norm_entity.split())
        score = int(len(wa & wb) / max(len(wa), len(wb)) * 100) if wa and wb else 0
        if score > best_score:
            best_score = score
            best_path  = name_el.get("href", "")
            best_meta  = {
                "legal_name":  entity_name,
                "status":      cols[5].get_text(strip=True) if len(cols) > 5 else "",
                "date_filed":  cols[3].get_text(strip=True) if len(cols) > 3 else "",
            }

    if best_score < 45 or not best_path:
        return {}

    detail = _parse_registry_detail(best_path)
    best_meta.update(detail)
    return best_meta


def run_registry_lookup(leads: list[dict]) -> list[dict]:
    """
    Look up FL businesses in SunBiz and store registry data separately.
    Only searches leads that are still missing owner info.
    """
    candidates = [
        (i, l) for i, l in enumerate(leads)
        if ("FL" in l.get("address", "") or "Florida" in l.get("address", ""))
        and l.get("name")
        and (not l.get("owner_name") or l.get("owner_name") == "Owner"
             or l.get("owner_confidence", "NONE") == "LOW")
    ][:40]  # cap at 40 to keep runtime reasonable

    if not candidates:
        print("  [SunBiz Registry] No FL leads need registry lookup")
        return leads

    print(f"  [SunBiz Registry] Looking up {len(candidates)} FL businesses...")
    found = 0

    for idx, (_, lead) in enumerate(candidates):
        reg = lookup_by_name(lead["name"])
        if reg:
            lead["registry_legal"]  = reg.get("legal_name", "")
            lead["registry_agent"]  = reg.get("registered_agent", "")
            lead["registry_member"] = reg.get("managing_member", "")
            lead["registry_status"] = reg.get("status", "")
            # Only fill owner if still missing
            if (not lead.get("owner_name") or lead["owner_name"] == "Owner") and reg.get("managing_member"):
                lead["owner_name"] = reg["managing_member"] + " (Reg.)"
            found += 1
        if idx < len(candidates) - 1:
            time.sleep(1.0)

    print(f"  [SunBiz Registry] Found data for {found}/{len(candidates)} businesses")
    return leads
