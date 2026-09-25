"""Pipeline step: build the PPC plan from keyword data (deterministic) plus an optional LLM narrative."""

import logging

from app.services.ppc_service import PPCService

logger = logging.getLogger(__name__)

# Fallbacks used only when upstream metrics are missing these values.
DEFAULT_SELLING_PRICE = 30.0
DEFAULT_LANDED_COST = 8.0
DEFAULT_FBA_FEES = 5.0
DEFAULT_DAILY_BUDGET = 30.0
TOP_KEYWORDS_SHOWN = 10


async def build_ppc_strategy(
    ppc_svc: PPCService, *, niche_id: int, keyword: str, metrics: dict, competitor_landscape: dict | None,
) -> dict:
    """Return the budget plan (numbers we computed) merged with break-even data and the LLM narrative."""
    selling_price = metrics.get("avg_price") or DEFAULT_SELLING_PRICE
    break_even = ppc_svc.calculate_break_even_acos(
        selling_price=selling_price,
        landed_cost=metrics.get("landed_cost") or DEFAULT_LANDED_COST,
        fba_fees=metrics.get("fba_fees") or DEFAULT_FBA_FEES,
    )
    portfolio = await ppc_svc.build_keyword_portfolio(niche_id=niche_id)
    budget_plan = ppc_svc.plan_budget(
        keyword_portfolio=portfolio,
        target_acos=break_even["target_acos"],
        selling_price=selling_price,
        daily_budget_cap=metrics.get("ppc_daily_budget") or DEFAULT_DAILY_BUDGET,
    )
    await ppc_svc.save_ppc_keywords(niche_id, portfolio)

    llm_strategy = None
    if ppc_svc.llm:
        try:
            llm_strategy = await ppc_svc.generate_ppc_strategy(
                niche_keyword=keyword,
                keyword_portfolio=portfolio,
                budget_plan=budget_plan,
                break_even_acos=break_even,
                competitor_landscape=competitor_landscape,
            )
        except Exception as e:
            logger.warning("LLM PPC strategy failed: %s", e)

    return {
        **budget_plan,
        "break_even": break_even,
        "top_keywords": [k["keyword"] for k in portfolio.get("exact_match", [])[:TOP_KEYWORDS_SHOWN]],
        "llm_strategy": llm_strategy,
    }


def ppc_metrics_from_strategy(ppc_strategy: dict) -> dict:
    """Extract the scoring inputs from a build_ppc_strategy() result. Zero CPC is omitted, not written."""
    launch = ppc_strategy.get("phases", {}).get("launch", {})
    metrics = {
        "break_even_acos": ppc_strategy.get("break_even", {}).get("break_even_acos", 0),
        "relevant_keyword_count": ppc_strategy.get("total_keywords", 0),
        "ppc_budget_90d": ppc_strategy.get("total_90_day_budget", 0),
        "estimated_acos": launch.get("estimated_acos", 0),
        "ppc_daily_budget": launch.get("daily_budget", 0),
    }
    # A zero avg_cpc means the keyword portfolio was empty (no data yet), not that
    # ads are free. Leaving the key out lets the earlier keyword-research estimate
    # (set upstream in metrics) survive instead of being overwritten with 0.
    if ppc_strategy.get("avg_cpc"):
        metrics["avg_cpc"] = ppc_strategy["avg_cpc"]
    return metrics
