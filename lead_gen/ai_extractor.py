"""AI extraction layer.

Sends cleaned website text + Schema.org data to Claude and returns
structured lead fields with confidence levels.
"""

import json
import re

from lead_gen import config

PROMPT = """You are a business intelligence analyst extracting structured contact data from website content.

Return ONLY a valid JSON object with these exact keys:

{
  "owner_name": "Full name of business owner/founder, or null",
  "owner_confidence": "HIGH | MEDIUM | LOW | NONE",
  "decision_maker": "Name of the best outreach contact (owner, doctor, attorney, manager), or null",
  "decision_maker_title": "Their role/title (use Dr., Esq., etc. where applicable), or null",
  "decision_maker_confidence": "HIGH | MEDIUM | LOW | NONE",
  "additional_contacts": [
    {"name": "...", "title": "...", "confidence": "HIGH|MEDIUM|LOW"}
  ],
  "primary_email": "Best contact email, or null",
  "all_emails": ["list", "of", "all", "emails"],
  "primary_phone": "Best phone number, or null",
  "all_phones": ["list", "of", "all", "phones"],
  "instagram": "Full URL or null",
  "facebook": "Full URL or null",
  "tiktok": "Full URL or null",
  "linkedin": "Full URL or null",
  "twitter": "Full URL or null",
  "business_description": "1-2 sentences describing what this business does, or null",
  "years_in_business": "Number as string (e.g. '12'), or null"
}

Confidence levels:
  HIGH   = Explicitly stated (\"Owner: John Smith\", \"Founded by Jane Doe\", named bio on About page)
  MEDIUM = Strongly implied (first-person bio, team section with role)
  LOW    = Inferred or uncertain
  NONE   = Not found

Rules:
- Medical/dental practices: doctor name is the decision_maker with title \"Dr.\"
- Law firms: founding/named partner is the decision_maker with \"Esq.\" or \"Attorney\"
- Multiple owners: most senior one in decision_maker, rest in additional_contacts
- Never fabricate — only use information present in the provided text
- Real names only — no \"The Owner\" or \"Management Team\""""


def extract(business_name: str, scraped: dict) -> dict:
    """Call Claude Haiku to extract structured fields from scraped website data."""
    if not config.ANTHROPIC_API_KEY:
        return {}
    if not scraped or (not scraped.get("clean_text") and not scraped.get("schema_data")):
        return {}

    parts = [f"Business: {business_name}\n"]

    if scraped.get("description"):
        parts.append(f"Meta description: {scraped['description']}\n")

    if scraped.get("schema_data"):
        s = json.dumps(scraped["schema_data"][:5], indent=2)
        parts.append(f"Schema.org structured data:\n{s[:2000]}\n")

    if scraped.get("footer"):
        parts.append(f"Footer text: {scraped['footer'][:400]}\n")

    if scraped.get("emails"):
        parts.append(f"Emails found in HTML: {', '.join(scraped['emails'])}\n")

    if scraped.get("phones"):
        parts.append(f"Phones found in HTML: {', '.join(scraped['phones'])}\n")

    if scraped.get("clean_text"):
        parts.append(f"Website text (cleaned):\n{scraped['clean_text'][:5500]}")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": "\n".join(parts)}],
        )
        text = msg.content[0].text.strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {}
