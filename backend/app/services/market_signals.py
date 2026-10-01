"""Pure functions that turn scraped product/supplier dicts into ScoringService inputs."""

from collections import Counter
from datetime import datetime
from statistics import median

from app.core.bsr_regression import BSRSalesEstimator
from app.services.competitor_service import CompetitorService

# A listing with this many reviews at this rating is an entrenched brand a new entrant must out-spend.
STRONG_SELLER_MIN_REVIEWS = 1000
STRONG_SELLER_MIN_RATING = 4.3

Snapshot = tuple[datetime, int]  # (recorded at, review count)

# WHY 14 days: Amazon updates the visible review count in batches; shorter windows read as noise.
MIN_VELOCITY_WINDOW_DAYS = 14
# Fewer products than this and one grey-hat listing would decide the whole niche.
MIN_PRODUCTS_FOR_VELOCITY = 3
DAYS_PER_MONTH = 30.4
SECONDS_PER_DAY = 86_400


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
    # WHY: listings Amazon sells itself usually have no seller-profile link, so
    # seller_id is often empty for them. The scraped "sold by Amazon" flag catches those.
    amazon_count = sum(
        1 for p in products
        if p.get("sold_by_amazon") or p.get("seller_id") == amazon_seller_id
    )
    return round(amazon_count / len(products) * 100, 1)


def recent_review_velocity_per_month(first: Snapshot, last: Snapshot) -> float | None:
    """Reviews gained per month between two snapshots. None if the window is shorter than MIN_VELOCITY_WINDOW_DAYS."""
    days = (last[0] - first[0]).total_seconds() / SECONDS_PER_DAY
    if days < MIN_VELOCITY_WINDOW_DAYS:
        return None
    # Amazon removes reviews too; a shrinking count is "no growth", not negative growth.
    gained = max(0, last[1] - first[1])
    return round(gained / days * DAYS_PER_MONTH, 2)


def average_recent_velocity_gap(windows: list[dict], estimator: BSRSalesEstimator, category: str) -> float | None:
    """Mean reviews-per-100-sales across products with a long-enough window. None below MIN_PRODUCTS_FOR_VELOCITY."""
    ratios = []
    for window in windows:
        velocity = recent_review_velocity_per_month(window["first"], window["last"])
        if velocity is None:
            continue
        monthly_sales = estimator.estimate_monthly_sales(int(window["bsr"]), category)
        ratios.append(CompetitorService.calculate_review_velocity_gap(monthly_sales, velocity)["gap_ratio"])
    if len(ratios) < MIN_PRODUCTS_FOR_VELOCITY:
        return None
    return round(sum(ratios) / len(ratios), 2)


def summarize_suppliers(suppliers: list[dict], price_to_usd_rate: float) -> dict:
    """Aggregate scraped listings into the supplier sub-score inputs.

    price_to_usd_rate is what each listing's price is divided by to reach USD: the
    CNY-per-USD rate for 1688 listings, or 1.0 for a source already quoting USD.
    """
    if not suppliers:
        return {"count": 0, "best_score": None, "min_moq": None, "median_fob_usd": None}
    moqs = [s["moq"] for s in suppliers if s.get("moq")]
    fob_usd = [round(s["price_min"] / price_to_usd_rate, 4) for s in suppliers if s.get("price_min")]
    scores = [s["supplier_score"] for s in suppliers if s.get("supplier_score") is not None]
    return {
        "count": len(suppliers),
        "best_score": max(scores) if scores else None,
        "min_moq": min(moqs) if moqs else None,
        "median_fob_usd": round(median(fob_usd), 4) if fob_usd else None,
    }


def apply_supplier_summary(metrics: dict, summary: dict) -> None:
    """Copy scraped supplier signals into the scoring inputs, leaving defaults in place for anything unknown."""
    if not summary.get("count"):
        return
    metrics["supplier_count"] = summary["count"]
    if summary.get("best_score") is not None:
        metrics["best_supplier_score"] = summary["best_score"]
    if summary.get("min_moq") is not None:
        metrics["min_moq"] = summary["min_moq"]
