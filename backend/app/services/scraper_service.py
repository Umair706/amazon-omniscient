"""Headless browser scraper for Amazon pages using Playwright."""

import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import quote_plus

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from app.core.exceptions import ScrapingError
from app.core.proxy_manager import ProxyManager
from app.scraping.block_detection import PageVerdict
from app.scraping.events import record_scrape_event
from app.scraping.page_cache import PageCache
from app.scraping.session import MAX_ROTATIONS_PER_SESSION, BrowserSession
from app.services.review_text import parse_helpful_votes, parse_review_date

logger = logging.getLogger(__name__)


def build_proxy_manager_from_settings() -> ProxyManager:
    """Return the ProxyManager described by the PROXY_* settings (env vars)."""
    from app.config import Settings

    settings = Settings()
    return ProxyManager(
        provider=settings.PROXY_PROVIDER or "none",
        host=settings.PROXY_HOST,
        port=settings.PROXY_PORT,
        username=settings.PROXY_USERNAME,
        password=settings.PROXY_PASSWORD,
    )

# fetch_autocomplete is a plain JSON call made outside the browser, so it has no
# browser persona to borrow a user agent from.
_AUTOCOMPLETE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_AUTOCOMPLETE_TIMEOUT_SECONDS = 10.0

# Elements that only exist when the page we asked for really rendered. A captcha
# or error page never has them, which is how BrowserSession tells the two apart.
_SEARCH_RESULT_SELECTOR = 'div[data-component-type="s-search-result"]'
_PRODUCT_TITLE_SELECTOR = "#productTitle"

# Review-count selectors. Their text can also be a star rating, so every
# match goes through ScraperService.parse_review_count_text.
_SERP_RATINGS_LINK_SELECTOR = 'a[aria-label*="ratings"]'
_SERP_REVIEW_COUNT_SELECTORS = (
    'a[href*="#customerReviews"]',
    'span[data-component-type="s-client-side-analytics"] span.a-size-base.s-underline-text',
    'a[href*="#customerReviews"] span.a-size-base',
    'span.a-size-base.s-underline-text',
    'a[data-hook="review-count"]',
)
# "#acrCustomerReviewCount" is the older template; the 2026 AU template only has the text span.
_PRODUCT_REVIEW_COUNT_SELECTORS = ("#acrCustomerReviewCount", "#acrCustomerReviewText")
_STAR_RATING_TEXT = re.compile(r"out of \d", re.IGNORECASE)
# Amazon abbreviates big counts on search pages: "(6.6K)".
_THOUSANDS_ABBREVIATION = re.compile(r"(\d+(?:\.\d+)?)\s*K\b", re.IGNORECASE)
_ONE_THOUSAND = 1000
_REVIEW_SELECTOR = 'div[data-hook="review"]'

# Verdicts that mean Amazon is blocking this proxy + persona. A fresh identity may get through.
_ROTATE_ON_VERDICTS = ("captcha", "server_error")

# scrape_events.site for every page this service loads — it only ever talks to Amazon.
_SITE_AMAZON = "amazon"

# scrape_events.verdict for a navigation error (proxy/tunnel failure, timeout). BrowserSession.load()
# never returns this verdict itself — it raises instead — so _load assigns it before recording.
_TIMEOUT_VERDICT = "timeout"

# Set on scrape_product_page's result when it was served from the page cache. Callers
# (the pipeline's BSR/price/stock snapshot step) read this to avoid re-stamping an
# up-to-24h-old value with today's timestamp.
FROM_CACHE_KEY = "from_cache"

# The buy box names the merchant. Older pages say "Ships from and sold by Amazon.com.au";
# the 2026 layout (#merchantInfoFeature_feature_div) says "Shipper / Seller  Amazon AU".
# Listings Amazon sells itself usually carry no seller-profile link, so seller_id alone misses them.
_MERCHANT_SELECTORS = (
    "#merchant-info", "#merchantInfoFeature_feature_div", "#sellerProfileTriggerId", "#tabular-buybox",
)
_SOLD_BY_AMAZON_MARKERS = ("sold by amazon", "seller amazon")

# How many brand labels on one search page we read when counting distinct brands.
_MAX_BRAND_LABELS_SCANNED = 48

# Review cards on the product page itself (the "Top reviews" section).
_PAGE_REVIEW_CARD_SELECTOR = (
    '#cm-cr-dp-review-list div[data-hook="review"], '
    '#reviewsMedley div[data-hook="review"], '
    'div[id^="customer_review-"]'
)
# WHY: the product page shows about 10-13 top reviews. 10 per ASIN is enough for the
# pain-point prompt and keeps one page from dominating the niche's review set.
_MAX_PAGE_REVIEWS = 10

# Selectors inside one review card, tried in order. Older pages use
# "review-title" / "review-body"; the 2026 template (seen on amazon.com.au)
# uses "reviewTitle" / "reviewRichContentContainer" instead. The rating,
# date, badge and helpful-vote hooks did not change.
_REVIEW_RATING_SELECTORS = (
    'i[data-hook="review-star-rating"] span.a-icon-alt',
    'i[data-hook="cmps-review-star-rating"] span.a-icon-alt',
)
_REVIEW_TITLE_SELECTORS = (
    'a[data-hook="review-title"] span:not(.a-icon-alt)',
    'span[data-hook="review-title"] span:not(.a-icon-alt)',
    '[data-hook="reviewTitle"]',
)
# NOTE: "reviewRichContentContainer" sits inside "reviewText". The outer one
# also holds hidden "Brief content visible..." helper text, so the inner one goes first.
_REVIEW_BODY_SELECTORS = (
    'span[data-hook="review-body"] span',
    '[data-hook="reviewRichContentContainer"]',
    '[data-hook="reviewText"]',
)
_REVIEW_DATE_SELECTORS = ('span[data-hook="review-date"]',)
_REVIEW_HELPFUL_SELECTORS = ('span[data-hook="helpful-vote-statement"]',)
_VERIFIED_PURCHASE_SELECTOR = 'span[data-hook="avp-badge"]'
_VINE_BADGE_SELECTOR = 'span[data-hook="vine-review-badge"], span.a-color-link:has-text("Vine")'

# Amazon sends /product-reviews/ to this sign-in page on some marketplaces (seen on AU in 2026).
SIGNIN_PATH_MARKER = "/ap/signin"


