import re
import time
import requests
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

# Pages checked for email / social media
CONTACT_PATHS = [
    "/contact", "/contact-us", "/contact_us", "/contactus",
    "/about", "/about-us", "/reach-us", "/get-in-touch",
]

# Pages checked for owner name / founding year
ABOUT_PATHS = [
    "/about", "/about-us", "/about_us", "/our-story", "/our-team",
    "/meet-the-team", "/team", "/who-we-are", "/company",
    "/founders", "/owner",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Name extraction patterns ──────────────────────────────────────────────────
# Captures a 2-4 word proper-noun name following common ownership/intro phrases
_NAME_PATTERNS = [
    # "Founded by John Smith" / "owned by Jane Doe"
    re.compile(r'(?:founded|owned|started|established|created|run)\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', re.IGNORECASE),
    # "Owner: John Smith" / "CEO: John Smith"
    re.compile(r'(?:owner|founder|president|ceo|principal|operator|proprietor)\s*[:\-–]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', re.IGNORECASE),
    # "Hi, I'm John Smith" / "I am Jane Doe"
    re.compile(r"(?:I'?m|I am|my name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.IGNORECASE),
    # "Meet John Smith, owner" — name first, role second
    re.compile(r'[Mm]eet\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*,?\s*(?:owner|founder|president|ceo)', re.IGNORECASE),
    # JSON-LD / schema.org  "name": "John Smith"
    re.compile(r'"(?:name|givenName|familyName)"\s*:\s*"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})"'),
]

# ── Founding year extraction patterns ────────────────────────────────────────
_YEAR_PATTERNS = [
    # "Founded in 1998" / "Established in 2001" / "Est. 2003"
    re.compile(r'(?:founded|established|est\.?|incorporated|started|opened|began)\s+(?:in\s+)?((?:19|20)\d{2})', re.IGNORECASE),
    # "Since 1998" / "serving since 2005"
    re.compile(r'(?:since|serving since|in business since)\s+((?:19|20)\d{2})', re.IGNORECASE),
    # "© 1998" (earliest copyright year often = founding)
    re.compile(r'(?:©|&copy;|copyright)\s*((?:19|20)\d{2})'),
    # "over 20 years" / "25+ years of experience"
    re.compile(r'(\d{1,2})\+?\s+years?\s+(?:of\s+)?(?:experience|in\s+business|serving)', re.IGNORECASE),
]

CURRENT_YEAR = 2026


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return url.rstrip("/")


def _is_valid_email(email: str) -> bool:
    if "@" not in email:
        return False
    local, domain = email.lower().rsplit("@", 1)
    if domain in SKIP_DOMAINS:
        return False
    if any(local.startswith(p) for p in SKIP_PREFIXES):
        return False
    if len(local) < 2 or "." not in domain:
        return False
    return True


def _fetch(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.ok:
            return resp.text
    except Exception:
        pass
    return ""


def _extract_emails(html: str) -> list[str]:
    raw = EMAIL_REGEX.findall(html)
    seen: set[str] = set()
    valid: list[str] = []
    for e in raw:
        e_lower = e.lower()
        if e_lower not in seen and _is_valid_email(e_lower):
            seen.add(e_lower)
            valid.append(e_lower)

    def _priority(e: str) -> int:
        local = e.split("@")[0]
        return 0 if local in {"contact", "info", "hello", "email", "mail", "hi"} else 1

    valid.sort(key=_priority)
    return valid


def _extract_social_links(html: str) -> dict:
    links = {}
    for platform, regex in SOCIAL_REGEX.items():
        for match in regex.finditer(html):
            handle = match.group(1).strip("/").split("?")[0].split("&")[0]
            if handle and handle.lower() not in SKIP_HANDLES[platform] and len(handle) > 1:
                if platform == "tiktok":
                    links[platform] = f"https://www.tiktok.com/@{handle}"
                else:
                    links[platform] = f"https://www.{platform}.com/{handle}"
                break
    return links


def _extract_owner_name(html: str) -> str:
    """Try to pull an owner / founder name from page HTML."""
    # Strip tags to reduce noise before regex matching
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    for pattern in _NAME_PATTERNS:
        m = pattern.search(text)
        if m:
            name = m.group(1).strip()
            # Reject obvious non-names (all caps, very long, contains digits)
            if len(name) <= 40 and not re.search(r'\d', name) and not name.isupper():
                return name
    return ""


def _extract_years_in_business(html: str) -> str:
    """Try to pull founding year or years-in-business from page HTML."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    for pattern in _YEAR_PATTERNS:
        m = pattern.search(text)
        if m:
            val = m.group(1).strip()
            # If it looks like a year (4 digits), convert to years-in-business
            if re.fullmatch(r'(?:19|20)\d{2}', val):
                year = int(val)
                if 1900 < year <= CURRENT_YEAR:
                    return str(CURRENT_YEAR - year)
            else:
                # It's already a "X years" number
                num = int(val)
                if 1 <= num <= 100:
                    return str(num)
    return ""


def _find_for_lead(lead: dict) -> dict:
    website = _normalize_url(lead.get("website", ""))
    if not website:
        return {"email": "", "instagram": "", "facebook": "", "tiktok": "",
                "owner_name": "", "years_in_business": ""}

    all_html   = ""
    about_html = ""
    email      = ""

    # ── Homepage ──────────────────────────────────────────────────────
    html = _fetch(website)
    all_html += html
    emails = _extract_emails(html)
    if emails:
        email = emails[0]

    # ── Contact / About pages (email + social) ────────────────────────
    if not email:
        for path in CONTACT_PATHS:
            url  = urljoin(website + "/", path.lstrip("/"))
            html = _fetch(url)
            all_html += html
            emails = _extract_emails(html)
            if emails:
                email = emails[0]
                break
            time.sleep(0.3)

    # ── About pages (owner name + years) ─────────────────────────────
    # Try /about-us style pages; use homepage HTML as fallback
    for path in ABOUT_PATHS:
        url  = urljoin(website + "/", path.lstrip("/"))
        html = _fetch(url)
        if html and len(html) > 500:   # ignore empty/redirect pages
            about_html += html
            break
        time.sleep(0.2)

    combined = about_html or all_html
    owner_name       = _extract_owner_name(combined)
    years_in_business = _extract_years_in_business(combined)

    social = _extract_social_links(all_html)
    return {
        "email":            email,
        "instagram":        social.get("instagram", ""),
        "facebook":         social.get("facebook",  ""),
        "tiktok":           social.get("tiktok",    ""),
        "owner_name":       owner_name,
        "years_in_business": years_in_business,
    }


def find_emails(leads: list[dict]) -> list[dict]:
    with_site = [l for l in leads if l.get("website")]
    no_site   = [l for l in leads if not l.get("website")]

    emails_found  = 0
    social_found  = 0
    owners_found  = 0
    years_found   = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Checking websites...", total=len(with_site))
        for i, lead in enumerate(with_site):
            progress.update(task, description=f"[dim]{lead['name'][:35]}[/dim]")
            result = _find_for_lead(lead)

            lead["email"]     = result["email"]
            lead["instagram"] = result["instagram"]
            lead["facebook"]  = result["facebook"]
            lead["tiktok"]    = result["tiktok"]

            # Only fill in if the field is currently empty
            if not lead.get("owner_name") and result["owner_name"]:
                lead["owner_name"] = result["owner_name"]
            if not lead.get("years_in_business") and result["years_in_business"]:
                lead["years_in_business"] = result["years_in_business"]

            if result["email"]:
                emails_found += 1
            if any([result["instagram"], result["facebook"], result["tiktok"]]):
                social_found += 1
            if result["owner_name"]:
                owners_found += 1
            if result["years_in_business"]:
                years_found += 1

            progress.advance(task)
            if i < len(with_site) - 1:
                time.sleep(0.5)

    for lead in no_site:
        lead["email"]     = ""
        lead["instagram"] = ""
        lead["facebook"]  = ""
        lead["tiktok"]    = ""

    console.print(
        f"  Found [green]{emails_found}[/green] emails, "
        f"[magenta]{social_found}[/magenta] social profiles, "
        f"[yellow]{owners_found}[/yellow] owner names, "
        f"[blue]{years_found}[/blue] founding years "
        f"from [cyan]{len(with_site)}[/cyan] sites checked"
    )
    return leads
