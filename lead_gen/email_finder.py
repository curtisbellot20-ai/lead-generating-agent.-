"""Website visit pipeline.

1. website_scraper visits all pages (Playwright or requests)
2. ai_extractor sends cleaned text + schema to Claude for structured extraction
3. Results merged into leads — only filling empty fields
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from lead_gen import website_scraper, ai_extractor

console = Console()


def _apply(lead: dict, scraped: dict, extracted: dict):
    """Merge scraped + AI-extracted data into lead without overwriting existing values."""
    # --- Raw scraper data ---------------------------------------------------
    if scraped.get("emails") and not lead.get("email"):
        lead["email"] = scraped["emails"][0]
    if scraped.get("phones") and not lead.get("phone"):
        lead["phone"] = scraped["phones"][0]
    if scraped.get("description") and not lead.get("description"):
        lead["description"] = scraped["description"]
    for p in ("instagram", "facebook", "tiktok", "linkedin", "twitter"):
        if not lead.get(p) and scraped.get("social", {}).get(p):
            lead[p] = scraped["social"][p]

    if not extracted:
        return

    # --- AI extraction ------------------------------------------------------
    if not lead.get("email") and extracted.get("primary_email"):
        lead["email"] = extracted["primary_email"]
    if not lead.get("phone") and extracted.get("primary_phone"):
        lead["phone"] = extracted["primary_phone"]

    # Owner / decision-maker: prefer higher confidence
    dm      = extracted.get("decision_maker") or ""
    own     = extracted.get("owner_name") or ""
    dm_c    = extracted.get("decision_maker_confidence", "NONE")
    own_c   = extracted.get("owner_confidence", "NONE")
    best    = (dm  if dm_c  in ("HIGH", "MEDIUM") else
               own if own_c in ("HIGH", "MEDIUM") else
               dm or own)
    best_c  = (dm_c  if dm_c  in ("HIGH", "MEDIUM") else
               own_c if own_c in ("HIGH", "MEDIUM") else
               dm_c or own_c)

    if (not lead.get("owner_name") or lead.get("owner_name") == "Owner") and best:
        lead["owner_name"]       = best
        lead["owner_confidence"] = best_c

    # Decision-maker stored separately for the DM column
    if not lead.get("decision_maker"):
        lead["decision_maker"]       = dm or own
        lead["decision_maker_title"] = extracted.get("decision_maker_title", "")

    if not lead.get("description") and extracted.get("business_description"):
        lead["description"] = extracted["business_description"]
    if not lead.get("years_in_business") and extracted.get("years_in_business"):
        lead["years_in_business"] = extracted["years_in_business"]

    for p in ("instagram", "facebook", "tiktok", "linkedin", "twitter"):
        if not lead.get(p) and extracted.get(p):
            lead[p] = extracted[p]


async def find_emails(leads: list[dict]) -> list[dict]:
    with_site = [l for l in leads if l.get("website")]
    no_site   = [l for l in leads if not l.get("website")]

    if not with_site:
        console.print("  No leads with websites to visit")
        return leads

    emails_found = social_found = owners_found = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"Scraping {len(with_site)} websites...",
            total=len(with_site) * 2,
        )

        # Step 1 — parallel page scraping (Playwright or requests)
        progress.update(task, description="Rendering pages...")
        scraped_list = await website_scraper.scrape_all(with_site)
        progress.advance(task, len(with_site))

        # Step 2 — AI field extraction (parallel via thread pool, sync SDK)
        progress.update(task, description="AI extracting owner / email / social...")
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [
                loop.run_in_executor(pool, ai_extractor.extract, lead["name"], scraped)
                for lead, scraped in zip(with_site, scraped_list)
            ]
            extracted_list = list(await asyncio.gather(*futures))
        progress.advance(task, len(with_site))

    # Merge results into leads
    for lead, scraped, extracted in zip(with_site, scraped_list, extracted_list):
        _apply(lead, scraped, extracted)
        if lead.get("email"):                                               emails_found += 1
        if any(lead.get(p) for p in ("instagram","facebook","tiktok")):    social_found += 1
        if lead.get("owner_name") and lead["owner_name"] != "Owner":        owners_found += 1

    for lead in no_site:
        for k in ("email","instagram","facebook","tiktok","linkedin","twitter",
                  "decision_maker","decision_maker_title","description"):
            lead.setdefault(k, "")

    console.print(
        f"  Found [green]{emails_found}[/green] emails, "
        f"[magenta]{social_found}[/magenta] social profiles, "
        f"[yellow]{owners_found}[/yellow] owner/decision-maker names "
        f"from [cyan]{len(with_site)}[/cyan] sites"
    )
    return leads
