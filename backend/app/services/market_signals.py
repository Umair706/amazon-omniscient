"""Pure functions that turn scraped product/supplier dicts into ScoringService inputs."""

from collections import Counter
from datetime import date, datetime
from statistics import median

from dateutil.parser import parse as parse_date

from app.core.bsr_regression import BSRSalesEstimator
from app.services.competitor_service import CompetitorService

# A listing with this many reviews at this rating is an entrenched brand a new entrant must out-spend.
STRONG_SELLER_MIN_REVIEWS = 1000
STRONG_SELLER_MIN_RATING = 4.3
DAYS_PER_MONTH = 30.4


def derive_category(products: list[dict]) -> str:
    """Most common main-category BSR label across products, or 'default'."""
    labels = [p["bsr_category"] for p in products if p.get("bsr_category")]
    if not labels:
        return "default"
    return Counter(labels).most_common(1)[0][0]


def count_strong_sellers(products: list[dict]) -> int:
    """Count listings that are both heavily reviewed and highly rated."""
    return sum(
        1 for p in products
        if (p.get("review_count") or 0) >= STRONG_SELLER_MIN_REVIEWS
        and float(p.get("rating") or 0) >= STRONG_SELLER_MIN_RATING
    )


def amazon_seller_pct(products: list[dict], amazon_seller_id: str) -> float:
    """Percentage of products whose Buy Box seller is Amazon itself."""
    if not products:
        return 0.0
    amazon_count = sum(1 for p in products if p.get("seller_id") == amazon_seller_id)
    return round(amazon_count / len(products) * 100, 1)


def _months_listed(date_first_available) -> float | None:
    if not date_first_available:
        return None
    try:
        listed = date_first_available if isinstance(date_first_available, date) else parse_date(str(date_first_available)).date()
    except (ValueError, OverflowError):
        return None
    days = (datetime.now().date() - listed).days
    return max(days / DAYS_PER_MONTH, 1.0)


def average_review_velocity_gap(products: list[dict], estimator: BSRSalesEstimator, category: str) -> float | None:
    """Mean reviews-per-100-sales ratio across products with a BSR and a listing date. None if no data."""
    ratios = []
    for p in products:
        months = _months_listed(p.get("date_first_available"))
        bsr = p.get("current_bsr") or p.get("bsr")
        if not months or not bsr:
            continue
        monthly_sales = estimator.estimate_monthly_sales(int(bsr), category)
        reviews_per_month = (p.get("review_count") or 0) / months
        ratios.append(CompetitorService.calculate_review_velocity_gap(monthly_sales, reviews_per_month)["gap_ratio"])
    if not ratios:
        return None
    return round(sum(ratios) / len(ratios), 2)


def summarize_suppliers(suppliers: list[dict], cny_to_usd_rate: float) -> dict:
    """Aggregate scraped 1688 listings into the supplier sub-score inputs. Prices in the input are CNY."""
    if not suppliers:
        return {"count": 0, "best_score": None, "min_moq": None, "median_fob_usd": None}
    moqs = [s["moq"] for s in suppliers if s.get("moq")]
    fob_usd = [round(s["price_min"] / cny_to_usd_rate, 4) for s in suppliers if s.get("price_min")]
    scores = [s.get("supplier_score") or 0 for s in suppliers]
    return {
        "count": len(suppliers),
        "best_score": max(scores) if scores else None,
        "min_moq": min(moqs) if moqs else None,
        "median_fob_usd": round(median(fob_usd), 4) if fob_usd else None,
    }
