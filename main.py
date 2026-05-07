import asyncio
import re
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
import questionary

from lead_gen import config
from lead_gen.pipeline import run_pipeline

console = Console()

# Suffixes users often add that hurt scraper results
_QUERY_NOISE = re.compile(
    r'\b(technicians?|contractors?|companies|company|services?|specialists?|experts?|professionals?)\b',
    re.IGNORECASE,
)


def _sanitize_query(raw: str) -> str:
    """Clean up the user's query so scrapers get the best possible search term."""
    # Take the last meaningful phrase if commas are present
    # e.g. "events, venue, event planners" → "event planners"
    if "," in raw:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        raw = parts[-1] if parts else raw

    # Remove common noise words that confuse SunBiz / structured search
    cleaned = _QUERY_NOISE.sub("", raw).strip()
    # Collapse extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned or raw.strip()


def _key_status(key: str) -> str:
    return "[green]✓ Set[/green]" if key else "[red]✗ Missing[/red]"


def show_header():
    console.print()
    console.print(Panel.fit(
        "[bold cyan]Lead Generation Agent[/bold cyan]\n[dim]Scrape · Enrich · Export[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()


def show_api_status():
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("Anthropic API key", _key_status(config.ANTHROPIC_API_KEY))
    table.add_row("ScraperAPI key",    _key_status(config.SCRAPERAPI_KEY))
    table.add_row(
        "Mode",
        "[yellow]DEMO — add SCRAPERAPI_KEY to .env for live scraping[/yellow]"
        if config.DEMO_MODE else "[green]LIVE[/green]",
    )
    console.print(table)
    console.print()


def _prompt_location() -> str:
    loc_type = questionary.select(
        "Search location by:",
        choices=[
            questionary.Choice("City & State",  value="city"),
            questionary.Choice("County",         value="county"),
            questionary.Choice("Zip Code",       value="zip"),
        ],
    ).ask()
    if loc_type is None:
        sys.exit(0)

    if loc_type == "city":
        value = questionary.text(
            "City & State:",
            default=config.SEARCH["location"],
            instruction="e.g. Fort Lauderdale, FL",
        ).ask()
    elif loc_type == "county":
        value = questionary.text(
            "County name:",
            default="Broward County, FL",
            instruction="e.g. Broward County, FL",
        ).ask()
    else:
        value = questionary.text(
            "Zip code:",
            default="33311",
            instruction="e.g. 33311",
            validate=lambda v: len(v.strip()) >= 5 or "Enter a valid zip code",
        ).ask()

    if value is None:
        sys.exit(0)
    return value.strip()


def prompt_inputs() -> dict:
    console.print("[bold]Configure your search[/bold]")
    console.print()
    console.print(
        "[dim]Tip: Use a single short phrase for best results — e.g. [cyan]plumbers[/cyan], "
        "[cyan]air conditioning[/cyan], [cyan]event planners[/cyan], [cyan]roofers[/cyan][/dim]"
    )
    console.print()

    raw_query = questionary.text(
        "Business type to search for:",
        default=config.SEARCH["query"],
    ).ask()
    if raw_query is None:
        sys.exit(0)

    query = _sanitize_query(raw_query)
    if query != raw_query.strip():
        console.print(f"  [dim]Query cleaned to:[/dim] [cyan]{query}[/cyan]")
        console.print()

    location = _prompt_location()

    max_per = questionary.text(
        "Max leads per source:",
        default=str(config.SEARCH["max_per_source"]),
        validate=lambda v: v.isdigit() and int(v) > 0 or "Enter a positive number",
    ).ask()
    if max_per is None:
        sys.exit(0)

    max_pages = questionary.text(
        "Max pages per source:",
        default=str(config.SEARCH.get("max_pages", 3)),
        instruction="More pages = more leads but takes longer",
        validate=lambda v: v.isdigit() and int(v) > 0 or "Enter a positive number",
    ).ask()
    if max_pages is None:
        sys.exit(0)

    source_choices = [
        questionary.Choice("Google Maps  ← primary source", value="google_maps",  checked=config.SOURCES.get("google_maps", True)),
        questionary.Choice("Yellow Pages",                  value="yellow_pages", checked=config.SOURCES.get("yellow_pages", True)),
        questionary.Choice("BBB",                           value="bbb",          checked=config.SOURCES.get("bbb", True)),
        questionary.Choice("Angi",                          value="angi",         checked=config.SOURCES.get("angi", True)),
        questionary.Choice("Yelp",                          value="yelp",         checked=config.SOURCES.get("yelp", False)),
        questionary.Choice("SunBiz (FL registry)",          value="sunbiz",       checked=config.SOURCES.get("sunbiz", False)),
        questionary.Choice("Chamber of Commerce",           value="chamber",      checked=config.SOURCES.get("chamber", False)),
        questionary.Choice("BNI Chapters",                  value="bni",          checked=config.SOURCES.get("bni", False)),
    ]

    sources = questionary.checkbox(
        "Sources (Google Maps = primary, rest fill in missing info):",
        choices=source_choices,
    ).ask()
    if sources is None:
        sys.exit(0)

    if not sources:
        console.print("[red]No sources selected — exiting.[/red]")
        sys.exit(1)

    console.print()
    return {
        "query":          query,
        "location":       location,
        "max_per_source": int(max_per),
        "max_pages":      int(max_pages),
        "sources":        {s: (s in sources) for s in ["google_maps", "yellow_pages", "bbb", "angi", "yelp", "sunbiz", "chamber", "bni"]},
    }


if __name__ == "__main__":
    show_header()
    show_api_status()
    params = prompt_inputs()
    asyncio.run(run_pipeline(params))
