"""Sales velocity service — computes daily sales estimates from BSR deltas + stock changes."""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SalesVelocityService:
    """Computes and stores daily sales velocity from BSR deltas, stock depletion, and regression."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # 1. Record stock snapshot
    # ------------------------------------------------------------------

    async def record_stock_snapshot(
        self,
        product_id: int,
        asin: str,
        stock_level: int | None,
        stock_text: str | None,
        is_in_stock: bool = True,
    ) -> None:
        """Save a stock level observation to the stock_history hypertable."""
        from app.models.stock_history import StockHistory

        entry = StockHistory(
            time=datetime.now(timezone.utc),
            product_id=product_id,
            asin=asin,
            stock_level=stock_level,
            stock_text=stock_text,
            is_in_stock=is_in_stock,
        )
        self.session.add(entry)
        await self.session.flush()

    # ------------------------------------------------------------------
    # 2. Compute daily velocity for a product
    # ------------------------------------------------------------------

    async def compute_daily_velocity(
        self,
        product_id: int,
        category: str = "default",
        target_date: date | None = None,
        marketplace: str = "US",
    ) -> dict:
        """Compute estimated daily sales for a product on a given date.

        Combines three signals:
          - BSR delta: rank drop → estimated sales
          - Stock delta: inventory depletion → direct sales count
          - Regression baseline: BSR-to-sales power law

        Returns a dict suitable for creating a SalesVelocitySnapshot row.
        """
        from app.models.bsr_history import BSRHistory
        from app.models.stock_history import StockHistory

        if target_date is None:
            target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        # ── BSR delta ──────────────────────────────────────────────
        bsr_stmt = (
            select(BSRHistory.bsr, BSRHistory.time)
            .where(
                BSRHistory.product_id == product_id,
                BSRHistory.time >= day_start,
                BSRHistory.time < day_end,
                BSRHistory.is_subcategory == False,  # noqa: E712
            )
            .order_by(BSRHistory.time)
        )
        bsr_rows = (await self.session.execute(bsr_stmt)).all()

        bsr_start = bsr_rows[0][0] if bsr_rows else None
        bsr_end = bsr_rows[-1][0] if bsr_rows else None
        bsr_delta = None
        bsr_derived_sales = None

        if bsr_start is not None and bsr_end is not None:
            bsr_delta = bsr_start - bsr_end  # positive = rank improved = sales
            # Rough scaling: BSR drop / velocity factor by rank range
            if bsr_end < 1000:
                velocity_factor = 50
            elif bsr_end < 5000:
                velocity_factor = 100
            elif bsr_end < 20000:
                velocity_factor = 200
            else:
                velocity_factor = 500
            bsr_derived_sales = max(0, round(bsr_delta / velocity_factor, 2)) if bsr_delta > 0 else 0

        # ── Stock delta ────────────────────────────────────────────
        prev_day_start = day_start - timedelta(days=1)
        prev_stock_stmt = (
            select(StockHistory.stock_level)
            .where(
                StockHistory.product_id == product_id,
                StockHistory.time >= prev_day_start,
                StockHistory.time < day_start,
                StockHistory.stock_level.isnot(None),
            )
            .order_by(StockHistory.time.desc())
            .limit(1)
        )
        prev_stock = (await self.session.execute(prev_stock_stmt)).scalar_one_or_none()

        curr_stock_stmt = (
            select(StockHistory.stock_level)
            .where(
                StockHistory.product_id == product_id,
                StockHistory.time >= day_start,
                StockHistory.time < day_end,
                StockHistory.stock_level.isnot(None),
            )
            .order_by(StockHistory.time.desc())
            .limit(1)
        )
        curr_stock = (await self.session.execute(curr_stock_stmt)).scalar_one_or_none()

        stock_derived_sales = None
        restock_detected = False
        if prev_stock is not None and curr_stock is not None:
            delta = prev_stock - curr_stock
            if delta > 0:
                stock_derived_sales = float(delta)
            elif delta < -5:
                # Large increase = restock
                restock_detected = True
                stock_derived_sales = None

        # ── Regression baseline ────────────────────────────────────
        from app.core.bsr_regression import BSRSalesEstimator

        regression_daily = None
        current_bsr = bsr_end or bsr_start
        if current_bsr:
            estimator = BSRSalesEstimator(marketplace=marketplace)
            monthly = estimator.estimate_monthly_sales(bsr=current_bsr, category=category)
            regression_daily = round(monthly / 30, 2)

        # ── Composite estimate ─────────────────────────────────────
        estimates = []
        weights = []

        if stock_derived_sales is not None and not restock_detected:
            estimates.append(stock_derived_sales)
            weights.append(0.50)

        if bsr_derived_sales is not None and bsr_derived_sales > 0:
            estimates.append(bsr_derived_sales)
            weights.append(0.30 if stock_derived_sales is not None else 0.60)

        if regression_daily is not None:
            estimates.append(regression_daily)
            weights.append(0.20 if (stock_derived_sales is not None or bsr_derived_sales) else 0.40)

        if estimates:
            total_weight = sum(weights)
            composite = sum(e * w for e, w in zip(estimates, weights)) / total_weight
            estimated_daily = round(composite, 2)
        elif regression_daily is not None:
            estimated_daily = regression_daily
            composite = regression_daily
        else:
            estimated_daily = None
            composite = None

        # Determine method
        has_stock = stock_derived_sales is not None and not restock_detected
        has_bsr = bsr_derived_sales is not None and bsr_derived_sales > 0
        if has_stock and has_bsr:
            method = "composite_full"
            confidence = 0.85
        elif has_bsr:
            method = "bsr_delta_regression"
            confidence = 0.65
        elif has_stock:
            method = "stock_regression"
            confidence = 0.70
        elif regression_daily is not None:
            method = "regression_only"
            confidence = 0.40
        else:
            method = "no_data"
            confidence = 0.0

        return {
            "date": target_date,
            "product_id": product_id,
            "bsr_start": bsr_start,
            "bsr_end": bsr_end,
            "bsr_delta": bsr_delta,
            "bsr_derived_daily_sales": bsr_derived_sales,
            "stock_start": prev_stock,
            "stock_end": curr_stock,
            "stock_derived_daily_sales": stock_derived_sales,
            "restock_detected": restock_detected,
            "regression_daily_sales": regression_daily,
            "estimated_daily_sales": estimated_daily,
            "estimation_method": method,
            "confidence": confidence,
        }

    # ------------------------------------------------------------------
    # 3. Save velocity snapshot
    # ------------------------------------------------------------------

    async def save_velocity_snapshot(self, product_id: int, asin: str, velocity_data: dict) -> None:
        """Persist a computed velocity snapshot to the database."""
        from app.models.sales_velocity import SalesVelocitySnapshot

        # Check for existing snapshot for this date+product
        existing = (await self.session.execute(
            select(SalesVelocitySnapshot).where(
                SalesVelocitySnapshot.product_id == product_id,
                SalesVelocitySnapshot.date == velocity_data["date"],
            )
        )).scalar_one_or_none()

        if existing:
            for key, val in velocity_data.items():
                if key not in ("date", "product_id") and val is not None:
                    setattr(existing, key, val)
        else:
            snapshot = SalesVelocitySnapshot(
                product_id=product_id,
                asin=asin,
                **velocity_data,
            )
            self.session.add(snapshot)

        await self.session.flush()

    # ------------------------------------------------------------------
    # 4. Compute niche-level aggregated velocity
    # ------------------------------------------------------------------

    async def compute_niche_velocity(
        self,
        niche_id: int,
        category: str = "default",
        days: int = 7,
    ) -> dict:
        """Aggregate velocity data across all products in a niche."""
        from app.models.product import Product
        from app.models.sales_velocity import SalesVelocitySnapshot

        cutoff = date.today() - timedelta(days=days)

        # Get products in niche
        product_stmt = select(Product.id, Product.asin, Product.estimated_daily_sales).where(
            Product.niche_id == niche_id
        )
        products = (await self.session.execute(product_stmt)).all()

        if not products:
            return {
                "total_estimated_daily_sales": 0,
                "total_estimated_monthly_sales": 0,
                "velocity_trend": "unknown",
                "confidence": 0,
                "product_count": 0,
            }

        product_ids = [p[0] for p in products]

        # Get recent velocity snapshots
        vel_stmt = (
            select(
                SalesVelocitySnapshot.product_id,
                func.avg(SalesVelocitySnapshot.estimated_daily_sales).label("avg_daily"),
                func.avg(SalesVelocitySnapshot.confidence).label("avg_conf"),
            )
            .where(
                SalesVelocitySnapshot.product_id.in_(product_ids),
                SalesVelocitySnapshot.date >= cutoff,
                SalesVelocitySnapshot.estimated_daily_sales.isnot(None),
            )
            .group_by(SalesVelocitySnapshot.product_id)
        )
        vel_results = (await self.session.execute(vel_stmt)).all()

        total_daily = 0.0
        total_conf = 0.0
        count_with_data = 0

        for _pid, avg_daily, avg_conf in vel_results:
            if avg_daily:
                total_daily += float(avg_daily)
                total_conf += float(avg_conf or 0)
                count_with_data += 1

        # Fall back to product-level estimates if no velocity snapshots
        if count_with_data == 0:
            for _pid, _asin, est_daily in products:
                if est_daily:
                    total_daily += est_daily
                    count_with_data += 1

        avg_confidence = round(total_conf / count_with_data, 2) if count_with_data else 0

        # Determine trend from recent snapshots
        velocity_trend = "stable"
        if count_with_data >= 2:
            recent_cutoff = date.today() - timedelta(days=days // 2)
            early_stmt = (
                select(func.avg(SalesVelocitySnapshot.estimated_daily_sales))
                .where(
                    SalesVelocitySnapshot.product_id.in_(product_ids),
                    SalesVelocitySnapshot.date >= cutoff,
                    SalesVelocitySnapshot.date < recent_cutoff,
                    SalesVelocitySnapshot.estimated_daily_sales.isnot(None),
                )
            )
            late_stmt = (
                select(func.avg(SalesVelocitySnapshot.estimated_daily_sales))
                .where(
                    SalesVelocitySnapshot.product_id.in_(product_ids),
                    SalesVelocitySnapshot.date >= recent_cutoff,
                    SalesVelocitySnapshot.estimated_daily_sales.isnot(None),
                )
            )
            early_avg = (await self.session.execute(early_stmt)).scalar_one_or_none()
            late_avg = (await self.session.execute(late_stmt)).scalar_one_or_none()

            if early_avg and late_avg and float(early_avg) > 0:
                change_pct = (float(late_avg) - float(early_avg)) / float(early_avg)
                if change_pct > 0.1:
                    velocity_trend = "increasing"
                elif change_pct < -0.1:
                    velocity_trend = "decreasing"

        return {
            "total_estimated_daily_sales": round(total_daily, 1),
            "total_estimated_monthly_sales": round(total_daily * 30, 0),
            "velocity_trend": velocity_trend,
            "confidence": avg_confidence,
            "product_count": len(products),
            "products_with_velocity_data": count_with_data,
        }

    # ------------------------------------------------------------------
    # 5. Get velocity time-series for charting
    # ------------------------------------------------------------------

    async def get_velocity_timeseries(
        self,
        product_id: int,
        days: int = 30,
    ) -> list[dict]:
        """Return daily velocity data points for a product."""
        from app.models.sales_velocity import SalesVelocitySnapshot

        cutoff = date.today() - timedelta(days=days)

        stmt = (
            select(SalesVelocitySnapshot)
            .where(
                SalesVelocitySnapshot.product_id == product_id,
                SalesVelocitySnapshot.date >= cutoff,
            )
            .order_by(SalesVelocitySnapshot.date.asc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()

        return [
            {
                "date": row.date.isoformat(),
                "estimated_daily_sales": float(row.estimated_daily_sales) if row.estimated_daily_sales else None,
                "bsr_delta": row.bsr_delta,
                "stock_start": row.stock_start,
                "stock_end": row.stock_end,
                "estimation_method": row.estimation_method,
                "confidence": float(row.confidence) if row.confidence else None,
                "restock_detected": row.restock_detected,
            }
            for row in rows
        ]
