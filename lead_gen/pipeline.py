import asyncio
import re

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich.table import Table
from rich import box

from lead_gen import config
from lead_gen.enricher import enrich_leads
from lead_gen.email_finder import find_emails
from lead_gen.google_enricher import enrich as google_enrich
from lead_gen.query_expander import expand as expand_queries
from lead_gen.exporter import export_to_excel
from lead_gen.scrapers import yellow_pages, yelp, chamber, bni, sunbiz, google_maps, bbb, angi

console = Console()

_STRIP_WORDS = {
    "inc", "llc", "ltd", "corp", "co", "company", "companies", "group",
    "services", "service", "solutions", "solution", "enterprises", "enterprise",
    "and", "the", "of",
}


def _normalize_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r'[^\w\s]', ' ', name)
    words = [w for w in name.split() if w not in _STRIP_WORDS]
    return " ".join(words).strip()


def _normalize_phone(phone: str) -> str:
    return re.sub(r'\D', '', phone or "")[-10:]


def _names_match(a: str, b: str) -> bool:
    na, nb = _normalize_name(a), _normalize_name(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    wa, wb = set(na.split()), set(nb.split())
    if not wa or not wb:
        return False
    return len(wa & wb) / max(len(wa), len(wb)) >= 0.70


def _merge(primary: dict, secondary: dict) -> dict:
    merged = primary.copy()
    for key, value in secondary.items():
        if key in ("name", "source"):
            continue
        if not merged.get(key) and value:
            merged[key] = value
    return merged


def cross_reference(primary: list[dict], secondary: list[dict]) -> list[dict]:
    matched_idx: set[int] = set()
    result: list[dict] = []
    for lead in primary:
        merged = lead.copy()
        p_name  = lead.get("name", "")
        p_phone = _normalize_phone(lead.get("phone", ""))
        for i, sec in enumerate(secondary):
            s_phone = _normalize_phone(sec.get("phone", ""))
            if (p_phone and s_phone and p_phone == s_phone) or _names_match(p_name, sec.get("name", "")):
                merged = _merge(merged, sec)
                matched_idx.add(i)
        result.append(merged)
    for i, sec in enumerate(secondary):
        if i not in matched_idx:
            result.append(sec)
    return result


def deduplicate(leads: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for lead in leads:
        key = lead.get("name", "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(lead)
    return unique


async def run_pipeline(params: dict | None = None):
    if params is None:
        params = {
            "query":          config.SEARCH["query"],
            "location":       config.SEARCH["location"],
            "max_per_source": config.SEARCH["max_per_source"],
            "max_pages":      config.SEARCH.get("max_pages", 3),
            "sources":        config.SOURCES,
        }

    query    = params["query"]
    location = params["location"]
    max_per  = params["max_per_source"]
    max_pg   = params["max_pages"]
    sources  = params["sources"]

    primary_leads:   list[dict] = []
    secondary_leads: list[dict] = []
    active_sources = [k for k, v in sources.items() if v]

    # ── Step 1: AI query expansion ──────────────────────────────────────
    console.rule("[bold]Expanding search queries with AI[/bold]")
    expanded = expand_queries(query, location)
    extra_queries = [q for q in expanded if q.lower() != query.lower()]
    console.print()

    # ── Step 2: Scrape all sources ─────────────────────────────────
    console.rule("[bold]Scraping sources[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Scraping sources...", total=len(active_sources))

        if sources.get("google_maps"):
            progress.update(task, description="Scraping [bold]Google Maps[/bold] (primary, multi-query)...")
            primary_leads = google_maps.scrape(query, location, max_per, max_pg, extra_queries=extra_queries)
            progress.advance(task)

        if sources.get("yellow_pages"):
            progress.update(task, description="Scraping [bold]Yellow Pages[/bold]...")
            secondary_leads.extend(yellow_pages.scrape(query, location, max_per, max_pg))
            progress.advance(task)

        if sources.get("yelp"):
            progress.update(task, description="Scraping [bold]Yelp[/bold]...")
            secondary_leads.extend(yelp.scrape(query, location, max_per, max_pg))
            progress.advance(task)

        if sources.get("bbb"):
            progress.update(task, description="Scraping [bold]BBB[/bold]...")
            secondary_leads.extend(bbb.scrape(query, location, max_per, max_pg))
            progress.advance(task)

        if sources.get("angi"):
            progress.update(task, description="Scraping [bold]Angi[/bold]...")
            secondary_leads.extend(angi.scrape(query, location, max_per, max_pg))
            progress.advance(task)

        if sources.get("sunbiz"):
            progress.update(task, description="Scraping [bold]SunBiz[/bold]...")
            secondary_leads.extend(sunbiz.scrape(query, location, max_per, max_pg))
            progress.advance(task)

        if sources.get("chamber"):
            progress.update(task, description="Scraping [bold]Chamber of Commerce[/bold]...")
            secondary_leads.extend(chamber.scrape(config.CHAMBER_URLS, max_per))
            progress.advance(task)

        if sources.get("bni"):
            progress.update(task, description="Scraping [bold]BNI Chapters[/bold]...")
            secondary_leads.extend(bni.scrape(config.BNI_CHAPTER_URLS, max_per))
            progress.advance(task)

    # ── Step 3: Cross-reference ─────────────────────────────────────
    if primary_leads:
        console.print(f"  Google Maps: [cyan]{len(primary_leads)}[/cyan] primary leads")
        console.print(f"  Other sources: [cyan]{len(secondary_leads)}[/cyan] secondary leads")
        console.print("  Cross-referencing to fill missing fields...")
        all_leads = cross_reference(primary_leads, secondary_leads)
        all_leads = deduplicate(all_leads)
        console.print(f"  Result: [green]{len(all_leads)}[/green] leads after merge\n")
    else:
        all_leads = deduplicate(primary_leads + secondary_leads)
        console.print(f"  Collected [green]{len(all_leads)}[/green] leads after deduplication\n")

    # ── Step 4: Google search enrichment ───────────────────────────
    console.rule("[bold]Google search enrichment[/bold]")
    all_leads = google_enrich(all_leads)
    console.print()

    # ── Step 5: Website visit ──────────────────────────────────────
    console.rule("[bold]Visiting websites (email, social, About Us)[/bold]")
    all_leads = find_emails(all_leads)
    console.print()

    # ── Step 6: Claude AI enrichment ─────────────────────────────
    console.rule("[bold]Enriching with Claude AI[/bold]")
    all_leads = enrich_leads(all_leads)
    console.print()

    # ── Step 7: Export ─────────────────────────────────────────
    console.rule("[bold]Exporting[/bold]")
    output_file = export_to_excel(all_leads, query, location)

    emails_found = sum(1 for l in all_leads if l.get("email"))
    social_found = sum(1 for l in all_leads if l.get("instagram") or l.get("facebook") or l.get("tiktok"))
    owners_found = sum(1 for l in all_leads if l.get("owner_name") and l["owner_name"] != "Owner")

    summary = Table(box=box.ROUNDED, show_header=False, padding=(0, 2), border_style="green")
    summary.add_column(style="dim")
    summary.add_column(style="bold")
    summary.add_row("Query",           f"{query} in {location}")
    summary.add_row("Search queries",  str(len(expanded)))
    summary.add_row("Total leads",     str(len(all_leads)))
    summary.add_row("Emails found",    f"{emails_found} / {len(all_leads)}")
    summary.add_row("Social profiles", f"{social_found} / {len(all_leads)}")
    summary.add_row("Owner names",     f"{owners_found} / {len(all_leads)}")
    summary.add_row("Saved to",        f"[cyan]{output_file}[/cyan]")

    console.print()
    console.print(Panel(summary, title="[bold green] Done! [/bold green]", border_style="green"))
    console.print()
