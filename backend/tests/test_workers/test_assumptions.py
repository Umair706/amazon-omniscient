"""Tests for apply_assumed_defaults — the single place that fills missing scoring inputs."""

from app.workers import tasks
from app.workers.pipeline_steps.assumptions import (
    ASSUMED_BREAK_EVEN_WEEK, ASSUMED_MOQ, ASSUMED_REVENUE_PER_SELLER, ASSUMED_SEARCH_VOLUME,
    GAP_BREAK_EVEN, GAP_BSR, GAP_FOB_ESTIMATED, GAP_MOQ_ASSUMED, GAP_REVENUE_PER_SELLER,
    GAP_REVIEW_VELOCITY, GAP_SALES_ESTIMATED, GAP_SEARCH_VOLUME, GAP_SUPPLIER_DATA,
    apply_assumed_defaults, clear_data_gap,
)

MEASURED_BREAK_EVEN_WEEK = 9
# A known BSR keeps the BSR gap out of tests that are about other signals.
MEASURED_BSR = 500


def test_no_supplier_data_is_a_gap_not_a_default():
    metrics = {"avg_bsr": MEASURED_BSR, "search_volume": 1200, "monthly_revenue_per_seller": 8000,
               "break_even_week_base": 10, "review_velocity_gap_ratio": 1.2}
    gaps = apply_assumed_defaults(metrics)
    assert gaps == [GAP_SUPPLIER_DATA]
    assert "supplier_count" not in metrics
    assert "best_supplier_score" not in metrics
    assert "min_moq" not in metrics
    assert metrics["data_gaps"] == [GAP_SUPPLIER_DATA]


def test_every_assumed_value_is_recorded():
    metrics = {"avg_bsr": MEASURED_BSR, "supplier_count": 4, "min_moq": 100, "fob_unit_cost_estimated": True}
    gaps = apply_assumed_defaults(metrics)
    assert metrics["search_volume"] == ASSUMED_SEARCH_VOLUME
    assert metrics["monthly_revenue_per_seller"] == ASSUMED_REVENUE_PER_SELLER
    assert metrics["break_even_week_base"] == ASSUMED_BREAK_EVEN_WEEK
    assert gaps == [GAP_FOB_ESTIMATED, GAP_BREAK_EVEN, GAP_SEARCH_VOLUME,
                    GAP_REVENUE_PER_SELLER, GAP_REVIEW_VELOCITY]


def test_zero_search_volume_counts_as_missing():
    metrics = {"avg_bsr": MEASURED_BSR, "supplier_count": 1, "min_moq": 50, "search_volume": 0,
               "monthly_revenue_per_seller": 1, "break_even_week_base": 1, "review_velocity_gap_ratio": 0.5}
    assert apply_assumed_defaults(metrics) == [GAP_SEARCH_VOLUME]
    assert metrics["search_volume"] == ASSUMED_SEARCH_VOLUME


def test_non_us_marketplace_sales_are_flagged_uncalibrated():
    from app.workers.pipeline_steps.assumptions import GAP_SALES_UNCALIBRATED

    au = {"avg_bsr": MEASURED_BSR, "supplier_count": 1, "min_moq": 50, "search_volume": 1200,
          "monthly_revenue_per_seller": 8000, "break_even_week_base": 10,
          "review_velocity_gap_ratio": 1.2, "marketplace": "AU"}
    assert GAP_SALES_UNCALIBRATED in apply_assumed_defaults(au)

    us = {**au, "marketplace": "US"}
    assert GAP_SALES_UNCALIBRATED not in apply_assumed_defaults(us)


def test_missing_bsr_is_recorded_and_never_invented():
    metrics = {"avg_bsr": 0, "supplier_count": 1, "min_moq": 50, "search_volume": 1200,
               "monthly_revenue_per_seller": 8000, "break_even_week_base": 10,
               "review_velocity_gap_ratio": 1.2, "sales_estimated": True}
    gaps = apply_assumed_defaults(metrics)
    assert gaps == [GAP_BSR, GAP_SALES_ESTIMATED]
    # Left absent on purpose so the scorer's 99999 fail-safe treats it as poor demand.
    assert not metrics.get("avg_bsr")


def test_a_second_pass_keeps_every_gap_without_duplicates():
    metrics = {"fob_unit_cost_estimated": True}
    first_pass = list(apply_assumed_defaults(metrics))
    second_pass = apply_assumed_defaults(metrics)
    assert second_pass == first_pass
    assert first_pass == [GAP_SUPPLIER_DATA, GAP_FOB_ESTIMATED, GAP_BREAK_EVEN, GAP_SEARCH_VOLUME,
                          GAP_REVENUE_PER_SELLER, GAP_BSR, GAP_REVIEW_VELOCITY]


def test_cleared_break_even_gap_stays_cleared_once_the_real_value_exists():
    metrics = {}
    apply_assumed_defaults(metrics)
    metrics["break_even_week_base"] = MEASURED_BREAK_EVEN_WEEK
    clear_data_gap(metrics, GAP_BREAK_EVEN)
    assert GAP_BREAK_EVEN not in metrics["data_gaps"]

    apply_assumed_defaults(metrics)
    assert GAP_BREAK_EVEN not in metrics["data_gaps"]
    assert metrics["break_even_week_base"] == MEASURED_BREAK_EVEN_WEEK


def test_clearing_a_gap_that_was_never_recorded_does_nothing():
    metrics = {"data_gaps": [GAP_SEARCH_VOLUME]}
    clear_data_gap(metrics, GAP_BREAK_EVEN)
    assert metrics["data_gaps"] == [GAP_SEARCH_VOLUME]


def test_gaps_clear_when_a_later_pass_finds_the_real_signal():
    metrics = {}
    apply_assumed_defaults(metrics)
    metrics["supplier_count"] = 3
    metrics["min_moq"] = 100
    metrics["review_velocity_gap_ratio"] = 2.5
    gaps = apply_assumed_defaults(metrics)
    assert GAP_SUPPLIER_DATA not in gaps
    assert GAP_REVIEW_VELOCITY not in gaps


def test_suppliers_without_a_parseable_moq_get_an_assumed_moq_and_a_gap():
    metrics = {"avg_bsr": MEASURED_BSR, "supplier_count": 3, "search_volume": 1200,
               "monthly_revenue_per_seller": 8000, "break_even_week_base": 10, "review_velocity_gap_ratio": 1.2}
    gaps = apply_assumed_defaults(metrics)
    assert metrics["min_moq"] == ASSUMED_MOQ
    assert gaps == [GAP_MOQ_ASSUMED]
    assert apply_assumed_defaults(metrics) == [GAP_MOQ_ASSUMED]


def test_enrich_metrics_twice_keeps_first_pass_gaps_and_drops_the_forecast_one():
    """Regression: the pipeline enriches metrics before scoring and again before the
    recommendation. The second pass used to rebuild data_gaps from scratch and lose
    every gap the first pass had already filled in."""
    metrics = {"avg_bsr": MEASURED_BSR}
    tasks._enrich_metrics(metrics, None, None, None, None)

    # What the pipeline does when the sales forecast succeeds between the two passes.
    metrics["break_even_week_base"] = MEASURED_BREAK_EVEN_WEEK
    clear_data_gap(metrics, GAP_BREAK_EVEN)

    tasks._enrich_metrics(metrics, None, None, None, None)
    assert metrics["data_gaps"] == [GAP_SUPPLIER_DATA, GAP_SEARCH_VOLUME,
                                    GAP_REVENUE_PER_SELLER, GAP_REVIEW_VELOCITY]
