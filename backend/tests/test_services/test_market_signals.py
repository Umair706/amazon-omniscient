from datetime import datetime, timedelta, timezone

from app.core.bsr_regression import BSRSalesEstimator
from app.services.market_signals import (
    MIN_PRODUCTS_FOR_VELOCITY, MIN_VELOCITY_WINDOW_DAYS,
    amazon_seller_pct, apply_supplier_summary, average_recent_velocity_gap, count_strong_sellers,
    derive_category, recent_review_velocity_per_month, summarize_suppliers,
)

PRODUCTS = [
    {"asin": "A", "bsr_category": "Home & Kitchen", "review_count": 2500, "rating": 4.6, "seller_id": "ATVPDKIKX0DER",
     "current_bsr": 1200, "date_first_available": "January 5, 2024"},
    {"asin": "B", "bsr_category": "Home & Kitchen", "review_count": 40, "rating": 4.1, "seller_id": "A1XYZ",
     "current_bsr": 30000, "date_first_available": "March 1, 2025"},
    {"asin": "C", "bsr_category": "Kitchen & Dining", "review_count": 1500, "rating": 3.9, "seller_id": "A2ABC",
     "current_bsr": None, "date_first_available": None},
]


def test_derive_category_picks_most_common():
    assert derive_category(PRODUCTS) == "Home & Kitchen"
    assert derive_category([]) == "default"


def test_count_strong_sellers_requires_reviews_and_rating():
    assert count_strong_sellers(PRODUCTS) == 1  # only A: 2500 reviews AND 4.6


def test_amazon_seller_pct():
    assert amazon_seller_pct(PRODUCTS, "ATVPDKIKX0DER") == round(100 / 3, 1)
    assert amazon_seller_pct([], "ATVPDKIKX0DER") == 0.0


def test_amazon_seller_pct_counts_sold_by_amazon_flag_without_seller_id():
    products = [
        {"asin": "A", "sold_by_amazon": True, "seller_id": None},
        {"asin": "B", "sold_by_amazon": False, "seller_id": "A1XYZ"},
    ]
    assert amazon_seller_pct(products, "ATVPDKIKX0DER") == 50.0


T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _snap(days: float, count: int):
    return (T0 + timedelta(days=days), count)


def test_velocity_needs_a_two_week_window():
    assert recent_review_velocity_per_month(_snap(0, 100), _snap(MIN_VELOCITY_WINDOW_DAYS - 1, 130)) is None
    assert recent_review_velocity_per_month(_snap(0, 100), _snap(30.4, 130)) == 30.0


def test_removed_reviews_count_as_zero_velocity():
    assert recent_review_velocity_per_month(_snap(0, 100), _snap(20, 90)) == 0.0


def test_gap_needs_enough_products():
    estimator = BSRSalesEstimator("US")
    window = {"bsr": 1000, "first": _snap(0, 100), "last": _snap(30.4, 130)}
    assert average_recent_velocity_gap([window] * (MIN_PRODUCTS_FOR_VELOCITY - 1), estimator, "Home & Kitchen") is None
    gap = average_recent_velocity_gap([window] * MIN_PRODUCTS_FOR_VELOCITY, estimator, "Home & Kitchen")
    monthly_sales = estimator.estimate_monthly_sales(1000, "Home & Kitchen")
    assert gap == round(30.0 / monthly_sales * 100, 2)


def test_summarize_suppliers():
    suppliers = [
        {"supplier_name": "X", "moq": 500, "price_min": 20.0, "supplier_score": 60},
        {"supplier_name": "Y", "moq": 100, "price_min": 30.0, "supplier_score": 85},
        {"supplier_name": "Z", "moq": None, "price_min": None, "supplier_score": 20},
    ]
    s = summarize_suppliers(suppliers, cny_to_usd_rate=10.0)
    assert s == {"count": 3, "best_score": 85, "min_moq": 100, "median_fob_usd": 2.5}
    assert summarize_suppliers([], cny_to_usd_rate=10.0) == {"count": 0, "best_score": None, "min_moq": None, "median_fob_usd": None}


def test_summarize_suppliers_ignores_missing_scores():
    # A supplier we couldn't score (no transaction/verification data scraped) must not look
    # like a real score of 0 and drag down best_score.
    suppliers = [{"supplier_name": "X", "moq": 500, "price_min": 20.0, "supplier_score": None}]
    s = summarize_suppliers(suppliers, cny_to_usd_rate=10.0)
    assert s["best_score"] is None


def test_apply_supplier_summary_sets_only_known_fields():
    metrics = {}
    apply_supplier_summary(metrics, {"count": 3, "best_score": None, "min_moq": None, "median_fob_usd": None})
    assert metrics == {"supplier_count": 3}


def test_apply_supplier_summary_noop_when_no_suppliers_scraped():
    metrics = {"best_supplier_score": 70}
    apply_supplier_summary(metrics, {"count": 0, "best_score": None, "min_moq": None, "median_fob_usd": None})
    assert metrics == {"best_supplier_score": 70}


def test_apply_supplier_summary_sets_all_known_fields():
    metrics = {}
    apply_supplier_summary(metrics, {"count": 2, "best_score": 85, "min_moq": 100, "median_fob_usd": 2.5})
    assert metrics == {"supplier_count": 2, "best_supplier_score": 85, "min_moq": 100}


def test_apply_supplier_summary_never_writes_a_none_that_would_crash_scoring():
    # Regression: an unknown min_moq must be left for ScoringService's own default (9999),
    # never written as a literal None that a numeric comparison would blow up on.
    metrics = {}
    apply_supplier_summary(metrics, {"count": 2, "best_score": 60, "min_moq": None, "median_fob_usd": None})
    assert "min_moq" not in metrics
