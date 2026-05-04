# Lead Gen Agent

AI-powered lead generation agent that scrapes Yellow Pages, Yelp, Chamber of Commerce, and BNI directories, then enriches every lead with Claude — outputting a clean, client-ready Excel file.

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in your API keys
cp .env.example .env

# 3. Run in demo mode (no keys needed)
python main.py
```

Output is saved to `outputs/leads_<query>_<timestamp>.xlsx`.

## Configuration

Edit `lead_gen/config.py` to change:

| Setting | Description |
|---|---|
| `SEARCH["query"]` | What to search for (e.g. `"plumbers"`, `"real estate agents"`) |
| `SEARCH["location"]` | City and state (e.g. `"Fort Lauderdale, FL"`) |
| `SEARCH["max_per_source"]` | Max leads per scraper (default: 25) |
| `SOURCES` | Toggle each scraper on/off |
| `CHAMBER_URLS` | Paste your local chamber member directory URLs here |
| `BNI_CHAPTER_URLS` | Paste your local BNI chapter URLs here |

## API Keys

- **ANTHROPIC_API_KEY** — Powers AI enrichment (owner names + outreach notes). Get one at [console.anthropic.com](https://console.anthropic.com).
- **SCRAPERAPI_KEY** — Lets the agent bypass bot protection on Yellow Pages and Yelp. Free tier at [scraperapi.com](https://scraperapi.com) gives you 1,000 scrapes/month. **Without this key the agent runs in demo mode.**

## Sources

| Source | What It Finds | Notes |
|---|---|---|
| Yellow Pages | Local service businesses | Needs ScraperAPI |
| Yelp | Local businesses with reviews + ratings | Needs ScraperAPI |
| Chamber of Commerce | Verified, paying business members | Add URLs to `config.py` |
| BNI | Referral-network business owners | Add chapter URLs to `config.py` |

## Output

The Excel file includes:
- Business Name, Owner Name (AI-inferred), Phone, Address, Website
- Category, Industry Tag, Rating, Source
- Personalized Outreach Note (AI-generated) ready to copy-paste
- Summary sheet with leads by source and industry

## Monetization

- Sell lists: $1–3 per lead depending on niche
- Monthly retainer: $500–$1,500/month for fresh leads
- Best buyers: real estate agents, insurance brokers, marketing agencies, contractors
