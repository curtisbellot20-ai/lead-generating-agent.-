"""Google search enrichment — fills in missing fields for each lead.

For every lead that is still missing key data (website, phone, address, rating)
we fire a targeted Google search via ScraperAPI and pull info from:
  - The knowledge graph panel (most accurate — shown when Google is confident)
  - The first local_result that name-matches
  - Organic snippet text (owner name, founding year, etc.)

Only leads that are actually missing data are searched, to conserve API credits.
"""

import re
import time
import requests

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from lead_gen import config

console = Console()

API_URL = "https://api.scraperapi.com/structured/google/search"

_STRIP_WORDS = {
    "inc", "llc", "ltd", "corp", "co", "company", "companies",
    "group", "services", "service", "solutions", "solution",
    "enterprises", "enterprise", "and", "the", "of",
}

# Patterns to mine owner name from Google snippet text
_NAME_PATTERNS = [
    re.compile(r'(?:founded|owned|started|established|created|run)\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', re.IGNORECASE),
    re.compile(r'(?:owner|founder|president|ceo|principal|operator)\s*[:\-–]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', re.IGNORECASE),
    re.compile(r"(?:I'?m|I am|my name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.IGNORECASE),
]

_YEAR_PATTERNS = [
    re.compile(r'(?:founded|established|est\.?|incorporated|started|opened|began)\s+(?:in\s+)?((?:19|20)\d{2})', re.IGNORECASE),
    re.compile(r'(?:since|serving since|in business since)\s+((?:19|20)\d{2})', re.IGNORECASE),
    re.compile(r'(\d{1,2})\+?\s+years?\s+(?:of\s+)?(?:experience|in\s+business|serving)', re.IGNORECASE),
]

CURRENT_YEAR = 2026


def _normalize(name: str) -> str:
    name = name.lower()
    name = re.sub(r'[^\w\s]', ' ', name)
    words = [w for w in name.split() if w not in _STRIP_WORDS]
    return " ".join(words).strip()


def _names_overlap(a: str, b: str) -> bool:
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    wa, wb = set(na.split()), set(nb.split())
    if not wa or not wb:
        return False
    return len(wa & wb) / max(len(wa), len(wb)) >= 0.6


def _extract_year(text: str) -> str:
    for pattern in _YEAR_PATTERNS:
        m = pattern.search(text)
        if m:
            val = m.group(1).strip()
            if re.fullmatch(r'(?:19|20)\d{2}', val):
                year = int(val)
                if 1900 < year <= CURRENT_YEAR:
                    return str(CURRENT_YEAR - year)
            else:
                num = int(val)
                if 1 <= num <= 100:
                    return str(num)
    return ""


def _extract_owner(text: str) -> str:
    for pattern in _NAME_PATTERNS:
        m = pattern.search(text)
        if m:
            name = m.group(1).strip()
            if len(name) <= 40 and not re.search(r'\d', name) and not name.isupper():
                return name
    return ""


def _needs_enrichment(lead: dict) -> bool:
    """Return True if the lead is missing at least one important field."""
    missing = [
        not lead.get("website"),
        not lead.get("phone"),
        not lead.get("rating"),
        not lead.get("owner_name"),
        not lead.get("years_in_business"),
    ]
    return sum(missing) >= 2  # search only if 2+ fields are missing


def _build_query(lead: dict) -> str:
    name  = lead.get("name", "")
    phone = lead.get("phone", "")
    addr  = lead.get("address", "")
    # Extract city from address (last part before state/zip)
    city = ""
    if addr:
        parts = [p.strip() for p in addr.split(",")]
        if len(parts) >= 2:
            city = parts[-2]  # e.g. "Fort Lauderdale" from "123 Main St, Fort Lauderdale, FL"

    if phone:
        return f'"{name}" {phone}'
    elif city:
        return f'"{name}" {city}'
    else:
        return f'"{name}"'


def _search_google(query: str) -> dict:
    try:
        resp = requests.get(
            API_URL,
            params={
                "api_key":      config.SCRAPERAPI_KEY,
                "query":        query,
                "country_code": "us",
                "num":          10,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def _parse_result(lead: dict, data: dict) -> dict:
    """Extract fields from Google search result and return only the new ones."""
    updates: dict = {}
    lead_name = lead.get("name", "")

    # ── 1. Knowledge graph (highest confidence) ─────────────────
    kg = data.get("knowledge_graph", {})
    if kg and isinstance(kg, dict):
        kg_title = kg.get("title", "")
        # Only trust KG if the name roughly matches
        if _names_overlap(lead_name, kg_title) or not kg_title:
            if not lead.get("website"):
                updates["website"] = kg.get("website", "")
            if not lead.get("phone"):
                updates["phone"] = kg.get("phone", "")
            if not lead.get("address"):
                updates["address"] = kg.get("address", "")
            if not lead.get("rating"):
                updates["rating"] = str(kg.get("rating", ""))
            # Mine description for owner / year
            desc = kg.get("description", "")
            if desc:
                if not lead.get("owner_name"):
                    owner = _extract_owner(desc)
                    if owner:
                        updates["owner_name"] = owner
                if not lead.get("years_in_business"):
                    yib = _extract_year(desc)
                    if yib:
                        updates["years_in_business"] = yib

    # ── 2. First matching local result ──────────────────────────
    for place in data.get("local_results", []):
        if not isinstance(place, dict):
            continue
        place_name = place.get("title") or place.get("name", "")
        if not _names_overlap(lead_name, place_name):
            continue
        if not lead.get("website") and not updates.get("website"):
            updates["website"] = place.get("website", "")
        if not lead.get("phone") and not updates.get("phone"):
            updates["phone"] = place.get("phone", "")
        if not lead.get("address") and not updates.get("address"):
            updates["address"] = place.get("address", place.get("full_address", ""))
        if not lead.get("rating") and not updates.get("rating"):
            updates["rating"] = str(place.get("rating", ""))
        if not lead.get("reviews") and not updates.get("reviews"):
            rev = place.get("reviews") or place.get("reviews_count") or place.get("rating_count", "")
            updates["reviews"] = str(rev) if rev else ""
        break  # only use the first name-matching result

    # ── 3. Organic snippet text (owner / year mining) ─────────────
    if not updates.get("owner_name") and not lead.get("owner_name"):
        for item in data.get("organic_results", data.get("results", []))[:5]:
            snippet = item.get("snippet", "") + " " + item.get("title", "")
            owner = _extract_owner(snippet)
            if owner:
                updates["owner_name"] = owner
                break

    if not updates.get("years_in_business") and not lead.get("years_in_business"):
        for item in data.get("organic_results", data.get("results", []))[:5]:
            snippet = item.get("snippet", "") + " " + item.get("title", "")
            yib = _extract_year(snippet)
            if yib:
                updates["years_in_business"] = yib
                break

    return {k: v for k, v in updates.items() if v}  # drop empty strings


def enrich(leads: list[dict]) -> list[dict]:
    """Google-search each lead that is missing key fields and fill in the gaps."""
    if not config.SCRAPERAPI_KEY:
        console.print("  [dim]No SCRAPERAPI_KEY — skipping Google search enrichment[/dim]")
        return leads

    to_search = [l for l in leads if _needs_enrichment(l)]
    if not to_search:
        console.print("  All leads already have sufficient data — skipping Google search enrichment")
        return leads

    filled_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Google search enrichment...", total=len(to_search))

        for i, lead in enumerate(to_search):
            progress.update(task, description=f"[dim]Searching: {lead['name'][:35]}[/dim]")
            query  = _build_query(lead)
            data   = _search_google(query)
            updates = _parse_result(lead, data)

            if updates:
                lead.update(updates)
                filled_count += 1

            progress.advance(task)
            if i < len(to_search) - 1:
                time.sleep(0.4)  # be polite to the API

    console.print(
        f"  Google search enriched [green]{filled_count}[/green] of "
        f"[cyan]{len(to_search)}[/cyan] leads with missing data"
    )
    return leads