class ScraperService:
    """Scrapes Amazon search results, product pages, and reviews via Playwright."""

    # Amazon appends "(See Top 100 in <Category>)" right after the main
    # rank. Stripping every "(...)" aside before matching keeps that text
    # out of the category name without having to special-case it in the
    # main pattern.
    _PARENTHETICAL_ASIDE = re.compile(r"\([^)]*\)")

    # Amazon shows "N in Category" for the main category and, when the
    # product also sits in a narrower sub-category, a second pair right after.
    # Older pages write "#N"; the 2026 template drops the "#" and, read with
    # text_content(), puts no line break between the two pairs.
    # WHY: category names can contain digits ("3D Printing"), accents
    # ("Wall Décor") and curly apostrophes ("Men’s Watches"), so the category
    # is "anything but a line break, # or (" rather than a list of allowed
    # letters. A fixed letter list made a whole rank pair vanish on one odd
    # character, and the sub-rank was then reported as the main BSR.
    # The category is matched lazily and ends where the next "<rank> in "
    # pair starts, or at a line break, a "#", a "(", or the end of the text.
    _BSR_PATTERN = re.compile(
        r"#?(\d[\d,]*)\s+in\s+"
        r"([^\n#(]+?)"
        r"(?=\s*#?\d[\d,]*\s+in\s|\s*[\n#(]|\s*$)"
    )

    # WHY: a whole details block also has rows like "Size 12 in Black".
    # Parsing only from this label onwards keeps those from looking like ranks.
    BSR_LABEL = "best sellers rank"

    # Ordered by reliability — the first selector that yields a positive
    # price wins. Shared by the full product-page scrape and the
    # lightweight rank/price snapshot so both read price the same way.
    _PRICE_SELECTORS = (
        "#corePriceDisplay_desktop_feature_div span.a-offscreen",
        "#corePrice_feature_div span.a-offscreen",
        ".priceToPay span.a-offscreen",
        "#apex_offerDisplay_desktop span.a-offscreen",
        "span.a-price[data-a-color='base'] span.a-offscreen",
        "span.a-price:not([data-a-strike='true']) span.a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
    )

    # Amazon renders the product-details block (which holds the BSR text)
    # under different element ids depending on page template.
    # WHY: the "Best Sellers Rank" row comes first. Reading the whole block
    # with text_content() runs the sub-category into the next rows
    # ("Garlic Presses ASIN B00HEZ888K ..."), so the whole blocks are only
    # a fallback for layouts we have not seen.
    _DETAILS_SELECTORS = (
        '#prodDetails tr:has(th:has-text("Best Sellers Rank")) td',
        '#productDetails_detailBullets_sections1 tr:has(th:has-text("Best Sellers Rank")) td',
        '#detailBulletsWrapper_feature_div li:has-text("Best Sellers Rank")',
        "#productDetails_detailBullets_sections1",
        "#detailBulletsWrapper_feature_div",
        "#productDetails_db_sections",
    )

    def __init__(
        self,
        proxy_manager: ProxyManager | None = None,
        marketplace: str = "US",
        session: BrowserSession | None = None,
        page_cache: PageCache | None = None,
        event_sink=None,
    ):
        self.proxy_manager = proxy_manager or build_proxy_manager_from_settings()

        # Load marketplace config for domain, locale, timezone
        from app.core.marketplace import get_marketplace
        self._marketplace = get_marketplace(marketplace)

        # WHY: a pipeline run injects one shared session so every page load reuses the
        # same cookies and fingerprint. None means "open a short-lived one per call".
        self._session = session

        # WHY: None disables caching entirely (e.g. a forced re-run must hit Amazon again).
        self._page_cache = page_cache

        # An async DB session factory. When set, _load() records one scrape_events row
        # per page load; None (the default) means "don't bother" — used in tests.
        self._event_sink = event_sink

    # ------------------------------------------------------------------
    # Session + page loading
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def _ensure_session(self):
        """Yield the injected session, or open a temporary one for the duration of one call."""
        if self._session is not None:
            yield self._session
            return
        # NOTE: this temporary session is stored on self, so one un-injected
        # ScraperService must not run two scrape calls concurrently.
        async with BrowserSession(self._marketplace, self.proxy_manager) as session:
            self._session = session
            try:
                yield session
            finally:
                self._session = None

    async def _load(self, url: str, expected_selector: str, url_kind: str) -> tuple[Page, PageVerdict]:
        """Load url through the session, rotating proxy + persona on a captcha, 5xx or navigation error.

        Returns (page, verdict) where verdict is "ok" or "soft_block".
        The caller must close the page. Records one scrape_events row per attempt
        (see _record_load_event), so a load that needed two rotations shows up as
        three rows — that is what makes block rates visible on /scrape-health.
        """
        for _ in range(MAX_ROTATIONS_PER_SESSION + 1):
            started_at = time.monotonic()
            try:
                page, verdict = await self._session.load(url, expected_selector)
            except PlaywrightError as exc:
                await self._record_load_event(_TIMEOUT_VERDICT, started_at, url_kind)
                # WHY: a timeout or proxy/tunnel failure usually means this proxy is dead.
                # A new one may work. session.load() already closed the tab.
                logger.warning("Navigation failed loading %s (%s: %s) — rotating", url, type(exc).__name__, exc)
                await self._rotate_session(url)
                continue
            await self._record_load_event(verdict, started_at, url_kind)
            if verdict not in _ROTATE_ON_VERDICTS:
                return page, verdict
            await page.close()
            logger.warning("Blocked (%s) loading %s — rotating", verdict, url)
            await self._rotate_session(url)
        # NOTE: defensive guard only — rotate() raises at the cap before the loop can end.
        raise ScrapingError(f"Still blocked after {MAX_ROTATIONS_PER_SESSION} rotations: {url}")

    async def _record_load_event(self, verdict: str, started_at: float, url_kind: str) -> None:
        """Record how long this page load took and what we got. No-op unless a sink is configured."""
        if self._event_sink is None:
            return
        duration_ms = int((time.monotonic() - started_at) * 1000)
        await record_scrape_event(
            self._event_sink,
            site=_SITE_AMAZON,
            url_kind=url_kind,
            verdict=verdict,
            proxy_label=self._session.proxy_label,
            duration_ms=duration_ms,
        )

    async def _rotate_session(self, url: str) -> None:
        """Rotate the proxy + persona. Raises ScrapingError once the rotation cap is hit."""
        try:
            await self._session.rotate()
        except RuntimeError as exc:
            raise ScrapingError(f"Gave up loading {url}: {exc}") from exc

    def _product_url(self, asin: str) -> str:
        return f"https://www.{self._marketplace.domain}/dp/{asin}"

    def _search_url(self, keyword: str) -> str:
        return f"https://www.{self._marketplace.domain}/s?k={quote_plus(keyword)}"

    async def _cached(self, kind: str, key: str) -> dict | list | None:
        """Return the cached value for (kind, key), or None on a miss or when caching is off."""
        if self._page_cache is None:
            return None
        cached = await self._page_cache.get(kind, key)
        if cached is not None:
            logger.info("%s %s served from cache", kind, key)
        return cached

    async def _store(self, kind: str, key: str, value: dict | list) -> None:
        """Write value to the cache for (kind, key). No-op when caching is off."""
        if self._page_cache is not None:
            await self._page_cache.set(kind, key, value)

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @staticmethod
    async def _safe_text(page: Page, selector: str) -> str | None:
        """Return the inner text of *selector*, or ``None`` if not found."""
        try:
            el = page.locator(selector).first
            if await el.count() == 0:
                return None
            text = await el.inner_text()
            return text.strip() if text else None
        except Exception:
            return None

    @staticmethod
    async def _safe_text_content(page: Page, selector: str) -> str | None:
        """Return the text_content() of *selector*, or ``None`` if not found.

        Unlike inner_text(), this includes text inside collapsed (hidden) sections.
        """
        try:
            el = page.locator(selector).first
            if await el.count() == 0:
                return None
            text = await el.text_content()
            return text.strip() if text else None
        except Exception:
            return None

    @staticmethod
    async def _safe_attr(page: Page, selector: str, attribute: str) -> str | None:
        """Return an element attribute value, or ``None`` if not found."""
        try:
            el = page.locator(selector).first
            if await el.count() == 0:
                return None
            return await el.get_attribute(attribute)
        except Exception:
            return None

    @staticmethod
    def _safe_float(text: str | None) -> float | None:
        """Parse the first decimal number from *text*, or return ``None``."""
        if not text:
            return None
        try:
            match = re.search(r"(\d+[.,]?\d*)", text.replace(",", ""))
            if match:
                return float(match.group(1))
        except (ValueError, AttributeError):
            pass
        return None

    @staticmethod
    def _safe_int(text: str | None) -> int | None:
        """Parse the first contiguous number (with optional commas) from *text*."""
        if not text:
            return None
        try:
            match = re.search(r"([\d,]+)", text)
            if match:
                return int(match.group(1).replace(",", ""))
        except (ValueError, AttributeError):
            pass
        return None

    @classmethod
    def parse_review_count_text(cls, text: str | None) -> int | None:
        """Review count from text like "(38,907)" or "6,602 ratings". None for a star rating.

        WHY: several review-count selectors also match the "4.6 out of 5 stars"
        span, and reading the first number of that gave every product 4 reviews.
        """
        if not text or _STAR_RATING_TEXT.search(text):
            return None
        abbreviated = _THOUSANDS_ABBREVIATION.search(text)
        if abbreviated:
            return round(float(abbreviated.group(1)) * _ONE_THOUSAND)
        count = cls._safe_int(text)
        return count if count else None

    async def _extract_serp_review_count(self, result_div) -> int | None:
        """Review count for one search result, or None if no selector yields one."""
        # WHY: the visible text is abbreviated ("(6.6K)"); the aria-label has
        # the exact number ("6,602 ratings"), so it is tried first.
        ratings_link = result_div.locator(_SERP_RATINGS_LINK_SELECTOR).first
        if await ratings_link.count():
            count = self.parse_review_count_text(await ratings_link.get_attribute("aria-label"))
            if count is not None:
                return count
        for selector in _SERP_REVIEW_COUNT_SELECTORS:
            element = result_div.locator(selector).first
            if await element.count():
                count = self.parse_review_count_text(await element.inner_text())
                if count is not None:
                    return count
        return None

    @staticmethod
    def parse_bsr_text(details_text: str | None) -> dict:
        """Parse 'N in Category' pairs ('#' optional). First match is the main category, second the sub-category."""
        empty = {"current_bsr": None, "bsr_category": None, "current_subcategory_bsr": None, "subcategory_name": None}
        if not details_text:
            return empty
        rank_text = ScraperService._text_from_bsr_label(details_text)
        # WHY: Amazon appends "(See Top 100 in <Category>)" after the main rank; drop asides before matching.
        cleaned = ScraperService._PARENTHETICAL_ASIDE.sub(" ", rank_text)
        matches = ScraperService._BSR_PATTERN.findall(cleaned)
        if not matches:
            return empty
        parsed = dict(empty)
        parsed["current_bsr"] = ScraperService._safe_int(matches[0][0])
        parsed["bsr_category"] = matches[0][1].strip()
        if len(matches) > 1:
            parsed["current_subcategory_bsr"] = ScraperService._safe_int(matches[1][0])
            parsed["subcategory_name"] = matches[1][1].strip()
        return parsed

    @staticmethod
    def _text_from_bsr_label(details_text: str) -> str:
        """The text from the "Best Sellers Rank" label onwards, or all of it when the label is absent."""
        label = re.search(re.escape(ScraperService.BSR_LABEL), details_text, re.IGNORECASE)
        if label is None:
            return details_text
        return details_text[label.start():]

    # ------------------------------------------------------------------
    # 1. Search results scraper
    # ------------------------------------------------------------------

    async def scrape_search_results(self, keyword: str, pages: int = 3) -> list[dict]:
        """Scrape Amazon search result pages for *keyword*.

        Returns a list of dicts, one per product, with keys matching the
        ``Product`` model columns wherever possible.
        """
        cache_key = f"{self._marketplace.code}:{keyword}:{pages}"
        cached = await self._cached("serp", cache_key)
        if cached is not None:
            return cached

        all_results: list[dict] = []
        cards_seen = 0
        async with self._ensure_session():
            for page_num in range(1, pages + 1):
                url = f"{self._search_url(keyword)}&page={page_num}"
                logger.info("Scraping search page %d/%d for '%s'", page_num, pages, keyword)
                page, verdict = await self._load(url, _SEARCH_RESULT_SELECTOR, "serp")
                try:
                    if verdict == "soft_block":
                        logger.warning("No search results found on page %d for '%s'", page_num, keyword)
                        break
                    page_results, cards_seen = await self._extract_search_page(page, cards_seen)
                finally:
                    await page.close()
                all_results.extend(page_results)

        logger.info("Scraped %d results for '%s'", len(all_results), keyword)
        if all_results:
            await self._store("serp", cache_key, all_results)
        return all_results

    async def _extract_search_page(
        self, page: Page, cards_seen_before: int
    ) -> tuple[list[dict], int]:
        """Extract every result card on one search page. Returns (results, cards seen so far)."""
        result_divs = page.locator(_SEARCH_RESULT_SELECTOR)
        count = await result_divs.count()
        results = []
        for i in range(count):
            # WHY: position counts every card, even ones without an ASIN,
            # so it matches the card's place on Amazon's page.
            card = await self._extract_search_card(result_divs.nth(i), cards_seen_before + i + 1)
            if card:
                results.append(card)
        return results, cards_seen_before + count

    async def _extract_search_card(self, div, position: int) -> dict | None:
        """Extract one search result card. Returns None for cards without an ASIN."""
        # ASIN
        asin = await div.get_attribute("data-asin") or ""
        if not asin:
            return None

        # Title — try multiple selectors
        title: str | None = None
        for title_sel in (
            "h2 a span",
            "h2 span a",
            "h2 a",
            "h2 span",
            "h2",
            'span[class*="a-text-normal"]',
            'a.a-link-normal span.a-text-normal',
            '[data-cy="title-recipe"] a span',
            '[data-cy="title-recipe"] h2',
        ):
            try:
                title_el = div.locator(title_sel).first
                if await title_el.count():
                    txt = (await title_el.inner_text()).strip()
                    if txt and len(txt) > 3:
                        title = txt
                        break
            except Exception:
                continue

        # Price — try non-struck-through price first, then any price
        price: float | None = None
        try:
            for price_sel in (
                "span.a-price:not([data-a-strike='true']) span.a-offscreen",
                ".a-price[data-a-color='base'] span.a-offscreen",
                "span.a-price span.a-offscreen",
            ):
                price_el = div.locator(price_sel).first
                if await price_el.count():
                    price = self._safe_float(await price_el.inner_text())
                    if price is not None and price > 0:
                        break
        except Exception:
            pass
        # Fallback: build from whole + fraction parts
        if price is None:
            try:
                whole_el = div.locator("span.a-price-whole").first
                frac_el = div.locator("span.a-price-fraction").first
                if await whole_el.count() and await frac_el.count():
                    whole = (await whole_el.inner_text()).strip().rstrip(".")
                    frac = (await frac_el.inner_text()).strip()
                    price = self._safe_float(f"{whole}.{frac}")
            except Exception:
                pass

        # Rating
        rating: float | None = None
        try:
            rating_el = div.locator("span.a-icon-alt").first
            if await rating_el.count():
                rating_text = await rating_el.inner_text()
                rating = self._safe_float(rating_text)
        except Exception:
            pass

        review_count = await self._extract_serp_review_count(div)

        # Sponsored
        is_sponsored = False
        try:
            comp_type = await div.get_attribute("data-component-type") or ""
            if "sp-sponsored" in comp_type:
                is_sponsored = True
            else:
                sp_label = div.locator("span.puis-label-popover-default, span:has-text('Sponsored')")
                if await sp_label.count() > 0:
                    is_sponsored = True
        except Exception:
            pass

        # Badges
        is_amazon_choice = False
        is_best_seller = False
        try:
            badge_text = ""
            badges = div.locator("span.a-badge-text, span.a-badge-label")
            badge_count = await badges.count()
            for b in range(badge_count):
                badge_text += " " + (await badges.nth(b).inner_text())
            full_div_text = badge_text.lower()
            if "amazon" in full_div_text and "choice" in full_div_text:
                is_amazon_choice = True
            if "best seller" in full_div_text:
                is_best_seller = True
        except Exception:
            pass

        # Image URL
        image_url: str | None = None
        try:
            img_el = div.locator("img.s-image").first
            if await img_el.count():
                image_url = await img_el.get_attribute("src")
        except Exception:
            pass

        # FBA / Prime
        is_fba = False
        try:
            div_html = await div.inner_text()
            if "FREE delivery" in div_html or "Prime" in div_html:
                is_fba = True
        except Exception:
            pass

        return {
            "position": position,
            "asin": asin,
            "title": title,
            "price": price,
            "rating": rating,
            "review_count": review_count,
            "is_sponsored": is_sponsored,
            "is_amazon_choice": is_amazon_choice,
            "is_best_seller": is_best_seller,
            "image_url": image_url,
            "is_fba": is_fba,
        }

    # ------------------------------------------------------------------
    # 2. Product detail page scraper
    # ------------------------------------------------------------------

    async def scrape_product_page(self, asin: str) -> dict:
        """Scrape an Amazon product detail page and return a dict of fields.

        The result carries FROM_CACHE_KEY = True when served from the cache, so a
        caller that records BSR/price/stock history can skip a cached (stale) read.
        """
        cache_key = f"{self._marketplace.code}:{asin}"
        cached = await self._cached("product", cache_key)
        if cached is not None:
            cached[FROM_CACHE_KEY] = True
            return cached

        logger.info("Scraping product page %s", asin)
        async with self._ensure_session():
            page, verdict = await self._load(self._product_url(asin), _PRODUCT_TITLE_SELECTOR, "product")
            try:
                if verdict == "soft_block":
                    logger.warning("Product title not found for ASIN %s", asin)
                result = await self._extract_product_fields(page, asin)
            finally:
                await page.close()

        logger.info("Scraped product page for ASIN %s", asin)
        # WHY only "ok": a soft-blocked page's fields are mostly None (title not
        # found), so caching it would serve that near-empty result for 24h.
        if verdict == "ok":
            await self._store("product", cache_key, result)
        return result

    async def _read_sold_by_amazon(self, page: Page) -> bool:
        """True when the buy box says Amazon itself sells this listing."""
        for selector in _MERCHANT_SELECTORS:
            merchant_text = await self._safe_text(page, selector)
            if merchant_text:
                return self.is_sold_by_amazon(merchant_text)
        return False

    @staticmethod
    def is_sold_by_amazon(merchant_text: str | None) -> bool:
        """True when a buy-box merchant line names Amazon as the seller."""
        if not merchant_text:
            return False
        # WHY: the buy box puts the "Sold by" / "Seller" label and "Amazon" in separate
        # cells, so its text has a newline between them. Collapse whitespace first.
        normalized = " ".join(merchant_text.split()).lower()
        return any(marker in normalized for marker in _SOLD_BY_AMAZON_MARKERS)

    async def _extract_product_fields(self, page: Page, asin: str) -> dict:
        """Read every field we use from a loaded product page."""
        # Title — try multiple selectors
        title: str | None = None
        for title_sel in (
            "#productTitle",
            "h1#title span",
            "h1#title",
            "span#productTitle",
            "h1[class*='title']",
            "#titleSection h1",
            "#title_feature_div #productTitle",
            "[data-feature-name='title'] h1",
            "#dp-container h1",
        ):
            title = await self._safe_text(page, title_sel)
            if title:
                break
        # Last resort: try the page's <title> tag (strip " - Amazon.com" suffix)
        if not title:
            try:
                page_title = await page.title()
                if page_title and "Amazon.com" in page_title:
                    title = page_title.split(" - Amazon.com")[0].split(" : Amazon.com")[0].strip()
                    if title and len(title) < 5:
                        title = None  # Too short, probably not a real title
            except Exception:
                pass

        # Price — try multiple selectors (ordered by reliability)
        price: float | None = None
        for sel in self._PRICE_SELECTORS:
            price_text = await self._safe_text(page, sel)
            if price_text:
                price = self._safe_float(price_text)
                if price is not None and price > 0:
                    break
        # Fallback: build from whole + fraction parts
        if price is None:
            try:
                whole_el = page.locator("span.a-price-whole").first
                frac_el = page.locator("span.a-price-fraction").first
                if await whole_el.count() and await frac_el.count():
                    whole = (await whole_el.inner_text()).strip().rstrip(".")
                    frac = (await frac_el.inner_text()).strip()
                    price = self._safe_float(f"{whole}.{frac}")
            except Exception:
                pass

        # Rating
        rating: float | None = None
        rating_text = await self._safe_text(page, "#acrPopover span.a-icon-alt")
        if rating_text:
            rating = self._safe_float(rating_text)

        # Review count
        review_count = await self._extract_review_count(page)

        # Brand
        brand = await self._safe_text(page, "#bylineInfo")
        if brand:
            # Clean "Visit the Xyz Store" / "Brand: Xyz"
            brand = (
                brand.replace("Visit the ", "")
                .replace(" Store", "")
                .replace("Brand: ", "")
                .strip()
            )

        # BSR — parse from product details table / bullets
        # Amazon reports both main-category BSR and sub-category BSR.
        # The sales velocity curves differ by ~10x between them, so we
        # must capture both and tag which is which.
        parsed_bsr = await self._extract_bsr(page)
        bsr = parsed_bsr["current_bsr"]
        bsr_category = parsed_bsr["bsr_category"]
        subcategory_bsr = parsed_bsr["current_subcategory_bsr"]
        subcategory_name = parsed_bsr["subcategory_name"]

        # Bullet points
        bullet_points: list[str] = []
        try:
            bullets = page.locator("#feature-bullets li span.a-list-item")
            bc = await bullets.count()
            for i in range(bc):
                txt = (await bullets.nth(i).inner_text()).strip()
                if txt and not txt.startswith("›"):
                    bullet_points.append(txt)
        except Exception:
            pass

        # Image count (from the thumbnail strip)
        image_count: int | None = None
        try:
            thumbs = page.locator("#altImages li.a-spacing-small.item")
            ic = await thumbs.count()
            if ic == 0:
                thumbs = page.locator("#altImages li.imageThumbnail")
                ic = await thumbs.count()
            image_count = ic if ic > 0 else None
        except Exception:
            pass

        # Has video
        has_video = False
        try:
            video_el = page.locator(
                "#altImages .videoThumbnail, "
                "#vse-vw-dp-vse-related-videos, "
                "#videoBlock, "
                "span.a-button-text:has-text('VIDEOS')"
            )
            has_video = (await video_el.count()) > 0
        except Exception:
            pass

        # A+ Content
        has_a_plus = False
        try:
            aplus_el = page.locator("#aplus, .aplus-v2, #aplus_feature_div")
            has_a_plus = (await aplus_el.count()) > 0
        except Exception:
            pass

        # Brand story
        has_brand_story = False
        try:
            bs_el = page.locator(
                "#brand-story, "
                "[class*='brand-story'], "
                "#brandstoredesktopcontent, "
                "#aplusBrandStory_feature_div"
            )
            has_brand_story = (await bs_el.count()) > 0
        except Exception:
            pass

        # Seller info
        seller_name: str | None = None
        seller_id: str | None = None
        try:
            seller_name = await self._safe_text(page, "#sellerProfileTriggerId")
            seller_link = await self._safe_attr(page, "#sellerProfileTriggerId", "href")
            if seller_link:
                sid_match = re.search(r"seller=([A-Z0-9]+)", seller_link)
                if sid_match:
                    seller_id = sid_match.group(1)
        except Exception:
            pass

        sold_by_amazon = await self._read_sold_by_amazon(page)

        # Coupon
        coupon: str | None = None
        try:
            coupon_el = page.locator("#couponTextpct498, #couponText, label[data-action='coupon-action'] .a-color-success").first
            if await coupon_el.count():
                coupon = (await coupon_el.inner_text()).strip()
        except Exception:
            pass

        # Subscribe & Save
        subscribe_save: bool = False
        try:
            sns_el = page.locator("#snsAccordionRowMiddle, #sns-base-price, #subscribe-and-save-pane")
            subscribe_save = (await sns_el.count()) > 0
        except Exception:
            pass

        # ── List Price / Strikethrough Price ──
        list_price: float | None = None
        try:
            for lp_sel in (
                "span.a-price[data-a-strike='true'] span.a-offscreen",
                "#listPrice",
                "#priceBlockStrikePriceRow .a-text-price span.a-offscreen",
                ".basisPrice span.a-offscreen",
            ):
                lp_text = await self._safe_text(page, lp_sel)
                if lp_text:
                    list_price = self._safe_float(lp_text)
                    if list_price and list_price > 0:
                        break
        except Exception:
            pass

        # ── Product Dimensions & Weight from detail table ──
        dimensions: str | None = None
        weight: str | None = None
        date_first_available: str | None = None
        try:
            for detail_sel in (
                "#productDetails_techSpec_section_1",
                "#productDetails_detailBullets_sections1",
                "#detailBulletsWrapper_feature_div",
                "#productDetails_db_sections",
                "#prodDetails",
            ):
                detail_el = page.locator(detail_sel).first
                if await detail_el.count():
                    detail_text = await detail_el.inner_text()
                    if detail_text:
                        # Dimensions
                        dim_match = re.search(
                            r"(?:Product|Package|Item)\s*Dimensions?\s*[:\u200f\-]*\s*:?\s*[:\u200e\s]*([\d.]+\s*x\s*[\d.]+\s*x\s*[\d.]+\s*(?:inches|cm|in|Centimetres|centimeters)?)",
                            detail_text,
                            re.IGNORECASE,
                        )
                        if dim_match and not dimensions:
                            dimensions = dim_match.group(1).strip()

                        # Weight
                        weight_match = re.search(
                            r"(?:Item|Product)\s*Weight\s*[:\u200f\-]*\s*:?\s*[:\u200e\s]*([\d.]+\s*(?:pounds|ounces|lbs|oz|kg|g|Kilograms|Grams|kilograms|grams))",
                            detail_text,
                            re.IGNORECASE,
                        )
                        if weight_match and not weight:
                            weight = weight_match.group(1).strip()

                        # Date First Available — multiple formats
                        for date_re in (
                            r"Date\s+First\s+Available\s*[:\u200f\-]*\s*:?\s*[:\u200e\s]*(\d{1,2}\s+\w+\s+\d{4})",
                            r"Date\s+First\s+Available\s*[:\u200f\-]*\s*:?\s*[:\u200e\s]*(\w+\s+\d{1,2},?\s+\d{4})",
                        ):
                            date_match = re.search(date_re, detail_text, re.IGNORECASE)
                            if date_match and not date_first_available:
                                date_first_available = date_match.group(1).strip()
                                break
        except Exception:
            pass

        # ── Star Distribution Histogram ──
        star_distribution: dict | None = None
        try:
            histogram_el = page.locator("#histogramTable")
            if await histogram_el.count():
                star_links = histogram_el.locator("a")
                link_count = await star_links.count()
                if link_count >= 5:
                    star_distribution = {}
                    for i in range(link_count):
                        link_text = (await star_links.nth(i).inner_text()).strip()
                        # Parse "5 star\n84%" or "5 star 84%"
                        star_match = re.search(r"(\d)\s*star\D*?(\d+)\s*%", link_text, re.IGNORECASE)
                        if star_match:
                            star_num = int(star_match.group(1))
                            pct = int(star_match.group(2))
                            star_distribution[f"{star_num}_star"] = pct
                    # Fill any missing stars with 0
                    for s in range(1, 6):
                        star_distribution.setdefault(f"{s}_star", 0)
        except Exception:
            pass

        # ── Variation Count ──
        variation_count: int | None = None
        try:
            # Check for variation widget
            variation_el = page.locator("#twister_feature_div li, #variation_style_name li, #variation_color_name li, #variation_size_name li")
            vc = await variation_el.count()
            if vc > 0:
                variation_count = vc
            else:
                # Check inline dropdown options
                dropdown = page.locator("#twister_feature_div select option")
                dc = await dropdown.count()
                if dc > 1:  # First option is "Select"
                    variation_count = dc - 1
        except Exception:
            pass

        # ── Category Breadcrumb Path ──
        category_path: str | None = None
        try:
            breadcrumb_el = page.locator(
                "#wayfinding-breadcrumbs_feature_div a, "
                "#wayfinding-breadcrumbs_container a, "
                ".a-breadcrumb a"
            )
            bc = await breadcrumb_el.count()
            if bc > 0:
                parts = []
                for i in range(min(bc, 8)):
                    part_text = (await breadcrumb_el.nth(i).inner_text()).strip()
                    if part_text and part_text not in ("", "‹", "›"):
                        parts.append(part_text)
                if parts:
                    category_path = " > ".join(parts)
        except Exception:
            pass

        # ── Number of Sellers / Offer Count ──
        seller_count: int | None = None
        try:
            offer_el = page.locator("#olp-upd-new a, #aod-offer-count, #olp_feature_div a, #usedAndNew a")
            if await offer_el.count():
                offer_text = await offer_el.first.inner_text()
                # Parse "New (5) from $X.XX" or "(5) New" or "5 offers"
                offer_match = re.search(r"(\d+)", offer_text)
                if offer_match:
                    seller_count = int(offer_match.group(1))
        except Exception:
            pass

        # ── Frequently Bought Together ──
        fbt_asins: list[str] = []
        try:
            fbt_el = page.locator('#sims-fbt .a-link-normal[href*="/dp/"], #sims-fbt a[href*="/gp/product/"]')
            fbt_count = await fbt_el.count()
            seen = set()
            for i in range(min(fbt_count, 6)):
                href = await fbt_el.nth(i).get_attribute("href")
                if href:
                    asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", href)
                    if asin_match and asin_match.group(1) != asin:
                        fbt_asin = asin_match.group(1)
                        if fbt_asin not in seen:
                            seen.add(fbt_asin)
                            fbt_asins.append(fbt_asin)
        except Exception:
            pass

        # ── Q&A Count ──
        qa_count: int | None = None
        try:
            qa_el = page.locator('#askATFLink span.a-size-base, a[href*="ask/questions/asin"] span')
            if await qa_el.count():
                qa_text = await qa_el.first.inner_text()
                qa_count = self._safe_int(qa_text)
        except Exception:
            pass

        # ── Deal Badge ──
        deal_badge: str | None = None
        try:
            for deal_sel, deal_type in (
                ("#dealBadge_feature_div", None),
                ("span.dealBadge", None),
                ("#dealprice_feature_div", "Deal"),
            ):
                deal_el = page.locator(deal_sel).first
                if await deal_el.count():
                    deal_text = (await deal_el.inner_text()).strip()
                    if "lightning" in deal_text.lower():
                        deal_badge = "Lightning Deal"
                    elif "deal of the day" in deal_text.lower():
                        deal_badge = "Deal of the Day"
                    elif deal_text:
                        deal_badge = deal_type or deal_text[:50]
                    break
        except Exception:
            pass

        # ── Amazon's Choice Keyword ──
        amazons_choice_keyword: str | None = None
        try:
            # Try direct keyword link
            ac_el = page.locator('#acBadge_feature_div .ac-keyword-link, span.ac-keyword-link')
            if await ac_el.count():
                amazons_choice_keyword = (await ac_el.first.inner_text()).strip().strip('"')
            else:
                # Try parsing from AC badge text or popover
                ac_badge = page.locator('#acBadge_feature_div')
                if await ac_badge.count():
                    ac_text = (await ac_badge.inner_text()).strip()
                    kw_match = re.search(r'for\s+"?([^"]+)"?', ac_text, re.IGNORECASE)
                    if kw_match:
                        amazons_choice_keyword = kw_match.group(1).strip()
                    elif not ac_text:
                        # Badge exists but no text — mark as present
                        amazons_choice_keyword = "(badge present)"
        except Exception:
            pass

        # ── Review Attribute Tags (feature sentiment) ──
        review_attributes: list[dict] | None = None
        try:
            attr_els = page.locator('#cr-dp-summarization-attributes div[data-hook="cr-summarization-attribute"]')
            attr_count = await attr_els.count()
            if attr_count > 0:
                review_attributes = []
                for i in range(min(attr_count, 10)):
                    attr_div = attr_els.nth(i)
                    name_el = attr_div.locator("span.a-text-bold, span.cr-lighthouse-term").first
                    pct_el = attr_div.locator("span.a-size-base:not(.a-text-bold), span.cr-lighthouse-term-text").first
                    if await name_el.count() and await pct_el.count():
                        attr_name = (await name_el.inner_text()).strip()
                        attr_pct = (await pct_el.inner_text()).strip()
                        sentiment = "positive"
                        pct_num = self._safe_int(attr_pct.replace("%", ""))
                        if pct_num and pct_num < 60:
                            sentiment = "mixed"
                        if pct_num and pct_num < 40:
                            sentiment = "negative"
                        review_attributes.append({
                            "attribute": attr_name,
                            "percentage": attr_pct,
                            "sentiment": sentiment,
                        })
        except Exception:
            pass

        # ── Comparison Table ASINs ──
        comparison_asins: list[str] = []
        try:
            comp_links = page.locator('#HLCXComparisonTable a[href*="/dp/"], .comparison-table a[href*="/dp/"]')
            comp_count = await comp_links.count()
            seen_comp = set()
            for i in range(min(comp_count, 6)):
                href = await comp_links.nth(i).get_attribute("href")
                if href:
                    comp_match = re.search(r"/dp/([A-Z0-9]{10})", href)
                    if comp_match and comp_match.group(1) != asin:
                        comp_asin = comp_match.group(1)
                        if comp_asin not in seen_comp:
                            seen_comp.add(comp_asin)
                            comparison_asins.append(comp_asin)
        except Exception:
            pass

        # ── Stock level / availability ──
        stock_level: int | None = None
        stock_text: str | None = None
        is_in_stock: bool = True
        try:
            avail_el = page.locator("#availability").first
            if await avail_el.count():
                avail_text = (await avail_el.inner_text()).strip()
                stock_text = avail_text
                # "Only X left in stock"
                stock_match = re.search(r"Only\s+(\d+)\s+left", avail_text, re.IGNORECASE)
                if stock_match:
                    stock_level = int(stock_match.group(1))
                # "Currently unavailable"
                if "currently unavailable" in avail_text.lower():
                    is_in_stock = False
                    stock_level = 0
                elif "out of stock" in avail_text.lower():
                    is_in_stock = False
                    stock_level = 0
        except Exception:
            pass

        page_reviews = await self._extract_page_reviews(page, asin)

        result = {
            "asin": asin,
            "title": title,
            "price": price,
            "rating": rating,
            "review_count": review_count,
            "brand": brand,
            "current_bsr": bsr,
            "bsr_category": bsr_category,
            "current_subcategory_bsr": subcategory_bsr,
            "subcategory_name": subcategory_name,
            "bullet_points": bullet_points,
            "bullet_count": len(bullet_points),
            "image_count": image_count,
            "has_video": has_video,
            "has_a_plus": has_a_plus,
            "has_brand_story": has_brand_story,
            "seller_name": seller_name,
            "seller_id": seller_id,
            "sold_by_amazon": sold_by_amazon,
            "coupon": coupon,
            "subscribe_save": subscribe_save,
            "is_fba": None,  # Will be enriched from search or SP-API
            "stock_level": stock_level,
            "stock_text": stock_text,
            "is_in_stock": is_in_stock,
            # ── New enriched fields ──
            "list_price": list_price,
            "dimensions": dimensions,
            "weight": weight,
            "date_first_available": date_first_available,
            "star_distribution": star_distribution,
            "variation_count": variation_count,
            "category_path": category_path,
            "seller_count": seller_count,
            "fbt_asins": fbt_asins,
            "qa_count": qa_count,
            "deal_badge": deal_badge,
            "amazons_choice_keyword": amazons_choice_keyword,
            "review_attributes": review_attributes,
            "comparison_asins": comparison_asins,
            "last_scraped_at": datetime.utcnow().isoformat(),
            "page_reviews": page_reviews,
        }
        return result

    # ------------------------------------------------------------------
    # 3. Single review extraction (shared helper)
    # ------------------------------------------------------------------

    async def _extract_page_reviews(self, page: Page, asin: str) -> list[dict]:
        """Top reviews shown on the product page itself. Cards without a body are skipped."""
        page_reviews: list[dict] = []
        try:
            cards = page.locator(_PAGE_REVIEW_CARD_SELECTOR)
            card_count = await cards.count()
            for index in range(min(card_count, _MAX_PAGE_REVIEWS)):
                review = await self._extract_single_review(cards.nth(index), asin)
                if review and review.get("body"):
                    page_reviews.append(review)
        except Exception as e:
            logger.debug("Product page review extraction failed for %s: %s", asin, e)
        return page_reviews

    async def _extract_single_review(self, div, asin: str) -> dict | None:
        """Extract one review card into a review dict. None when the card has neither title nor body.

        Reusable across product-page top reviews and dedicated review pages.
        """
        title = await self._first_inner_text(div, _REVIEW_TITLE_SELECTORS)
        body = await self._first_inner_text(div, _REVIEW_BODY_SELECTORS)
        if not body and not title:
            return None
        rating = self._safe_float(await self._first_inner_text(div, _REVIEW_RATING_SELECTORS))
        date_line = await self._first_inner_text(div, _REVIEW_DATE_SELECTORS)
        helpful_line = await self._first_inner_text(div, _REVIEW_HELPFUL_SELECTORS)
        return {
            "asin": asin,
            "review_id": await div.get_attribute("id"),
            "rating": int(rating) if rating is not None else None,
            "title": title,
            "body": body,
            "review_date": parse_review_date(date_line),
            "verified_purchase": await self._contains(div, _VERIFIED_PURCHASE_SELECTOR),
            "helpful_votes": parse_helpful_votes(helpful_line),
            "is_vine": await self._contains(div, _VINE_BADGE_SELECTOR),
        }

    @staticmethod
    async def _first_inner_text(container, selectors: tuple[str, ...]) -> str | None:
        """Visible text of the first selector (in the given order) that matches inside *container*."""
        for selector in selectors:
            try:
                element = container.locator(selector).first
                if await element.count() == 0:
                    continue
                text = (await element.inner_text()).strip()
            except Exception:
                continue
            if text:
                return text
        return None

    @staticmethod
    async def _contains(container, selector: str) -> bool:
        """True when *selector* matches at least one element inside *container*."""
        try:
            return await container.locator(selector).count() > 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 4. Reviews scraper
    # ------------------------------------------------------------------

    async def scrape_reviews(
        self,
        asin: str,
        filter_star: str = "critical",
        max_pages: int = 50,
    ) -> list[dict]:
        """Scrape Amazon product reviews for *asin*.

        Parameters
        ----------
        asin : str
            The Amazon ASIN to scrape reviews for.
        filter_star : str
            Star filter value.  Common values: ``"critical"`` (1-3 stars),
            ``"positive"`` (4-5 stars), ``"all_stars"``, ``"one_star"`` ...
            ``"five_star"``.
        max_pages : int
            Maximum number of review pages to paginate through.

        Returns
        -------
        list[dict]
            A list of review dicts matching the ``Review`` model columns.
        """
        all_reviews: list[dict] = []
        async with self._ensure_session():
            for page_num in range(1, max_pages + 1):
                page_reviews = await self._scrape_review_page(asin, filter_star, page_num)
                if not page_reviews:
                    break
                all_reviews.extend(page_reviews)

        logger.info("Scraped %d reviews for ASIN %s (filter=%s)", len(all_reviews), asin, filter_star)
        return all_reviews

    async def _scrape_review_page(self, asin: str, filter_star: str, page_num: int) -> list[dict]:
        """Load one page of reviews. Returns [] when there are no (more) reviews."""
        url = (
            f"https://www.{self._marketplace.domain}/product-reviews/{asin}"
            f"?filterByStar={filter_star}&pageNumber={page_num}"
        )
        logger.info("Scraping reviews for %s, page %d, filter=%s", asin, page_num, filter_star)
        page, verdict = await self._load(url, _REVIEW_SELECTOR, "reviews")
        try:
            # NOTE: a sign-in wall is not a block, so rotating would not help.
            # Returning [] also stops pagination, so this warns once per call.
            if SIGNIN_PATH_MARKER in page.url:
                logger.warning("/product-reviews/ requires sign-in for this marketplace; skipping (%s)", asin)
                return []
            if verdict == "soft_block":
                logger.info("No more reviews found for %s at page %d", asin, page_num)
                return []
            return await self._extract_reviews(page, asin)
        finally:
            await page.close()

    async def _extract_reviews(self, page: Page, asin: str) -> list[dict]:
        """Extract every review card on a loaded review page."""
        review_divs = page.locator(_REVIEW_SELECTOR)
        count = await review_divs.count()
        reviews = []
        for i in range(count):
            review = await self._extract_single_review(review_divs.nth(i), asin)
            if review:
                reviews.append(review)
        return reviews

    # ------------------------------------------------------------------
    # 5. Stock level + rank snapshot scrapers (lightweight, for the tracker)
    # ------------------------------------------------------------------

    async def scrape_stock_level(self, asin: str) -> dict:
        """Scrape only the availability/stock level for an ASIN.

        Much lighter than a full product page scrape — only extracts the
        #availability element to get stock status. The "verdict" key is "ok"
        only for a real product page (see scrape_rank_snapshot).
        """
        async with self._ensure_session():
            page, verdict = await self._load(self._product_url(asin), _PRODUCT_TITLE_SELECTOR, "rank")
            try:
                availability = await self._extract_availability(page)
            finally:
                await page.close()
        return {"asin": asin, "verdict": verdict, **availability}

    async def scrape_rank_snapshot(self, asin: str) -> dict:
        """Scrape current BSR, price, stock and review count for an ASIN.

        Much lighter than a full product page scrape — only extracts the
        details block, price, availability, and review count, for the periodic
        tracker. The "verdict" key is "ok" only for a real product page. Callers
        must not record a snapshot with any other verdict — a soft-blocked page
        parses as "no rank, no price, in stock", which would corrupt the history.
        """
        async with self._ensure_session():
            page, verdict = await self._load(self._product_url(asin), _PRODUCT_TITLE_SELECTOR, "rank")
            try:
                price = await self._extract_first_positive_price(page)
                parsed_bsr = await self._extract_bsr(page)
                availability = await self._extract_availability(page)
                review_count = await self._extract_review_count(page)
            finally:
                await page.close()
        return {
            "asin": asin, "verdict": verdict, "price": price,
            "review_count": review_count, **parsed_bsr, **availability,
        }

    async def _extract_first_positive_price(self, page: Page) -> float | None:
        """Price from the first price selector that yields a positive number."""
        price: float | None = None
        for sel in self._PRICE_SELECTORS:
            price_text = await self._safe_text(page, sel)
            if price_text:
                price = self._safe_float(price_text)
                if price is not None and price > 0:
                    break
        return price

    async def _extract_review_count(self, page: Page) -> int | None:
        """Review count from the first product-page selector that yields a number."""
        for selector in _PRODUCT_REVIEW_COUNT_SELECTORS:
            count = self.parse_review_count_text(await self._safe_text(page, selector))
            if count is not None:
                return count
        return None

    async def _extract_bsr(self, page: Page) -> dict:
        """Main + sub-category BSR from whichever product-details block the page uses."""
        parsed_bsr = self.parse_bsr_text(None)
        for sel in self._DETAILS_SELECTORS:
            # WHY: the 2026 template keeps this block in a collapsed accordion,
            # and inner_text() returns nothing for hidden nodes.
            details_text = await self._safe_text_content(page, sel)
            if details_text:
                parsed_bsr = self.parse_bsr_text(details_text)
                if parsed_bsr["current_bsr"] is not None:
                    break
        return parsed_bsr

    @staticmethod
    async def _extract_availability(page: Page) -> dict:
        """Stock level, raw availability text, and in-stock flag from the #availability block."""
        stock_level: int | None = None
        stock_text: str | None = None
        is_in_stock: bool = True

        avail_el = page.locator("#availability").first
        if await avail_el.count():
            avail_text = (await avail_el.inner_text()).strip()
            stock_text = avail_text
            stock_match = re.search(r"Only\s+(\d+)\s+left", avail_text, re.IGNORECASE)
            if stock_match:
                stock_level = int(stock_match.group(1))
            if "currently unavailable" in avail_text.lower():
                is_in_stock = False
                stock_level = 0
            elif "out of stock" in avail_text.lower():
                is_in_stock = False
                stock_level = 0

        return {"stock_level": stock_level, "stock_text": stock_text, "is_in_stock": is_in_stock}

    # ------------------------------------------------------------------
    # 6. Amazon Autocomplete API (no Playwright needed)
    # ------------------------------------------------------------------

    async def fetch_autocomplete(self, prefix: str) -> list[str]:
        """Fetch autocomplete suggestions from Amazon's suggestion API.

        Uses httpx directly — this is a lightweight JSON endpoint with
        minimal bot detection.
        """
        import httpx

        domain = self._marketplace.domain
        marketplace_id = self._marketplace.marketplace_id

        url = (
            f"https://completion.{domain}/api/2017/suggestions"
            f"?mid={marketplace_id}&alias=aps&prefix={quote_plus(prefix)}"
        )

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": _AUTOCOMPLETE_USER_AGENT},
                timeout=_AUTOCOMPLETE_TIMEOUT_SECONDS,
                verify=False,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                suggestions = data.get("suggestions", [])
                return [s.get("value", "") for s in suggestions if s.get("value")]
        except Exception as e:
            logger.warning("Autocomplete fetch failed for '%s': %s", prefix, e)
            return []

    # ------------------------------------------------------------------
    # 7. SERP metadata scraper (result count + sponsored count)
    # ------------------------------------------------------------------

    async def scrape_serp_metadata(self, keyword: str) -> dict:
        """Scrape page 1 of Amazon search results to extract metadata only.

        Returns total_result_count, sponsored_count, and brand_count
        without parsing individual product cards.
        """
        try:
            async with self._ensure_session():
                url = self._search_url(keyword)
                page, _verdict = await self._load(url, _SEARCH_RESULT_SELECTOR, "serp_meta")
                try:
                    return await self._extract_serp_metadata(page, keyword)
                finally:
                    await page.close()
        except Exception as exc:
            # WHY: SERP metadata only refines keyword volume estimates. Keyword research
            # must carry on without it, so a failure degrades to zeros instead of raising.
            logger.warning("SERP metadata failed for '%s': %s", keyword, exc)
            return {
                "keyword": keyword, "total_result_count": 0, "sponsored_count": 0, "brand_count": 0,
            }

    async def _extract_serp_metadata(self, page: Page, keyword: str) -> dict:
        """Read result count, sponsored count and distinct brand count from a loaded search page."""
        return {
            "keyword": keyword,
            "total_result_count": await self._read_total_result_count(page),
            "sponsored_count": await self._count_sponsored_results(page),
            "brand_count": await self._count_distinct_brands(page),
        }

    async def _read_total_result_count(self, page: Page) -> int:
        """Parse "1-48 of over 2,000 results" (or "1-48 of 347 results") from the results header."""
        total_result_count: int = 0
        try:
            result_header = await self._safe_text(
                page,
                'span[data-component-type="s-result-info-bar"] .a-text-bold, '
                '.s-desktop-toolbar .a-spacing-small span, '
                '#search h1 .a-color-state'
            )
            if result_header:
                count_match = re.search(r"of\s+(?:over\s+)?([\d,]+)", result_header)
                if count_match:
                    total_result_count = int(count_match.group(1).replace(",", ""))
        except Exception:
            pass
        return total_result_count

    @staticmethod
    async def _count_sponsored_results(page: Page) -> int:
        try:
            sponsored_els = page.locator(
                'div[data-component-type="sp-sponsored-result"], '
                'div.AdHolder, '
                'span.a-color-secondary:has-text("Sponsored")'
            )
            return await sponsored_els.count()
        except Exception:
            return 0

    @staticmethod
    async def _count_distinct_brands(page: Page) -> int:
        """Count distinct brand labels among the result cards."""
        try:
            brand_els = page.locator(
                'div.s-result-item span.a-size-base-plus.a-color-base, '
                'div.s-result-item .a-row .a-size-base'
            )
            label_count = await brand_els.count()
            brands_seen = set()
            for i in range(min(label_count, _MAX_BRAND_LABELS_SCANNED)):
                try:
                    brand_text = (await brand_els.nth(i).inner_text()).strip().lower()
                    if brand_text:
                        brands_seen.add(brand_text)
                except Exception:
                    continue
            return len(brands_seen)
        except Exception:
            return 0
