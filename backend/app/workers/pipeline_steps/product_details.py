"""Pipeline step: scrape each product's detail page and save what it shows."""

import logging
import re
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
    db: AsyncSession, products_data: list[dict], scraper: ScraperService,
    marketplace: str = "US", sales_multiplier: float = 1.0,
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
        await _save_detail_in_savepoint(db, asin, detail, marketplace, sales_multiplier)
    await db.commit()
    return detailed


async def _scrape_one_product_page(scraper: ScraperService, asin: str) -> dict | None:
    """Scrape one product page. Returns None (and logs) when the scrape fails."""
    try:
        return await scraper.scrape_product_page(asin)
    except Exception as e:
        logger.warning("Failed to scrape details for %s: %s", asin, e)
        return None


async def _save_detail_in_savepoint(
    db: AsyncSession, asin: str, detail: dict, marketplace: str, sales_multiplier: float = 1.0,
) -> None:
    """Save one product's detail. A failure rolls back only this product's changes."""
    # WHY: without a savepoint one failed insert leaves the whole session
    # unusable, so every later product and the final commit would fail too.
    try:
        async with db.begin_nested():
            await _save_detail(db, asin, detail, marketplace, sales_multiplier)
    except Exception as e:
        logger.warning("Failed to save details for %s (rolled back to savepoint): %s", asin, e)


async def _save_detail(
    db: AsyncSession, asin: str, detail: dict, marketplace: str, sales_multiplier: float = 1.0,
) -> None:
    """Copy the detail onto the stored product and record its first history snapshot."""
    product = (await db.execute(select(Product).where(Product.asin == asin))).scalar_one_or_none()
    if product is None:
        return
    apply_detail_to_product(product, detail)
    _apply_derived_economics(db, product, detail, marketplace, sales_multiplier)
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


def _apply_derived_economics(
    db: AsyncSession, product: Product, detail: dict, marketplace: str, sales_multiplier: float = 1.0,
) -> None:
    """Fill the per-product economics the UI shows: monthly units/revenue, listing quality, fees.

    These are derived from data already on the product (BSR, price, category, listing
    attributes), not scraped. Without them the product page shows blank stat cards even
    though everything needed to compute them is known. Best-effort: each piece is set only
    when its inputs exist, so a listing missing (say) dimensions still gets units and revenue.
    """
    from app.core.bsr_regression import BSRSalesEstimator
    from app.core.category_mapping import category_slugs
    from app.core.fba_calculator import FBAFeeCalculator
    from app.core.units import parse_weight_lb
    from app.services.competitor_service import CompetitorService

    quality = CompetitorService(db).score_listing(detail).get("overall_score")
    if quality is not None:
        product.listing_quality_score = quality

    price = _as_positive_float(detail.get("price"))
    bsr = detail.get("current_bsr")
    category_name = detail.get("bsr_category")
    if bsr:
        units = BSRSalesEstimator(marketplace, sales_multiplier).estimate_monthly_sales(int(bsr), category_name or "default")
        product.estimated_monthly_units = units
        if price:
            product.estimated_monthly_revenue = round(units * price, 2)

    if not price:
        return
    _, fee_slug = category_slugs(category_name)
    calc = FBAFeeCalculator(marketplace)
    weight_lb = parse_weight_lb(detail.get("weight"))
    if weight_lb:
        product.product_weight_lbs = round(weight_lb, 2)
    dims = _parse_dimensions_inches(detail.get("dimensions"))
    if weight_lb and dims:
        # Full fee breakdown needs a size tier, which needs dimensions + weight.
        fees = calc.calculate_all_fees(
            price, *dims, weight_lb, category=fee_slug,
            monthly_units=product.estimated_monthly_units or 100,
        )
        product.fba_fee = fees["fulfillment_fee"]
        product.referral_fee_pct = fees["referral_fee_pct"]
    else:
        # No dimensions: the fulfilment fee is genuinely unknown, but the referral rate is
        # category-based, so fill that and leave fba_fee null.
        referral = calc.calculate_referral_fee(price, fee_slug)
        product.referral_fee_pct = round(referral / price * 100, 2)


def _as_positive_float(value) -> float | None:
    """Coerce a scraped price to a positive float, or None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _parse_dimensions_inches(text: str | None) -> tuple[float, float, float] | None:
    """Parse '10 x 6 x 4 inches' into (10, 6, 4). None if three numbers aren't present."""
    if not text:
        return None
    numbers = re.findall(r"[\d.]+", text)
    if len(numbers) < 3:
        return None
    try:
        return float(numbers[0]), float(numbers[1]), float(numbers[2])
    except ValueError:
        return None


async def _record_first_snapshots(db: AsyncSession, product: Product, detail: dict) -> None:
    """Record a BSR/price/stock snapshot at analysis time, so charts have a starting point before the first tracker run."""
    await BSRTracker(db).record_product_snapshot(
        product_id=product.id, asin=product.asin,
        bsr=detail.get("current_bsr"), category_name=detail.get("bsr_category"),
        subcategory_bsr=detail.get("current_subcategory_bsr"), subcategory_name=detail.get("subcategory_name"),
        price=detail.get("price"), review_count=detail.get("review_count"),
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
