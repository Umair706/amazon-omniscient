"""BSR & price tracking service — records snapshots and computes trends."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bsr_regression import bsr_estimator
from app.models.bsr_history import BSRHistory
from app.models.price_history import PriceHistory
from app.models.product import Product

logger = logging.getLogger(__name__)


class BSRTracker:
    """
    Tracks BSR and price over time, stores snapshots in TimescaleDB
    hypertables, and computes trend statistics.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # 1. Record BSR snapshot
    # ------------------------------------------------------------------
    async def record_bsr(
        self,
        product_id: int,
        asin: str,
        bsr: int,
        category_id: str | None = None,
        category_name: str | None = None,
        is_subcategory: bool = False,
        recorded_at: datetime | None = None,
    ) -> BSRHistory:
        """Insert a BSR snapshot into the hypertable."""
        snapshot = BSRHistory(
            time=recorded_at or datetime.now(timezone.utc),
            product_id=product_id,
            asin=asin,
            bsr=bsr,
            category_id=category_id,
            category_name=category_name,
            is_subcategory=is_subcategory,
        )
        self.db.add(snapshot)
        await self.db.flush()
        logger.debug(
            "Recorded %s BSR %d for ASIN %s",
            "sub-category" if is_subcategory else "main-category",
            bsr, asin,
        )
        return snapshot

    # ------------------------------------------------------------------
    # 2. Record price snapshot
    # ------------------------------------------------------------------
    async def record_price(
        self,
        product_id: int,
        asin: str,
        price: float,
        has_coupon: bool = False,
        coupon_value: float | None = None,
        is_lightning_deal: bool = False,
        buy_box_seller_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> PriceHistory:
        """Insert a price snapshot into the hypertable."""
        snapshot = PriceHistory(
            time=recorded_at or datetime.now(timezone.utc),
            product_id=product_id,
            asin=asin,
            price=Decimal(str(price)) if price is not None else None,
            has_coupon=has_coupon,
            coupon_value=Decimal(str(coupon_value)) if coupon_value else None,
            is_lightning_deal=is_lightning_deal,
            buy_box_seller_id=buy_box_seller_id,
        )
        self.db.add(snapshot)
        await self.db.flush()
        logger.debug("Recorded price $%.2f for ASIN %s", price, asin)
        return snapshot

    # ------------------------------------------------------------------
    # 3. Batch record from scraper/SP-API data
    # ------------------------------------------------------------------
    async def record_product_snapshot(
        self,
        product_id: int,
        asin: str,
        bsr: int | None = None,
        category_id: str | None = None,
        category_name: str | None = None,
        subcategory_bsr: int | None = None,
        subcategory_name: str | None = None,
        price: float | None = None,
        has_coupon: bool = False,
        coupon_value: float | None = None,
        is_lightning_deal: bool = False,
        buy_box_seller_id: str | None = None,
    ) -> dict:
        """Record BSR (main + sub-category) and price snapshots in a single call."""
        now = datetime.now(timezone.utc)
        result = {"bsr_recorded": False, "subcategory_bsr_recorded": False, "price_recorded": False}

        if bsr is not None and bsr > 0:
            await self.record_bsr(
                product_id, asin, bsr, category_id,
                category_name=category_name,
                is_subcategory=False, recorded_at=now,
            )
            result["bsr_recorded"] = True

        if subcategory_bsr is not None and subcategory_bsr > 0:
            await self.record_bsr(
                product_id, asin, subcategory_bsr, category_id,
                category_name=subcategory_name,
                is_subcategory=True, recorded_at=now,
            )
            result["subcategory_bsr_recorded"] = True

        if price is not None and price > 0:
            await self.record_price(
                product_id, asin, price, has_coupon,
                coupon_value, is_lightning_deal, buy_box_seller_id, now,
            )
            result["price_recorded"] = True

        return result

    # ------------------------------------------------------------------
    # 4. BSR trend analysis
    # ------------------------------------------------------------------
    async def get_bsr_trend(
        self,
        product_id: int,
        days: int = 30,
        *,
        is_subcategory: bool = False,
    ) -> dict:
        """
        Compute BSR trend statistics over the last N days.

        Args:
            is_subcategory: If True, analyze sub-category BSR instead of
                main-category BSR.  The two differ by roughly 10x.

        Returns:
            current_bsr, avg_bsr, min_bsr, max_bsr, bsr_velocity,
            bsr_stability, data_points, trend_direction
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = (
            select(
                func.min(BSRHistory.bsr).label("min_bsr"),
                func.max(BSRHistory.bsr).label("max_bsr"),
                func.avg(BSRHistory.bsr).label("avg_bsr"),
                func.count(BSRHistory.bsr).label("data_points"),
            )
            .where(BSRHistory.product_id == product_id)
            .where(BSRHistory.time >= cutoff)
            .where(BSRHistory.is_subcategory == is_subcategory)
        )
        row = (await self.db.execute(stmt)).one_or_none()

        if not row or row.data_points == 0:
            return self._empty_bsr_trend()

        # Get first and last BSR for velocity calculation
        first_stmt = (
            select(BSRHistory.bsr)
            .where(BSRHistory.product_id == product_id)
            .where(BSRHistory.time >= cutoff)
            .where(BSRHistory.is_subcategory == is_subcategory)
            .order_by(BSRHistory.time.asc())
            .limit(1)
        )
        first_bsr = (await self.db.execute(first_stmt)).scalar()

        last_stmt = (
            select(BSRHistory.bsr)
            .where(BSRHistory.product_id == product_id)
            .where(BSRHistory.time >= cutoff)
            .where(BSRHistory.is_subcategory == is_subcategory)
            .order_by(BSRHistory.time.desc())
            .limit(1)
        )
        last_bsr = (await self.db.execute(last_stmt)).scalar()

        # BSR velocity: negative = improving (rank going down = good)
        bsr_velocity = 0.0
        if first_bsr and last_bsr and first_bsr > 0:
            bsr_velocity = ((last_bsr - first_bsr) / first_bsr) * 100

        # BSR stability: coefficient of variation (lower = more stable)
        avg_bsr = float(row.avg_bsr) if row.avg_bsr else 0
        bsr_range = (row.max_bsr - row.min_bsr) if row.min_bsr and row.max_bsr else 0
        stability = 100 - min(100, (bsr_range / max(avg_bsr, 1)) * 100) if avg_bsr > 0 else 0

        # Trend direction
        if bsr_velocity < -10:
            trend = "improving"
        elif bsr_velocity > 10:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "current_bsr": last_bsr,
            "avg_bsr": round(avg_bsr),
            "min_bsr": row.min_bsr,
            "max_bsr": row.max_bsr,
            "bsr_velocity_pct": round(bsr_velocity, 1),
            "bsr_stability": round(stability, 1),
            "data_points": row.data_points,
            "trend_direction": trend,
            "period_days": days,
        }

    # ------------------------------------------------------------------
    # 5. Price trend analysis
    # ------------------------------------------------------------------
    async def get_price_trend(
        self,
        product_id: int,
        days: int = 30,
    ) -> dict:
        """
        Compute price trend statistics over the last N days.

        Returns:
            current_price, avg_price, min_price, max_price,
            price_volatility, coupon_frequency, data_points
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = (
            select(
                func.min(PriceHistory.price).label("min_price"),
                func.max(PriceHistory.price).label("max_price"),
                func.avg(PriceHistory.price).label("avg_price"),
                func.count(PriceHistory.price).label("data_points"),
                func.sum(
                    func.cast(PriceHistory.has_coupon, type_=func.coalesce.type)
                ).label("coupon_count"),
            )
            .where(PriceHistory.product_id == product_id)
            .where(PriceHistory.time >= cutoff)
        )

        # Simpler approach: separate queries for clarity
        stats_stmt = (
            select(
                func.min(PriceHistory.price).label("min_price"),
                func.max(PriceHistory.price).label("max_price"),
                func.avg(PriceHistory.price).label("avg_price"),
                func.count(PriceHistory.price).label("data_points"),
            )
            .where(PriceHistory.product_id == product_id)
            .where(PriceHistory.time >= cutoff)
        )
        stats = (await self.db.execute(stats_stmt)).one_or_none()

        if not stats or stats.data_points == 0:
            return self._empty_price_trend()

        # Coupon frequency
        coupon_stmt = (
            select(func.count())
            .select_from(PriceHistory)
            .where(PriceHistory.product_id == product_id)
            .where(PriceHistory.time >= cutoff)
            .where(PriceHistory.has_coupon.is_(True))
        )
        coupon_count = (await self.db.execute(coupon_stmt)).scalar() or 0

        # Current price
        current_stmt = (
            select(PriceHistory.price)
            .where(PriceHistory.product_id == product_id)
            .where(PriceHistory.time >= cutoff)
            .order_by(PriceHistory.time.desc())
            .limit(1)
        )
        current_price = (await self.db.execute(current_stmt)).scalar()

        avg_price = float(stats.avg_price) if stats.avg_price else 0
        min_price = float(stats.min_price) if stats.min_price else 0
        max_price = float(stats.max_price) if stats.max_price else 0

        # Price volatility
        price_range = max_price - min_price
        volatility = (price_range / avg_price * 100) if avg_price > 0 else 0

        coupon_frequency = (coupon_count / stats.data_points * 100) if stats.data_points > 0 else 0

        return {
            "current_price": float(current_price) if current_price else None,
            "avg_price": round(avg_price, 2),
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "price_volatility_pct": round(volatility, 1),
            "coupon_frequency_pct": round(coupon_frequency, 1),
            "data_points": stats.data_points,
            "period_days": days,
        }

    # ------------------------------------------------------------------
    # 6. Time series data for charts
    # ------------------------------------------------------------------
    async def get_bsr_timeseries(
        self,
        product_id: int,
        days: int = 90,
        bucket_hours: int = 24,
    ) -> list[dict]:
        """
        Get BSR time series bucketed by time intervals.
        Uses TimescaleDB time_bucket if available, otherwise date_trunc.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Use TimescaleDB time_bucket for efficient aggregation
        query = text("""
            SELECT
                time_bucket(:bucket_interval, time) AS bucket,
                AVG(bsr)::integer AS avg_bsr,
                MIN(bsr) AS min_bsr,
                MAX(bsr) AS max_bsr
            FROM bsr_history
            WHERE product_id = :product_id
              AND time >= :cutoff
            GROUP BY bucket
            ORDER BY bucket ASC
        """)

        result = await self.db.execute(
            query,
            {
                "bucket_interval": f"{bucket_hours} hours",
                "product_id": product_id,
                "cutoff": cutoff,
            },
        )

        return [
            {
                "timestamp": row.bucket.isoformat(),
                "avg_bsr": row.avg_bsr,
                "min_bsr": row.min_bsr,
                "max_bsr": row.max_bsr,
            }
            for row in result.fetchall()
        ]

    async def get_price_timeseries(
        self,
        product_id: int,
        days: int = 90,
        bucket_hours: int = 24,
    ) -> list[dict]:
        """Get price time series bucketed by time intervals."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = text("""
            SELECT
                time_bucket(:bucket_interval, time) AS bucket,
                AVG(price)::numeric(10,2) AS avg_price,
                MIN(price) AS min_price,
                MAX(price) AS max_price
            FROM price_history
            WHERE product_id = :product_id
              AND time >= :cutoff
            GROUP BY bucket
            ORDER BY bucket ASC
        """)

        result = await self.db.execute(
            query,
            {
                "bucket_interval": f"{bucket_hours} hours",
                "product_id": product_id,
                "cutoff": cutoff,
            },
        )

        return [
            {
                "timestamp": row.bucket.isoformat(),
                "avg_price": float(row.avg_price) if row.avg_price else None,
                "min_price": float(row.min_price) if row.min_price else None,
                "max_price": float(row.max_price) if row.max_price else None,
            }
            for row in result.fetchall()
        ]

    # ------------------------------------------------------------------
    # 7. Sales estimation from BSR
    # ------------------------------------------------------------------
    async def estimate_sales(
        self,
        product_id: int,
        category: str,
        days: int = 30,
    ) -> dict:
        """
        Estimate monthly/weekly/daily sales from BSR trend data.
        Uses average BSR over the period for more stable estimates.
        """
        trend = await self.get_bsr_trend(product_id, days)

        if not trend["current_bsr"]:
            return {
                "estimated_monthly_sales": 0,
                "estimated_weekly_sales": 0,
                "estimated_daily_sales": 0,
                "based_on": "no_data",
                "bsr_used": None,
                "category": category,
            }

        # Use average BSR for more stable estimation
        bsr_for_calc = trend["avg_bsr"] or trend["current_bsr"]

        monthly = bsr_estimator.estimate_monthly_sales(bsr_for_calc, category)
        weekly = bsr_estimator.estimate_weekly_sales(bsr_for_calc, category)
        daily = bsr_estimator.estimate_daily_sales(bsr_for_calc, category)

        return {
            "estimated_monthly_sales": monthly,
            "estimated_weekly_sales": weekly,
            "estimated_daily_sales": daily,
            "based_on": "avg_bsr" if trend["data_points"] > 1 else "current_bsr",
            "bsr_used": bsr_for_calc,
            "current_bsr": trend["current_bsr"],
            "avg_bsr": trend["avg_bsr"],
            "category": category,
            "trend_direction": trend["trend_direction"],
        }

    # ------------------------------------------------------------------
    # 8. Niche-level BSR analysis
    # ------------------------------------------------------------------
    async def analyze_niche_bsr(
        self,
        product_ids: list[int],
        category: str,
        days: int = 30,
    ) -> dict:
        """
        Aggregate BSR analysis across all products in a niche.

        Returns niche-level stats: avg BSR, total estimated sales,
        revenue estimate, market concentration.
        """
        if not product_ids:
            return self._empty_niche_analysis()

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Get latest BSR for each product
        latest_bsrs = []
        for pid in product_ids:
            stmt = (
                select(BSRHistory.bsr)
                .where(BSRHistory.product_id == pid)
                .where(BSRHistory.time >= cutoff)
                .order_by(BSRHistory.time.desc())
                .limit(1)
            )
            bsr = (await self.db.execute(stmt)).scalar()
            if bsr:
                latest_bsrs.append(bsr)

        if not latest_bsrs:
            return self._empty_niche_analysis()

        avg_bsr = round(sum(latest_bsrs) / len(latest_bsrs))
        min_bsr = min(latest_bsrs)
        max_bsr = max(latest_bsrs)
        median_bsr = sorted(latest_bsrs)[len(latest_bsrs) // 2]

        # Estimate total niche sales
        total_monthly = sum(
            bsr_estimator.estimate_monthly_sales(bsr, category)
            for bsr in latest_bsrs
        )

        # Get average prices for revenue estimation
        price_stmt = (
            select(func.avg(PriceHistory.price))
            .where(PriceHistory.product_id.in_(product_ids))
            .where(PriceHistory.time >= cutoff)
        )
        avg_price = (await self.db.execute(price_stmt)).scalar()
        avg_price = float(avg_price) if avg_price else 0

        # Market concentration (Herfindahl index approximation)
        sales_shares = []
        for bsr in latest_bsrs:
            monthly = bsr_estimator.estimate_monthly_sales(bsr, category)
            share = monthly / total_monthly if total_monthly > 0 else 0
            sales_shares.append(share)
        hhi = sum(s ** 2 for s in sales_shares) * 10000  # Scale to 0-10000

        return {
            "products_analyzed": len(latest_bsrs),
            "avg_bsr": avg_bsr,
            "median_bsr": median_bsr,
            "min_bsr": min_bsr,
            "max_bsr": max_bsr,
            "total_estimated_monthly_sales": total_monthly,
            "total_estimated_monthly_revenue": round(total_monthly * avg_price, 2),
            "avg_price": round(avg_price, 2),
            "market_concentration_hhi": round(hhi),
            "market_type": (
                "highly_concentrated" if hhi > 2500
                else "moderately_concentrated" if hhi > 1500
                else "competitive"
            ),
            "period_days": days,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _empty_bsr_trend() -> dict:
        return {
            "current_bsr": None,
            "avg_bsr": None,
            "min_bsr": None,
            "max_bsr": None,
            "bsr_velocity_pct": 0,
            "bsr_stability": 0,
            "data_points": 0,
            "trend_direction": "unknown",
            "period_days": 0,
        }

    @staticmethod
    def _empty_price_trend() -> dict:
        return {
            "current_price": None,
            "avg_price": None,
            "min_price": None,
            "max_price": None,
            "price_volatility_pct": 0,
            "coupon_frequency_pct": 0,
            "data_points": 0,
            "period_days": 0,
        }

    @staticmethod
    def _empty_niche_analysis() -> dict:
        return {
            "products_analyzed": 0,
            "avg_bsr": None,
            "median_bsr": None,
            "min_bsr": None,
            "max_bsr": None,
            "total_estimated_monthly_sales": 0,
            "total_estimated_monthly_revenue": 0,
            "avg_price": 0,
            "market_concentration_hhi": 0,
            "market_type": "unknown",
            "period_days": 0,
        }
