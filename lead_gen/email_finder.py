import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from lead_gen import config

console = Console()

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

SOCIAL_REGEX = {
    "instagram": re.compile(r'instagram\.com/(?!p/|reel/|stories/|explore/|accounts/|share)([A-Za-z0-9._]{1,40})', re.IGNORECASE),
    "facebook":  re.compile(r'facebook\.com/(?!sharer|share|plugins|tr/|dialog/|events/|groups/)([A-Za-z0-9._\-]{3,})', re.IGNORECASE),
    "tiktok":    re.compile(r'tiktok\.com/@?([A-Za-z0-9._]{2,40})', re.IGNORECASE),
}

SKIP_HANDLES = {
    "instagram": {"p", "reel", "stories", "explore", "accounts", "share", "sharer", "photo", "tv"},
    "facebook":  {"sharer", "share", "plugins", "tr", "dialog", "groups", "events", "pages", "photo"},
    "tiktok":    {"share", "discover", "trending", "following", "foryou"},
}

SKIP_DOMAINS = {
    "example.com", "sentry.io", "wixpress.com", "squarespace.com",
    "wordpress.com", "godaddy.com", "schema.org", "w3.org",
    "googleapis.com", "cloudflare.com", "facebook.com", "twitter.com",
    "instagram.com", "youtube.com", "linkedin.com", "yelp.com",
    "yellowpages.com", "google.com", "apple.com", "microsoft.com",
}

SKIP_PREFIXES = {
    "noreply", "no-reply", "donotreply", "mailer-daemon",
    "bounce", "postmaster", "webmaster",
}

