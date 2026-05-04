import asyncio
from lead_gen import config
from lead_gen.enricher import enrich_leads
from lead_gen.exporter import export_to_excel
from lead_gen.scrapers import yellow_pages, yelp, chamber, bni


def deduplicate(leads: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for lead in leads:
        key = lead.get("name", "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(lead)
    return unique


async def run_pipeline():
    query = config.SEARCH["query"]
    location = config.SEARCH["location"]
    max_per = config.SEARCH["max_per_source"]

    mode = "DEMO" if config.DEMO_MODE else "LIVE"
    print(f"\n{'='*60}")
    print(f"  Lead Gen Agent — {mode} MODE")
    print(f"  Query: {query} | Location: {location}")
    print(f"{'='*60}\n")

    all_leads = []
    step = 1

    if config.SOURCES.get("yellow_pages"):
        print(f"[{step}/4] Scraping Yellow Pages...")
        all_leads.extend(yellow_pages.scrape(query, location, max_per))
        step += 1

    if config.SOURCES.get("yelp"):
        print(f"[{step}/4] Scraping Yelp...")
        all_leads.extend(yelp.scrape(query, location, max_per))
        step += 1

    if config.SOURCES.get("chamber"):
        print(f"[{step}/4] Scraping Chamber of Commerce...")
        all_leads.extend(chamber.scrape(config.CHAMBER_URLS, max_per))
        step += 1

    if config.SOURCES.get("bni"):
        print(f"[{step}/4] Scraping BNI Chapters...")
        all_leads.extend(bni.scrape(config.BNI_CHAPTER_URLS, max_per))

    print(f"\n  Raw leads collected : {len(all_leads)}")
    all_leads = deduplicate(all_leads)
    print(f"  After deduplication : {len(all_leads)}")

    print("\n[AI] Enriching leads with Claude...")
    all_leads = enrich_leads(all_leads)

    print("\n[XLS] Exporting to Excel...")
    output_file = export_to_excel(all_leads, query, location)

    print(f"\n{'='*60}")
    print(f"  Done! {len(all_leads)} leads saved to:")
    print(f"  {output_file}")
    print(f"{'='*60}\n")
