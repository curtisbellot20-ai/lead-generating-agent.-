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

CONTACT_PATHS = [
    "/contact", "/contact-us", "/contact_us", "/contactus",
    "/about", "/about-us", "/reach-us", "/get-in-touch",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


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


def _find_for_lead(lead: dict) -> dict:
    website = _normalize_url(lead.get("website", ""))
    if not website:
        return {"email": "", "instagram": "", "facebook": "", "tiktok": ""}

    all_html = ""
    email = ""

    # Check homepage first
    html = _fetch(website)
    all_html += html
    emails = _extract_emails(html)
    if emails:
        email = emails[0]

    # Check contact/about pages if no email yet
    if not email:
        for path in CONTACT_PATHS:
            url = urljoin(website + "/", path.lstrip("/"))
            html = _fetch(url)
            all_html += html
            emails = _extract_emails(html)
            if emails:
                email = emails[0]
                break
            time.sleep(0.3)

    social = _extract_social_links(all_html)
    return {
        "email":     email,
        "instagram": social.get("instagram", ""),
        "facebook":  social.get("facebook", ""),
        "tiktok":    social.get("tiktok", ""),
    }


def find_emails(leads: list[dict]) -> list[dict]:
    with_site = [l for l in leads if l.get("website")]
    no_site   = [l for l in leads if not l.get("website")]

    emails_found = 0
    social_found = 0

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
            if result["email"]:
                emails_found += 1
            if any([result["instagram"], result["facebook"], result["tiktok"]]):
                social_found += 1
            progress.advance(task)
            if i < len(with_site) - 1:
                time.sleep(0.5)

    for lead in no_site:
        lead["email"]     = ""
        lead["instagram"] = ""
        lead["facebook"]  = ""
        lead["tiktok"]    = ""

    console.print(
        f"  Found [green]{emails_found}[/green] emails and "
        f"[magenta]{social_found}[/magenta] social profiles "
        f"from [cyan]{len(with_site)}[/cyan] sites checked"
    )
    return leads
