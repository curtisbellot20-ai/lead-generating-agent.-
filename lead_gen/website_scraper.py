"""Deep website scraper.

Rendering  : Playwright headless Chromium -> requests fallback
Parsing    : BeautifulSoup + lxml
Clean text : readability-lxml (Mozilla Readability algorithm)
Structured : Schema.org JSON-LD from every page

Pages visited: /  /about  /about-us  /team  /our-team
               /meet-the-team  /staff  /contact  /contact-us
"""

import re
import json
import asyncio
from typing import Optional

import requests
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    from readability import Document
    HAS_READABILITY = True
except ImportError:
    HAS_READABILITY = False

PAGE_PATHS = [
    "/", "/about", "/about-us",
    "/team", "/our-team", "/meet-the-team", "/staff",
    "/contact", "/contact-us",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)')

SOCIAL_RE = {
    "instagram": re.compile(r'instagram\.com/(?!p/|reel/|stories/|explore/|accounts/|share)([A-Za-z0-9._]{1,40})', re.I),
    "facebook":  re.compile(r'facebook\.com/(?!sharer|share|plugins|tr/|dialog/|events/|groups/)([A-Za-z0-9._\-]{3,})', re.I),
    "tiktok":    re.compile(r'tiktok\.com/@?([A-Za-z0-9._]{2,40})', re.I),
    "linkedin":  re.compile(r'linkedin\.com/(?:in|company)/([A-Za-z0-9._\-]{2,60})', re.I),
    "twitter":   re.compile(r'(?:twitter|x)\.com/(?!share|intent|home|i/)([A-Za-z0-9_]{1,50})', re.I),
}
SKIP_HANDLES = {
    "instagram": {"p","reel","stories","explore","accounts","share","sharer"},
    "facebook":  {"sharer","share","plugins","tr","dialog","groups","events"},
    "tiktok":    {"share","discover","trending","following","foryou"},
    "linkedin":  {"feed","jobs","pulse","mynetwork","notifications"},
    "twitter":   {"share","intent","home","i","hashtag"},
}
SKIP_EMAIL_DOMAINS = {
    "example.com","sentry.io","wixpress.com","squarespace.com",
    "wordpress.com","godaddy.com","schema.org","w3.org",
    "googleapis.com","cloudflare.com","facebook.com","twitter.com",
    "instagram.com","youtube.com","linkedin.com",
}
SKIP_EMAIL_LOCAL = {
    "noreply","no-reply","donotreply","mailer-daemon",
    "bounce","postmaster","webmaster",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

_pw                          = None
_browser                     = None
_sem: Optional[asyncio.Semaphore] = None


async def browser_start() -> bool:
    """Launch shared Playwright browser. Call once before scraping."""
    global _pw, _browser, _sem
    if not HAS_PLAYWRIGHT:
        return False
    try:
        _pw      = await async_playwright().start()
        _browser = await _pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        _sem = asyncio.Semaphore(4)   # max 4 pages open at once
        return True
    except Exception as e:
        print(f"  [Playwright] {e} -- using requests fallback")
        return False


async def browser_stop():
    """Close shared browser. Call once after scraping."""
    global _pw, _browser
    for obj in (_browser, _pw):
        if obj:
            try:
                await obj.close()
            except Exception:
                pass
    _browser = _pw = None


# ---------------------------------------------------------------------------

def _valid_email(e: str) -> bool:
    if "@" not in e:
        return False
    local, domain = e.lower().rsplit("@", 1)
    return (
        domain not in SKIP_EMAIL_DOMAINS
        and not any(local.startswith(p) for p in SKIP_EMAIL_LOCAL)
        and len(local) >= 2
        and "." in domain
    )


def _schema_objs(soup: BeautifulSoup) -> list:
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(tag.string or "")
            out.extend(d if isinstance(d, list) else [d])
        except Exception:
            pass
    return out


def _clean_text(html: str) -> str:
    """Extract readable body text using readability-lxml or plain BS4."""
    if HAS_READABILITY and html:
        try:
            soup = BeautifulSoup(Document(html).summary(), "lxml")
            return re.sub(r'\s+', ' ', soup.get_text(" ", strip=True)).strip()
        except Exception:
            pass
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "nav", "noscript"]):
        t.decompose()
    return re.sub(r'\s+', ' ', soup.get_text(" ", strip=True)).strip()


