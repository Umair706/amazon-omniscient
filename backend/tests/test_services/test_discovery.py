"""Discovery pre-score and candidate selection."""

from app.services.discovery import DiscoveryService, opportunity_prescore


def test_promising_niche_scores_high():
    # Solid demand, few competing listings, no dominant brands or heavy ads.
    result = opportunity_prescore(volume_tier="high", total_results=1500, sponsored_count=2, brand_count=1)
    assert result["score"] >= 65
    assert result["label"] == "Promising"


def test_saturated_niche_scores_low():
    # High demand but a saturated, brand-dominated, ad-heavy shelf.
    result = opportunity_prescore(volume_tier="very_high", total_results=50000, sponsored_count=12, brand_count=18)
    assert result["score"] < 45
    assert result["label"] == "Crowded"


def test_thin_market_is_flagged():
    result = opportunity_prescore(volume_tier="very_low", total_results=20, sponsored_count=0, brand_count=0)
    assert result["label"] == "Too thin"
    assert result["score"] < 45


def test_pick_candidates_drops_the_bare_seed_and_single_words():
    candidates = [
        {"keyword": "kitchen"},            # the seed itself — too broad
        {"keyword": "knives"},             # single word — still too broad
        {"keyword": "garlic press"},       # a real niche
        {"keyword": "silicone baking mat"},
    ]
    picked = DiscoveryService._pick_candidates("kitchen", candidates, limit=10)
    assert picked == ["garlic press", "silicone baking mat"]


def test_pick_candidates_respects_the_limit():
    candidates = [{"keyword": f"widget type {i}"} for i in range(20)]
    assert len(DiscoveryService._pick_candidates("widget", candidates, limit=5)) == 5
