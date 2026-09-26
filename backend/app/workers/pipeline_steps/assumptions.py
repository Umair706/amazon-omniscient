"""Fills the scoring inputs we could not measure, and records each one as a data gap.

WHY: the score must run even when 1688 is blocked or keyword research came back empty,
but the brief must say which numbers are assumptions. Before this module the same
values were injected silently and looked like measurements.
"""

# Names shown to the user (see frontend/src/lib/data-gaps.ts) — keep them stable.
GAP_SUPPLIER_DATA = "supplier_data_unavailable"
GAP_FOB_ESTIMATED = "fob_estimated_from_price"
GAP_BREAK_EVEN = "break_even_assumed"
GAP_SEARCH_VOLUME = "search_volume_assumed"
GAP_REVENUE_PER_SELLER = "revenue_per_seller_assumed"
GAP_REVIEW_VELOCITY = "review_velocity_unavailable"

# Typical values for a mid-range niche; used only when the real signal is missing.
ASSUMED_BREAK_EVEN_WEEK = 16
ASSUMED_SEARCH_VOLUME = 3000
ASSUMED_REVENUE_PER_SELLER = 5000


def apply_assumed_defaults(metrics: dict) -> list[str]:
    """Fill missing scoring inputs with assumed values; return the list of gaps recorded in metrics["data_gaps"]."""
    gaps: list[str] = []
    # NOTE: supplier inputs get no default on purpose. ScoringService scores a missing
    # supplier_count as "unknown" (neutral) instead of pretending five suppliers exist.
    if metrics.get("supplier_count") is None:
        gaps.append(GAP_SUPPLIER_DATA)
    if metrics.get("fob_unit_cost_estimated"):
        gaps.append(GAP_FOB_ESTIMATED)
    if metrics.get("break_even_week_base") is None:
        metrics["break_even_week_base"] = ASSUMED_BREAK_EVEN_WEEK
        gaps.append(GAP_BREAK_EVEN)
    if not metrics.get("search_volume"):
        metrics["search_volume"] = ASSUMED_SEARCH_VOLUME
        gaps.append(GAP_SEARCH_VOLUME)
    if metrics.get("monthly_revenue_per_seller") is None:
        metrics["monthly_revenue_per_seller"] = ASSUMED_REVENUE_PER_SELLER
        gaps.append(GAP_REVENUE_PER_SELLER)
    if metrics.get("avg_review_velocity_gap_ratio") is None:
        gaps.append(GAP_REVIEW_VELOCITY)
    metrics["data_gaps"] = gaps
    return gaps