async def _pw_get(url: str) -> str:
    async with _sem:
        page = await _browser.new_page()
        try:
            await page.goto(url, timeout=12000, wait_until="domcontentloaded")
            await page.wait_for_timeout(800)
            return await page.content()
        except Exception:
            return ""
        finally:
            await page.close()


def _req_get(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
        return r.text if r.ok else ""
    except Exception:
        return ""


async def _get(url: str) -> str:
    if _browser:
        return await _pw_get(url)
    return await asyncio.get_event_loop().run_in_executor(None, _req_get, url)


async def scrape_lead(lead: dict) -> dict:
    """
    Visit homepage + about/team/contact pages for one business.
    Returns combined scraped data.
    """
    raw = (lead.get("website") or "").strip()
    if not raw:
        return {}
    base = ("https://" + raw if not raw.startswith("http") else raw).rstrip("/")

    all_html = all_text = footer = desc = ""
    schemas: list = []
    visited: set  = set()

    for path in PAGE_PATHS:
        url = base if path == "/" else f"{base}{path}"
        if url in visited:
            continue
        visited.add(url)
        html = await _get(url)
        if not html or len(html) < 300:
            continue
        soup      = BeautifulSoup(html, "lxml")
        all_html += html
        all_text += " " + _clean_text(html)
        schemas.extend(_schema_objs(soup))
        if not footer:
            ft = soup.find("footer")
            if ft:
                footer = re.sub(r'\s+', ' ', ft.get_text(" ", strip=True))[:800]
        if not desc:
            for attrs in ({"name": "description"}, {"property": "og:description"}):
                tag = soup.find("meta", attrs=attrs)
                if tag and tag.get("content"):
                    desc = tag["content"].strip()
                    break

    # Emails
    raw_e = [e.lower() for e in EMAIL_RE.findall(all_html) if _valid_email(e.lower())]
    seen_e: set = set()
    emails: list = []
    for e in raw_e:
        if e not in seen_e:
            seen_e.add(e)
            emails.append(e)
    emails.sort(key=lambda e: 0 if e.split("@")[0] in {"contact","info","hello","mail","hi"} else 1)

    # Phones
    phones: list = []
    seen_p: set  = set()
    for p in PHONE_RE.findall(all_html):
        p = re.sub(r'\s+', ' ', p.strip())
        d = re.sub(r'\D', '', p)[-10:]
        if len(d) == 10 and d not in seen_p:
            seen_p.add(d)
            phones.append(p)

    # Social media
    social: dict = {}
    for platform, regex in SOCIAL_RE.items():
        for m in regex.finditer(all_html):
            h = m.group(1).strip("/").split("?")[0]
            skip = SKIP_HANDLES.get(platform, set())
            if h and h.lower() not in skip and len(h) > 1:
                if platform == "tiktok":
                    social[platform] = f"https://www.tiktok.com/@{h}"
                elif platform == "twitter":
                    social["twitter"] = f"https://twitter.com/{h}"
                else:
                    social[platform] = f"https://www.{platform}.com/{h}"
                break

    return {
        "clean_text":  re.sub(r'\s+', ' ', all_text).strip()[:8000],
        "schema_data": schemas[:8],
        "emails":      emails[:6],
        "phones":      phones[:4],
        "social":      social,
        "footer":      footer,
        "description": desc,
    }


async def _maybe(lead: dict) -> dict:
    return await scrape_lead(lead) if lead.get("website") else {}


async def scrape_all(leads: list) -> list:
    """Parallel scrape for all leads. Returns list of scraped-data dicts (same order)."""
    return list(await asyncio.gather(*[_maybe(l) for l in leads]))
