import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

from lead_gen import config
from lead_gen.enricher import enrich_leads
from lead_gen.email_finder import find_emails
from lead_gen.exporter import export_to_excel
from lead_gen.scrapers import yellow_pages, yelp, chamber, bni

console = Console()


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

    all_leads: list[dict] = []
    active_sources = [k for k, v in sources.items() if v]

    # ── Scraping ──────────────────────────────────────────────────
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Scraping sources...", total=len(active_sources))

        if sources.get("yellow_pages"):
            progress.update(task, description="Scraping [bold]Yellow Pages[/bold]...")
            all_leads.extend(yellow_pages.scrape(query, location, max_per, max_pg))
            progress.advance(task)

        if sources.get("yelp"):
            progress.update(task, description="Scraping [bold]Yelp[/bold]...")
            all_leads.extend(yelp.scrape(query, location, max_per, max_pg))
            progress.advance(task)

        if sources.get("chamber"):
            progress.update(task, description="Scraping [bold]Chamber of Commerce[/bold]...")
            all_leads.extend(chamber.scrape(config.CHAMBER_URLS, max_per))
            progress.advance(task)

        if sources.get("bni"):
            progress.update(task, description="Scraping [bold]BNI Chapters[/bold]...")
            all_leads.extend(bni.scrape(config.BNI_CHAPTER_URLS, max_per))
            progress.advance(task)

    raw_count = len(all_leads)
    all_leads = deduplicate(all_leads)
    console.print(
        f"  Collected [cyan]{raw_count}[/cyan] leads "
        f"→ [green]{len(all_leads)}[/green] after deduplication\n"
    )

    # ── Email finder ─────────────────────────────────────────────
    console.rule("[bold]Finding email addresses[/bold]")
    all_leads = find_emails(all_leads)
    console.print()

    # ── AI enrichment ────────────────────────────────────────────
    console.rule("[bold]Enriching with Claude AI[/bold]")
    all_leads = enrich_leads(all_leads)
    console.print()

    # ── Export ───────────────────────────────────────────────────
    console.rule("[bold]Exporting[/bold]")
    output_file = export_to_excel(all_leads, query, location)

    # ── Summary ──────────────────────────────────────────────────
    emails_found = sum(1 for l in all_leads if l.get("email"))

    summary = Table(box=box.ROUNDED, show_header=False, padding=(0, 2), border_style="green")
    summary.add_column(style="dim")
    summary.add_column(style="bold")
    summary.add_row("Query",        f"{query} in {location}")
    summary.add_row("Total leads",  str(len(all_leads)))
    summary.add_row("Emails found", f"{emails_found} / {len(all_leads)}")
    summary.add_row("Saved to",     f"[cyan]{output_file}[/cyan]")

    console.print()
    console.print(Panel(summary, title="[bold green] Done! [/bold green]", border_style="green"))
    console.print()
