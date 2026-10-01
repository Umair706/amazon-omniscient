"""Scrapes Made-in-China.com for supplier FOB prices and MOQ.

WHY this exists alongside the 1688 scraper: 1688 forces a Taobao login to view any
search results, so anonymous scraping only ever reaches the login wall. Made-in-China
serves the same China-sourced products to anonymous visitors, in English, with FOB
prices already in USD — so it needs no login, no translation, and no CNY conversion.
"""

import asyncio
import logging
import re
from urllib.parse import quote

from playwright.async_api import Browser, Page, async_playwright

logger = logging.getLogger(__name__)

# Made-in-China serves search results at this path. F1/1 means "page 1, default filters".
_SEARCH_URL = "https://www.made-in-china.com/multi-search/{keyword}/F1/1.html"

# Each result is one of these blocks. The site keeps this class stable across layouts.
_CARD_SELECTOR = ".prod-info"

# A card's price looks like "US$1.24-1.34" or a single "US$7.00". Captures low and optional high.
_PRICE_RE = re.compile(r"US\$\s*([\d,]+(?:\.\d+)?)(?:\s*-\s*([\d,]+(?:\.\d+)?))?")

# MOQ looks like "3,000 Pieces" or "500 Sets". Captures the number before the unit word.
_MOQ_RE = re.compile(r"([\d,]+)\s*(?:Pieces?|Sets?|Units?|Pairs?|Bags?|Boxes?|PCS)", re.IGNORECASE)

# A card showing any of these badges is a vetted supplier, not an unverified listing.
_VERIFIED_RE = re.compile(r"Audited Supplier|Diamond Member|Verified", re.IGNORECASE)

# One scraped card, matching the dict shape SupplierScraper.search_suppliers returns.
# NOTE: price_min / price_max are already in USD here (1688's are in CNY).
_EMPTY_RECORD = {
    "supplier_name": None, "product_title": None, "price_min": None, "price_max": None,
    "moq": None, "location": None, "years_in_business": None, "is_verified": False,
    "transaction_count": None, "response_rate": None, "product_url": None, "image_url": None,
}


def _to_number(raw: str | None) -> str | None:
    """Strip thousands commas so '3,000' can become a number."""
    return raw.replace(",", "") if raw else None


def parse_price_usd(card_text: str) -> tuple[float | None, float | None]:
    """Return (min, max) FOB price in USD from a card's text. A single price gives (p, p)."""
    match = _PRICE_RE.search(card_text or "")
    if not match:
        return (None, None)
    low = float(_to_number(match.group(1)))
    high = float(_to_number(match.group(2))) if match.group(2) else low
    return (low, high)


def parse_moq(card_text: str) -> int | None:
    """Return the minimum order quantity from a card's text, or None if not stated."""
    match = _MOQ_RE.search(card_text or "")
    return int(_to_number(match.group(1))) if match else None


def build_supplier_record(raw_card: dict) -> dict:
    """Turn one raw card ({title, url, company, text}) into a supplier record with USD prices."""
    price_min, price_max = parse_price_usd(raw_card.get("text", ""))
    record = dict(_EMPTY_RECORD)
    record.update(
        supplier_name=raw_card.get("company"),
        product_title=raw_card.get("title"),
        price_min=price_min,
        price_max=price_max,
        moq=parse_moq(raw_card.get("text", "")),
        is_verified=bool(_VERIFIED_RE.search(raw_card.get("text", ""))),
        product_url=raw_card.get("url"),
    )
    return record


class MadeInChinaScraper:
    """Scrapes Made-in-China.com search results. No login, prices in USD."""

    _MAX_RETRIES = 2

    def __init__(self, proxy_manager=None, pacer=None):
        self.proxy_manager = proxy_manager
        self.pacer = pacer

    async def _launch_browser(self, playwright) -> Browser:
        launch_kwargs = {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--no-sandbox"],
        }
        if self.proxy_manager is not None:
            launch_kwargs["proxy"] = self.proxy_manager.get_playwright_proxy()
        return await playwright.chromium.launch(**launch_kwargs)

    async def _new_page(self, browser: Browser) -> Page:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-US",
            viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        return page

    async def _extract_raw_cards(self, page: Page, max_results: int) -> list[dict]:
        """Read the title, product URL, company and full text of each result card."""
        return await page.evaluate(
            """(max) => Array.from(document.querySelectorAll('.prod-info')).slice(0, max).map(c => {
                const a = c.querySelector('h2 a, .product-name a, a.product-name');
                const comp = c.querySelector('.company-name, [class*=company]');
                return {
                    title: a ? (a.innerText || '').trim() : null,
                    url: a ? a.getAttribute('href') : null,
                    company: comp ? (comp.innerText || '').trim() : null,
                    text: (c.innerText || '').trim(),
                };
            })""",
            max_results,
        )

    async def search_suppliers(self, keyword: str, max_results: int = 10) -> list[dict]:
        """Return up to *max_results* supplier records for *keyword*. Prices are in USD."""
        url = _SEARCH_URL.format(keyword=quote(keyword))
        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                return await self._search_with_retries(browser, keyword, url, max_results)
            finally:
                await browser.close()

    async def _search_with_retries(self, browser, keyword, url, max_results) -> list[dict]:
        for attempt in range(1, self._MAX_RETRIES + 1):
            page = await self._new_page(browser)
            try:
                if self.pacer:
                    await self.pacer.wait_turn("made-in-china.com")
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await asyncio.sleep(5)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(2)

                raw_cards = await self._extract_raw_cards(page, max_results)
                records = [build_supplier_record(c) for c in raw_cards if c.get("text")]
                priced = [r for r in records if r["price_min"] is not None]
                if priced:
                    logger.info("Made-in-China: %d priced suppliers for '%s'", len(priced), keyword)
                    return priced
                logger.warning("Made-in-China: no priced cards for '%s' (attempt %d)", keyword, attempt)
            except Exception as e:
                logger.warning("Made-in-China scrape failed for '%s' (attempt %d): %s", keyword, attempt, e)
            finally:
                await page.close()
        return []
