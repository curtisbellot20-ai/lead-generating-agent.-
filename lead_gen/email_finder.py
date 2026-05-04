import re
import time
import requests
from urllib.parse import urljoin
from lead_gen import config

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Domains that show up in page source but are never real business emails
SKIP_DOMAINS = {
    "example.com", "sentry.io", "wixpress.com", "squarespace.com",
    "wordpress.com", "godaddy.com", "schema.org", "w3.org",
    "googleapis.com", "cloudflare.com", "facebook.com", "twitter.com",
    "instagram.com", "youtube.com", "linkedin.com", "yelp.com",
    "yellowpages.com", "google.com", "apple.com", "microsoft.com",
}

# Local parts that are never real contact emails
SKIP_PREFIXES = {
    "noreply", "no-reply", "donotreply", "mailer-daemon",
    "bounce", "postmaster", "webmaster",
}

# Contact pages to try in order
CONTACT_PATHS = [
    "/contact",
    "/contact-us",
    "/contact_us",
    "/contactus",
    "/about",
    "/about-us",
    "/reach-us",
    "/get-in-touch",
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

    # Prioritise contact/info/hello over generic addresses
    def _priority(e: str) -> int:
        local = e.split("@")[0]
        return 0 if local in {"contact", "info", "hello", "email", "mail", "hi", "hello"} else 1

    valid.sort(key=_priority)
    return valid


def _find_for_lead(lead: dict) -> str:
    website = _normalize_url(lead.get("website", ""))
    if not website:
        return ""

    # 1. Try the homepage
    html = _fetch(website)
    emails = _extract_emails(html)
    if emails:
        return emails[0]

    # 2. Try common contact/about pages
    for path in CONTACT_PATHS:
        url = urljoin(website + "/", path.lstrip("/"))
        html = _fetch(url)
        emails = _extract_emails(html)
        if emails:
            return emails[0]
        time.sleep(0.3)

    return ""


def find_emails(leads: list[dict]) -> list[dict]:
    with_site  = [l for l in leads if l.get("website")]
    no_site    = [l for l in leads if not l.get("website")]

    print(f"  [Email Finder] Checking {len(with_site)} business websites...")

    found = 0
    for i, lead in enumerate(with_site):
        email = _find_for_lead(lead)
        lead["email"] = email
        if email:
            found += 1
            print(f"  [Email Finder] ✓ {lead['name']}: {email}")
        else:
            print(f"  [Email Finder] - {lead['name']}: not found")
        if i < len(with_site) - 1:
            time.sleep(0.5)

    for lead in no_site:
        lead["email"] = ""

    total = len(with_site)
    print(f"  [Email Finder] Done — {found}/{total} emails found")
    return leads
