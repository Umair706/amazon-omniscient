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
GAP_MOQ_ASSUMED = "moq_assumed"
GAP_BSR = "bsr_unavailable"
GAP_SALES_ESTIMATED = "sales_estimate_assumed"
GAP_SALES_UNCALIBRATED = "sales_estimate_uncalibrated"
GAP_FX_ASSUMED = "fx_rate_assumed"
GAP_PPC_AD_SHARE = "ppc_ad_share_assumed"

# Typical values for a mid-range niche; used only when the real signal is missing.
ASSUMED_BREAK_EVEN_WEEK = 16
ASSUMED_SEARCH_VOLUME = 3000
ASSUMED_REVENUE_PER_SELLER = 5000
ASSUMED_MOQ = 500


def record_data_gap(metrics: dict, gap: str) -> None:
    """Add `gap` to metrics["data_gaps"] once (creating the list if needed)."""
    gaps = metrics.setdefault("data_gaps", [])
    if gap not in gaps:
        gaps.append(gap)


def clear_data_gap(metrics: dict, gap: str) -> None:
    """Remove `gap` from metrics["data_gaps"] once a real value has replaced the assumption."""
    gaps = metrics.get("data_gaps", [])
    if gap in gaps:
        gaps.remove(gap)


def apply_assumed_defaults(metrics: dict) -> list[str]:
    """Fill missing scoring inputs with assumed values; return the list of gaps recorded in metrics["data_gaps"].

    WHY safe to call twice: the pipeline runs it before scoring and again before the
    recommendation. The second pass sees the values the first pass filled in, so it
    keeps the gaps already recorded instead of rebuilding the list from scratch.
    """
    metrics["data_gaps"] = list(metrics.get("data_gaps", []))
    _record_supplier_gaps(metrics)
    _fill_missing_market_inputs(metrics)
    _record_review_velocity_gap(metrics)
    return metrics["data_gaps"]


def _record_data_gap(metrics: dict, gap: str) -> None:
    if gap not in metrics["data_gaps"]:
        metrics["data_gaps"].append(gap)


def _record_supplier_gaps(metrics: dict) -> None:
    # NOTE: supplier inputs get no default on purpose. ScoringService scores a missing
    # supplier_count as "unknown" (neutral) instead of pretending five suppliers exist.
    if metrics.get("supplier_count") is None:
        _record_data_gap(metrics, GAP_SUPPLIER_DATA)
    else:
        clear_data_gap(metrics, GAP_SUPPLIER_DATA)
        # WHY: 1688 listed suppliers but none had a readable MOQ. Without this the
        # scorer would read its 9999 fallback and mark the niche down with no gap shown.
        if metrics.get("min_moq") is None:
            metrics["min_moq"] = ASSUMED_MOQ
            _record_data_gap(metrics, GAP_MOQ_ASSUMED)
    if metrics.get("fob_unit_cost_estimated"):
        _record_data_gap(metrics, GAP_FOB_ESTIMATED)


def _fill_missing_market_inputs(metrics: dict) -> None:
    if metrics.get("break_even_week_base") is None:
        metrics["break_even_week_base"] = ASSUMED_BREAK_EVEN_WEEK
        _record_data_gap(metrics, GAP_BREAK_EVEN)
    if not metrics.get("search_volume"):
        metrics["search_volume"] = ASSUMED_SEARCH_VOLUME
        _record_data_gap(metrics, GAP_SEARCH_VOLUME)
    if metrics.get("monthly_revenue_per_seller") is None:
        metrics["monthly_revenue_per_seller"] = ASSUMED_REVENUE_PER_SELLER
        _record_data_gap(metrics, GAP_REVENUE_PER_SELLER)
    # NOTE: avg_bsr is left absent (not set) when unknown so the scorer's 99999 fail-safe
    # applies. We only record the gap here; we do not invent a rank.
    if not metrics.get("avg_bsr"):
        _record_data_gap(metrics, GAP_BSR)
    else:
        clear_data_gap(metrics, GAP_BSR)
    if metrics.get("sales_estimated"):
        _record_data_gap(metrics, GAP_SALES_ESTIMATED)
    else:
        clear_data_gap(metrics, GAP_SALES_ESTIMATED)
    # Non-US sales estimates use the US curve scaled by a market-size ratio, not a fitted
    # model, so disclose them as uncalibrated rather than presenting them as precise.
    from app.core.bsr_regression import is_calibrated_marketplace

    if not is_calibrated_marketplace(metrics.get("marketplace", "US")):
        _record_data_gap(metrics, GAP_SALES_UNCALIBRATED)
    else:
        clear_data_gap(metrics, GAP_SALES_UNCALIBRATED)


def _record_review_velocity_gap(metrics: dict) -> None:
    # NOTE: reads the observed ratio, not the one hard filter #9 uses. The filter copy
    # is only set when REVIEW_VELOCITY_FILTER_ENABLED is on; the gap is about the data.
    if metrics.get("review_velocity_gap_ratio") is None:
        _record_data_gap(metrics, GAP_REVIEW_VELOCITY)
    else:
        clear_data_gap(metrics, GAP_REVIEW_VELOCITY)
