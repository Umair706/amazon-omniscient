"""Pipeline step: scrape each product's detail page and save what it shows."""

import logging
from datetime import date, datetime, timezone

from dateutil.parser import parse as parse_date_text
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.stock_history import StockHistory
from app.services.bsr_tracker import BSRTracker
from app.services.scraper_service import FROM_CACHE_KEY, ScraperService

logger = logging.getLogger(__name__)

# (key in the scraped detail dict, attribute on the Product row).
# A value is copied only when the scrape actually found one.
_DETAIL_TO_PRODUCT_FIELDS = [
    ("title", "title"), ("price", "current_price"), ("rating", "rating"),
    ("review_count", "review_count"), ("brand", "brand"),
    ("current_bsr", "current_bsr"), ("bsr_category", "bsr_category"),
    ("current_subcategory_bsr", "current_subcategory_bsr"), ("subcategory_name", "subcategory_name"),
    ("bullet_count", "bullet_count"), ("image_count", "image_count"),
    ("has_video", "has_video"), ("has_a_plus", "has_a_plus"), ("has_brand_story", "has_brand_story"),
    ("seller_id", "seller_id"), ("stock_level", "last_stock_level"),
    ("list_price", "list_price"), ("star_distribution", "star_distribution"),
    ("variation_count", "variation_count"), ("category_path", "category_path"),
    ("seller_count", "seller_count"), ("fbt_asins", "fbt_asins"), ("qa_count", "qa_count"),
    ("deal_badge", "deal_badge"), ("amazons_choice_keyword", "amazons_choice_keyword"),
    ("review_attributes", "review_attributes"), ("comparison_asins", "comparison_asins"),
    ("weight", "weight"), ("dimensions", "product_dimensions"),
]

_EMPTY_VALUES = (None, "", [], {})


async def scrape_product_details(
    db: AsyncSession, products_data: list[dict], scraper: ScraperService
) -> list[dict]:
    """Scrape each product's detail page, save it onto its Product row, and return the detail dicts."""
    detailed = []
    for product_data in products_data:
        asin = product_data.get("asin")
        if not asin:
            continue
        detail = await _scrape_one_product_page(scraper, asin)
        if not detail:
            continue
        detailed.append(detail)
        await _save_detail_in_savepoint(db, asin, detail)
    await db.commit()
    return detailed


async def _scrape_one_product_page(scraper: ScraperService, asin: str) -> dict | None:
    """Scrape one product page. Returns None (and logs) when the scrape fails."""
    try:
        return await scraper.scrape_product_page(asin)
    except Exception as e:
        logger.warning("Failed to scrape details for %s: %s", asin, e)
        return None


async def _save_detail_in_savepoint(db: AsyncSession, asin: str, detail: dict) -> None:
    """Save one product's detail. A failure rolls back only this product's changes."""
    # WHY: without a savepoint one failed insert leaves the whole session
    # unusable, so every later product and the final commit would fail too.
    try:
        async with db.begin_nested():
            await _save_detail(db, asin, detail)
    except Exception as e:
        logger.warning("Failed to save details for %s (rolled back to savepoint): %s", asin, e)


async def _save_detail(db: AsyncSession, asin: str, detail: dict) -> None:
    """Copy the detail onto the stored product and record its first history snapshot."""
    product = (await db.execute(select(Product).where(Product.asin == asin))).scalar_one_or_none()
    if product is None:
        return
    apply_detail_to_product(product, detail)
    # WHY: a cache hit returns a page that may be up to 24h old. Recording it
    # under today's timestamp would corrupt the BSR/price/stock history the
    # velocity and trend code reads, so only a live scrape gets a snapshot.
    if not detail.get(FROM_CACHE_KEY):
        await _record_first_snapshots(db, product, detail)


def apply_detail_to_product(product: Product, detail: dict) -> None:
    """Copy every field the scrape found onto the Product row. Missing fields keep their stored value."""
    for detail_key, product_attribute in _DETAIL_TO_PRODUCT_FIELDS:
        value = detail.get(detail_key)
        if value not in _EMPTY_VALUES:
            setattr(product, product_attribute, value)
    last_scraped_at = _parse_iso_datetime(detail.get("last_scraped_at"))
    if last_scraped_at is not None:
        product.last_scraped_at = last_scraped_at
    date_first_available = _parse_loose_date(detail.get("date_first_available"))
    if date_first_available is not None:
        product.date_first_available = date_first_available


async def _record_first_snapshots(db: AsyncSession, product: Product, detail: dict) -> None:
    """Record a BSR/price/stock snapshot at analysis time, so charts have a starting point before the first tracker run."""
    await BSRTracker(db).record_product_snapshot(
        product_id=product.id, asin=product.asin,
        bsr=detail.get("current_bsr"), category_name=detail.get("bsr_category"),
        subcategory_bsr=detail.get("current_subcategory_bsr"), subcategory_name=detail.get("subcategory_name"),
        price=detail.get("price"),
    )
    if detail.get("is_in_stock") is None:
        return
    db.add(StockHistory(
        time=datetime.now(timezone.utc), product_id=product.id, asin=product.asin,
        stock_level=detail.get("stock_level"), stock_text=detail.get("stock_text"),
        is_in_stock=detail["is_in_stock"],
    ))


def _parse_iso_datetime(text: str | None) -> datetime | None:
    """Parse an ISO timestamp. Returns None for missing or malformed text."""
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None


def _parse_loose_date(text: str | None) -> date | None:
    """Parse a date written the way Amazon shows it ("12 March 2021"). Returns None if unreadable."""
    if not text:
        return None
    try:
        return parse_date_text(text).date()
    except (ValueError, OverflowError, TypeError):
        return None
