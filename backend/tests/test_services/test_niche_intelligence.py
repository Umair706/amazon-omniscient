from unittest.mock import AsyncMock

from app.services.niche_intelligence import NicheIntelligenceService

LANDSCAPE = {
    "price_stats": {"min": 10, "max": 40}, "review_stats": {"min": 5, "max": 900},
    "competitor_details": [{
        "asin": "B0A",
        "listing_scores": {"overall_score": 72.5},
        "vulnerabilities": {"vulnerability_level": "high", "vulnerability_types": ["few_reviews", "no_video"]},
    }],
}
PRODUCTS = [{"asin": "B0A", "title": "Press", "price": 20, "rating": 4.0, "review_count": 30, "current_bsr": 5000}]


async def test_niche_overview_counts_high_vulnerability_competitors():
    llm = AsyncMock(); llm.generate_json = AsyncMock(return_value={})
    await NicheIntelligenceService(llm).generate_niche_overview("garlic press", PRODUCTS, LANDSCAPE, {"avg_price": 20})
    assert "High vulnerability competitors: 1" in llm.generate_json.call_args.args[0]


async def test_product_overviews_prompt_shows_score_and_vulnerabilities():
    llm = AsyncMock(); llm.generate_json = AsyncMock(return_value=[{"asin": "B0A"}])
    await NicheIntelligenceService(llm).generate_product_overviews(PRODUCTS, LANDSCAPE["competitor_details"])
    prompt = llm.generate_json.call_args.args[0]
    assert "Listing quality: 72.5/100" in prompt
    assert "Vulnerabilities: few_reviews, no_video" in prompt