# Ordered by most likely to have useful content — stop at first hit
CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/about-us"]
ABOUT_PATHS   = ["/about", "/about-us", "/our-story", "/our-team", "/team", "/who-we-are"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Owner / year extraction ────────────────────────────────────────────
_NAME_PATTERNS = [
    re.compile(r'(?:founded|owned|started|established|created|run)\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', re.IGNORECASE),
    re.compile(r'(?:owner|founder|president|ceo|principal|operator|proprietor)\s*[:\-–]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', re.IGNORECASE),
    re.compile(r"(?:I'?m|I am|my name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.IGNORECASE),
    re.compile(r'[Mm]eet\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*,?\s*(?:owner|founder|president|ceo)', re.IGNORECASE),
    re.compile(r'"(?:name|givenName)"\s*:\s*"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})"'),
]

_YEAR_PATTERNS = [
    re.compile(r'(?:founded|established|est\.?|incorporated|started|opened|began)\s+(?:in\s+)?((?:19|20)\d{2})', re.IGNORECASE),
    re.compile(r'(?:since|serving since|in business since)\s+((?:19|20)\d{2})', re.IGNORECASE),
    re.compile(r'(?:©|&copy;|copyright)\s*((?:19|20)\d{2})'),
    re.compile(r'(\d{1,2})\+?\s+years?\s+(?:of\s+)?(?:experience|in\s+business|serving)', re.IGNORECASE),
]

CURRENT_YEAR = 2026
WORKERS      = 6   # parallel website visits


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return url.rstrip("/")


def _is_valid_email(email: str) -> bool:
    if "@" not in email:
        return False
    local, domain = email.lower().rsplit("@", 1)
    if domain in SKIP_DOMAINS or any(local.startswith(p) for p in SKIP_PREFIXES):
        return False
    return len(local) >= 2 and "." in domain


def _fetch(url: str, timeout: int = 7) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.ok:
            return resp.text
    except Exception:
        pass
    return ""


def _best_email(html: str) -> str:
    raw   = EMAIL_REGEX.findall(html)
    valid = [e.lower() for e in raw if _is_valid_email(e.lower())]
    priority = [e for e in valid if e.split("@")[0] in {"contact", "info", "hello", "email", "mail", "hi"}]
    return (priority or valid or [""])[0]


def _extract_social(html: str) -> dict:
    links = {}
    for platform, regex in SOCIAL_REGEX.items():
        for m in regex.finditer(html):
            handle = m.group(1).strip("/").split("?")[0].split("&")[0]
            if handle and handle.lower() not in SKIP_HANDLES[platform] and len(handle) > 1:
                links[platform] = (
                    f"https://www.tiktok.com/@{handle}" if platform == "tiktok"
                    else f"https://www.{platform}.com/{handle}"
                )
                break
    return links


def _extract_owner(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    for p in _NAME_PATTERNS:
        m = p.search(text)
        if m:
            name = m.group(1).strip()
            if len(name) <= 40 and not re.search(r'\d', name) and not name.isupper():
                return name
    return ""


def _extract_year(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    for p in _YEAR_PATTERNS:
        m = p.search(text)
        if m:
            val = m.group(1).strip()
            if re.fullmatch(r'(?:19|20)\d{2}', val):
                year = int(val)
                if 1900 < year <= CURRENT_YEAR:
                    return str(CURRENT_YEAR - year)
            else:
                num = int(val)
                if 1 <= num <= 100:
                    return str(num)
    return ""


def _find_for_lead(lead: dict) -> dict:
    """Visit a lead's website and extract email, social, owner name, years."""
    website = _normalize_url(lead.get("website", ""))
    empty = {"email": "", "instagram": "", "facebook": "", "tiktok": "",
             "owner_name": "", "years_in_business": ""}
    if not website:
        return empty

    already_has_owner = bool(lead.get("owner_name"))
    already_has_years = bool(lead.get("years_in_business"))

    all_html   = ""
    about_html = ""
    email      = ""

    # Homepage
    html = _fetch(website)
    all_html += html
    email = _best_email(html)

    # One contact/about page if still no email
    if not email:
        for path in CONTACT_PATHS:
            url  = urljoin(website + "/", path.lstrip("/"))
            html = _fetch(url)
            if not html:
                continue
            all_html += html
            email = _best_email(html)
            if email:
                break

    # One about page for owner / year (skip if already filled from Google enrichment)
    if not already_has_owner or not already_has_years:
        for path in ABOUT_PATHS:
            url  = urljoin(website + "/", path.lstrip("/"))
            html = _fetch(url)
            if html and len(html) > 500:
                about_html = html
                break

    combined = about_html or all_html
    owner = "" if already_has_owner else _extract_owner(combined)
    years = "" if already_has_years else _extract_year(combined)

    social = _extract_social(all_html)
    return {
        "email":             email,
        "instagram":         social.get("instagram", ""),
        "facebook":          social.get("facebook",  ""),
        "tiktok":            social.get("tiktok",    ""),
        "owner_name":        owner,
        "years_in_business": years,
    }


def find_emails(leads: list[dict]) -> list[dict]:
    with_site = [l for l in leads if l.get("website")]
    no_site   = [l for l in leads if not l.get("website")]

    emails_found = social_found = owners_found = years_found = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"Visiting {len(with_site)} sites ({WORKERS} at a time)...",
            total=len(with_site),
        )

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(_find_for_lead, lead): lead for lead in with_site}
            for future in as_completed(futures):
                lead   = futures[future]
                result = future.result()

                lead["email"]     = result["email"]
                lead["instagram"] = result["instagram"]
                lead["facebook"]  = result["facebook"]
                lead["tiktok"]    = result["tiktok"]

                if not lead.get("owner_name") and result["owner_name"]:
                    lead["owner_name"] = result["owner_name"]
                if not lead.get("years_in_business") and result["years_in_business"]:
                    lead["years_in_business"] = result["years_in_business"]

                if result["email"]:      emails_found += 1
                if any([result["instagram"], result["facebook"], result["tiktok"]]): social_found += 1
                if result["owner_name"]: owners_found += 1
                if result["years_in_business"]: years_found += 1

                progress.update(task, description=f"[dim]{lead['name'][:35]}[/dim]")
                progress.advance(task)

    for lead in no_site:
        lead.update({"email": "", "instagram": "", "facebook": "", "tiktok": ""})

    console.print(
        f"  Found [green]{emails_found}[/green] emails, "
        f"[magenta]{social_found}[/magenta] social profiles, "
        f"[yellow]{owners_found}[/yellow] owner names, "
        f"[blue]{years_found}[/blue] founding years "
        f"from [cyan]{len(with_site)}[/cyan] sites checked"
    )
    return leads
