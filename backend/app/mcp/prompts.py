"""MCP prompts: guided workflows so the agent follows a proven playbook.

Each returns instruction text that steers the agent to use the tools (not guess)
and to respect FAIL verdicts and flagged data gaps."""

from __future__ import annotations

from app.mcp import mcp

_HONESTY = (
    "Use the Omniscient tools for every fact; do not invent numbers. Respect FAIL "
    "verdicts and any data gaps (e.g. uncalibrated AU sales, missing suppliers) — "
    "call them out rather than papering over them."
)


@mcp.prompt()
def build_business_plan(idea: str, marketplace: str = "AU") -> str:
    """Turn a rough idea into a sourced, costed business plan with a go/no-go."""
    return (
        f"Help a seller build an Amazon FBA business around '{idea}' in {marketplace}. {_HONESTY}\n"
        "1. discover_opportunities(seed, marketplace); poll job_status for candidates.\n"
        "2. analyze_keyword on the best candidate; poll job_status.\n"
        "3. get_recommendation for the niche: read score, hard filters, financials, suppliers, data gaps.\n"
        "4. Write the plan: product thesis, unit economics/margin, sourcing, launch + PPC budget, "
        "review strategy, a week-by-week execution roadmap, key risks, and a clear go/no-go."
    )


@mcp.prompt()
def validate_product_idea(keyword: str, marketplace: str = "AU") -> str:
    """Quickly stress-test a specific product idea before committing."""
    return (
        f"Stress-test the product idea '{keyword}' in {marketplace}. {_HONESTY}\n"
        "1. analyze_keyword(keyword, marketplace); poll job_status.\n"
        "2. get_recommendation: check every hard filter, the margin after fees, the review moat, "
        "and Amazon's shelf share.\n"
        "3. Give a blunt verdict: is this worth pursuing? Name the single biggest reason for and against."
    )


@mcp.prompt()
def sourcing_plan(niche_id: int) -> str:
    """Build a sourcing and unit-economics plan for an analysed niche."""
    return (
        f"Build a sourcing plan for niche {niche_id}. {_HONESTY}\n"
        "1. get_niche and get_niche_suppliers for the niche.\n"
        "2. If supplier data is a gap, say so and use landed_cost_and_margin to model economics from a "
        "target factory cost and the sale price instead.\n"
        "3. Produce: target landed cost, MOQ and first-order capital, the margin at the expected price, "
        "and what to confirm with a real supplier quote before committing."
    )


@mcp.prompt()
def launch_plan(recommendation_id: int) -> str:
    """Draft a launch and PPC plan from an existing recommendation."""
    return (
        f"Draft a launch plan from recommendation {recommendation_id}. {_HONESTY}\n"
        "1. get_recommendation: read the PPC plan (break-even vs target ACOS, phase budgets), review "
        "strategy, and financials.\n"
        "2. Produce a 90-day launch plan: PPC budget by phase, review-growth targets, the break-even "
        "week to expect, and the cash needed to get there."
    )
