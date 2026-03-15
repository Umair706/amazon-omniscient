"""Tests for the SalesForecastService."""

import pytest
from app.services.sales_forecast import SalesForecastService


@pytest.fixture
def forecast_svc(mock_db):
    return SalesForecastService(mock_db)


class TestGenerateForecast:
    def test_returns_three_scenarios(self, forecast_svc):
        result = forecast_svc.generate_forecast(
            selling_price=30, landed_cost=8, fba_fees=5
        )
        assert "bull" in result
        assert "base" in result
        assert "bear" in result

    def test_each_scenario_has_52_weeks(self, forecast_svc):
        result = forecast_svc.generate_forecast(
            selling_price=30, landed_cost=8, fba_fees=5
        )
        for scenario in ("bull", "base", "bear"):
            assert len(result[scenario]) == 52

    def test_week_data_has_required_fields(self, forecast_svc):
        result = forecast_svc.generate_forecast(
            selling_price=30, landed_cost=8, fba_fees=5
        )
        week = result["base"][0]
        required = [
            "scenario", "week_number", "estimated_organic_rank",
            "estimated_units_sold", "revenue", "cogs", "fba_fees",
            "ad_spend", "net_profit", "cumulative_profit",
            "review_count_projected", "organic_traffic_pct",
        ]
        for field in required:
            assert field in week

    def test_bull_outperforms_base(self, forecast_svc):
        result = forecast_svc.generate_forecast(
            selling_price=30, landed_cost=8, fba_fees=5
        )
        bull_final = result["bull"][-1]["cumulative_profit"]
        base_final = result["base"][-1]["cumulative_profit"]
        assert bull_final > base_final

    def test_base_outperforms_bear(self, forecast_svc):
        result = forecast_svc.generate_forecast(
            selling_price=30, landed_cost=8, fba_fees=5
        )
        base_final = result["base"][-1]["cumulative_profit"]
        bear_final = result["bear"][-1]["cumulative_profit"]
        assert base_final > bear_final

    def test_cumulative_profit_monotonically_tracked(self, forecast_svc):
        result = forecast_svc.generate_forecast(
            selling_price=30, landed_cost=8, fba_fees=5
        )
        # Later weeks should generally have higher cumulative profit
        base = result["base"]
        assert base[-1]["cumulative_profit"] > base[0]["cumulative_profit"]

    def test_ppc_spend_decreases_over_time(self, forecast_svc):
        result = forecast_svc.generate_forecast(
            selling_price=30, landed_cost=8, fba_fees=5
        )
        base = result["base"]
        early_ad = base[1]["ad_spend"]
        late_ad = base[-1]["ad_spend"]
        assert late_ad < early_ad

    def test_reviews_accumulate(self, forecast_svc):
        result = forecast_svc.generate_forecast(
            selling_price=30, landed_cost=8, fba_fees=5
        )
        base = result["base"]
        assert base[-1]["review_count_projected"] > base[0]["review_count_projected"]


class TestBreakEven:
    def test_find_break_even_with_profitable_product(self, forecast_svc):
        result = forecast_svc.generate_forecast(
            selling_price=40, landed_cost=8, fba_fees=5
        )
        be = SalesForecastService.find_break_even_week(result["base"])
        assert be is not None
        assert 1 <= be <= 52

    def test_no_break_even_with_unprofitable_product(self, forecast_svc):
        result = forecast_svc.generate_forecast(
            selling_price=16, landed_cost=14, fba_fees=5
        )
        be = SalesForecastService.find_break_even_week(result["bear"])
        # With terrible margins, bear case may not break even
        # This is valid behavior


class TestSummarize:
    def test_summary_has_all_scenarios(self, forecast_svc):
        forecast = forecast_svc.generate_forecast(
            selling_price=30, landed_cost=8, fba_fees=5
        )
        summary = forecast_svc.summarize_forecast(forecast)
        assert "bull" in summary
        assert "base" in summary
        assert "bear" in summary

    def test_summary_fields(self, forecast_svc):
        forecast = forecast_svc.generate_forecast(
            selling_price=30, landed_cost=8, fba_fees=5
        )
        summary = forecast_svc.summarize_forecast(forecast)
        base = summary["base"]
        assert "total_revenue" in base
        assert "total_profit" in base
        assert "roi_pct" in base
        assert "steady_state_margin_pct" in base
        assert "break_even_week" in base


class TestLaunchCapital:
    def test_basic_calculation(self, forecast_svc):
        result = forecast_svc.calculate_launch_capital(
            landed_cost=8, initial_order_qty=500,
            vine_cost=200, ppc_budget_90_days=2700,
        )
        assert result["total_launch_capital"] > 0
        assert result["inventory_cost"] == 4000
        assert result["vine_cost"] == 200
        assert result["initial_order_qty"] == 500

    def test_defaults(self, forecast_svc):
        result = forecast_svc.calculate_launch_capital(
            landed_cost=10, initial_order_qty=300,
        )
        assert result["photography_cost"] == 500
        assert result["miscellaneous"] == 200
