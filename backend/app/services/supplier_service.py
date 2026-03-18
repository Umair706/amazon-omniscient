"""Supplier intelligence service: Alibaba scraping, landed cost calculations, supplier scoring."""

import logging
from dataclasses import dataclass

import httpx

from app.core.exceptions import SupplierAPIError
from app.llm.base_client import BaseLLMClient

logger = logging.getLogger(__name__)


@dataclass
class ShippingQuote:
    """Shipping cost estimate."""
    method: str  # "sea", "air", "express"
    cost_per_unit: float
    transit_days_min: int
    transit_days_max: int
    minimum_quantity: int


@dataclass
class LandedCost:
    """Full landed cost breakdown."""
    unit_cost: float
    shipping_per_unit: float
    customs_duty: float
    customs_duty_rate: float
    section_301_tariff: float
    section_301_rate: float
    insurance_per_unit: float
    inspection_per_unit: float
    freight_forwarding_per_unit: float
    total_landed_cost: float

    # FBA costs (at Amazon)
    fba_prep_per_unit: float
    fba_inbound_shipping: float

    # Grand total
    total_cost_to_amazon: float


class SupplierService:
    """
    Supplier intelligence and cost analysis service.

    Capabilities:
    1. Search Alibaba for suppliers (via API/scraping)
    2. Calculate full landed costs (COGS + shipping + duties + tariffs + insurance + prep)
    3. Score suppliers on reliability metrics
    4. Generate supplier comparison reports via LLM
    """

    # US customs duty rates by common Amazon product categories
    # These are approximate HTS rates - real implementation would use HTS API
    DUTY_RATES = {
        "electronics": 0.0,
        "toys": 0.0,
        "kitchen": 0.032,
        "home": 0.035,
        "beauty": 0.0,
        "health": 0.0,
        "sports": 0.048,
        "clothing": 0.12,
        "shoes": 0.087,
        "bags": 0.08,
        "jewelry": 0.065,
        "pet": 0.0,
        "garden": 0.025,
        "office": 0.0,
        "automotive": 0.025,
        "default": 0.035,
    }

    # Section 301 tariff rates (China-origin goods)
    SECTION_301_RATES = {
        "list_1": 0.25,  # $34B list
        "list_2": 0.25,  # $16B list
        "list_3": 0.25,  # $200B list (raised from 10% to 25%)
        "list_4a": 0.075,  # $300B list (reduced from 15% to 7.5%)
        "exempt": 0.0,
        "default": 0.25,  # Assume List 3 as default
    }

    # Shipping cost estimates per unit by method (for a typical 1-2 lb product)
    SHIPPING_ESTIMATES = {
        "sea_lcl": ShippingQuote("sea_lcl", 1.50, 30, 45, 100),
        "sea_fcl_20ft": ShippingQuote("sea_fcl_20ft", 0.80, 25, 40, 500),
        "sea_fcl_40ft": ShippingQuote("sea_fcl_40ft", 0.60, 25, 40, 1000),
        "air_standard": ShippingQuote("air_standard", 4.50, 7, 14, 50),
        "air_express": ShippingQuote("air_express", 8.00, 3, 7, 10),
    }

    def __init__(self, llm_client: BaseLLMClient | None = None, marketplace: str = "US"):
        self.llm = llm_client
        self._http_client = httpx.AsyncClient(timeout=30.0)
        self._marketplace = marketplace.strip().upper()

        # Load marketplace-specific duty/shipping from marketplace config
        from app.core.marketplace import get_marketplace
        self._mp_config = get_marketplace(self._marketplace)

    async def close(self):
        await self._http_client.aclose()

    # ------------------------------------------------------------------
    # 1. Landed cost calculator
    # ------------------------------------------------------------------
    def calculate_landed_cost(
        self,
        unit_cost: float,
        quantity: int,
        weight_kg: float = 0.5,
        category: str = "default",
        shipping_method: str = "sea_fcl_20ft",
        origin_country: str = "CN",
        section_301_list: str = "default",
        insurance_rate: float = 0.01,
        inspection_per_unit: float = 0.05,
        freight_forwarding_per_unit: float = 0.15,
        fba_prep_per_unit: float = 0.50,
        fba_inbound_per_unit: float = 0.30,
    ) -> LandedCost:
        """
        Calculate complete landed cost for importing goods to Amazon FBA.

        Parameters
        ----------
        unit_cost : float
            FOB unit cost from supplier
        quantity : int
            Order quantity
        weight_kg : float
            Per-unit weight in kg
        category : str
            Product category for duty rate lookup
        shipping_method : str
            One of: sea_lcl, sea_fcl_20ft, sea_fcl_40ft, air_standard, air_express
        origin_country : str
            Country of origin (CN = China, default)
        section_301_list : str
            Section 301 tariff list (list_1, list_2, list_3, list_4a, exempt)
        insurance_rate : float
            Insurance as a fraction of goods value (default 1%)
        inspection_per_unit : float
            Third-party inspection cost per unit
        freight_forwarding_per_unit : float
            Freight forwarder fees per unit
        fba_prep_per_unit : float
            FBA prep/labeling cost per unit
        fba_inbound_per_unit : float
            FBA inbound shipping per unit
        """
        # Shipping — use marketplace-specific profile if available
        mp_ship = self._mp_config.shipping_profile
        shipping_methods_mp = {
            "sea_lcl": mp_ship.sea_lcl_per_unit,
            "sea_fcl_20ft": mp_ship.sea_fcl_20ft_per_unit,
            "sea_fcl_40ft": mp_ship.sea_fcl_40ft_per_unit,
            "air_standard": mp_ship.air_standard_per_unit,
            "air_express": mp_ship.air_express_per_unit,
        }
        base_ship_cost = shipping_methods_mp.get(
            shipping_method, mp_ship.sea_fcl_20ft_per_unit
        )
        # Adjust shipping by weight (base rate is for ~0.5kg)
        weight_factor = max(weight_kg / 0.5, 1.0)
        shipping_per_unit = base_ship_cost * weight_factor

        # Customs duty — use marketplace duty profile
        duty_profile = self._mp_config.duty_profile
        duty_rate = duty_profile.category_rates.get(
            category.lower(), duty_profile.default_duty_rate
        )
        customs_duty = unit_cost * duty_rate

        # Tariff surcharge (Section 301 for US, none for AU under ChAFTA)
        s301_rate = 0.0
        if origin_country.upper() == "CN" and duty_profile.surcharge_name:
            s301_rate = duty_profile.surcharge_category_rates.get(
                section_301_list, duty_profile.surcharge_default_rate
            )
        section_301_tariff = unit_cost * s301_rate

        # Insurance
        insurance_per_unit = (unit_cost + shipping_per_unit) * insurance_rate

        # Total landed cost
        total_landed = (
            unit_cost
            + shipping_per_unit
            + customs_duty
            + section_301_tariff
            + insurance_per_unit
            + inspection_per_unit
            + freight_forwarding_per_unit
        )

        # Total cost to Amazon (including FBA prep)
        total_to_amazon = total_landed + fba_prep_per_unit + fba_inbound_per_unit

        return LandedCost(
            unit_cost=round(unit_cost, 2),
            shipping_per_unit=round(shipping_per_unit, 2),
            customs_duty=round(customs_duty, 2),
            customs_duty_rate=duty_rate,
            section_301_tariff=round(section_301_tariff, 2),
            section_301_rate=s301_rate,
            insurance_per_unit=round(insurance_per_unit, 2),
            inspection_per_unit=round(inspection_per_unit, 2),
            freight_forwarding_per_unit=round(freight_forwarding_per_unit, 2),
            total_landed_cost=round(total_landed, 2),
            fba_prep_per_unit=round(fba_prep_per_unit, 2),
            fba_inbound_shipping=round(fba_inbound_per_unit, 2),
            total_cost_to_amazon=round(total_to_amazon, 2),
        )

    # ------------------------------------------------------------------
    # 2. Margin calculator
    # ------------------------------------------------------------------
    def calculate_margins(
        self,
        selling_price: float,
        landed_cost: LandedCost,
        fba_referral_fee_pct: float = 0.15,
        fba_fulfillment_fee: float = 3.50,
        monthly_storage_per_unit: float = 0.10,
        ppc_cost_per_unit: float = 2.00,
        returns_rate: float = 0.03,
    ) -> dict:
        """
        Calculate profit margins given selling price and all costs.

        Returns dict with pre-PPC margin, post-PPC margin, break-even analysis.
        """
        referral_fee = selling_price * fba_referral_fee_pct
        returns_cost = selling_price * returns_rate

        total_amazon_fees = referral_fee + fba_fulfillment_fee + monthly_storage_per_unit

        # Pre-PPC profit
        pre_ppc_profit = selling_price - landed_cost.total_cost_to_amazon - total_amazon_fees - returns_cost
        pre_ppc_margin = (pre_ppc_profit / selling_price * 100) if selling_price > 0 else 0

        # Post-PPC profit
        post_ppc_profit = pre_ppc_profit - ppc_cost_per_unit
        post_ppc_margin = (post_ppc_profit / selling_price * 100) if selling_price > 0 else 0

        # Break-even units (how many units to sell to recover initial investment)
        # Assuming initial order is MOQ * landed cost
        initial_investment = landed_cost.total_cost_to_amazon  # per unit
        break_even_price = landed_cost.total_cost_to_amazon + total_amazon_fees + returns_cost + ppc_cost_per_unit

        # ROI
        roi = (post_ppc_profit / landed_cost.total_cost_to_amazon * 100) if landed_cost.total_cost_to_amazon > 0 else 0

        return {
            "selling_price": round(selling_price, 2),
            "landed_cost": round(landed_cost.total_cost_to_amazon, 2),
            "referral_fee": round(referral_fee, 2),
            "fba_fulfillment_fee": round(fba_fulfillment_fee, 2),
            "monthly_storage": round(monthly_storage_per_unit, 2),
            "returns_cost": round(returns_cost, 2),
            "total_amazon_fees": round(total_amazon_fees, 2),
            "ppc_cost_per_unit": round(ppc_cost_per_unit, 2),
            "pre_ppc_profit": round(pre_ppc_profit, 2),
            "pre_ppc_margin_pct": round(pre_ppc_margin, 1),
            "post_ppc_profit": round(post_ppc_profit, 2),
            "post_ppc_margin_pct": round(post_ppc_margin, 1),
            "break_even_price": round(break_even_price, 2),
            "roi_pct": round(roi, 1),
            "is_profitable": post_ppc_profit > 0,
            "meets_30pct_target": pre_ppc_margin >= 30,
        }

    # ------------------------------------------------------------------
    # 3. Score a supplier
    # ------------------------------------------------------------------
    def score_supplier(
        self,
        years_in_business: int = 0,
        transaction_count: int = 0,
        response_rate: float = 0.0,
        on_time_delivery_rate: float = 0.0,
        has_trade_assurance: bool = False,
        is_verified: bool = False,
        is_gold_supplier: bool = False,
        rating: float = 0.0,
        sample_available: bool = False,
    ) -> dict:
        """
        Score a supplier on a 0-100 scale based on reliability metrics.
        """
        score = 0
        breakdown = {}

        # Years in business (max 15 pts)
        years_score = min(years_in_business * 2, 15)
        score += years_score
        breakdown["years_in_business"] = years_score

        # Transaction history (max 15 pts)
        if transaction_count >= 1000:
            txn_score = 15
        elif transaction_count >= 500:
            txn_score = 12
        elif transaction_count >= 100:
            txn_score = 9
        elif transaction_count >= 50:
            txn_score = 6
        elif transaction_count >= 10:
            txn_score = 3
        else:
            txn_score = 0
        score += txn_score
        breakdown["transaction_history"] = txn_score

        # Response rate (max 10 pts)
        resp_score = int(response_rate * 10)
        score += resp_score
        breakdown["response_rate"] = resp_score

        # On-time delivery (max 15 pts)
        otd_score = int(on_time_delivery_rate * 15)
        score += otd_score
        breakdown["on_time_delivery"] = otd_score

        # Trade assurance (10 pts)
        ta_score = 10 if has_trade_assurance else 0
        score += ta_score
        breakdown["trade_assurance"] = ta_score

        # Verified supplier (10 pts)
        ver_score = 10 if is_verified else 0
        score += ver_score
        breakdown["verified"] = ver_score

        # Gold supplier (10 pts)
        gold_score = 10 if is_gold_supplier else 0
        score += gold_score
        breakdown["gold_supplier"] = gold_score

        # Rating (max 10 pts)
        rating_score = int((rating / 5.0) * 10) if rating > 0 else 0
        score += rating_score
        breakdown["rating"] = rating_score

        # Sample available (5 pts)
        sample_score = 5 if sample_available else 0
        score += sample_score
        breakdown["sample_available"] = sample_score

        # Tier
        if score >= 80:
            tier = "excellent"
        elif score >= 60:
            tier = "good"
        elif score >= 40:
            tier = "fair"
        else:
            tier = "risky"

        return {
            "total_score": min(score, 100),
            "tier": tier,
            "breakdown": breakdown,
        }

    # ------------------------------------------------------------------
    # 4. LLM supplier comparison
    # ------------------------------------------------------------------
    async def generate_supplier_comparison(
        self,
        suppliers: list[dict],
        product_requirements: str,
    ) -> dict:
        """Use LLM to generate a detailed supplier comparison and recommendation."""
        if not self.llm:
            raise SupplierAPIError("LLM client required for supplier comparison")

        prompt = f"""Compare these suppliers for the following product requirements:

REQUIREMENTS: {product_requirements}

SUPPLIERS:
{self._format_suppliers(suppliers)}

Return a JSON object:
{{
    "recommended_supplier_index": <0-based index of best supplier>,
    "recommendation_reason": "<why this supplier is best>",
    "supplier_analyses": [
        {{
            "supplier_name": "<name>",
            "strengths": ["<strength>"],
            "weaknesses": ["<weakness>"],
            "risk_level": "<low|medium|high>",
            "negotiation_tips": ["<tip for negotiating with this supplier>"]
        }}
    ],
    "general_advice": "<overall sourcing advice for this product>",
    "red_flags": ["<any concerns across all suppliers>"],
    "suggested_questions_for_suppliers": [
        "<questions to ask before placing an order>"
    ]
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096)

    # ------------------------------------------------------------------
    # 5. Calculate optimal order quantity
    # ------------------------------------------------------------------
    def calculate_optimal_moq(
        self,
        price_tiers: list[dict],
        estimated_monthly_sales: int,
        months_of_inventory: int = 3,
        max_budget: float = 10000,
        storage_cost_per_unit_month: float = 0.10,
    ) -> dict:
        """
        Determine optimal order quantity balancing cost savings vs cash flow.

        price_tiers: [{"min_qty": 100, "max_qty": 499, "unit_price": 5.00}, ...]
        """
        target_units = estimated_monthly_sales * months_of_inventory

        best_option = None
        options = []

        for tier in sorted(price_tiers, key=lambda t: t.get("min_qty", 0)):
            min_qty = tier.get("min_qty", 0)
            unit_price = tier.get("unit_price", 0)

            # Consider both the tier minimum and the target
            for qty in [min_qty, target_units]:
                if qty < min_qty:
                    continue

                total_cost = qty * unit_price
                if total_cost > max_budget:
                    continue

                # Months of inventory at this quantity
                months_supply = qty / max(estimated_monthly_sales, 1)
                storage_cost = qty * storage_cost_per_unit_month * months_supply / 2  # average inventory

                total_with_storage = total_cost + storage_cost
                effective_unit_cost = total_with_storage / qty if qty > 0 else 0

                option = {
                    "quantity": qty,
                    "unit_price": unit_price,
                    "total_cost": round(total_cost, 2),
                    "storage_cost_estimate": round(storage_cost, 2),
                    "effective_unit_cost": round(effective_unit_cost, 2),
                    "months_of_inventory": round(months_supply, 1),
                    "within_budget": total_cost <= max_budget,
                }
                options.append(option)

                if best_option is None or effective_unit_cost < best_option["effective_unit_cost"]:
                    best_option = option

        return {
            "recommended_quantity": best_option["quantity"] if best_option else 0,
            "recommended_option": best_option,
            "all_options": options,
            "target_units": target_units,
            "max_budget": max_budget,
        }

    @staticmethod
    def _format_suppliers(suppliers: list[dict]) -> str:
        lines = []
        for i, s in enumerate(suppliers):
            lines.append(
                f"Supplier {i + 1}: {s.get('name', 'Unknown')}\n"
                f"  Location: {s.get('location', '?')}\n"
                f"  Years: {s.get('years_in_business', '?')}\n"
                f"  MOQ: {s.get('moq', '?')}\n"
                f"  Unit Price: ${s.get('unit_price', '?')}\n"
                f"  Trade Assurance: {s.get('has_trade_assurance', False)}\n"
                f"  Verified: {s.get('is_verified', False)}\n"
                f"  Rating: {s.get('rating', '?')}/5\n"
                f"  Transactions: {s.get('transaction_count', '?')}\n"
            )
        return "\n".join(lines)
