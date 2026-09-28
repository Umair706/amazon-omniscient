"""ScraperService._load: rotate on a block or a navigation error, give up at the rotation cap."""

import pytest
from playwright.async_api import Error as PlaywrightError

import app.services.scraper_service as scraper_service_module
from app.core.exceptions import ScrapingError
from app.core.proxy_manager import ProxyManager
from app.scraping.session import MAX_ROTATIONS_PER_SESSION
from app.services.scraper_service import ScraperService

URL = "https://www.amazon.com/dp/B0TEST0001"
SELECTOR = "#productTitle"
PROXY_DOWN = PlaywrightError("net::ERR_PROXY_CONNECTION_FAILED")


class FakePage:
    def __init__(self, name: str):
        self.name = name
        self.closed = False

    async def close(self):
        self.closed = True


class FakeSession:
    """Stands in for BrowserSession. Each load() returns the next scripted verdict, or raises a scripted error."""

    def __init__(self, script: list):
        self.script = list(script)
        self.rotations = 0
        self.pages: list[FakePage] = []
        # WHY: _record_load_event reads this when telemetry is on; a fixed value is
        # enough since these tests only care what verdict gets recorded, not the label.
        self.proxy_label = "http://fake-proxy:8080"

    async def load(self, url, selector):
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        page = FakePage(f"page-{len(self.pages) + 1}")
        self.pages.append(page)
        return page, step

    async def rotate(self):
        self.rotations += 1
        if self.rotations > MAX_ROTATIONS_PER_SESSION:
            raise RuntimeError(f"Blocked {self.rotations} times in one session; giving up")


def scraper_with(session: FakeSession) -> ScraperService:
    return ScraperService(proxy_manager=ProxyManager(provider="none"), marketplace="US", session=session)


async def test_ok_on_first_try_does_not_rotate():
    session = FakeSession(["ok"])
    page, verdict = await scraper_with(session)._load(URL, SELECTOR, "product")
    assert verdict == "ok"
    assert session.rotations == 0
    assert not page.closed


async def test_captcha_then_ok_rotates_once_and_returns_the_second_page():
    session = FakeSession(["captcha", "ok"])
    page, verdict = await scraper_with(session)._load(URL, SELECTOR, "product")
    assert verdict == "ok"
    assert session.rotations == 1
    assert page is session.pages[1]
    assert session.pages[0].closed


async def test_navigation_error_then_ok_rotates_once():
    session = FakeSession([PROXY_DOWN, "ok"])
    page, verdict = await scraper_with(session)._load(URL, SELECTOR, "product")
    assert verdict == "ok"
    assert session.rotations == 1


async def test_soft_block_is_returned_without_rotating():
    session = FakeSession(["soft_block"])
    _page, verdict = await scraper_with(session)._load(URL, SELECTOR, "product")
    assert verdict == "soft_block"
    assert session.rotations == 0


async def test_blocked_every_time_raises_scraping_error_naming_the_url():
    session = FakeSession(["captcha"] * (MAX_ROTATIONS_PER_SESSION + 1))
    with pytest.raises(ScrapingError, match="B0TEST0001"):
        await scraper_with(session)._load(URL, SELECTOR, "product")
    assert all(page.closed for page in session.pages)


async def test_records_one_event_per_attempt(monkeypatch):
    """A load that rotates once (captcha, then ok) records both verdicts, in order."""
    recorded_verdicts = []

    async def fake_record_scrape_event(_session_factory, **fields):
        recorded_verdicts.append(fields["verdict"])

    monkeypatch.setattr(scraper_service_module, "record_scrape_event", fake_record_scrape_event)

    session = FakeSession(["captcha", "ok"])
    scraper = ScraperService(
        proxy_manager=ProxyManager(provider="none"), marketplace="US", session=session,
        event_sink=object(),  # any truthy value — the fake above ignores it
    )
    await scraper._load(URL, SELECTOR, "product")

    assert recorded_verdicts == ["captcha", "ok"]


async def test_navigation_error_records_timeout_verdict(monkeypatch):
    """A PlaywrightError (proxy/tunnel failure) is recorded as verdict 'timeout', not left out."""
    recorded_verdicts = []

    async def fake_record_scrape_event(_session_factory, **fields):
        recorded_verdicts.append(fields["verdict"])

    monkeypatch.setattr(scraper_service_module, "record_scrape_event", fake_record_scrape_event)

    session = FakeSession([PROXY_DOWN, "ok"])
    scraper = ScraperService(
        proxy_manager=ProxyManager(provider="none"), marketplace="US", session=session,
        event_sink=object(),
    )
    await scraper._load(URL, SELECTOR, "product")

    assert recorded_verdicts == ["timeout", "ok"]


async def test_wrong_marketplace_fails_at_once_without_rotating():
    session = FakeSession(["wrong_marketplace"])
    with pytest.raises(ScrapingError) as raised:
        await scraper_with(session)._load(URL, SELECTOR, "product")
    assert "amazon.com redirected" in str(raised.value)
    assert "United States" in str(raised.value)
    assert session.rotations == 0
    assert session.pages[0].closed
