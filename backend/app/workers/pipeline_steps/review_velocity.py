"""Derives the niche's recent review velocity from stored rank snapshots."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bsr_regression import BSRSalesEstimator
from app.models.bsr_history import BSRHistory
from app.models.product import Product
from app.services.market_signals import average_recent_velocity_gap

# Older snapshots describe a listing that may have changed hands or relaunched.
VELOCITY_LOOKBACK_DAYS = 90


def windows_from_rows(rows: list[tuple]) -> list[dict]:
    """Group (product_id, bsr, time, review_count) rows, ordered by product then time, into first/last windows."""
    windows: dict[int, dict] = {}
    for product_id, bsr, recorded_at, review_count in rows:
        if not bsr:
            continue
        snapshot = (recorded_at, review_count)
        window = windows.setdefault(product_id, {"bsr": bsr, "first": snapshot, "last": snapshot})
        window["last"] = snapshot
    return list(windows.values())


async def load_review_count_rows(db: AsyncSession, niche_id: int) -> list[tuple]:
    """Main-rank snapshots with a review count for every product in the niche, oldest first."""
    since = datetime.now(timezone.utc) - timedelta(days=VELOCITY_LOOKBACK_DAYS)
    query = (
        select(Product.id, Product.current_bsr, BSRHistory.time, BSRHistory.review_count)
        .join(BSRHistory, BSRHistory.product_id == Product.id)
        .where(Product.niche_id == niche_id, BSRHistory.is_subcategory.is_(False),
               BSRHistory.review_count.is_not(None), BSRHistory.time >= since)
        .order_by(Product.id, BSRHistory.time)
    )
    return [tuple(row) for row in (await db.execute(query)).all()]


async def review_velocity_gap_for_niche(
    db: AsyncSession, niche_id: int, estimator: BSRSalesEstimator, category: str,
) -> float | None:
    """Reviews-per-100-sales for the niche, or None until enough products have two weeks of snapshots."""
    rows = await load_review_count_rows(db, niche_id)
    return average_recent_velocity_gap(windows_from_rows(rows), estimator, category)
