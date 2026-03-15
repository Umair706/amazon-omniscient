"""Tests for the ScoringService."""

import pytest
from app.services.scoring_service import ScoringService


@pytest.fixture
def scorer():
    return ScoringService()


class TestComputeScore:
    def test_compute_score_returns_all_keys(self, scorer, sample_metrics):
        result = scorer.compute_score(sample_metrics)
        assert "omniscient_score" in result
        assert "confidence_tier" in result
        assert "sub_scores" in result
        assert "hard_filters" in result
        assert "pass_all_filters" in result
        assert "fail_reasons" in result

    def test_score_in_valid_range(self, scorer, sample_metrics):
        result = scorer.compute_score(sample_metrics)
        assert 0 <= result["omniscient_score"] <= 100

    def test_all_sub_scores_present(self, scorer, sample_metrics):
        result = scorer.compute_score(sample_metrics)
        expected_keys = [
            "demand", "competition", "revenue", "margin", "trend",
            "review_feasibility", "supplier", "ppc_viability", "launch_feasibility",
        ]
        for key in expected_keys:
            assert key in result["sub_scores"]
            assert 0 <= result["sub_scores"][key] <= 100

    def test_high_quality_metrics_give_high_score(self, scorer):
        metrics = {
            "search_volume": 15000, "avg_bsr": 800,
            "estimated_monthly_sales": 1500, "avg_price": 35,
            "monthly_revenue_per_seller": 15000, "pre_ppc_margin_pct": 55,
            "post_ppc_margin_pct": 30, "avg_listing_quality": 30,
            "median_competitor_reviews": 50, "strong_seller_count": 0,
            "bsr_velocity_pct": -25, "search_volume_trend": "rising",
            "is_seasonal": False, "review_threshold": 10,
            "weeks_to_review_threshold": 6, "supplier_count": 15,
            "best_supplier_score": 95, "min_moq": 50,
            "avg_cpc": 0.40, "break_even_acos": 55,
            "relevant_keyword_count": 60, "total_launch_capital": 2500,
            "break_even_week_base": 6, "amazon_seller_pct": 0,
            "is_restricted_category": False, "ip_risk_detected": False,
        }
        result = scorer.compute_score(metrics)
        assert result["omniscient_score"] >= 75
        assert result["confidence_tier"] in ("HIGH", "MEDIUM")

    def test_poor_metrics_give_low_score(self, scorer):
        metrics = {
            "search_volume": 200, "avg_bsr": 60000,
            "estimated_monthly_sales": 20, "avg_price": 12,
            "monthly_revenue_per_seller": 500, "pre_ppc_margin_pct": 15,
            "post_ppc_margin_pct": 2, "avg_listing_quality": 85,
            "median_competitor_reviews": 3000, "strong_seller_count": 6,
            "bsr_velocity_pct": 30, "search_volume_trend": "declining",
            "is_seasonal": True, "review_threshold": 500,
            "weeks_to_review_threshold": 52, "supplier_count": 1,
            "best_supplier_score": 20, "min_moq": 2000,
            "avg_cpc": 5.0, "break_even_acos": 8,
            "relevant_keyword_count": 3, "total_launch_capital": 60000,
            "break_even_week_base": 52, "amazon_seller_pct": 40,
            "is_restricted_category": False, "ip_risk_detected": False,
        }
        result = scorer.compute_score(metrics)
        assert result["omniscient_score"] <= 35


class TestHardFilters:
    def test_all_pass(self, scorer, sample_metrics):
        result = scorer.compute_score(sample_metrics)
        assert result["pass_all_filters"] is True
        assert len(result["fail_reasons"]) == 0

    def test_price_too_low_fails(self, scorer, sample_metrics):
        sample_metrics["avg_price"] = 10
        result = scorer.compute_score(sample_metrics)
        assert result["pass_all_filters"] is False
        assert result["confidence_tier"] == "FAIL"
        assert any("price" in r.lower() for r in result["fail_reasons"])

    def test_price_too_high_fails(self, scorer, sample_metrics):
        sample_metrics["avg_price"] = 85
        result = scorer.compute_score(sample_metrics)
        assert result["pass_all_filters"] is False

    def test_review_moat_fails(self, scorer, sample_metrics):
        sample_metrics["median_competitor_reviews"] = 3000
        result = scorer.compute_score(sample_metrics)
        assert result["pass_all_filters"] is False

    def test_bsr_too_high_fails(self, scorer, sample_metrics):
        sample_metrics["avg_bsr"] = 60000
        result = scorer.compute_score(sample_metrics)
        assert result["pass_all_filters"] is False

    def test_margin_too_low_fails(self, scorer, sample_metrics):
        sample_metrics["pre_ppc_margin_pct"] = 20
        result = scorer.compute_score(sample_metrics)
        assert result["pass_all_filters"] is False

    def test_amazon_dominance_fails(self, scorer, sample_metrics):
        sample_metrics["amazon_seller_pct"] = 40
        result = scorer.compute_score(sample_metrics)
        assert result["pass_all_filters"] is False

    def test_restricted_category_fails(self, scorer, sample_metrics):
        sample_metrics["is_restricted_category"] = True
        result = scorer.compute_score(sample_metrics)
        assert result["pass_all_filters"] is False

    def test_ip_risk_fails(self, scorer, sample_metrics):
        sample_metrics["ip_risk_detected"] = True
        result = scorer.compute_score(sample_metrics)
        assert result["pass_all_filters"] is False

    def test_seasonal_fails_unless_allowed(self, scorer, sample_metrics):
        sample_metrics["is_seasonal"] = True
        result = scorer.compute_score(sample_metrics)
        assert result["pass_all_filters"] is False

        sample_metrics["allow_seasonal"] = True
        result2 = scorer.compute_score(sample_metrics)
        assert all(
            f["passed"] for f in result2["hard_filters"] if f["filter"] == "seasonality"
        )

    def test_eight_filters_returned(self, scorer, sample_metrics):
        result = scorer.compute_score(sample_metrics)
        assert len(result["hard_filters"]) == 8


class TestConfidenceTiers:
    def test_fail_tier_on_filter_failure(self, scorer, sample_metrics):
        sample_metrics["avg_price"] = 10
        result = scorer.compute_score(sample_metrics)
        assert result["confidence_tier"] == "FAIL"

    def test_weights_sum_to_one(self, scorer):
        total = sum(scorer.WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


class TestSubScores:
    def test_demand_max_score(self, scorer):
        m = {"search_volume": 20000, "avg_bsr": 500, "estimated_monthly_sales": 2000}
        assert scorer._score_demand(m) == 100

    def test_demand_min_score(self, scorer):
        m = {"search_volume": 50, "avg_bsr": 100000, "estimated_monthly_sales": 5}
        assert scorer._score_demand(m) == 6

    def test_competition_weak_competitors_high_score(self, scorer):
        m = {"avg_listing_quality": 25, "median_competitor_reviews": 20, "strong_seller_count": 0}
        assert scorer._score_competition(m) == 100

    def test_margin_score_high(self, scorer):
        m = {"pre_ppc_margin_pct": 55, "post_ppc_margin_pct": 30}
        assert scorer._score_margin(m) == 100

    def test_trend_rising(self, scorer):
        m = {"bsr_velocity_pct": -25, "search_volume_trend": "rising", "is_seasonal": False}
        score = scorer._score_trend(m)
        assert score >= 85

    def test_trend_declining(self, scorer):
        m = {"bsr_velocity_pct": 25, "search_volume_trend": "declining", "is_seasonal": True}
        score = scorer._score_trend(m)
        assert score <= 15
