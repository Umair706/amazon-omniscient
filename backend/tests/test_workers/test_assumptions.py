"""Tests for apply_assumed_defaults — the single place that fills missing scoring inputs."""

from app.workers.pipeline_steps.assumptions import (
    ASSUMED_BREAK_EVEN_WEEK, ASSUMED_REVENUE_PER_SELLER, ASSUMED_SEARCH_VOLUME,
    GAP_BREAK_EVEN, GAP_FOB_ESTIMATED, GAP_REVENUE_PER_SELLER, GAP_REVIEW_VELOCITY,
    GAP_SEARCH_VOLUME, GAP_SUPPLIER_DATA, apply_assumed_defaults,
)


def test_no_supplier_data_is_a_gap_not_a_default():
    metrics = {"search_volume": 1200, "monthly_revenue_per_seller": 8000,
               "break_even_week_base": 10, "avg_review_velocity_gap_ratio": 1.2}
    gaps = apply_assumed_defaults(metrics)
    assert gaps == [GAP_SUPPLIER_DATA]
    assert "supplier_count" not in metrics
    assert "best_supplier_score" not in metrics
    assert "min_moq" not in metrics
    assert metrics["data_gaps"] == [GAP_SUPPLIER_DATA]


def test_every_assumed_value_is_recorded():
    metrics = {"supplier_count": 4, "fob_unit_cost_estimated": True}
    gaps = apply_assumed_defaults(metrics)
    assert metrics["search_volume"] == ASSUMED_SEARCH_VOLUME
    assert metrics["monthly_revenue_per_seller"] == ASSUMED_REVENUE_PER_SELLER
    assert metrics["break_even_week_base"] == ASSUMED_BREAK_EVEN_WEEK
    assert gaps == [GAP_FOB_ESTIMATED, GAP_BREAK_EVEN, GAP_SEARCH_VOLUME,
                    GAP_REVENUE_PER_SELLER, GAP_REVIEW_VELOCITY]


def test_zero_search_volume_counts_as_missing():
    metrics = {"supplier_count": 1, "search_volume": 0, "monthly_revenue_per_seller": 1,
               "break_even_week_base": 1, "avg_review_velocity_gap_ratio": 0.5}
    assert apply_assumed_defaults(metrics) == [GAP_SEARCH_VOLUME]
    assert metrics["search_volume"] == ASSUMED_SEARCH_VOLUME
