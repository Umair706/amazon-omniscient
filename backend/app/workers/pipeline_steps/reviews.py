"""Pipeline step: collect stored reviews for a niche and run the LLM review analysis."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.review import Review
from app.services.review_analyzer import ReviewAnalyzer

logger = logging.getLogger(__name__)

# WHY: 30 reviews per ASIN keeps the blueprint/intelligence prompts under ~8K tokens.
MAX_REVIEWS_PER_ASIN = 30


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
