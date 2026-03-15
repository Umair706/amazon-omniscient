"""Consolidated financial report service — the ONLY financial document a merchant needs.

Pulls together per-unit economics, launch capital, cash flow timeline, monthly P&L,
reorder planning, scenario comparison, and key metrics into one comprehensive report.
"""

import logging
import math
from dataclasses import dataclass

from app.services.supplier_service import SupplierService
from app.core.fba_calculator import FBAFeeCalculator

logger = logging.getLogger(__name__)


@dataclass
class _UnitEconomics:
    """Internal container for per-unit cost breakdown."""

    selling_price: float
    coupon_discount: float
    effective_revenue: float
    fob_cost: float
    shipping: float
    customs_duty: float
    section_301_tariff: float
    insurance: float
    inspection: float
    freight_forwarding: float
    fba_prep: float
    fba_inbound: float
    total_landed_cost: float
    referral_fee: float
    fba_fulfillment_fee: float
    monthly_storage: float
    returns_cost: float
    total_amazon_fees: float
    ppc_cost_per_unit: float
    pre_ppc_profit: float
    pre_ppc_margin_pct: float
    post_ppc_profit: float
    post_ppc_margin_pct: float
    break_even_price: float
    roi_per_unit_pct: float


class FinancialReportService:
    """
    Generates a consolidated financial report covering every financial
    dimension an Amazon FBA merchant needs to evaluate a product opportunity.

    This service is pure computation — no database session required.

    Report sections:
        1. Per-Unit P&L Waterfall
        2. Launch Capital Requirements
        3. Cash Flow Timeline
        4. Monthly P&L Summary (12 months)
        5. Reorder Planning
        6. Scenario Comparison (Bull / Base / Bear)
        7. Key Metrics Summary
    """

    # Vine enrollment fee per unit (Amazon charges $200 for 0-30 units enrollment)
    VINE_FEE_PER_UNIT = 200 / 30  # ~$6.67 — but Amazon charges flat $200 per enrollment
    VINE_ENROLLMENT_FEE = 200.0  # Flat fee for Vine enrollment (up to 30 units)

    # Default referral fee percentage
    REFERRAL_FEE_PCT = 0.15

    # Default returns rate
    RETURNS_RATE = 0.03

    # PPC ramp: month 1 is full spend, tapering as organic rank builds
    PPC_MONTHLY_TAPER = [
        1.00, 0.95, 0.90, 0.85, 0.80, 0.75,
        0.70, 0.65, 0.60, 0.55, 0.50, 0.45,
    ]

    # Sales ramp for months 1-12 (fraction of estimated_monthly_sales)
    SALES_RAMP = [
        0.60, 0.75, 0.85, 0.90, 0.95, 1.00,
        1.00, 1.00, 1.00, 1.00, 1.00, 1.00,
    ]

    def __init__(self):
        self._supplier_service = SupplierService()
        self._fba_calculator = FBAFeeCalculator()

    # ==================================================================
    # Main entry point
    # ==================================================================
    async def generate_full_report(
        self,
        selling_price: float,
        unit_cost_fob: float,
        product_dims: dict,
        category: str = "default",
        order_quantity: int = 500,
        weight_kg_per_unit: float = 0.5,
        shipping_method: str = "sea_fcl_20ft",
        estimated_monthly_sales: int = 200,
        avg_cpc: float = 1.50,
        conversion_rate: float = 0.12,
        coupon_pct: float = 0.0,
        coupon_budget_units: int = 0,
        vine_units: int = 30,
        photography_budget: float = 500,
        a_plus_design_budget: float = 300,
        launch_ppc_daily: float = 30.0,
        supplier_lead_time_weeks: int = 4,
        shipping_transit_weeks: int = 4,
        amazon_inbound_weeks: int = 1,
    ) -> dict:
        """
        Generate a comprehensive financial report for an Amazon FBA product.

        Parameters
        ----------
        selling_price : float
            Target retail price on Amazon.
        unit_cost_fob : float
            FOB (Free On Board) price per unit from the supplier in USD.
        product_dims : dict
            Product dimensions: {length, width, height, weight_lb}.
        category : str
            Product category for duty rate lookup (e.g. "kitchen", "toys").
        order_quantity : int
            Initial order quantity.
        weight_kg_per_unit : float
            Per-unit weight in kilograms for shipping cost estimation.
        shipping_method : str
            Shipping method key (sea_lcl, sea_fcl_20ft, sea_fcl_40ft,
            air_standard, air_express).
        estimated_monthly_sales : int
            Expected monthly unit sales at steady state.
        avg_cpc : float
            Average cost per click for PPC advertising.
        conversion_rate : float
            PPC click-to-purchase conversion rate (0.0 to 1.0).
        coupon_pct : float
            Coupon discount as a fraction (e.g. 0.10 for 10% off).
        coupon_budget_units : int
            Number of units to subsidize with coupons.
        vine_units : int
            Number of units to enroll in Amazon Vine (max 30).
        photography_budget : float
            Product photography budget.
        a_plus_design_budget : float
            A+ Content design budget.
        launch_ppc_daily : float
            Daily PPC budget during launch.
        supplier_lead_time_weeks : int
            Weeks from order placement to shipment.
        shipping_transit_weeks : int
            Weeks for goods to transit from supplier to US port.
        amazon_inbound_weeks : int
            Weeks for Amazon to receive and shelve inventory.

        Returns
        -------
        dict
            Comprehensive report with seven sections: per_unit_economics,
            launch_capital, cash_flow_timeline, monthly_summary,
            reorder_plan, scenarios, key_metrics.
        """
        # --- Step 1: Calculate landed cost via SupplierService ---
        landed = self._supplier_service.calculate_landed_cost(
            unit_cost=unit_cost_fob,
            quantity=order_quantity,
            weight_kg=weight_kg_per_unit,
            category=category,
            shipping_method=shipping_method,
        )

        # --- Step 2: Calculate FBA fees ---
        fba_fees = self._fba_calculator.calculate_all_fees(
            selling_price=selling_price,
            length=product_dims.get("length", 10),
            width=product_dims.get("width", 6),
            height=product_dims.get("height", 4),
            weight_lb=product_dims.get("weight_lb", 1.0),
            category=category,
        )

        # --- Step 3: Compute per-unit economics ---
        unit_econ = self._compute_unit_economics(
            selling_price=selling_price,
            coupon_pct=coupon_pct,
            coupon_budget_units=coupon_budget_units,
            estimated_monthly_sales=estimated_monthly_sales,
            landed=landed,
            fba_fees=fba_fees,
            avg_cpc=avg_cpc,
            conversion_rate=conversion_rate,
        )

        # --- Step 4: Build each report section ---
        per_unit = self._build_per_unit_section(unit_econ)

        launch_capital = self._build_launch_capital(
            landed=landed,
            order_quantity=order_quantity,
            launch_ppc_daily=launch_ppc_daily,
            coupon_pct=coupon_pct,
            coupon_budget_units=coupon_budget_units,
            selling_price=selling_price,
            vine_units=vine_units,
            photography_budget=photography_budget,
            a_plus_design_budget=a_plus_design_budget,
        )

        total_lead_time_weeks = (
            supplier_lead_time_weeks
            + shipping_transit_weeks
            + amazon_inbound_weeks
        )

        cash_flow = self._build_cash_flow_timeline(
            landed=landed,
            order_quantity=order_quantity,
            launch_ppc_daily=launch_ppc_daily,
            vine_units=vine_units,
            photography_budget=photography_budget,
            a_plus_design_budget=a_plus_design_budget,
            selling_price=selling_price,
            unit_econ=unit_econ,
            estimated_monthly_sales=estimated_monthly_sales,
            supplier_lead_time_weeks=supplier_lead_time_weeks,
            shipping_transit_weeks=shipping_transit_weeks,
            amazon_inbound_weeks=amazon_inbound_weeks,
            fba_fees=fba_fees,
        )

        monthly_summary = self._build_monthly_summary(
            selling_price=selling_price,
            unit_econ=unit_econ,
            landed=landed,
            fba_fees=fba_fees,
            estimated_monthly_sales=estimated_monthly_sales,
            launch_ppc_daily=launch_ppc_daily,
            order_quantity=order_quantity,
        )

        reorder_plan = self._build_reorder_plan(
            estimated_monthly_sales=estimated_monthly_sales,
            order_quantity=order_quantity,
            total_lead_time_weeks=total_lead_time_weeks,
            landed=landed,
        )

        scenarios = self._build_scenarios(
            selling_price=selling_price,
            unit_econ=unit_econ,
            estimated_monthly_sales=estimated_monthly_sales,
            launch_ppc_daily=launch_ppc_daily,
            launch_capital_total=launch_capital["total_with_buffer"],
            landed=landed,
            fba_fees=fba_fees,
        )

        key_metrics = self._build_key_metrics(
            unit_econ=unit_econ,
            scenarios=scenarios,
            launch_capital=launch_capital,
            selling_price=selling_price,
            landed=landed,
            fba_fees=fba_fees,
            avg_cpc=avg_cpc,
            conversion_rate=conversion_rate,
        )

        return {
            "per_unit_economics": per_unit,
            "launch_capital": launch_capital,
            "cash_flow_timeline": cash_flow,
            "monthly_summary": monthly_summary,
            "reorder_plan": reorder_plan,
            "scenarios": scenarios,
            "key_metrics": key_metrics,
        }

    # ==================================================================
    # Section builders
    # ==================================================================

    def _compute_unit_economics(
        self,
        selling_price: float,
        coupon_pct: float,
        coupon_budget_units: int,
        estimated_monthly_sales: int,
        landed,
        fba_fees: dict,
        avg_cpc: float,
        conversion_rate: float,
    ) -> _UnitEconomics:
        """Compute the full per-unit P&L waterfall."""
        # Coupon discount amortized across all units if budget is set,
        # otherwise applied directly when coupon_pct > 0
        if coupon_budget_units > 0 and estimated_monthly_sales > 0:
            coupon_discount = round(
                (selling_price * coupon_pct * coupon_budget_units)
                / estimated_monthly_sales,
                2,
            )
        elif coupon_pct > 0:
            coupon_discount = round(selling_price * coupon_pct, 2)
        else:
            coupon_discount = 0.0

        effective_revenue = round(selling_price - coupon_discount, 2)

        # Amazon fees from FBA calculator
        referral_fee = round(fba_fees.get("referral_fee", selling_price * self.REFERRAL_FEE_PCT), 2)
        fba_fulfillment_fee = round(fba_fees.get("fulfillment_fee", 3.50), 2)
        monthly_storage = round(fba_fees.get("monthly_storage_per_unit", 0.10), 2)
        returns_cost = round(selling_price * self.RETURNS_RATE, 2)
        total_amazon_fees = round(
            referral_fee + fba_fulfillment_fee + monthly_storage + returns_cost, 2
        )

        # PPC cost per unit: CPC / conversion_rate
        ppc_cost_per_unit = round(
            avg_cpc / conversion_rate if conversion_rate > 0 else 0.0, 2
        )

        # Landed cost components from SupplierService
        total_landed_cost = round(landed.total_cost_to_amazon, 2)

        # Profit calculations
        pre_ppc_profit = round(effective_revenue - total_landed_cost - total_amazon_fees, 2)
        pre_ppc_margin_pct = round(
            (pre_ppc_profit / effective_revenue * 100) if effective_revenue > 0 else 0.0, 1
        )

        post_ppc_profit = round(pre_ppc_profit - ppc_cost_per_unit, 2)
        post_ppc_margin_pct = round(
            (post_ppc_profit / effective_revenue * 100) if effective_revenue > 0 else 0.0, 1
        )

        # Break-even price: the minimum selling price to still have positive
        # post-PPC profit. Solve: price - landed - amazon_fees(price) - ppc = 0
        # amazon_fees(price) = price*0.15 + fba_fulfillment + storage + price*0.03
        # price - landed - 0.15*price - fba_ff - storage - 0.03*price - ppc = 0
        # price * (1 - 0.15 - 0.03) = landed + fba_ff + storage + ppc
        # price = (landed + fba_ff + storage + ppc) / 0.82
        break_even_price = round(
            (total_landed_cost + fba_fulfillment_fee + monthly_storage + ppc_cost_per_unit)
            / (1.0 - self.REFERRAL_FEE_PCT - self.RETURNS_RATE),
            2,
        )

        # ROI per unit: profit / landed cost
        roi_per_unit_pct = round(
            (post_ppc_profit / total_landed_cost * 100) if total_landed_cost > 0 else 0.0, 1
        )

        return _UnitEconomics(
            selling_price=selling_price,
            coupon_discount=coupon_discount,
            effective_revenue=effective_revenue,
            fob_cost=landed.unit_cost,
            shipping=landed.shipping_per_unit,
            customs_duty=landed.customs_duty,
            section_301_tariff=landed.section_301_tariff,
            insurance=landed.insurance_per_unit,
            inspection=landed.inspection_per_unit,
            freight_forwarding=landed.freight_forwarding_per_unit,
            fba_prep=landed.fba_prep_per_unit,
            fba_inbound=landed.fba_inbound_shipping,
            total_landed_cost=total_landed_cost,
            referral_fee=referral_fee,
            fba_fulfillment_fee=fba_fulfillment_fee,
            monthly_storage=monthly_storage,
            returns_cost=returns_cost,
            total_amazon_fees=total_amazon_fees,
            ppc_cost_per_unit=ppc_cost_per_unit,
            pre_ppc_profit=pre_ppc_profit,
            pre_ppc_margin_pct=pre_ppc_margin_pct,
            post_ppc_profit=post_ppc_profit,
            post_ppc_margin_pct=post_ppc_margin_pct,
            break_even_price=break_even_price,
            roi_per_unit_pct=roi_per_unit_pct,
        )

    # ------------------------------------------------------------------
    # Section 1: Per-Unit P&L Waterfall
    # ------------------------------------------------------------------
    @staticmethod
    def _build_per_unit_section(ue: _UnitEconomics) -> dict:
        return {
            "selling_price": ue.selling_price,
            "coupon_discount": ue.coupon_discount,
            "effective_revenue": ue.effective_revenue,
            "costs": {
                "fob_cost": ue.fob_cost,
                "shipping": ue.shipping,
                "customs_duty": ue.customs_duty,
                "section_301_tariff": ue.section_301_tariff,
                "insurance": ue.insurance,
                "inspection": ue.inspection,
                "freight_forwarding": ue.freight_forwarding,
                "fba_prep": ue.fba_prep,
                "fba_inbound": ue.fba_inbound,
                "total_landed_cost": ue.total_landed_cost,
                "referral_fee": ue.referral_fee,
                "fba_fulfillment_fee": ue.fba_fulfillment_fee,
                "monthly_storage": ue.monthly_storage,
                "returns_cost": ue.returns_cost,
                "total_amazon_fees": ue.total_amazon_fees,
                "ppc_cost_per_unit": ue.ppc_cost_per_unit,
            },
            "pre_ppc_profit": ue.pre_ppc_profit,
            "pre_ppc_margin_pct": ue.pre_ppc_margin_pct,
            "post_ppc_profit": ue.post_ppc_profit,
            "post_ppc_margin_pct": ue.post_ppc_margin_pct,
            "break_even_price": ue.break_even_price,
            "roi_per_unit_pct": ue.roi_per_unit_pct,
        }

    # ------------------------------------------------------------------
    # Section 2: Launch Capital Requirements
    # ------------------------------------------------------------------
    def _build_launch_capital(
        self,
        landed,
        order_quantity: int,
        launch_ppc_daily: float,
        coupon_pct: float,
        coupon_budget_units: int,
        selling_price: float,
        vine_units: int,
        photography_budget: float,
        a_plus_design_budget: float,
    ) -> dict:
        inventory_total = round(landed.total_cost_to_amazon * order_quantity, 2)
        ppc_90_day = round(launch_ppc_daily * 90, 2)
        coupon_budget = round(selling_price * coupon_pct * coupon_budget_units, 2)

        # Vine cost: $200 flat enrollment fee per batch of up to 30 units
        # plus the cost of the free units themselves (landed cost)
        vine_enrollments = math.ceil(vine_units / 30) if vine_units > 0 else 0
        vine_enrollment_cost = round(self.VINE_ENROLLMENT_FEE * vine_enrollments, 2)
        vine_unit_cost = round(landed.total_cost_to_amazon * vine_units, 2)
        vine_total = round(vine_enrollment_cost + vine_unit_cost, 2)

        samples_cost = 150.00
        misc_cost = 200.00

        subtotals = {
            "inventory": {"quantity": order_quantity, "total": inventory_total},
            "advertising": {"ppc_90_day": ppc_90_day, "coupon_budget": coupon_budget},
            "vine_enrollment": {
                "units": vine_units,
                "enrollment_fee": vine_enrollment_cost,
                "unit_cost": vine_unit_cost,
                "cost": vine_total,
            },
            "creative": {
                "photography": photography_budget,
                "a_plus_design": a_plus_design_budget,
            },
            "other": {
                "brand_registry": 0.00,
                "samples": samples_cost,
                "misc": misc_cost,
            },
        }

        total = round(
            inventory_total
            + ppc_90_day
            + coupon_budget
            + vine_total
            + photography_budget
            + a_plus_design_budget
            + samples_cost
            + misc_cost,
            2,
        )

        buffer = round(total * 0.15, 2)

        return {
            **subtotals,
            "total_launch_capital": total,
            "recommended_buffer_15pct": buffer,
            "total_with_buffer": round(total + buffer, 2),
        }

    # ------------------------------------------------------------------
    # Section 3: Cash Flow Timeline
    # ------------------------------------------------------------------
    def _build_cash_flow_timeline(
        self,
        landed,
        order_quantity: int,
        launch_ppc_daily: float,
        vine_units: int,
        photography_budget: float,
        a_plus_design_budget: float,
        selling_price: float,
        unit_econ: _UnitEconomics,
        estimated_monthly_sales: int,
        supplier_lead_time_weeks: int,
        shipping_transit_weeks: int,
        amazon_inbound_weeks: int,
        fba_fees: dict,
    ) -> list[dict]:
        """
        Build a week-by-week cash flow timeline from supplier deposit
        through to break-even.
        """
        timeline = []
        balance = 0.0

        total_lead = supplier_lead_time_weeks + shipping_transit_weeks + amazon_inbound_weeks
        start_week = -(supplier_lead_time_weeks + shipping_transit_weeks)

        # Total inventory cost
        inventory_total = landed.total_cost_to_amazon * order_quantity
        deposit_pct = 0.30
        balance_pct = 0.70

        supplier_deposit = round(inventory_total * deposit_pct, 2)
        supplier_balance = round(inventory_total * balance_pct, 2)

        # Freight cost (shipping + insurance + inspection + freight forwarding per unit * qty)
        freight_cost = round(
            (landed.shipping_per_unit
             + landed.insurance_per_unit
             + landed.inspection_per_unit
             + landed.freight_forwarding_per_unit)
            * order_quantity,
            2,
        )

        # Customs duties and tariffs paid at port entry
        customs_total = round(
            (landed.customs_duty + landed.section_301_tariff) * order_quantity, 2
        )

        # FBA prep and inbound
        fba_prep_total = round(
            (landed.fba_prep_per_unit + landed.fba_inbound_shipping) * order_quantity, 2
        )

        creative_cost = round(photography_budget + a_plus_design_budget, 2)

        # Vine enrollment fee
        vine_enrollments = math.ceil(vine_units / 30) if vine_units > 0 else 0
        vine_cost = round(
            self.VINE_ENROLLMENT_FEE * vine_enrollments
            + landed.total_cost_to_amazon * vine_units,
            2,
        )

        # Weekly PPC spend
        weekly_ppc = round(launch_ppc_daily * 7, 2)

        # Weekly sales revenue (with Amazon's 14-day hold for new sellers)
        weekly_sales_units = estimated_monthly_sales / 4.33
        # Use ramped sales for the first weeks
        ramp_factor_initial = self.SALES_RAMP[0]  # Month 1 ramp
        ramped_weekly_units = weekly_sales_units * ramp_factor_initial

        # Per-unit revenue after Amazon fees
        referral_fee = fba_fees.get("referral_fee", selling_price * self.REFERRAL_FEE_PCT)
        fulfillment_fee = fba_fees.get("fulfillment_fee", 3.50)
        net_revenue_per_unit = selling_price - referral_fee - fulfillment_fee

        # --- Event: Supplier deposit ---
        deposit_week = start_week
        balance -= supplier_deposit
        timeline.append({
            "week": deposit_week,
            "event": f"Pay supplier deposit ({int(deposit_pct * 100)}%)",
            "cash_out": supplier_deposit,
            "cash_in": 0,
            "balance": round(balance, 2),
        })

        # --- Event: Supplier balance + freight ---
        ship_week = -(shipping_transit_weeks + amazon_inbound_weeks)
        balance -= supplier_balance
        timeline.append({
            "week": ship_week,
            "event": f"Pay supplier balance ({int(balance_pct * 100)}%)",
            "cash_out": supplier_balance,
            "cash_in": 0,
            "balance": round(balance, 2),
        })

        balance -= freight_cost
        timeline.append({
            "week": ship_week,
            "event": "Pay freight forwarder",
            "cash_out": freight_cost,
            "cash_in": 0,
            "balance": round(balance, 2),
        })

        # --- Event: Customs at port entry (approx 1 week before FBA arrival) ---
        customs_week = -(amazon_inbound_weeks)
        if customs_total > 0:
            balance -= customs_total
            timeline.append({
                "week": customs_week,
                "event": "Customs duties & tariffs",
                "cash_out": customs_total,
                "cash_in": 0,
                "balance": round(balance, 2),
            })

        # --- Event: Goods arrive at FBA + creative costs + FBA prep ---
        arrival_week = 0
        arrival_costs = round(creative_cost + fba_prep_total, 2)
        balance -= arrival_costs
        timeline.append({
            "week": arrival_week,
            "event": "Goods arrive at FBA + creative costs + FBA prep",
            "cash_out": arrival_costs,
            "cash_in": 0,
            "balance": round(balance, 2),
        })

        # --- Event: Week 1 — PPC launch + Vine enrollment ---
        week_1_cost = round(weekly_ppc + vine_cost, 2)
        balance -= week_1_cost
        timeline.append({
            "week": 1,
            "event": "PPC launch + Vine enrollment",
            "cash_out": week_1_cost,
            "cash_in": 0,
            "balance": round(balance, 2),
        })

        # --- Weeks 2+ : PPC spend + revenue (with 14-day hold) ---
        # Amazon holds payouts for ~14 days for new sellers, then pays biweekly.
        # First payout arrives around week 3 (14-day hold from first sale in week 0/1).
        max_week = 26  # default end
        break_even_found = False

        for week in range(2, 53):
            week_cash_out = weekly_ppc
            week_cash_in = 0.0

            # Determine sales ramp for this week's month
            month_index = min((week - 1) // 4, 11)
            ramp = self.SALES_RAMP[month_index]
            ppc_taper = self.PPC_MONTHLY_TAPER[month_index]
            tapered_ppc = round(launch_ppc_daily * 7 * ppc_taper, 2)
            week_cash_out = tapered_ppc

            units_this_week = round(weekly_sales_units * ramp)

            # Revenue arrives with a 2-week delay (Amazon 14-day hold)
            if week >= 3:
                # Revenue from sales 2 weeks ago
                delayed_month = min((week - 3) // 4, 11)
                delayed_ramp = self.SALES_RAMP[delayed_month]
                delayed_units = round(weekly_sales_units * delayed_ramp)
                week_cash_in = round(net_revenue_per_unit * delayed_units, 2)

            balance = round(balance - week_cash_out + week_cash_in, 2)

            event_parts = []
            if week_cash_out > 0:
                event_parts.append(f"PPC spend (tapered {int(ppc_taper * 100)}%)")
            if week_cash_in > 0:
                event_parts.append(f"Amazon payout (~{int(round(delayed_units))} units)")
            event = " + ".join(event_parts) if event_parts else "No activity"

            # Check for break-even
            if balance >= 0 and not break_even_found:
                event = f"Break-even point — {event}"
                break_even_found = True

            timeline.append({
                "week": week,
                "event": event,
                "cash_out": round(week_cash_out, 2),
                "cash_in": round(week_cash_in, 2),
                "balance": round(balance, 2),
            })

            # Stop if we have passed break-even and reached at least week 26
            if break_even_found and week >= max_week:
                break
            # Hard cap at week 52
            if week >= 52:
                break

        return timeline

    # ------------------------------------------------------------------
    # Section 4: Monthly P&L Summary (12 months)
    # ------------------------------------------------------------------
    def _build_monthly_summary(
        self,
        selling_price: float,
        unit_econ: _UnitEconomics,
        landed,
        fba_fees: dict,
        estimated_monthly_sales: int,
        launch_ppc_daily: float,
        order_quantity: int,
    ) -> list[dict]:
        monthly = []
        cumulative_profit = 0.0
        inventory_remaining = order_quantity

        referral_fee_per_unit = unit_econ.referral_fee
        fulfillment_fee_per_unit = unit_econ.fba_fulfillment_fee
        storage_per_unit = unit_econ.monthly_storage
        returns_rate = self.RETURNS_RATE
        landed_cost_per_unit = landed.total_cost_to_amazon

        for month in range(1, 13):
            idx = month - 1
            ramp = self.SALES_RAMP[idx]
            ppc_taper = self.PPC_MONTHLY_TAPER[idx]

            units_sold = int(round(estimated_monthly_sales * ramp))

            # Don't sell more than remaining inventory
            units_sold = min(units_sold, max(inventory_remaining, 0))

            revenue = round(selling_price * units_sold, 2)
            cogs = round(landed_cost_per_unit * units_sold, 2)

            amazon_fees = round(
                (referral_fee_per_unit + fulfillment_fee_per_unit + storage_per_unit)
                * units_sold
                + revenue * returns_rate,
                2,
            )

            ppc_spend = round(launch_ppc_daily * 30 * ppc_taper, 2)

            other_costs = 0.0

            net_profit = round(revenue - cogs - amazon_fees - ppc_spend - other_costs, 2)
            cumulative_profit = round(cumulative_profit + net_profit, 2)

            inventory_remaining -= units_sold

            # Determine if reorder is needed (when inventory < 2 months of sales)
            reorder_needed = inventory_remaining < (estimated_monthly_sales * 2)

            monthly.append({
                "month": month,
                "units_sold": units_sold,
                "revenue": revenue,
                "cogs": cogs,
                "amazon_fees": amazon_fees,
                "ppc_spend": ppc_spend,
                "other_costs": round(other_costs, 2),
                "net_profit": net_profit,
                "cumulative_profit": cumulative_profit,
                "margin_pct": round(
                    (net_profit / revenue * 100) if revenue > 0 else 0.0, 1
                ),
                "inventory_remaining": max(inventory_remaining, 0),
                "reorder_needed": reorder_needed,
            })

        return monthly

    # ------------------------------------------------------------------
    # Section 5: Reorder Planning
    # ------------------------------------------------------------------
    @staticmethod
    def _build_reorder_plan(
        estimated_monthly_sales: int,
        order_quantity: int,
        total_lead_time_weeks: int,
        landed,
    ) -> dict:
        daily_sales = round(estimated_monthly_sales / 30, 1)
        days_of_inventory = round(order_quantity / daily_sales, 0) if daily_sales > 0 else 0
        lead_time_days = total_lead_time_weeks * 7

        reorder_trigger_units = round(lead_time_days * daily_sales)

        # When to reorder: inventory drops to reorder_trigger_units
        days_until_reorder = (
            round((order_quantity - reorder_trigger_units) / daily_sales)
            if daily_sales > 0
            else 0
        )
        reorder_week_approx = round(days_until_reorder / 7)

        # Recommend ordering ~3 months of inventory for the reorder
        recommended_reorder_qty = max(
            int(round(estimated_monthly_sales * 3, -2)),  # round to nearest 100
            order_quantity,
        )

        reorder_cost = round(landed.total_cost_to_amazon * recommended_reorder_qty, 2)

        # Estimate total year 1 inventory investment
        # Initial order + approximately 2-3 reorders depending on sell-through
        annual_units_needed = estimated_monthly_sales * 12
        total_orders_year_1 = math.ceil(annual_units_needed / recommended_reorder_qty)
        total_year_1_investment = round(
            (order_quantity * landed.total_cost_to_amazon)
            + (max(total_orders_year_1 - 1, 0) * reorder_cost),
            2,
        )

        return {
            "sell_through_rate_units_per_day": daily_sales,
            "days_of_inventory": int(days_of_inventory),
            "lead_time_days": lead_time_days,
            "reorder_trigger_units": reorder_trigger_units,
            "reorder_trigger_date_approx": f"Week {reorder_week_approx}-{reorder_week_approx + 1}",
            "recommended_reorder_qty": recommended_reorder_qty,
            "reorder_cost": reorder_cost,
            "working_capital_for_reorder": reorder_cost,
            "total_year_1_inventory_investment": total_year_1_investment,
        }

    # ------------------------------------------------------------------
    # Section 6: Scenario Comparison (Bull / Base / Bear)
    # ------------------------------------------------------------------
    def _build_scenarios(
        self,
        selling_price: float,
        unit_econ: _UnitEconomics,
        estimated_monthly_sales: int,
        launch_ppc_daily: float,
        launch_capital_total: float,
        landed,
        fba_fees: dict,
    ) -> dict:
        """
        Generate simplified bull (1.3x), base (1.0x), bear (0.7x) annual
        projections. This does NOT duplicate the full 52-week logic from
        SalesForecastService — it computes annual totals directly.
        """
        multipliers = {"bull": 1.3, "base": 1.0, "bear": 0.7}
        scenarios = {}

        for label, mult in multipliers.items():
            annual_units = 0
            annual_revenue = 0.0
            annual_cogs = 0.0
            annual_amazon_fees = 0.0
            annual_ppc = 0.0

            for month in range(12):
                ramp = self.SALES_RAMP[month]
                ppc_taper = self.PPC_MONTHLY_TAPER[month]

                monthly_units = int(round(estimated_monthly_sales * ramp * mult))
                monthly_revenue = selling_price * monthly_units
                monthly_cogs = landed.total_cost_to_amazon * monthly_units
                monthly_amazon_fees = (
                    (unit_econ.referral_fee
                     + unit_econ.fba_fulfillment_fee
                     + unit_econ.monthly_storage)
                    * monthly_units
                    + monthly_revenue * self.RETURNS_RATE
                )
                monthly_ppc = launch_ppc_daily * 30 * ppc_taper

                annual_units += monthly_units
                annual_revenue += monthly_revenue
                annual_cogs += monthly_cogs
                annual_amazon_fees += monthly_amazon_fees
                annual_ppc += monthly_ppc

            annual_profit = round(
                annual_revenue - annual_cogs - annual_amazon_fees - annual_ppc, 2
            )
            annual_revenue = round(annual_revenue, 2)

            # ROI: annual profit / total launch capital
            roi_pct = round(
                (annual_profit / launch_capital_total * 100)
                if launch_capital_total > 0
                else 0.0,
                0,
            )

            # Approximate break-even week: cumulative profit turns positive
            # Simplified: find when cumulative net crosses zero
            cumulative = -launch_capital_total
            break_even_week = None
            for month in range(12):
                ramp = self.SALES_RAMP[month]
                ppc_taper = self.PPC_MONTHLY_TAPER[month]

                mu = int(round(estimated_monthly_sales * ramp * mult))
                mr = selling_price * mu
                mc = landed.total_cost_to_amazon * mu
                maf = (
                    (unit_econ.referral_fee
                     + unit_econ.fba_fulfillment_fee
                     + unit_econ.monthly_storage)
                    * mu
                    + mr * self.RETURNS_RATE
                )
                mppc = launch_ppc_daily * 30 * ppc_taper
                monthly_net = mr - mc - maf - mppc
                cumulative += monthly_net
                if cumulative >= 0 and break_even_week is None:
                    # Approximate week within this month
                    # How much was needed at start of month
                    needed = cumulative - monthly_net  # still negative
                    if monthly_net > 0:
                        fraction = abs(needed) / monthly_net
                        break_even_week = int(round(month * 4.33 + fraction * 4.33))
                    else:
                        break_even_week = (month + 1) * 4

            scenarios[label] = {
                "annual_units": annual_units,
                "annual_revenue": annual_revenue,
                "annual_profit": annual_profit,
                "roi_pct": int(roi_pct),
                "break_even_week": break_even_week,
            }

        return scenarios

    # ------------------------------------------------------------------
    # Section 7: Key Metrics Summary
    # ------------------------------------------------------------------
    def _build_key_metrics(
        self,
        unit_econ: _UnitEconomics,
        scenarios: dict,
        launch_capital: dict,
        selling_price: float,
        landed,
        fba_fees: dict,
        avg_cpc: float,
        conversion_rate: float,
    ) -> dict:
        base = scenarios.get("base", {})
        annual_profit_base = base.get("annual_profit", 0.0)
        break_even_week_base = base.get("break_even_week")
        total_investment = launch_capital["total_with_buffer"]
        annual_roi = base.get("roi_pct", 0)

        # Verdict
        margin = unit_econ.post_ppc_margin_pct
        if margin >= 20:
            verdict = "PROFITABLE"
        elif margin >= 10:
            verdict = "MARGINAL"
        else:
            verdict = "UNPROFITABLE"

        # Maximum CPC that still allows break-even
        # At break-even: revenue = all costs including PPC
        # PPC cost per unit = CPC / CR
        # profit_before_ppc = effective_revenue - landed - amazon_fees
        # At break-even: CPC / CR = profit_before_ppc
        # CPC_max = profit_before_ppc * CR
        profit_before_ppc = unit_econ.pre_ppc_profit
        max_cpc_breakeven = round(profit_before_ppc * conversion_rate, 2)

        # Units to break even on total investment
        profit_per_unit = unit_econ.post_ppc_profit
        units_to_break_even = (
            math.ceil(total_investment / profit_per_unit)
            if profit_per_unit > 0
            else None
        )

        return {
            "verdict": verdict,
            "post_ppc_margin_pct": unit_econ.post_ppc_margin_pct,
            "annual_profit_base": annual_profit_base,
            "break_even_week_base": break_even_week_base,
            "total_investment_needed": total_investment,
            "annual_roi_pct": annual_roi,
            "minimum_viable_price": unit_econ.break_even_price,
            "max_cpc_breakeven": max_cpc_breakeven,
            "units_to_break_even": units_to_break_even,
        }
