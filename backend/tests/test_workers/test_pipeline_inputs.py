from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.workers import tasks


@pytest.fixture
def captured_options(monkeypatch) -> list[dict]:
    """Replace the async pipeline with a recorder of the options it was given."""
    seen: list[dict] = []

    def fake_pipeline(task, niche_id, keyword, options, **kwargs):
        seen.append(options)
        return "pipeline-ran"

    monkeypatch.setattr(tasks, "_run_full_analysis_async", fake_pipeline)
    monkeypatch.setattr(tasks, "_run_async", lambda result: result)
    return seen


def _run_task_with_retries(retries: int) -> None:
    tasks.run_full_analysis.push_request(retries=retries)
    try:
        tasks.run_full_analysis.run(7, "garlic press", options={})
    finally:
        tasks.run_full_analysis.pop_request()


def test_first_attempt_keeps_existing_rows(captured_options):
    _run_task_with_retries(0)
    assert not captured_options[0].get("force")


def test_retry_forces_a_reset_of_derived_rows(captured_options):
    _run_task_with_retries(1)
    assert captured_options[0]["force"] is True


def test_stored_product_carries_the_fields_market_signals_read():
    stored = SimpleNamespace(
        asin="B0A", title="Garlic press", brand="OXO", image_url="https://img",
        current_price=Decimal("29.95"), rating=Decimal("4.6"), review_count=1200,
        current_bsr=118, bsr_category="Home & Kitchen", seller_id="A2QZ",
        date_first_available=date(2021, 3, 12),
    )
    detail = tasks._stored_product_as_detail(stored)
    assert detail["price"] == 29.95
    assert detail["rating"] == 4.6
    assert detail["current_bsr"] == 118
    assert detail["bsr_category"] == "Home & Kitchen"
    assert detail["seller_id"] == "A2QZ"
    assert detail["date_first_available"] == "2021-03-12"
    assert detail["image_url"] == "https://img"


def test_revenue_per_seller_comes_from_sales_times_price():
    metrics = tasks._build_base_metrics(None, [{"price": 30.0, "current_bsr": 500}], marketplace="US")
    assert metrics["monthly_revenue_per_seller"] == round(metrics["estimated_monthly_sales"] * 30.0)


def test_revenue_per_seller_is_left_to_the_fallback_without_real_sales():
    metrics = tasks._build_base_metrics(None, [], marketplace="US")
    assert "monthly_revenue_per_seller" not in metrics


def test_break_even_week_uses_the_base_case():
    assert tasks._base_case_break_even_week({"base": {"break_even_week": 11}}) == 11


def test_no_break_even_inside_the_forecast_counts_as_the_whole_horizon():
    assert tasks._base_case_break_even_week({"base": {"break_even_week": None}}) == tasks.FORECAST_HORIZON_WEEKS


def test_average_weight_understands_ounces():
    dims = tasks._extract_avg_dimensions([
        {"dimensions": "10 x 6 x 4 inches", "weight": "12 ounces"},
        {"dimensions": "10 x 6 x 4 inches", "weight": "1.25 pounds"},
    ])
    assert dims["weight_lb"] == 1.0
