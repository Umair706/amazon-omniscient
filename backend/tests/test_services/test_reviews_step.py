from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.workers.pipeline_steps.reviews import (
    flatten_reviews,
    run_review_analysis,
    save_reviews_for_product,
)

# The shape ScraperService._extract_single_review returns.
SCRAPED_REVIEW = {
    "asin": "B00HEZ888K", "review_id": "RB8S0EREZIV75", "rating": 5,
    "title": "OXO Good Grips Garlic Press, Black", "body": "Great garlic press, easy to use and clean.",
    "review_date": "2026-07-28", "verified_purchase": True, "helpful_votes": 1, "is_vine": False,
}


def _fake_db(review_id_already_stored: list[bool]) -> MagicMock:
    """A session whose duplicate lookups answer in the given order."""
    lookups = []
    for already_stored in review_id_already_stored:
        result = MagicMock()
        result.scalar_one_or_none.return_value = 1 if already_stored else None
        lookups.append(result)
    db = MagicMock()
    db.execute = AsyncMock(side_effect=lookups)
    db.flush = AsyncMock()
    return db


async def test_save_reviews_for_product_stores_every_scraped_field():
    db = _fake_db([False])
    product = SimpleNamespace(id=7, asin="B00HEZ888K")
    saved = await save_reviews_for_product(db, product, [SCRAPED_REVIEW])
    assert saved == 1
    stored = db.add.call_args.args[0]
    assert stored.product_id == 7
    assert stored.asin == "B00HEZ888K"
    assert stored.review_id == "RB8S0EREZIV75"
    assert stored.rating == 5
    assert stored.body == "Great garlic press, easy to use and clean."
    assert stored.review_date == date(2026, 7, 28)
    assert stored.verified_purchase is True
    assert stored.helpful_votes == 1
    assert stored.is_vine is False


async def test_save_reviews_for_product_skips_review_ids_already_stored():
    db = _fake_db([True, False])
    second = {**SCRAPED_REVIEW, "review_id": "R9W51ZVQXG7F3"}
    saved = await save_reviews_for_product(db, SimpleNamespace(id=7, asin="B00HEZ888K"), [SCRAPED_REVIEW, second])
    assert saved == 1
    assert db.add.call_args.args[0].review_id == "R9W51ZVQXG7F3"


async def test_save_reviews_for_product_keeps_a_review_without_a_date():
    db = _fake_db([False])
    undated = {**SCRAPED_REVIEW, "review_date": None}
    await save_reviews_for_product(db, SimpleNamespace(id=7, asin="B00HEZ888K"), [undated])
    assert db.add.call_args.args[0].review_date is None

REVIEWS_BY_ASIN = {
    "B0A": [{"rating": 2, "title": "Broke", "body": "Handle snapped after a week", "verified_purchase": True, "helpful_votes": 3}],
    "B0B": [{"rating": 5, "title": "Great", "body": "Crushes garlic fine", "verified_purchase": True, "helpful_votes": 0}],
}


def test_flatten_reviews_keeps_every_review():
    flat = flatten_reviews(REVIEWS_BY_ASIN)
    assert len(flat) == 2
    assert {r["body"] for r in flat} == {"Handle snapped after a week", "Crushes garlic fine"}


async def test_run_review_analysis_passes_dicts_and_keyword_to_llm():
    llm = AsyncMock()
    llm.generate_json = AsyncMock(return_value={"sentiment_score": 60, "pain_points": [{"theme": "handle breaks"}], "positive_themes": []})
    result = await run_review_analysis(llm, REVIEWS_BY_ASIN, keyword="garlic press")
    prompt = llm.generate_json.call_args.args[0]
    assert "garlic press" in prompt
    assert "Handle snapped after a week" in prompt
    assert result["pain_points"][0]["theme"] == "handle breaks"


async def test_run_review_analysis_returns_none_without_reviews_or_llm():
    assert await run_review_analysis(None, REVIEWS_BY_ASIN, keyword="x") is None
    assert await run_review_analysis(AsyncMock(), {}, keyword="x") is None
