"""One Chromium browser + context for a whole scraping run.

WHY: launching a fresh browser per page (the old behaviour) means every request
arrives with an empty cookie jar and a new fingerprint — the strongest bot
signal we were sending. Residential proxies also bill per GB, so we drop images.
"""

import logging

from playwright.async_api import Browser, BrowserContext, Page, Playwright, Route, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.core.marketplace import MarketplaceConfig
from app.core.proxy_manager import ProxyManager
from app.scraping.block_detection import PageVerdict, classify_page
from app.scraping.pacing import pacer_for
from app.scraping.persona import Persona, build_persona

logger = logging.getLogger(__name__)

_BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}
MAX_ROTATIONS_PER_SESSION = 3

# How long to wait for the page's initial HTML to load before giving up.
PAGE_LOAD_TIMEOUT_MS = 30_000

# How much of the page body to sample when classifying a soft-block/captcha page.
BODY_SAMPLE_CHARS = 4_000


def should_block_request(resource_type: str, url: str) -> bool:
    """Drop bandwidth-heavy resources we never parse. Captcha images are kept."""
    # WHY: if we ever add a solver it needs the challenge image, so this one
    # resource type is let through even though images are normally blocked.
    if "/captcha/" in url:
        return False
    return resource_type in _BLOCKED_RESOURCE_TYPES


class BrowserSession:
    """Owns one Playwright browser + context for a whole scraping run."""

    def __init__(self, marketplace: MarketplaceConfig, proxy_manager: ProxyManager, site: str = "amazon"):
        self.marketplace = marketplace
        self.proxy_manager = proxy_manager
        self.site = site
        self.rotations = 0
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._proxy_conf: dict = {}
        self.persona: Persona | None = None

    async def __aenter__(self) -> "BrowserSession":
        self._pw = await async_playwright().start()
        try:
            await self._open()
        except BaseException:
            # NOTE: if _open() fails partway (e.g. browser launched but context
            # creation raised) we must not leak the browser process or the driver.
            await self._close()
            await self._pw.stop()
            raise
        return self

    async def __aexit__(self, *_exc) -> None:
        await self._close()
        if self._pw:
            await self._pw.stop()

    async def _open(self) -> None:
        """Launch a browser behind the current proxy and attach a fresh persona + request filter."""
        self._proxy_conf = self.proxy_manager.get_playwright_proxy()
        launch_kwargs = {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--no-sandbox"],
        }
        if self._proxy_conf.get("server"):
            launch_kwargs["proxy"] = self._proxy_conf
        self._browser = await self._pw.chromium.launch(**launch_kwargs)
        self.persona = build_persona(self._browser.version, self.marketplace)
        # NOTE: routing (below) disables Playwright's HTTP cache, and a service worker
        # can serve requests without ever going through our route handler — blocking
        # service workers keeps should_block_request() actually effective.
        self._context = await self._browser.new_context(
            user_agent=self.persona.user_agent,
            viewport=self.persona.viewport,
            locale=self.persona.locale,
            timezone_id=self.persona.timezone_id,
            extra_http_headers={"Accept-Language": self.persona.accept_language},
            ignore_https_errors=True,
            service_workers="block",
        )
        await self._context.add_init_script(self.persona.init_script())
        await self._context.route("**/*", self._route)

    async def _route(self, route: Route) -> None:
        """Playwright request interceptor: abort blocked resource types, let everything else through."""
        request = route.request
        if should_block_request(request.resource_type, request.url):
            await route.abort()
        else:
            await route.continue_()

    async def _close(self) -> None:
        """Close the context and browser if they are open. Safe to call even if _open() never ran."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        self._context = self._browser = None

    @property
    def proxy_label(self) -> str | None:
        """The current proxy's server address, or None when running direct (no proxy)."""
        return self._proxy_conf.get("server") or None

    async def rotate(self) -> None:
        """Abandon the current proxy session + persona and start over. Raises after MAX_ROTATIONS_PER_SESSION."""
        self.rotations += 1
        if self.rotations > MAX_ROTATIONS_PER_SESSION:
            raise RuntimeError(f"Blocked {self.rotations} times in one session; giving up")
        # WHY: marking a proxy failed only changes behaviour in free mode, where
        # ProxyManager skips failed servers next time. Paid providers already get a
        # brand-new random session id on every get_next() call, so this is a no-op
        # safety net for them, not the mechanism that actually rotates the identity.
        if self._proxy_conf.get("username"):
            self.proxy_manager.mark_failed(self._proxy_conf["username"])
        elif self._proxy_conf.get("server"):
            self.proxy_manager.mark_failed(self._proxy_conf["server"])
        logger.warning("Rotating browser session (%d/%d)", self.rotations, MAX_ROTATIONS_PER_SESSION)
        await self._close()
        await self._open()

    async def load(self, url: str, expected_selector: str, wait_ms: int = 15_000) -> tuple[Page, PageVerdict]:
        """Open url in a new tab after pacing; return the page and what kind of page it is.

        expected_selector must be specific to this page's real content (e.g. "#productTitle"),
        not a generic element that would also appear on a captcha or error page — otherwise
        every page looks "ok". wait_for_selector only succeeds once the element is visible,
        not merely present in the DOM.
        """
        if self._context is None:
            raise RuntimeError(
                "BrowserSession.load() called with no open context; use `async with` (or the last rotate() failed)"
            )
        await pacer_for(self.site).wait_turn(self.marketplace.domain)
        page = await self._context.new_page()
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
            verdict = await self._classify_loaded_page(page, response, expected_selector, wait_ms)
        except BaseException:
            # NOTE: the page is only ever handed to the caller on success. On any
            # failure (timeout, proxy error, page crash) close the tab ourselves —
            # nothing else will.
            await page.close()
            raise
        return page, verdict

    async def _classify_loaded_page(self, page: Page, response, expected_selector: str, wait_ms: int) -> PageVerdict:
        """Wait for the expected content, then classify the page as ok/captcha/soft_block/server_error."""
        found = True
        try:
            await page.wait_for_selector(expected_selector, timeout=wait_ms)
        except PlaywrightTimeoutError:
            found = False
        title = await page.title()
        body = "" if found else (await page.locator("body").inner_text())[:BODY_SAMPLE_CHARS]
        return classify_page(response.status if response else None, title, body, found)
