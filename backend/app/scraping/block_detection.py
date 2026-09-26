"""Classify a loaded Amazon page so callers can rotate proxies instead of parsing an empty page."""

from typing import Literal
from urllib.parse import urlparse

# "wrong_marketplace": Amazon redirected us to another country's store (for example
# amazon.com -> amazon.com.au when the request comes from an Australian IP). The page
# is a real product page, just for the wrong market, so no parser would notice.
PageVerdict = Literal["ok", "captcha", "soft_block", "server_error", "wrong_marketplace"]

# Phrases Amazon puts on its automated-traffic challenge page.
_CAPTCHA_MARKERS = (
    "enter the characters you see below",
    "api-services-support@amazon.com",
    "validatecaptcha",
)
_CAPTCHA_TITLES = ("robot check", "bot check")


def is_on_marketplace(url: str, marketplace_domain: str) -> bool:
    """True if url is served by marketplace_domain (or one of its subdomains, like www.)."""
    host = (urlparse(url).hostname or "").lower()
    domain = marketplace_domain.lower()
    return host == domain or host.endswith("." + domain)


def classify_page(status: int | None, title: str, body_text: str, expected_selector_found: bool) -> PageVerdict:
    """Return what kind of page we got. 'soft_block' = 200 OK but the content we wanted is absent."""
    lowered_title = (title or "").lower()
    lowered_body = (body_text or "").lower()
    if any(t in lowered_title for t in _CAPTCHA_TITLES) or any(m in lowered_body for m in _CAPTCHA_MARKERS):
        return "captcha"
    if status is not None and status >= 500:
        return "server_error"
    if not expected_selector_found:
        return "soft_block"
    return "ok"
