import json
from lead_gen import config

SYSTEM_PROMPT = """You are a B2B lead enrichment specialist. Given a list of business leads, your job is to:
1. Infer the likely owner/decision-maker name from the business name and type (use "Owner" if unknown)
2. Write a short, personalized outreach note (2-3 sentences) a salesperson could send
3. Assign an industry tag

Return a JSON array — one object per lead — in this exact format:
[
  {
    "index": 0,
    "owner_name": "John Smith",
    "outreach_note": "Hi John, I noticed Sunshine Plumbing has been serving Fort Lauderdale for years. I help local service businesses get more qualified leads. Would you be open to a quick call this week?",
    "industry_tag": "Home Services"
  }
]

Rules:
- Outreach notes must be natural and conversational — not salesy or spammy
- Never invent specific facts you don't know
- Use "Owner" for owner_name when a name can't be reasonably inferred
- industry_tag must be one of: Home Services, Food & Beverage, Retail, Professional Services, Health & Wellness, Auto, Real Estate, Other"""


def enrich_leads(leads: list[dict]) -> list[dict]:
    if not config.ANTHROPIC_API_KEY:
        print("  [Enricher] No ANTHROPIC_API_KEY — skipping AI enrichment")
        for lead in leads:
            lead["owner_name"] = "Owner"
            lead["outreach_note"] = (
                f"Hi, I'd love to connect with the team at {lead['name']} "
                "about a service that could help grow your business."
            )
            lead["industry_tag"] = ""
        return leads

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        batch_size = 20
        enriched = []

        for i in range(0, len(leads), batch_size):
            batch = leads[i : i + batch_size]
            leads_payload = json.dumps(
                [
                    {
                        "index": j,
                        "name": l.get("name", ""),
                        "phone": l.get("phone", ""),
                        "address": l.get("address", ""),
                        "category": l.get("category", ""),
                        "website": l.get("website", ""),
                    }
                    for j, l in enumerate(batch)
                ],
                indent=2,
            )

            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {"role": "user", "content": f"Enrich these leads:\n\n{leads_payload}"}
                ],
            )

            text = message.content[0].text.strip()
            json_start = text.find("[")
            json_end = text.rfind("]")
            if json_start != -1 and json_end != -1:
                results = json.loads(text[json_start : json_end + 1])
                result_map = {r["index"]: r for r in results}
                for j, lead in enumerate(batch):
                    r = result_map.get(j, {})
                    lead["owner_name"] = r.get("owner_name", "Owner")
                    lead["outreach_note"] = r.get("outreach_note", "")
                    lead["industry_tag"] = r.get("industry_tag", "")
                    enriched.append(lead)
            else:
                for lead in batch:
                    lead["owner_name"] = "Owner"
                    lead["outreach_note"] = ""
                    lead["industry_tag"] = ""
                    enriched.append(lead)

        print(f"  [Enricher] Enriched {len(enriched)} leads")
        return enriched

    except Exception as e:
        print(f"  [Enricher] Error: {e}")
        for lead in leads:
            lead.setdefault("owner_name", "Owner")
            lead.setdefault("outreach_note", "")
            lead.setdefault("industry_tag", "")
        return leads
