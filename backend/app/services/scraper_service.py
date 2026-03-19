"""Headless browser scraper for Amazon pages using Playwright."""

import asyncio
import logging
import random
import re
from datetime import datetime
from urllib.parse import quote_plus

from playwright.async_api import Browser, Page, async_playwright

from app.core.exceptions import ScrapingError
from app.core.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

_MAX_RETRIES = 3


class ScraperService:
    """Scrapes Amazon search results, product pages, and reviews via Playwright."""

    def __init__(
        self,
        proxy_manager: ProxyManager | None = None,
        marketplace: str = "US",
    ):
        if proxy_manager is None:
            from app.config import Settings

            settings = Settings()
            proxy_manager = ProxyManager(
                provider=settings.PROXY_PROVIDER or "none",
                host=settings.PROXY_HOST,
                port=settings.PROXY_PORT,
                username=settings.PROXY_USERNAME,
                password=settings.PROXY_PASSWORD,
            )
        self.proxy_manager = proxy_manager

        # Load marketplace config for domain, locale, timezone
        from app.core.marketplace import get_marketplace
        self._marketplace = get_marketplace(marketplace)

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _get_random_user_agent() -> str:
        """Return a random realistic Chrome user-agent string."""
        return random.choice(_USER_AGENTS)

    @staticmethod
    async def _random_delay(min_s: float = 2.0, max_s: float = 3.5) -> None:
        """Sleep for a random duration to mimic human behaviour."""
        await asyncio.sleep(random.uniform(min_s, max_s))

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

    async def _launch_browser(self, playwright) -> Browser:
        """Launch a Chromium browser instance, optionally with a rotating proxy."""
        launch_kwargs = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        }
        if self.proxy_manager.has_proxy:
            proxy_conf = self.proxy_manager.get_playwright_proxy()
            # Only pass proxy if it has a non-empty server URL
            if proxy_conf and proxy_conf.get("server"):
                launch_kwargs["proxy"] = proxy_conf
        browser = await playwright.chromium.launch(**launch_kwargs)
        return browser

    async def _new_page(self, browser: Browser) -> Page:
        """Create a new page with randomised fingerprint settings."""
        context = await browser.new_context(
            user_agent=self._get_random_user_agent(),
            viewport={"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
            locale=self._marketplace.locale,
            timezone_id=self._marketplace.timezone,
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        page = await context.new_page()

        # Mask webdriver property so Amazon doesn't flag as bot
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            """
        )
        return page

    # ------------------------------------------------------------------
    # 1. Search results scraper
    # ------------------------------------------------------------------

    async def scrape_search_results(self, keyword: str, pages: int = 3) -> list[dict]:
        """Scrape Amazon search result pages for *keyword*.

        Returns a list of dicts, one per product, with keys matching the
        ``Product`` model columns wherever possible.
        """
        all_results: list[dict] = []
        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            browser: Browser | None = None
            try:
                pw = await async_playwright().start()
                browser = await self._launch_browser(pw)
                page = await self._new_page(browser)

                position_counter = 0

                for page_num in range(1, pages + 1):
                    url = (
                        f"https://www.{self._marketplace.domain}/s?k={quote_plus(keyword)}"
                        f"&page={page_num}"
                    )
                    logger.info("Scraping search page %d/%d for '%s' (attempt %d)", page_num, pages, keyword, attempt)

                    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

                    # Wait for search result cards to appear
                    try:
                        await page.wait_for_selector(
                            'div[data-component-type="s-search-result"]',
                            timeout=15_000,
                        )
                    except Exception:
                        # Debug: log page title and CAPTCHA detection
                        try:
                            page_title = await page.title()
                            has_captcha = await page.locator("form[action*='validateCaptcha'], #captchacharacters, img[src*='captcha']").count()
                            body_len = len(await page.locator("body").inner_text())
                            logger.warning(
                                "No search results found on page %d for '%s' — "
                                "page_title='%s', captcha=%s, body_len=%d",
                                page_num, keyword,
                                page_title[:80] if page_title else "N/A",
                                has_captcha > 0,
                                body_len,
                            )
                        except Exception:
                            logger.warning("No search results found on page %d for '%s'", page_num, keyword)
                        break

                    result_divs = page.locator('div[data-component-type="s-search-result"]')
                    count = await result_divs.count()

                    for i in range(count):
                        div = result_divs.nth(i)
                        position_counter += 1

                        # ASIN
                        asin = await div.get_attribute("data-asin") or ""
                        if not asin:
                            continue

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

                        # Review count — try multiple selectors
                        review_count: int | None = None
                        for rc_sel in (
                            'span[data-component-type="s-client-side-analytics"] span.a-size-base.s-underline-text',
                            'a.a-link-normal .a-size-base',
                            'a[href*="#customerReviews"] span.a-size-base',
                            'span.a-size-base.s-underline-text',
                            'a[data-hook="review-count"]',
                            '.a-row.a-size-small span:last-child',
                        ):
                            try:
                                rc_el = div.locator(rc_sel).first
                                if await rc_el.count():
                                    val = self._safe_int(await rc_el.inner_text())
                                    if val is not None and val > 0:
                                        review_count = val
                                        break
                            except Exception:
                                continue

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

                        all_results.append(
                            {
                                "position": position_counter,
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
                        )

                    # Random human-like delay between pages
                    if page_num < pages:
                        await self._random_delay()

                # If we got here successfully, break out of retries
                logger.info("Scraped %d results for '%s'", len(all_results), keyword)
                return all_results

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Search scrape attempt %d/%d failed for '%s': %s",
                    attempt, _MAX_RETRIES, keyword, exc,
                )
                all_results.clear()
                if attempt < _MAX_RETRIES:
                    await self._random_delay(1.0, 2.0)
            finally:
                if browser:
                    await browser.close()
                try:
                    await pw.stop()
                except Exception:
                    pass

        raise ScrapingError(
            f"Failed to scrape search results for '{keyword}' after {_MAX_RETRIES} attempts: {last_error}"
        )

    # ------------------------------------------------------------------
    # 2. Product detail page scraper
    # ------------------------------------------------------------------

    async def scrape_product_page(self, asin: str) -> dict:
        """Scrape an Amazon product detail page and return a dict of fields."""
        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            browser: Browser | None = None
            pw = None
            try:
                pw = await async_playwright().start()
                browser = await self._launch_browser(pw)
                page = await self._new_page(browser)

                url = f"https://www.{self._marketplace.domain}/dp/{asin}"
                logger.info("Scraping product page %s (attempt %d)", asin, attempt)

                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

                # Wait for the product title to confirm the page loaded
                try:
                    await page.wait_for_selector("#productTitle, h1#title, span#productTitle, h1[class*='title']", timeout=15_000)
                except Exception:
                    logger.warning("Product title not found for ASIN %s", asin)

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
                for sel in (
                    "#corePriceDisplay_desktop_feature_div span.a-offscreen",
                    "#corePrice_feature_div span.a-offscreen",
                    ".priceToPay span.a-offscreen",
                    "#apex_offerDisplay_desktop span.a-offscreen",
                    "span.a-price[data-a-color='base'] span.a-offscreen",
                    "span.a-price:not([data-a-strike='true']) span.a-offscreen",
                    "#priceblock_ourprice",
                    "#priceblock_dealprice",
                ):
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
                review_count: int | None = None
                rc_text = await self._safe_text(page, "#acrCustomerReviewCount")
                if rc_text:
                    review_count = self._safe_int(rc_text)

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
                bsr: int | None = None
                bsr_category: str | None = None
                subcategory_bsr: int | None = None
                subcategory_name: str | None = None
                try:
                    for sel in (
                        "#productDetails_detailBullets_sections1",
                        "#detailBulletsWrapper_feature_div",
                        "#productDetails_db_sections",
                    ):
                        details_text = await self._safe_text(page, sel)
                        if details_text:
                            # findall returns ALL "#N in Category" matches
                            bsr_matches = re.findall(
                                r"#([\d,]+)\s+in\s+([A-Za-z &',\-]+)",
                                details_text,
                            )
                            if bsr_matches:
                                # First match = main category BSR (broadest)
                                bsr = self._safe_int(bsr_matches[0][0])
                                bsr_category = bsr_matches[0][1].strip()
                                # Subsequent matches = sub-category BSRs
                                # (narrower, lower numbers, more niche-specific)
                                if len(bsr_matches) > 1:
                                    subcategory_bsr = self._safe_int(bsr_matches[1][0])
                                    subcategory_name = bsr_matches[1][1].strip()
                                break
                except Exception:
                    pass

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

                # ── Extract top reviews from the product page ──
                page_reviews: list[dict] = []
                try:
                    review_containers = page.locator(
                        '#cm-cr-dp-review-list div[data-hook="review"], '
                        '#reviewsMedley div[data-hook="review"], '
                        'div[id^="customer_review-"]'
                    )
                    rev_count = await review_containers.count()
                    for ri in range(min(rev_count, 10)):
                        rdiv = review_containers.nth(ri)
                        rev = await self._extract_single_review(rdiv, asin)
                        if rev and rev.get("body"):
                            page_reviews.append(rev)
                except Exception as e:
                    logger.debug("Product page review extraction failed for %s: %s", asin, e)

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

                logger.info("Scraped product page for ASIN %s", asin)
                return result

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Product scrape attempt %d/%d failed for ASIN %s: %s",
                    attempt, _MAX_RETRIES, asin, exc,
                )
                if attempt < _MAX_RETRIES:
                    await self._random_delay(1.0, 2.0)
            finally:
                if browser:
                    await browser.close()
                if pw:
                    try:
                        await pw.stop()
                    except Exception:
                        pass

        raise ScrapingError(
            f"Failed to scrape product page for ASIN '{asin}' after {_MAX_RETRIES} attempts: {last_error}"
        )

    # ------------------------------------------------------------------
    # 3. Single review extraction (shared helper)
    # ------------------------------------------------------------------

    async def _extract_single_review(self, div, asin: str) -> dict | None:
        """Extract a single review from a review div element.

        Reusable across product-page top reviews and dedicated review pages.
        """
        review_id = await div.get_attribute("id")

        # Rating
        review_rating: int | None = None
        try:
            star_el = div.locator(
                'i[data-hook="review-star-rating"] span.a-icon-alt, '
                'i[data-hook="cmps-review-star-rating"] span.a-icon-alt'
            ).first
            if await star_el.count():
                star_text = await star_el.inner_text()
                parsed = self._safe_float(star_text)
                review_rating = int(parsed) if parsed is not None else None
        except Exception:
            pass

        # Title
        review_title: str | None = None
        try:
            title_el = div.locator(
                'a[data-hook="review-title"] span:not(.a-icon-alt), '
                'span[data-hook="review-title"] span:not(.a-icon-alt)'
            ).first
            if await title_el.count():
                review_title = (await title_el.inner_text()).strip()
        except Exception:
            pass

        # Body
        review_body: str | None = None
        try:
            body_el = div.locator('span[data-hook="review-body"] span').first
            if await body_el.count():
                review_body = (await body_el.inner_text()).strip()
        except Exception:
            pass

        # Date
        review_date: str | None = None
        try:
            date_el = div.locator('span[data-hook="review-date"]').first
            if await date_el.count():
                date_text = (await date_el.inner_text()).strip()
                date_match = re.search(
                    r"on\s+(\w+\s+\d{1,2},\s+\d{4})",
                    date_text,
                )
                if date_match:
                    try:
                        parsed_date = datetime.strptime(
                            date_match.group(1), "%B %d, %Y"
                        )
                        review_date = parsed_date.date().isoformat()
                    except ValueError:
                        review_date = date_match.group(1)
        except Exception:
            pass

        # Verified purchase
        verified_purchase = False
        try:
            vp_el = div.locator('span[data-hook="avp-badge"]')
            verified_purchase = (await vp_el.count()) > 0
        except Exception:
            pass

        # Helpful votes
        helpful_votes: int = 0
        try:
            helpful_el = div.locator('span[data-hook="helpful-vote-statement"]').first
            if await helpful_el.count():
                helpful_text = await helpful_el.inner_text()
                if "one" in helpful_text.lower():
                    helpful_votes = 1
                else:
                    helpful_votes = self._safe_int(helpful_text) or 0
        except Exception:
            pass

        # Vine voice
        is_vine = False
        try:
            vine_el = div.locator(
                'span[data-hook="vine-review-badge"], '
                'span.a-color-link:has-text("Vine")'
            )
            is_vine = (await vine_el.count()) > 0
        except Exception:
            pass

        if not review_body and not review_title:
            return None

        return {
            "asin": asin,
            "review_id": review_id,
            "rating": review_rating,
            "title": review_title,
            "body": review_body,
            "review_date": review_date,
            "verified_purchase": verified_purchase,
            "helpful_votes": helpful_votes,
            "is_vine": is_vine,
        }

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
        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            browser: Browser | None = None
            pw = None
            try:
                pw = await async_playwright().start()
                browser = await self._launch_browser(pw)
                page = await self._new_page(browser)

                for page_num in range(1, max_pages + 1):
                    url = (
                        f"https://www.{self._marketplace.domain}/product-reviews/{asin}"
                        f"?filterByStar={filter_star}"
                        f"&pageNumber={page_num}"
                    )
                    logger.info(
                        "Scraping reviews for %s, page %d/%d, filter=%s (attempt %d)",
                        asin, page_num, max_pages, filter_star, attempt,
                    )

                    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

                    # Wait for review cards — try multiple selectors
                    review_selector: str | None = None
                    for rs in (
                        'div[data-hook="review"]',
                        'div.review',
                        'div[id^="customer_review-"]',
                        'div.a-section.review',
                        'div[class*="review-views"]',
                        'div.cr-widget-FocalReviews div[id^="R"]',
                    ):
                        try:
                            await page.wait_for_selector(rs, timeout=8_000)
                            review_selector = rs
                            break
                        except Exception:
                            continue

                    if not review_selector:
                        # Debug: log what's on the page
                        try:
                            page_title = await page.title()
                            body_text_len = len(await page.locator("body").inner_text())
                            logger.info(
                                "Review page debug for %s page %d: title='%s', body_len=%d",
                                asin, page_num, page_title[:80] if page_title else "N/A", body_text_len,
                            )
                        except Exception:
                            pass
                        logger.info(
                            "No more reviews found for %s at page %d",
                            asin, page_num,
                        )
                        break

                    review_divs = page.locator(review_selector)
                    count = await review_divs.count()
                    if count == 0:
                        break

                    for i in range(count):
                        div = review_divs.nth(i)
                        rev = await self._extract_single_review(div, asin)
                        if rev:
                            all_reviews.append(rev)

                    # Random delay between review pages
                    if page_num < max_pages:
                        await self._random_delay()

                logger.info(
                    "Scraped %d reviews for ASIN %s (filter=%s)",
                    len(all_reviews), asin, filter_star,
                )
                return all_reviews

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Review scrape attempt %d/%d failed for ASIN %s: %s",
                    attempt, _MAX_RETRIES, asin, exc,
                )
                all_reviews.clear()
                if attempt < _MAX_RETRIES:
                    await self._random_delay(1.0, 2.0)
            finally:
                if browser:
                    await browser.close()
                if pw:
                    try:
                        await pw.stop()
                    except Exception:
                        pass

        raise ScrapingError(
            f"Failed to scrape reviews for ASIN '{asin}' after {_MAX_RETRIES} attempts: {last_error}"
        )

    # ------------------------------------------------------------------
    # 5. Stock level scraper (lightweight)
    # ------------------------------------------------------------------

    async def scrape_stock_level(self, asin: str) -> dict:
        """Scrape only the availability/stock level for an ASIN.

        Much lighter than a full product page scrape — only extracts the
        #availability element to get stock status.
        """
        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            browser: Browser | None = None
            pw = None
            try:
                pw = await async_playwright().start()
                browser = await self._launch_browser(pw)
                page = await self._new_page(browser)

                url = f"https://www.{self._marketplace.domain}/dp/{asin}"
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await self._random_delay(1.0, 2.0)

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

                return {
                    "asin": asin,
                    "stock_level": stock_level,
                    "stock_text": stock_text,
                    "is_in_stock": is_in_stock,
                }

            except Exception as exc:
                last_error = exc
                logger.warning("Stock scrape attempt %d/%d failed for %s: %s", attempt, _MAX_RETRIES, asin, exc)
                if attempt < _MAX_RETRIES:
                    await self._random_delay(1.0, 2.0)
            finally:
                if browser:
                    await browser.close()
                if pw:
                    try:
                        await pw.stop()
                    except Exception:
                        pass

        raise ScrapingError(f"Failed to scrape stock for ASIN '{asin}' after {_MAX_RETRIES} attempts: {last_error}")

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
                headers={"User-Agent": self._get_random_user_agent()},
                timeout=10.0,
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
        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            browser: Browser | None = None
            pw = None
            try:
                pw = await async_playwright().start()
                browser = await self._launch_browser(pw)
                page = await self._new_page(browser)

                url = f"https://www.{self._marketplace.domain}/s?k={quote_plus(keyword)}"
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await self._random_delay(1.5, 3.0)

                # Total result count from header text
                total_result_count: int = 0
                try:
                    result_header = await self._safe_text(
                        page,
                        'span[data-component-type="s-result-info-bar"] .a-text-bold, '
                        '.s-desktop-toolbar .a-spacing-small span, '
                        '#search h1 .a-color-state'
                    )
                    if result_header:
                        # Parse "1-48 of over 2,000 results" or "1-48 of 347 results"
                        count_match = re.search(r"of\s+(?:over\s+)?([\d,]+)", result_header)
                        if count_match:
                            total_result_count = int(count_match.group(1).replace(",", ""))
                except Exception:
                    pass

                # Count sponsored results
                sponsored_count: int = 0
                try:
                    sponsored_els = page.locator(
                        'div[data-component-type="sp-sponsored-result"], '
                        'div.AdHolder, '
                        'span.a-color-secondary:has-text("Sponsored")'
                    )
                    sponsored_count = await sponsored_els.count()
                except Exception:
                    pass

                # Count unique brands visible
                brand_count: int = 0
                try:
                    brand_els = page.locator(
                        'div.s-result-item span.a-size-base-plus.a-color-base, '
                        'div.s-result-item .a-row .a-size-base'
                    )
                    bc = await brand_els.count()
                    brands_seen = set()
                    for i in range(min(bc, 48)):
                        try:
                            bt = (await brand_els.nth(i).inner_text()).strip().lower()
                            if bt:
                                brands_seen.add(bt)
                        except Exception:
                            continue
                    brand_count = len(brands_seen)
                except Exception:
                    pass

                return {
                    "keyword": keyword,
                    "total_result_count": total_result_count,
                    "sponsored_count": sponsored_count,
                    "brand_count": brand_count,
                }

            except Exception as exc:
                last_error = exc
                logger.warning("SERP metadata attempt %d/%d failed for '%s': %s", attempt, _MAX_RETRIES, keyword, exc)
                if attempt < _MAX_RETRIES:
                    await self._random_delay(1.0, 2.0)
            finally:
                if browser:
                    await browser.close()
                if pw:
                    try:
                        await pw.stop()
                    except Exception:
                        pass

        logger.warning("SERP metadata failed for '%s' after all retries: %s", keyword, last_error)
        return {"keyword": keyword, "total_result_count": 0, "sponsored_count": 0, "brand_count": 0}
