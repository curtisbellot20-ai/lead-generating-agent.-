import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
import questionary

from lead_gen import config
from lead_gen.pipeline import run_pipeline

console = Console()


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

    else:  # zip
        value = questionary.text(
            "Zip code:",
            default="33311",
            instruction="e.g. 33311  or  33301, 33304  for multiple",
            validate=lambda v: len(v.strip()) >= 5 or "Enter a valid zip code",
        ).ask()

    if value is None:
        sys.exit(0)
    return value.strip()


def prompt_inputs() -> dict:
    console.print("[bold]Configure your search[/bold]")
    console.print()

    query = questionary.text(
        "Business type to search for:",
        default=config.SEARCH["query"],
    ).ask()
    if query is None:
        sys.exit(0)

    location = _prompt_location()

    max_per = questionary.text(
        "Max leads per source:",
        default=str(config.SEARCH["max_per_source"]),
        validate=lambda v: v.isdigit() and int(v) > 0 or "Enter a positive number",
    ).ask()
    if max_per is None:
        sys.exit(0)

    source_choices = [
        questionary.Choice("Yellow Pages",         value="yellow_pages", checked=config.SOURCES.get("yellow_pages", True)),
        questionary.Choice("Yelp",                 value="yelp",         checked=config.SOURCES.get("yelp", True)),
        questionary.Choice("Google Maps",           value="google_maps",  checked=config.SOURCES.get("google_maps", False)),
        questionary.Choice("SunBiz (FL registry)",  value="sunbiz",       checked=config.SOURCES.get("sunbiz", False)),
        questionary.Choice("Chamber of Commerce",  value="chamber",      checked=config.SOURCES.get("chamber", False)),
        questionary.Choice("BNI Chapters",          value="bni",          checked=config.SOURCES.get("bni", False)),
    ]

    sources = questionary.checkbox(
        "Sources to scrape (space to toggle, enter to confirm):",
        choices=source_choices,
    ).ask()
    if sources is None:
        sys.exit(0)

    if not sources:
        console.print("[red]No sources selected — exiting.[/red]")
        sys.exit(1)

    console.print()
    return {
        "query":          query.strip(),
        "location":       location,
        "max_per_source": int(max_per),
        "max_pages":      config.SEARCH.get("max_pages", 3),
        "sources":        {s: (s in sources) for s in ["yellow_pages", "yelp", "google_maps", "sunbiz", "chamber", "bni"]},
    }


if __name__ == "__main__":
    show_header()
    show_api_status()
    params = prompt_inputs()
    asyncio.run(run_pipeline(params))
