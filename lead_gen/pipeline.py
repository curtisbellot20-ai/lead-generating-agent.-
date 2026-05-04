import asyncio
from lead_gen import config
from lead_gen.enricher import enrich_leads
from lead_gen.email_finder import find_emails
from lead_gen.exporter import export_to_excel
from lead_gen.scrapers import yellow_pages, yelp, chamber, bni


def deduplicate(leads: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for lead in leads:
        key = lead.get("name", "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(lead)
    return unique


async def run_pipeline():
    query   = config.SEARCH["query"]
    location = config.SEARCH["location"]
    max_per  = config.SEARCH["max_per_source"]
    max_pg   = config.SEARCH.get("max_pages", 3)

    mode = "DEMO" if config.DEMO_MODE else "LIVE"
    print(f"\n{'='*60}")
    print(f"  Lead Gen Agent — {mode} MODE")
    print(f"  Query: {query} | Location: {location}")
    print(f"{'='*60}\n")

    all_leads: list[dict] = []
    step = 1

    # ── Scrape ─────────────────────────────────────────────────────
    if config.SOURCES.get("yellow_pages"):
        print(f"[{step}] Scraping Yellow Pages...")
        all_leads.extend(yellow_pages.scrape(query, location, max_per, max_pg))
        step += 1

    if config.SOURCES.get("yelp"):
        print(f"[{step}] Scraping Yelp...")
        all_leads.extend(yelp.scrape(query, location, max_per, max_pg))
        step += 1

    if config.SOURCES.get("chamber"):
        print(f"[{step}] Scraping Chamber of Commerce...")
        all_leads.extend(chamber.scrape(config.CHAMBER_URLS, max_per))
        step += 1

    if config.SOURCES.get("bni"):
        print(f"[{step}] Scraping BNI Chapters...")
        all_leads.extend(bni.scrape(config.BNI_CHAPTER_URLS, max_per))
        step += 1

    print(f"\n  Raw leads collected : {len(all_leads)}")
    all_leads = deduplicate(all_leads)
    print(f"  After deduplication : {len(all_leads)}")

    # ── Email finder ──────────────────────────────────────────────
    print(f"\n[{step}] Finding email addresses...")
    all_leads = find_emails(all_leads)
    step += 1

    # ── AI enrichment ─────────────────────────────────────────────
    print(f"\n[{step}] Enriching leads with Claude AI...")
    all_leads = enrich_leads(all_leads)
    step += 1

    # ── Export ─────────────────────────────────────────────────────
    print(f"\n[{step}] Exporting to Excel...")
    output_file = export_to_excel(all_leads, query, location)

    emails_found = sum(1 for l in all_leads if l.get("email"))
    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"  Total leads   : {len(all_leads)}")
    print(f"  Emails found  : {emails_found}")
    print(f"  File saved to : {output_file}")
    print(f"{'='*60}\n")
