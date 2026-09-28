"""MCP resources: reference context the agent can read to interpret results.

The scoring guide is generated from the live config so it never drifts from the
actual defaults."""

from __future__ import annotations

from app.mcp import mcp


@mcp.resource("omniscient://scoring-guide")
def scoring_guide() -> str:
    """How to read an Omniscient Score, its tiers, weights, and hard filters."""
    from app.services.scoring_config import DEFAULT_MARKETPLACE_THRESHOLDS, DEFAULT_WEIGHTS

    weights = "\n".join(f"  - {k}: {int(v * 100)}%" for k, v in DEFAULT_WEIGHTS.items())
    thresholds = "\n".join(
        f"  {mk}: " + ", ".join(f"{k}={v}" for k, v in vals.items())
        for mk, vals in DEFAULT_MARKETPLACE_THRESHOLDS.items()
    )
    return (
        "OMNISCIENT SCORE — how to read it\n\n"
        "A 0-100 weighted score, then a tier. A niche FAILS (regardless of score) if any hard "
        "filter fails — treat FAIL as walk-away unless the seller has deliberately loosened that "
        "rule in Settings.\n\n"
        "Tiers: HIGH 80-100 (strong), MEDIUM 60-79 (viable with caveats), LOW 40-59 (marginal), "
        "VERY_LOW <40 (avoid), FAIL (a hard filter failed).\n\n"
        f"Sub-score weights (default):\n{weights}\n\n"
        "Hard-filter thresholds are per-marketplace and seller-tunable. Defaults:\n"
        f"{thresholds}\n"
        "  (plus: not restricted/hazmat, no IP risk, not seasonal-only, no review-velocity trap)\n\n"
        "Data gaps: any value marked as a data gap (uncalibrated sales, assumed MOQ, FOB estimated "
        "from price, assumed FX rate, missing suppliers) is an assumption, not a measurement. Weigh "
        "them accordingly and tell the seller to verify. AU sales estimates are uncalibrated (rough)."
    )
