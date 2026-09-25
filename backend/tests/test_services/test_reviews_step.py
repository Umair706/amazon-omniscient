import pytest
from unittest.mock import AsyncMock

from app.workers.pipeline_steps.reviews import flatten_reviews, run_review_analysis

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
