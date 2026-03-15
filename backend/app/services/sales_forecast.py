"""Sales forecast service — 52-week Bull/Base/Bear projections with break-even analysis."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_projection import FinancialProjection

logger = logging.getLogger(__name__)


class SalesForecastService:
    """
    Generates 52-week financial projections under three scenarios:
    Bull (optimistic), Base (realistic), Bear (pessimistic).

    Accounts for:
    - Organic rank progression over time
    - PPC spend tapering as organic traffic grows
    - Review accumulation and its impact on conversion
    - Seasonality factors
    - FBA fees, storage costs, returns
    """

    # Scenario multipliers relative to base case
    SCENARIO_MULTIPLIERS = {
        "bull": {
            "sales_multiplier": 1.3,
            "rank_improvement_rate": 1.4,
            "conversion_boost": 1.15,
            "ppc_efficiency": 1.2,
        },
        "base": {
            "sales_multiplier": 1.0,
            "rank_improvement_rate": 1.0,
            "conversion_boost": 1.0,
            "ppc_efficiency": 1.0,
        },
        "bear": {
            "sales_multiplier": 0.7,
            "rank_improvement_rate": 0.6,
            "conversion_boost": 0.85,
            "ppc_efficiency": 0.8,
        },
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # 1. Generate 52-week forecast
    # ------------------------------------------------------------------
    def generate_forecast(
        self,
        selling_price: float,
        landed_cost: float,
        fba_fees: float,
        referral_fee_pct: float = 0.15,
        base_weekly_sales: int = 20,
        initial_ppc_daily: float = 30.0,
        ppc_acos: float = 35.0,
        storage_per_unit_month: float = 0.10,
        returns_rate: float = 0.03,
        review_rate: float = 0.02,
        initial_reviews: int = 0,
        vine_reviews: int = 24,
    ) -> dict[str, list[dict]]:
        """
        Generate 52-week projections for all three scenarios.

        Returns:
            {"bull": [...weeks], "base": [...weeks], "bear": [...weeks]}
        """
        results = {}

        for scenario, multipliers in self.SCENARIO_MULTIPLIERS.items():
            weeks = self._project_scenario(
                scenario=scenario,
                selling_price=selling_price,
                landed_cost=landed_cost,
                fba_fees=fba_fees,
                referral_fee_pct=referral_fee_pct,
                base_weekly_sales=base_weekly_sales,
                initial_ppc_daily=initial_ppc_daily,
                ppc_acos=ppc_acos,
                storage_per_unit_month=storage_per_unit_month,
                returns_rate=returns_rate,
                review_rate=review_rate,
                initial_reviews=initial_reviews,
                vine_reviews=vine_reviews,
                multipliers=multipliers,
            )
            results[scenario] = weeks

        return results

    def _project_scenario(
        self,
        scenario: str,
        selling_price: float,
        landed_cost: float,
        fba_fees: float,
        referral_fee_pct: float,
        base_weekly_sales: int,
        initial_ppc_daily: float,
        ppc_acos: float,
        storage_per_unit_month: float,
        returns_rate: float,
        review_rate: float,
        initial_reviews: int,
        vine_reviews: int,
        multipliers: dict,
    ) -> list[dict]:
        """Project a single scenario for 52 weeks."""
        weeks = []
        cumulative_profit = 0.0
        cumulative_reviews = initial_reviews
        cumulative_units_sold = 0

        # Vine reviews arrive in week 3-6
        vine_schedule = {3: 8, 4: 8, 5: 5, 6: 3}  # Vine reviews per week

        referral_fee = selling_price * referral_fee_pct

        for week in range(1, 53):
            # --- Organic rank progression ---
            # Rank improves over time as reviews accumulate and sales history builds
            rank_improvement = multipliers["rank_improvement_rate"]
            if week <= 4:
                organic_rank = 48  # Start deep on page 3+
            elif week <= 8:
                organic_rank = max(20, int(48 - (week - 4) * 3 * rank_improvement))
            elif week <= 16:
                organic_rank = max(10, int(20 - (week - 8) * 1.5 * rank_improvement))
            elif week <= 26:
                organic_rank = max(5, int(10 - (week - 16) * 0.5 * rank_improvement))
            else:
                organic_rank = max(3, int(5 - (week - 26) * 0.1 * rank_improvement))

            # --- Sales estimation ---
            # Sales increase as rank improves
            rank_to_sales_multiplier = self._rank_to_sales_factor(organic_rank)
            weekly_sales = int(
                base_weekly_sales
                * rank_to_sales_multiplier
                * multipliers["sales_multiplier"]
            )

            # Review boost: more reviews → higher conversion → more sales
            review_boost = min(1.0 + (cumulative_reviews / 500) * 0.3, 1.3)
            weekly_sales = int(weekly_sales * review_boost * multipliers["conversion_boost"])
            weekly_sales = max(1, weekly_sales)

            # --- PPC spend ---
            # PPC spend tapers as organic traffic grows
            organic_traffic_pct = self._estimate_organic_traffic_pct(week, organic_rank)
            ppc_taper = max(0.2, 1.0 - organic_traffic_pct * 0.8)
            daily_ppc = initial_ppc_daily * ppc_taper / multipliers["ppc_efficiency"]
            weekly_ad_spend = daily_ppc * 7

            # --- Revenue ---
            revenue = weekly_sales * selling_price

            # --- Costs ---
            cogs = weekly_sales * landed_cost
            total_fba = weekly_sales * fba_fees
            total_referral = weekly_sales * referral_fee
            returns_cost = revenue * returns_rate
            storage = weekly_sales * storage_per_unit_month / 4.33  # Weekly storage

            # --- Net profit ---
            net_profit = (
                revenue
                - cogs
                - total_fba
                - total_referral
                - weekly_ad_spend
                - returns_cost
                - storage
            )
            cumulative_profit += net_profit

            # --- Reviews ---
            organic_reviews = weekly_sales * review_rate
            vine_this_week = vine_schedule.get(week, 0)
            weekly_reviews = organic_reviews + vine_this_week
            cumulative_reviews += weekly_reviews

            cumulative_units_sold += weekly_sales

            weeks.append({
                "scenario": scenario,
                "week_number": week,
                "estimated_organic_rank": organic_rank,
                "estimated_units_sold": weekly_sales,
                "revenue": round(revenue, 2),
                "cogs": round(cogs, 2),
                "fba_fees": round(total_fba + total_referral, 2),
                "ad_spend": round(weekly_ad_spend, 2),
                "storage_fees": round(storage, 2),
                "returns_cost": round(returns_cost, 2),
                "net_profit": round(net_profit, 2),
                "cumulative_profit": round(cumulative_profit, 2),
                "review_count_projected": round(cumulative_reviews),
                "organic_traffic_pct": round(organic_traffic_pct * 100, 1),
                "cumulative_units_sold": cumulative_units_sold,
            })

        return weeks

    # ------------------------------------------------------------------
    # 2. Find break-even week
    # ------------------------------------------------------------------
    @staticmethod
    def find_break_even_week(projections: list[dict]) -> int | None:
        """Find the first week where cumulative profit turns positive."""
        for week_data in projections:
            if week_data["cumulative_profit"] > 0:
                return week_data["week_number"]
        return None  # Doesn't break even within 52 weeks

    # ------------------------------------------------------------------
    # 3. Summary metrics
    # ------------------------------------------------------------------
    def summarize_forecast(self, forecast: dict[str, list[dict]]) -> dict:
        """Generate summary metrics from the full 52-week forecast."""
        summaries = {}

        for scenario, weeks in forecast.items():
            if not weeks:
                continue

            total_revenue = sum(w["revenue"] for w in weeks)
            total_profit = weeks[-1]["cumulative_profit"]
            total_units = sum(w["estimated_units_sold"] for w in weeks)
            total_ad_spend = sum(w["ad_spend"] for w in weeks)
            break_even_week = self.find_break_even_week(weeks)

            # ROI: total profit / total investment (COGS + ads)
            total_cogs = sum(w["cogs"] for w in weeks)
            total_investment = total_cogs + total_ad_spend
            roi = (total_profit / total_investment * 100) if total_investment > 0 else 0

            # Average margin (last 12 weeks = steady state)
            last_12 = weeks[-12:]
            avg_weekly_profit = sum(w["net_profit"] for w in last_12) / 12
            avg_weekly_revenue = sum(w["revenue"] for w in last_12) / 12
            steady_state_margin = (
                (avg_weekly_profit / avg_weekly_revenue * 100)
                if avg_weekly_revenue > 0
                else 0
            )

            summaries[scenario] = {
                "total_revenue": round(total_revenue, 2),
                "total_profit": round(total_profit, 2),
                "total_units_sold": total_units,
                "total_ad_spend": round(total_ad_spend, 2),
                "break_even_week": break_even_week,
                "roi_pct": round(roi, 1),
                "steady_state_margin_pct": round(steady_state_margin, 1),
                "final_weekly_sales": weeks[-1]["estimated_units_sold"],
                "final_review_count": weeks[-1]["review_count_projected"],
                "final_organic_rank": weeks[-1]["estimated_organic_rank"],
            }

        return summaries

    # ------------------------------------------------------------------
    # 4. Save projections to DB
    # ------------------------------------------------------------------
    async def save_projections(
        self,
        niche_id: int,
        forecast: dict[str, list[dict]],
    ) -> int:
        """Save all projection weeks to the database."""
        now = datetime.now(timezone.utc)
        count = 0

        # Delete existing projections for this niche
        existing = await self.db.execute(
            select(FinancialProjection).where(
                FinancialProjection.niche_id == niche_id
            )
        )
        for row in existing.scalars().all():
            await self.db.delete(row)

        # Insert new projections
        for scenario, weeks in forecast.items():
            for week_data in weeks:
                projection = FinancialProjection(
                    niche_id=niche_id,
                    scenario=scenario,
                    week_number=week_data["week_number"],
                    estimated_organic_rank=week_data["estimated_organic_rank"],
                    estimated_units_sold=week_data["estimated_units_sold"],
                    revenue=Decimal(str(week_data["revenue"])),
                    cogs=Decimal(str(week_data["cogs"])),
                    fba_fees=Decimal(str(week_data["fba_fees"])),
                    ad_spend=Decimal(str(week_data["ad_spend"])),
                    storage_fees=Decimal(str(week_data["storage_fees"])),
                    net_profit=Decimal(str(week_data["net_profit"])),
                    cumulative_profit=Decimal(str(week_data["cumulative_profit"])),
                    review_count_projected=week_data["review_count_projected"],
                    organic_traffic_pct=Decimal(str(week_data["organic_traffic_pct"])),
                    calculated_at=now,
                )
                self.db.add(projection)
                count += 1

        await self.db.flush()
        logger.info("Saved %d projection rows for niche %d", count, niche_id)
        return count

    # ------------------------------------------------------------------
    # 5. Calculate required launch capital
    # ------------------------------------------------------------------
    def calculate_launch_capital(
        self,
        landed_cost: float,
        initial_order_qty: int,
        vine_cost: float = 0,
        ppc_budget_90_days: float = 0,
        photography_cost: float = 500,
        brand_registry_cost: float = 0,
        miscellaneous: float = 200,
    ) -> dict:
        """Calculate total capital needed to launch."""
        inventory_cost = landed_cost * initial_order_qty

        total = (
            inventory_cost
            + vine_cost
            + ppc_budget_90_days
            + photography_cost
            + brand_registry_cost
            + miscellaneous
        )

        return {
            "inventory_cost": round(inventory_cost, 2),
            "vine_cost": round(vine_cost, 2),
            "ppc_budget_90_days": round(ppc_budget_90_days, 2),
            "photography_cost": round(photography_cost, 2),
            "brand_registry_cost": round(brand_registry_cost, 2),
            "miscellaneous": round(miscellaneous, 2),
            "total_launch_capital": round(total, 2),
            "initial_order_qty": initial_order_qty,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _rank_to_sales_factor(organic_rank: int) -> float:
        """Map organic rank to a sales multiplier."""
        if organic_rank <= 3:
            return 2.5
        elif organic_rank <= 8:
            return 2.0
        elif organic_rank <= 16:
            return 1.5
        elif organic_rank <= 24:
            return 1.0
        elif organic_rank <= 36:
            return 0.6
        elif organic_rank <= 48:
            return 0.3
        else:
            return 0.15

    @staticmethod
    def _estimate_organic_traffic_pct(week: int, organic_rank: int) -> float:
        """Estimate percentage of traffic that's organic (vs PPC)."""
        # As rank improves and time passes, organic traffic increases
        rank_factor = max(0, 1.0 - (organic_rank / 48))
        time_factor = min(1.0, week / 26)  # Full organic potential by week 26
        return min(0.85, rank_factor * time_factor * 0.85)
