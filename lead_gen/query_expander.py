"""AI-powered query expansion.

Given a business type and location, uses Claude to generate a list of
related search queries so we cast a much wider net on Google Maps.

Example: "event planners" in "Broward County, FL" expands to:
  - "wedding planners Fort Lauderdale FL"
  - "corporate event coordinators Broward County"
  - "party planners Hollywood FL"
  - "event venue coordinators Pompano Beach"
  ... (10-15 total)
"""

import json
import re

from rich.console import Console

from lead_gen import config

console = Console()

EXPAND_PROMPT = """You are a lead generation expert.

Given a business type and location, generate exactly 12 Google search queries
that would surface LOCAL businesses of that type or closely related types.

Rules:
- Each query should be short (3-6 words) — just the business type phrase,
  NO location in the query (the scraper adds location automatically)
- Use synonyms, niches, and related service types to maximize coverage
- Think about what different customers would search for the same service
- Vary the terminology: formal vs casual, specific vs general
- Do NOT repeat the same phrase twice
- Return ONLY a JSON array of 12 strings, no explanation

Example for "plumbers":
["plumbers", "plumbing contractors", "drain cleaning", "pipe repair",
 "water heater installation", "emergency plumbing", "sewer repair",
 "leak detection", "bathroom remodeling plumber", "kitchen plumbing",
 "plumbing services", "licensed plumber"]
"""


def _call_claude(query: str, location: str) -> list[str]:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=[
            {
                "type": "text",
                "text": EXPAND_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f'Business type: "{query}"\nLocation: "{location}"\n\nGenerate 12 search queries:',
            }
        ],
    )
    text = message.content[0].text.strip()
    # Extract JSON array from response
    m = re.search(r'\[.*?\]', text, re.DOTALL)
    if not m:
        return [query]
    try:
        queries = json.loads(m.group())
        # Keep only non-empty strings, deduplicate, max 15
        seen: set[str] = set()
        clean: list[str] = []
        for q in queries:
            q = str(q).strip()
            if q and q.lower() not in seen:
                seen.add(q.lower())
                clean.append(q)
            if len(clean) >= 15:
                break
        return clean if clean else [query]
    except Exception:
        return [query]


def expand(query: str, location: str) -> list[str]:
    """Return an expanded list of search queries. Falls back to [query] if AI unavailable."""
    if not config.ANTHROPIC_API_KEY:
        console.print("  [dim]No ANTHROPIC_API_KEY — using single query (no expansion)[/dim]")
        return [query]

    try:
        console.print(f"  Asking Claude to expand [cyan]{query!r}[/cyan] into related queries...")
        queries = _call_claude(query, location)
        console.print(
            f"  Generated [green]{len(queries)}[/green] search queries: "
            + ", ".join(f"[dim]{q}[/dim]" for q in queries[:5])
            + (f" [dim]... +{len(queries)-5} more[/dim]" if len(queries) > 5 else "")
        )
        return queries
    except Exception as e:
        console.print(f"  [yellow]Query expansion failed ({e}) — using original query[/yellow]")
        return [query]
