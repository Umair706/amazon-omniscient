"""Headless browser scraper for 1688.com (Chinese wholesale marketplace) supplier data."""

import asyncio
import logging
import random
import re
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

_MAX_RETRIES = 2

# 1688 supplier badge keywords
_POWER_SUPPLIER_BADGE = "\u5b9e\u529b\u5546\u5bb6"  # Power supplier
_GOLD_SUPPLIER_BADGE = "\u91d1\u54c1\u8bda\u4f01"  # Gold supplier
_VERIFIED_BADGES = [_POWER_SUPPLIER_BADGE, _GOLD_SUPPLIER_BADGE, "\u8bda\u4fe1\u901a"]  # Includes Trustpass

# Container selectors for product cards — 1688 updates its layout frequently,
# so we try multiple selectors in order of likelihood.
_CARD_SELECTORS = [
    'div[data-trackkey="offercard"]',
    "div.pc-offer-card",
    "div.sm-offer-item",
    "div.offer-item-row",
    "div.space-offer-card-box",
    "div.common-offer-card",
    "div.img-offer-item",
    "div.mojar-offer-card",
    'div[class*="OfferCard"]',
    'div[class*="offer-card"]',
    'a[class*="CardContainer"]',
]


class SupplierScraper:
    """Scrapes 1688.com search results and product pages for supplier data via Playwright."""

    def __init__(self, proxy_manager: ProxyManager | None = None):
        self.proxy_manager = proxy_manager

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
    async def _safe_text(page_or_locator, selector: str) -> str | None:
        """Return the inner text of *selector*, or ``None`` if not found."""
        try:
            el = page_or_locator.locator(selector).first
            if await el.count() == 0:
                return None
            text = await el.inner_text()
            return text.strip() if text else None
        except Exception:
            return None

    @staticmethod
    async def _safe_attr(page_or_locator, selector: str, attribute: str) -> str | None:
        """Return an element attribute value, or ``None`` if not found."""
        try:
            el = page_or_locator.locator(selector).first
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

    @staticmethod
    def _parse_price_range(text: str | None) -> tuple[float | None, float | None]:
        """Parse a CNY price range from text like '¥12.50 - ¥18.00' or '12.50 - 18.00'.

        Returns (price_min, price_max). If only one price found, both are equal.
        """
        if not text:
            return None, None
        # Remove currency symbols and whitespace
        cleaned = text.replace("\u00a5", "").replace("\u5143", "").replace(",", "").strip()
        # Find all numbers
        prices = re.findall(r"(\d+\.?\d*)", cleaned)
        if not prices:
            return None, None
        try:
            if len(prices) >= 2:
                return float(prices[0]), float(prices[1])
            return float(prices[0]), float(prices[0])
        except (ValueError, IndexError):
            return None, None

    @staticmethod
    def _parse_moq(text: str | None) -> int | None:
        """Parse MOQ from text like '2件起批' or 'Min. Order: 100'.

        Chinese MOQ pattern: number followed by 件起批 / 个起批 / 起订.
        """
        if not text:
            return None
        match = re.search(r"(\d+)", text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_years(text: str | None) -> int | None:
        """Parse years in business from badge text like '8年' or '8 yrs'."""
        if not text:
            return None
        match = re.search(r"(\d+)", text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_transaction_count(text: str | None) -> int | None:
        """Parse transaction count from text like '2.5万笔' or '12345笔'.

        Handles Chinese 万 (10,000) multiplier.
        """
        if not text:
            return None
        # Check for 万 (10k multiplier)
        wan_match = re.search(r"([\d.]+)\s*\u4e07", text)
        if wan_match:
            try:
                return int(float(wan_match.group(1)) * 10000)
            except ValueError:
                pass
        # Plain number
        match = re.search(r"(\d+)", text.replace(",", ""))
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    @staticmethod
    def _check_verified(text: str) -> bool:
        """Check if any verification badges are present in text."""
        for badge in _VERIFIED_BADGES:
            if badge in text:
                return True
        return False

    async def _launch_browser(self, playwright) -> Browser:
        """Launch a Chromium browser instance, optionally with a proxy."""
        launch_kwargs = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        }
        if self.proxy_manager is not None:
            launch_kwargs["proxy"] = self.proxy_manager.get_playwright_proxy()

        browser = await playwright.chromium.launch(**launch_kwargs)
        return browser

    async def _new_page(self, browser: Browser) -> Page:
        """Create a new page with randomised fingerprint, locale set to zh-CN for 1688."""
        context = await browser.new_context(
            user_agent=self._get_random_user_agent(),
            viewport={"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        page = await context.new_page()

        # Mask webdriver property so 1688 doesn't flag as bot
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
            """
        )
        return page

    async def _find_card_selector(self, page: Page) -> str | None:
        """Try each known card selector and return the first one that matches elements."""
        for selector in _CARD_SELECTORS:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    logger.debug("Using card selector: %s (%d cards found)", selector, count)
                    return selector
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # 1. Search results scraper
    # ------------------------------------------------------------------

    async def search_suppliers(self, keyword: str, max_results: int = 10) -> list[dict]:
        """Scrape 1688.com search results for *keyword*.

        1688 supports English keywords directly, so no translation is needed.

        Returns a list of supplier dicts with keys:
            supplier_name, product_title, price_min, price_max, moq,
            location, years_in_business, is_verified, transaction_count,
            response_rate, product_url, image_url
        """
        all_results: list[dict] = []
        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            browser: Browser | None = None
            pw = None
            try:
                pw = await async_playwright().start()
                browser = await self._launch_browser(pw)
                page = await self._new_page(browser)

                url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={quote_plus(keyword)}"
                logger.info(
                    "Scraping 1688 search for '%s' (attempt %d/%d)",
                    keyword, attempt, _MAX_RETRIES,
                )

                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

                # Wait for product cards to appear — try multiple selectors
                card_selector = None
                try:
                    # Give 1688 time to render its dynamic content
                    await asyncio.sleep(5)
                    # Try waiting for any known card selector
                    for sel in _CARD_SELECTORS:
                        try:
                            await page.wait_for_selector(sel, timeout=3000)
                            break
                        except Exception:
                            continue
                    card_selector = await self._find_card_selector(page)
                except Exception:
                    pass

                # If no cards found, try scrolling down to trigger lazy loading
                if not card_selector:
                    try:
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                        await asyncio.sleep(3)
                        card_selector = await self._find_card_selector(page)
                    except Exception:
                        pass

                if not card_selector:
                    # Log what's actually on the page for debugging
                    try:
                        page_title = await page.title()
                        body_classes = await page.evaluate("document.body.className || ''")
                        div_count = await page.evaluate("document.querySelectorAll('div').length")
                        logger.warning(
                            "No product cards found for '%s' on 1688 (attempt %d) - page title: '%s', body classes: '%s', div count: %d",
                            keyword, attempt, page_title, body_classes, div_count,
                        )
                    except Exception:
                        logger.warning(
                            "No product cards found for '%s' on 1688 (attempt %d)",
                            keyword, attempt,
                        )
                    if attempt < _MAX_RETRIES:
                        await self._random_delay(1.0, 2.0)
                        continue
                    break

                cards = page.locator(card_selector)
                count = await cards.count()
                count = min(count, max_results)

                for i in range(count):
                    card = cards.nth(i)
                    try:
                        supplier = await self._extract_card_data(card)
                        if supplier.get("product_title") or supplier.get("supplier_name"):
                            all_results.append(supplier)
                    except Exception as e:
                        logger.debug("Failed to extract card %d: %s", i, e)
                        continue

                    if len(all_results) >= max_results:
                        break

                logger.info(
                    "Scraped %d supplier results for '%s' from 1688",
                    len(all_results), keyword,
                )
                return all_results

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "1688 search scrape attempt %d/%d failed for '%s': %s",
                    attempt, _MAX_RETRIES, keyword, exc,
                )
                all_results.clear()
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

        if last_error:
            raise ScrapingError(
                f"Failed to scrape 1688 suppliers for '{keyword}' "
                f"after {_MAX_RETRIES} attempts: {last_error}"
            )
        return all_results

    async def _extract_card_data(self, card) -> dict:
        """Extract supplier and product data from a single 1688 product card.

        Uses multiple fallback selectors since 1688 updates its layout frequently.
        """
        result: dict = {
            "supplier_name": None,
            "product_title": None,
            "price_min": None,
            "price_max": None,
            "moq": None,
            "location": None,
            "years_in_business": None,
            "is_verified": False,
            "transaction_count": None,
            "response_rate": None,
            "product_url": None,
            "image_url": None,
        }

        # ── Product title ──────────────────────────────────────────────
        for sel in (
            "a.sm-offer-title",
            ".offer-title-text",
            "a[title]",
            "h4 a",
            ".title a",
            ".mojar-element-title a",
        ):
            title = await self._safe_text(card, sel)
            if title:
                result["product_title"] = title
                break

        # ── Product URL ────────────────────────────────────────────────
        for sel in (
            "a.sm-offer-title",
            ".offer-title-text a",
            "a[title]",
            "h4 a",
            ".title a",
            ".mojar-element-title a",
        ):
            href = await self._safe_attr(card, sel, "href")
            if href:
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/"):
                    href = "https://detail.1688.com" + href
                result["product_url"] = href
                break

        # ── Price range ────────────────────────────────────────────────
        for sel in (
            ".sm-offer-priceNum",
            ".element-price",
            ".price",
            ".offer-price",
            "span.price-num",
            ".mojar-element-price",
        ):
            price_text = await self._safe_text(card, sel)
            if price_text:
                price_min, price_max = self._parse_price_range(price_text)
                if price_min is not None:
                    result["price_min"] = price_min
                    result["price_max"] = price_max
                    break

        # ── MOQ (minimum order quantity) ───────────────────────────────
        for sel in (
            ".sm-offer-moq",
            ".offer-quantity",
            ".moq",
            "span.moq-text",
            ".mojar-element-quantity",
        ):
            moq_text = await self._safe_text(card, sel)
            if moq_text:
                moq = self._parse_moq(moq_text)
                if moq is not None:
                    result["moq"] = moq
                    break

        # ── Supplier name ──────────────────────────────────────────────
        for sel in (
            ".sm-offer-companyName",
            ".company-name",
            "a.company-name-text",
            ".offer-company",
            ".mojar-element-company a",
        ):
            name = await self._safe_text(card, sel)
            if name:
                result["supplier_name"] = name
                break

        # ── Location ───────────────────────────────────────────────────
        for sel in (
            ".sm-offer-location",
            ".offer-address",
            ".location",
            ".address",
            ".mojar-element-address",
        ):
            loc = await self._safe_text(card, sel)
            if loc:
                result["location"] = loc
                break

        # ── Years in business & verification badges ────────────────────
        # These are typically in icon/badge containers near the supplier name
        try:
            card_text = await card.inner_text()
        except Exception:
            card_text = ""

        # Years: look for patterns like "8年" (8 years)
        years_match = re.search(r"(\d+)\s*\u5e74", card_text)
        if years_match:
            result["years_in_business"] = self._parse_years(years_match.group(0))

        # Verification badges
        result["is_verified"] = self._check_verified(card_text)

        # ── Transaction count ──────────────────────────────────────────
        for sel in (
            ".sm-offer-trade",
            ".trade-quantity",
            ".deal-cnt",
            ".mojar-element-trade",
        ):
            trade_text = await self._safe_text(card, sel)
            if trade_text:
                result["transaction_count"] = self._parse_transaction_count(trade_text)
                if result["transaction_count"] is not None:
                    break

        # Fallback: parse transaction count from full card text
        if result["transaction_count"] is None and card_text:
            # Look for patterns like "2.5万笔" or "12345笔"
            txn_match = re.search(r"([\d.]+\u4e07?\u7b14)", card_text)
            if txn_match:
                result["transaction_count"] = self._parse_transaction_count(txn_match.group(0))

        # ── Response rate ──────────────────────────────────────────────
        for sel in (
            ".sm-offer-response",
            ".response-rate",
            ".reply-rate",
        ):
            rate_text = await self._safe_text(card, sel)
            if rate_text:
                result["response_rate"] = self._safe_float(rate_text)
                if result["response_rate"] is not None:
                    break

        # Fallback: parse from full card text
        if result["response_rate"] is None and card_text:
            rate_match = re.search(r"(\d+\.?\d*)\s*%", card_text)
            if rate_match:
                result["response_rate"] = float(rate_match.group(1))

        # ── Image URL ─────────────────────────────────────────────────
        for sel in (
            ".sm-offer-photo img",
            ".offer-photo img",
            ".img-container img",
            "img.offer-img",
            ".mojar-element-image img",
            "img",
        ):
            img = await self._safe_attr(card, sel, "src")
            if img:
                if img.startswith("//"):
                    img = "https:" + img
                result["image_url"] = img
                break

        return result

    # ------------------------------------------------------------------
    # 2. Product detail page scraper
    # ------------------------------------------------------------------

    async def get_supplier_detail(self, product_url: str) -> dict:
        """Scrape a specific 1688 product page for additional supplier detail.

        Extracts:
            - moq_tiers: list of {qty, price} dicts for tiered pricing
            - shipping_options: list of available shipping methods
            - certifications: list of certification names
            - factory_photos_count: number of factory/workshop photos
            - detailed_description: product description text (truncated)
        """
        result: dict = {
            "moq_tiers": [],
            "shipping_options": [],
            "certifications": [],
            "factory_photos_count": 0,
            "detailed_description": None,
        }

        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            browser: Browser | None = None
            pw = None
            try:
                pw = await async_playwright().start()
                browser = await self._launch_browser(pw)
                page = await self._new_page(browser)

                logger.info(
                    "Scraping 1688 product detail: %s (attempt %d/%d)",
                    product_url, attempt, _MAX_RETRIES,
                )

                await page.goto(product_url, wait_until="domcontentloaded", timeout=30_000)
                await asyncio.sleep(3)  # Let dynamic content render

                # ── MOQ tiers (tiered pricing table) ───────────────────
                try:
                    tier_rows = page.locator(
                        "table.price-range-table tr, "
                        ".obj-sku .price-range tr, "
                        "div.sku-price-range tr, "
                        ".d-content-price-item"
                    )
                    tier_count = await tier_rows.count()
                    for t in range(tier_count):
                        row = tier_rows.nth(t)
                        row_text = await row.inner_text()
                        # Parse "100-499 ¥12.50" style rows
                        qty_match = re.search(r"(\d+)", row_text)
                        price_match = re.search(r"[\u00a5\u5143]?\s*([\d.]+)", row_text)
                        if qty_match and price_match:
                            result["moq_tiers"].append({
                                "qty": int(qty_match.group(1)),
                                "price": float(price_match.group(1)),
                            })
                except Exception:
                    pass

                # ── Shipping options ───────────────────────────────────
                try:
                    shipping_els = page.locator(
                        "div.logistics-content span, "
                        ".obj-logistics span.type-text, "
                        ".shipping-method span"
                    )
                    ship_count = await shipping_els.count()
                    for s in range(min(ship_count, 10)):
                        ship_text = (await shipping_els.nth(s).inner_text()).strip()
                        if ship_text and len(ship_text) < 50:
                            result["shipping_options"].append(ship_text)
                except Exception:
                    pass

                # ── Certifications ─────────────────────────────────────
                try:
                    cert_els = page.locator(
                        "div.cert-list span, "
                        ".qualification-item, "
                        ".cert-name, "
                        ".certificate-item span"
                    )
                    cert_count = await cert_els.count()
                    for c in range(min(cert_count, 20)):
                        cert_text = (await cert_els.nth(c).inner_text()).strip()
                        if cert_text and len(cert_text) < 100:
                            result["certifications"].append(cert_text)
                except Exception:
                    pass

                # Fallback: scan page text for common certifications
                if not result["certifications"]:
                    try:
                        page_text = await page.inner_text("body")
                        cert_keywords = ["ISO", "CE", "FCC", "RoHS", "BSCI", "SGS", "UL", "FDA"]
                        for cert in cert_keywords:
                            if cert in page_text:
                                result["certifications"].append(cert)
                    except Exception:
                        pass

                # ── Factory photos count ───────────────────────────────
                try:
                    factory_imgs = page.locator(
                        "div.factory-info img, "
                        ".company-photo img, "
                        ".workshop-photo img, "
                        ".factory-album img"
                    )
                    result["factory_photos_count"] = await factory_imgs.count()
                except Exception:
                    pass

                # ── Product description (truncated) ────────────────────
                try:
                    for sel in (
                        "div.detail-descript",
                        "div.offer-attr-list",
                        "#desc-lazyload-container",
                        ".de-description",
                    ):
                        desc = await self._safe_text(page, sel)
                        if desc:
                            # Truncate to first 500 chars for storage
                            result["detailed_description"] = desc[:500]
                            break
                except Exception:
                    pass

                logger.info("Scraped 1688 product detail: %s", product_url)
                return result

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "1688 detail scrape attempt %d/%d failed for %s: %s",
                    attempt, _MAX_RETRIES, product_url, exc,
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

        if last_error:
            raise ScrapingError(
                f"Failed to scrape 1688 product detail for '{product_url}' "
                f"after {_MAX_RETRIES} attempts: {last_error}"
            )
        return result
