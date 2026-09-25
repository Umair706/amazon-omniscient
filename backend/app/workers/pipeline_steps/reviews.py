"""Pipeline step: save scraped reviews, collect stored reviews for a niche, and run the LLM review analysis."""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.review import Review
from app.services.review_analyzer import ReviewAnalyzer

logger = logging.getLogger(__name__)

# WHY: 30 reviews per ASIN keeps the blueprint/intelligence prompts under ~8K tokens.
MAX_REVIEWS_PER_ASIN = 30

# WHY: reviews.rating is NOT NULL, so a card whose stars we could not read is stored as 0 (never a real rating).
UNREADABLE_RATING = 0


async def collect_reviews_by_asin(db: AsyncSession, niche_id: int) -> dict[str, list[dict]]:
    """Return {asin: [review dicts]} for every product in the niche, most helpful first."""
    stmt = (
        select(Product.asin, Review.rating, Review.title, Review.body, Review.verified_purchase, Review.helpful_votes)
        .join(Review, Review.product_id == Product.id)
        .where(Product.niche_id == niche_id)
        .order_by(Product.asin, Review.helpful_votes.desc())
    )
    rows = (await db.execute(stmt)).all()

    reviews_by_asin: dict[str, list[dict]] = {}
    for asin, rating, title, body, verified, helpful in rows:
        bucket = reviews_by_asin.setdefault(asin, [])
        if len(bucket) >= MAX_REVIEWS_PER_ASIN:
            continue
        bucket.append({
            "rating": rating,
            "title": title,
            "body": body,
            "verified_purchase": verified,
            "helpful_votes": helpful or 0,
        })
    return reviews_by_asin


async def save_reviews_for_product(db: AsyncSession, product: Product, reviews: list[dict]) -> int:
    """Add scraped review dicts for *product* to the session. Skips review_ids already stored. Returns how many were added."""
    saved = 0
    for review in reviews:
        if await _is_review_already_stored(db, review.get("review_id")):
            continue
        db.add(_build_review_row(product, review))
        saved += 1
    await db.flush()
    return saved


async def _is_review_already_stored(db: AsyncSession, review_id: str | None) -> bool:
    """True when a review with this Amazon review id is already in the table."""
    if not review_id:
        return False
    existing = await db.execute(select(Review.id).where(Review.review_id == review_id).limit(1))
    return existing.scalar_one_or_none() is not None


def _build_review_row(product: Product, review: dict) -> Review:
    """Turn one scraped review dict (ScraperService._extract_single_review) into a Review row."""
    return Review(
        product_id=product.id,
        asin=product.asin,
        review_id=review.get("review_id"),
        rating=review.get("rating") or UNREADABLE_RATING,
        title=review.get("title") or "",
        body=review.get("body") or "",
        review_date=_parse_iso_date(review.get("review_date")),
        verified_purchase=bool(review.get("verified_purchase")),
        helpful_votes=review.get("helpful_votes") or 0,
        is_vine=bool(review.get("is_vine")),
    )


def _parse_iso_date(date_text: str | None) -> date | None:
    """Turn the scraper's ISO date text into a date. None when it is missing or not ISO."""
    # WHY: the column is a Date and asyncpg rejects strings, so the text must be converted here.
    if not date_text:
        return None
    try:
        return date.fromisoformat(date_text)
    except ValueError:
        logger.debug("Review date %r is not ISO (YYYY-MM-DD); storing no date", date_text)
        return None


def flatten_reviews(reviews_by_asin: dict[str, list[dict]]) -> list[dict]:
    """Merge the per-ASIN buckets into one list for the sentiment analyzer."""
    flat: list[dict] = []
    for reviews in reviews_by_asin.values():
        flat.extend(reviews)
    return flat


async def run_review_analysis(llm_client, reviews_by_asin: dict[str, list[dict]], keyword: str) -> dict | None:
    """Run sentiment + pain-point analysis. Returns None when there is nothing to analyze or no LLM."""
    reviews = flatten_reviews(reviews_by_asin)
    if not reviews or llm_client is None:
        return None
    analyzer = ReviewAnalyzer(llm_client)
    try:
        return await analyzer.analyze_reviews(reviews, product_title=keyword, category=keyword)
    except Exception as e:
        logger.warning("Review analysis failed: %s", e)
        return None
