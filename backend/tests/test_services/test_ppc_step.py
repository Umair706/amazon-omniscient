from unittest.mock import AsyncMock, MagicMock

from app.workers.pipeline_steps.ppc import build_ppc_strategy, ppc_metrics_from_strategy


def _fake_ppc_service():
    from app.services.ppc_service import PPCService
    svc = PPCService(db=MagicMock(), llm_client=None)
    svc.build_keyword_portfolio = AsyncMock(return_value={
        "exact_match": [{"keyword": "garlic press", "search_volume": 3000, "avg_cpc": 1.2, "competition": "high", "relevance_score": 90}],
        "phrase_match": [], "broad_match": [], "negative_candidates": [],
        "total_keywords": 1, "estimated_daily_spend": 3.6, "estimated_monthly_spend": 108,
    })
    svc.save_ppc_keywords = AsyncMock(return_value=1)
    return svc


async def test_build_ppc_strategy_uses_deterministic_budget_and_saves_keywords():
    svc = _fake_ppc_service()
    metrics = {"avg_price": 30, "landed_cost": 8, "fba_fees": 5, "ppc_daily_budget": 30}
    strategy = await build_ppc_strategy(svc, niche_id=1, keyword="garlic press", metrics=metrics, competitor_landscape=None)
    assert strategy["phases"]["launch"]["monthly_budget"] > 0
    assert strategy["break_even"]["break_even_acos"] > 0
    assert strategy["top_keywords"] == ["garlic press"]
    assert strategy["llm_strategy"] is None
    svc.save_ppc_keywords.assert_awaited_once()


def test_ppc_metrics_from_strategy_maps_real_keys():
    strategy = {
        "avg_cpc": 1.2, "total_keywords": 12, "total_90_day_budget": 2700,
        "phases": {"launch": {"daily_budget": 45, "estimated_acos": 62.5}},
        "break_even": {"break_even_acos": 41.0},
    }
    m = ppc_metrics_from_strategy(strategy)
    assert m == {
        "avg_cpc": 1.2, "break_even_acos": 41.0, "relevant_keyword_count": 12,
        "ppc_budget_90d": 2700, "estimated_acos": 62.5, "ppc_daily_budget": 45,
    }


def test_ppc_metrics_from_strategy_omits_zero_cpc_so_keyword_research_estimate_survives():
    m = ppc_metrics_from_strategy({"avg_cpc": 0, "total_keywords": 0, "phases": {}, "break_even": {}})
    assert "avg_cpc" not in m
