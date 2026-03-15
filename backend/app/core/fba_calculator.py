"""
FBA Fee Calculator — Amazon US Marketplace (2024/2025 Fee Schedule)

Computes realistic Amazon FBA fees based on product dimensions, weight,
selling price, and category. Covers fulfillment fees, referral fees,
monthly storage fees, variable closing fees, and returns processing fees.

Reference: Amazon Seller Central — Revenue Calculator / FBA fee schedule
effective January 15, 2024 and updated for 2025.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class SizeTier(str, Enum):
    """Amazon FBA product size tiers (US marketplace)."""
    SMALL_STANDARD = "Small Standard"
    LARGE_STANDARD = "Large Standard"
    SMALL_OVERSIZE = "Small Oversize"
    LARGE_OVERSIZE = "Large Oversize"
    SPECIAL_OVERSIZE = "Special Oversize"


# Fulfillment fee tables keyed by size tier.
# Each entry is a list of (max_weight_oz, fee) tuples.
# For standard tiers, weight thresholds are in *ounces*.
# For oversize tiers, the base fee plus per-lb surcharge model is used instead.
_SMALL_STANDARD_FEES: list[tuple[float, float]] = [
    (2, 3.22),
    (4, 3.40),
    (6, 3.58),
    (8, 3.77),
    (10, 3.92),
    (12, 4.09),
    (14, 4.25),
    (16, 4.42),  # 16 oz = 1 lb; small standard max is 15 oz but we cap here
]

_LARGE_STANDARD_FEES: list[tuple[float, float]] = [
    (4, 4.75),    # 0-4 oz
    (8, 5.14),    # 4-8 oz
    (12, 5.40),   # 8-12 oz
    (16, 5.69),   # 12-16 oz  (1 lb)
    (24, 6.10),   # 1-1.5 lb
    (32, 6.49),   # 1.5-2 lb
    (40, 7.05),   # 2-2.5 lb
    (48, 7.47),   # 2.5-3 lb
    # Above 3 lb: $7.47 + $0.42 per additional 0.5 lb (up to 20 lb)
]

# Oversize fulfillment fee parameters: (base_fee, per_lb_surcharge, first_lb_included)
_OVERSIZE_FEE_PARAMS: dict[SizeTier, tuple[float, float, float]] = {
    SizeTier.SMALL_OVERSIZE:   (9.73,  0.42, 1.0),
    SizeTier.LARGE_OVERSIZE:   (19.05, 0.42, 1.0),
    SizeTier.SPECIAL_OVERSIZE: (89.98, 0.83, 90.0),
}

# Monthly storage fees ($ per cubic foot)
_STORAGE_STANDARD = {"off_peak": 0.87, "peak": 2.40}   # Jan-Sep / Oct-Dec
_STORAGE_OVERSIZE = {"off_peak": 0.56, "peak": 1.40}

# Referral fee percentages by category slug.
# "min_referral" is the per-item minimum referral fee Amazon charges (usually $0.30).
_REFERRAL_FEES: dict[str, dict] = {
    "default":                     {"rate": 0.15, "min_referral": 0.30},
    "amazon_device_accessories":   {"rate": 0.45, "min_referral": 0.30},
    "electronics_accessories":     {"rate": 0.08, "min_referral": 0.30},
    "personal_computers":          {"rate": 0.06, "min_referral": 0.30},
    "consumer_electronics":        {"rate": 0.08, "min_referral": 0.30},
    "video_game_consoles":         {"rate": 0.08, "min_referral": 0.30},
    "grocery_and_gourmet":         {"rate": 0.08, "min_referral": 0.30},
    "health_and_personal_care":    {"rate": 0.08, "min_referral": 0.30},
    "clothing_and_accessories":    {"rate": 0.17, "min_referral": 0.30},
    "shoes_handbags_sunglasses":   {"rate": 0.15, "min_referral": 0.30},
    "jewelry":                     {"rate": 0.20, "min_referral": 0.30},
    "watches":                     {"rate": 0.15, "min_referral": 0.30},
    "furniture":                   {"rate": 0.15, "min_referral": 0.30},
    "appliances":                  {"rate": 0.15, "min_referral": 0.30},
    "automotive":                  {"rate": 0.12, "min_referral": 0.30},
    "baby_products":               {"rate": 0.08, "min_referral": 0.30},
    "books":                       {"rate": 0.15, "min_referral": 0.00},
    "music":                       {"rate": 0.15, "min_referral": 0.00},
    "dvd":                         {"rate": 0.15, "min_referral": 0.00},
    "video_games":                 {"rate": 0.15, "min_referral": 0.00},
    "software":                    {"rate": 0.15, "min_referral": 0.00},
    "sports_and_outdoors":         {"rate": 0.15, "min_referral": 0.30},
    "tools_and_home_improvement":  {"rate": 0.15, "min_referral": 0.30},
    "toys_and_games":              {"rate": 0.15, "min_referral": 0.30},
    "pet_supplies":                {"rate": 0.15, "min_referral": 0.30},
    "office_products":             {"rate": 0.15, "min_referral": 0.30},
    "beauty":                      {"rate": 0.08, "min_referral": 0.30},
    "industrial_and_scientific":   {"rate": 0.12, "min_referral": 0.30},
    "lawn_and_garden":             {"rate": 0.15, "min_referral": 0.30},
    "kitchen":                     {"rate": 0.15, "min_referral": 0.30},
    "home":                        {"rate": 0.15, "min_referral": 0.30},
}

# Categories that carry a variable closing fee ($1.80 per unit, media items only)
_MEDIA_CATEGORIES = {"books", "music", "dvd", "video_games", "software"}

# Categories that carry a returns processing fee
_RETURNS_PROCESSING_FEES: dict[str, float] = {
    "clothing_and_accessories":  2.00,
    "shoes_handbags_sunglasses": 3.00,
    "watches":                   3.00,
    "jewelry":                   3.00,
    "apparel":                   2.00,   # alias
}


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductDimensions:
    """Normalised product dimensions (longest side = length, etc.)."""
    length: float   # inches -- longest side
    width: float    # inches -- median side
    height: float   # inches -- shortest side
    weight_lb: float

    @property
    def weight_oz(self) -> float:
        return self.weight_lb * 16.0

    @property
    def girth_plus_length(self) -> float:
        """Length + girth, used for oversize classification."""
        return self.length + 2 * (self.width + self.height)

    @property
    def cubic_inches(self) -> float:
        return self.length * self.width * self.height

    @property
    def cubic_feet(self) -> float:
        return self.cubic_inches / 1728.0  # 12^3

    def as_dict(self) -> Dict:
        return {
            "length": round(self.length, 2),
            "width": round(self.width, 2),
            "height": round(self.height, 2),
            "weight_lb": round(self.weight_lb, 2),
            "cubic_ft": round(self.cubic_feet, 4),
        }


# ---------------------------------------------------------------------------
# FBA Fee Calculator
# ---------------------------------------------------------------------------

class FBAFeeCalculator:
    """
    Comprehensive Amazon FBA fee calculator for the US marketplace.

    Implements the 2024/2025 fee schedule including:
      - Size-tier classification
      - Fulfillment (pick & pack / shipping) fees
      - Monthly inventory storage fees (standard and peak season)
      - Referral fees by product category
      - Variable closing fees (media items)
      - Returns processing fees (apparel / shoes / jewelry)

    Usage::

        calc = FBAFeeCalculator()
        result = calc.calculate_all_fees(
            selling_price=29.99,
            length=10, width=8, height=3,
            weight_lb=1.2,
            category="default",
            monthly_units=100,
        )
        print(result)
    """

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _normalise_dims(
        length: float, width: float, height: float, weight_lb: float
    ) -> ProductDimensions:
        """Sort dimensions so length >= width >= height."""
        sides = sorted([length, width, height], reverse=True)
        return ProductDimensions(
            length=sides[0],
            width=sides[1],
            height=sides[2],
            weight_lb=weight_lb,
        )

    @staticmethod
    def _dimensional_weight_lb(length: float, width: float, height: float) -> float:
        """
        Calculate dimensional weight.

        Amazon uses a divisor of 139 for standard-size and oversize items
        to derive dimensional weight in pounds.
        """
        return (length * width * height) / 139.0

    @staticmethod
    def _shipping_weight_lb(dims: ProductDimensions, is_oversize: bool) -> float:
        """
        Determine the shipping weight used for fee calculation.

        For standard-size: greater of actual weight or dimensional weight,
        rounded up to the next whole ounce then converted to pounds.

        For oversize: greater of actual weight or dimensional weight,
        rounded up to the next whole pound.

        Amazon also adds a packaging weight allowance:
          - Standard: +0.25 lb
          - Oversize: +1.0 lb
        """
        dim_weight = (dims.length * dims.width * dims.height) / 139.0
        unit_weight = max(dims.weight_lb, dim_weight)

        if is_oversize:
            unit_weight += 1.0  # packaging weight
            return math.ceil(unit_weight)  # round up to whole lb
        else:
            unit_weight += 0.25  # packaging weight
            # Round up to nearest ounce, keep as lb for consistency
            weight_oz = unit_weight * 16.0
            weight_oz = math.ceil(weight_oz)
            return weight_oz / 16.0

    # ---- public API -------------------------------------------------------

    def determine_size_tier(
        self,
        length: float,
        width: float,
        height: float,
        weight_lb: float,
    ) -> str:
        """
        Classify a product into an Amazon FBA size tier.

        Parameters
        ----------
        length, width, height : float
            Product dimensions in inches (any order -- they will be sorted).
        weight_lb : float
            Product weight in pounds.

        Returns
        -------
        str
            One of the ``SizeTier`` values, e.g. ``"Large Standard"``.
        """
        dims = self._normalise_dims(length, width, height, weight_lb)
        return self._classify(dims).value

    def _classify(self, dims: ProductDimensions) -> SizeTier:
        """Internal classification returning the enum member."""
        l, w, h, wt = dims.length, dims.width, dims.height, dims.weight_lb
        wt_oz = dims.weight_oz
        girth_len = dims.girth_plus_length

        # --- Small Standard ---
        # Max 15 oz, max dimensions 15" x 12" x 0.75"
        if wt_oz <= 16 and l <= 15 and w <= 12 and h <= 0.75:
            return SizeTier.SMALL_STANDARD

        # --- Large Standard ---
        # Max 20 lb, max dimensions 18" x 14" x 8"
        if wt <= 20 and l <= 18 and w <= 14 and h <= 8:
            return SizeTier.LARGE_STANDARD

        # --- Small Oversize ---
        # Max 70 lb, max longest side 60", max median side 30",
        # length + girth <= 130"
        if wt <= 70 and l <= 60 and w <= 30 and girth_len <= 130:
            return SizeTier.SMALL_OVERSIZE

        # --- Large Oversize ---
        # Max 150 lb, max longest side 108", max length+girth 165"
        if wt <= 150 and l <= 108 and girth_len <= 165:
            return SizeTier.LARGE_OVERSIZE

        # --- Special Oversize ---
        return SizeTier.SPECIAL_OVERSIZE

    def calculate_fulfillment_fee(
        self,
        length: float,
        width: float,
        height: float,
        weight_lb: float,
    ) -> float:
        """
        Calculate the FBA fulfillment fee (pick, pack, and ship).

        Parameters
        ----------
        length, width, height : float
            Product dimensions in inches.
        weight_lb : float
            Product weight in pounds.

        Returns
        -------
        float
            Fulfillment fee in USD, rounded to two decimal places.
        """
        dims = self._normalise_dims(length, width, height, weight_lb)
        tier = self._classify(dims)
        is_oversize = tier not in (SizeTier.SMALL_STANDARD, SizeTier.LARGE_STANDARD)
        ship_wt = self._shipping_weight_lb(dims, is_oversize)
        ship_wt_oz = ship_wt * 16.0

        if tier == SizeTier.SMALL_STANDARD:
            return self._lookup_standard_fee(_SMALL_STANDARD_FEES, ship_wt_oz)

        if tier == SizeTier.LARGE_STANDARD:
            return self._calc_large_standard_fee(ship_wt_oz)

        # Oversize tiers
        base_fee, per_lb, first_lb = _OVERSIZE_FEE_PARAMS[tier]
        extra_lb = max(0.0, ship_wt - first_lb)
        fee = base_fee + per_lb * math.ceil(extra_lb)
        return round(fee, 2)

    # ---- fulfillment fee helpers ------------------------------------------

    @staticmethod
    def _lookup_standard_fee(
        table: list[tuple[float, float]], weight_oz: float
    ) -> float:
        """Look up the fee from a tiered weight-based table (ounces)."""
        for max_oz, fee in table:
            if weight_oz <= max_oz:
                return fee
        # Fallback: return the last tier fee
        return table[-1][1]

    @staticmethod
    def _calc_large_standard_fee(weight_oz: float) -> float:
        """
        Calculate large-standard fulfillment fee.

        Uses the tiered table up to 3 lb (48 oz), then adds $0.42
        per additional half-pound above 3 lb, up to the 20 lb maximum.
        """
        for max_oz, fee in _LARGE_STANDARD_FEES:
            if weight_oz <= max_oz:
                return fee

        # Above 3 lb (48 oz): base of $7.47 + $0.42 per 0.5 lb increment
        extra_oz = weight_oz - 48.0
        extra_half_lbs = math.ceil(extra_oz / 8.0)  # 0.5 lb = 8 oz
        fee = 7.47 + 0.42 * extra_half_lbs
        return round(fee, 2)

    # ---- storage fees -----------------------------------------------------

    def calculate_storage_fee(
        self,
        length: float,
        width: float,
        height: float,
        units: int = 1,
        months: int = 1,
        peak_season: bool = False,
    ) -> float:
        """
        Calculate monthly inventory storage fees.

        Parameters
        ----------
        length, width, height : float
            Product dimensions in inches.
        units : int
            Number of units stored.
        months : int
            Number of months to estimate.
        peak_season : bool
            ``True`` for Oct-Dec (Q4) peak-season rates; ``False`` for
            Jan-Sep off-peak rates.

        Returns
        -------
        float
            Total storage cost in USD for the given units and months.
        """
        dims = self._normalise_dims(length, width, height, weight_lb=0)
        tier = self._classify(
            self._normalise_dims(length, width, height, weight_lb=0)
        )
        is_oversize = tier not in (SizeTier.SMALL_STANDARD, SizeTier.LARGE_STANDARD)

        cubic_ft = dims.cubic_feet
        rate_table = _STORAGE_OVERSIZE if is_oversize else _STORAGE_STANDARD
        rate = rate_table["peak"] if peak_season else rate_table["off_peak"]

        total = rate * cubic_ft * units * months
        return round(total, 2)

    # ---- referral fees ----------------------------------------------------

    def calculate_referral_fee(
        self,
        selling_price: float,
        category: str = "default",
    ) -> float:
        """
        Calculate the Amazon referral fee.

        Parameters
        ----------
        selling_price : float
            Item selling price in USD.
        category : str
            Product category slug (see ``_REFERRAL_FEES`` keys).

        Returns
        -------
        float
            Referral fee in USD, rounded to two decimal places.
        """
        cat_info = _REFERRAL_FEES.get(category, _REFERRAL_FEES["default"])
        rate = cat_info["rate"]
        min_ref = cat_info["min_referral"]

        # Category-specific tiered rates
        fee = self._tiered_referral(selling_price, category, rate)
        return round(max(fee, min_ref), 2)

    @staticmethod
    def _tiered_referral(
        price: float, category: str, default_rate: float
    ) -> float:
        """
        Handle categories with tiered referral rates based on price.

        Amazon applies different percentages to different price portions
        for certain categories.
        """
        # Clothing: 17% for items > $15, 5% for items <= $15
        if category == "clothing_and_accessories":
            if price <= 15.0:
                return price * 0.05
            return price * 0.17

        # Grocery / health / beauty / baby: 8% for items <= threshold, 15% above
        if category in ("grocery_and_gourmet", "health_and_personal_care", "beauty"):
            threshold = 10.0 if category != "grocery_and_gourmet" else 15.0
            if price <= threshold:
                return price * 0.08
            return price * 0.15

        if category == "baby_products":
            if price <= 10.0:
                return price * 0.08
            return price * 0.15

        # Jewelry: 20% on first $250, 5% on remainder
        if category == "jewelry":
            if price <= 250.0:
                return price * 0.20
            return 250.0 * 0.20 + (price - 250.0) * 0.05

        # Watches: 15% on first $100, 3% on remainder
        if category == "watches":
            if price <= 100.0:
                return price * 0.15
            return 100.0 * 0.15 + (price - 100.0) * 0.03

        # Appliances: 15% on first $300, 8% on remainder
        if category == "appliances":
            if price <= 300.0:
                return price * 0.15
            return 300.0 * 0.15 + (price - 300.0) * 0.08

        # Default: flat rate
        return price * default_rate

    # ---- variable closing fee ---------------------------------------------

    @staticmethod
    def _variable_closing_fee(category: str) -> float:
        """
        Return the variable closing fee for media items.

        Amazon charges $1.80 per unit for books, music, DVDs, video games,
        and software (BMVD categories).
        """
        if category in _MEDIA_CATEGORIES:
            return 1.80
        return 0.0

    # ---- returns processing fee -------------------------------------------

    @staticmethod
    def _returns_processing_fee(category: str) -> float:
        """
        Return the per-unit returns processing fee, if applicable.

        Most categories have free returns processing. Apparel, shoes,
        watches, and jewelry incur a fee.
        """
        return _RETURNS_PROCESSING_FEES.get(category, 0.0)

    # ---- comprehensive calculation ----------------------------------------

    def calculate_all_fees(
        self,
        selling_price: float,
        length: float,
        width: float,
        height: float,
        weight_lb: float,
        category: str = "default",
        monthly_units: int = 100,
    ) -> Dict:
        """
        Calculate every FBA fee line item for a product.

        Parameters
        ----------
        selling_price : float
            Item selling price in USD.
        length, width, height : float
            Product dimensions in inches (any order).
        weight_lb : float
            Product weight in pounds.
        category : str
            Category slug for referral / returns fee calculation.
        monthly_units : int
            Estimated monthly sales volume (used to amortise storage).

        Returns
        -------
        dict
            Comprehensive fee breakdown::

                {
                    "size_tier": "Large Standard",
                    "fulfillment_fee": 5.40,
                    "referral_fee": 4.50,
                    "referral_fee_pct": 15.0,
                    "monthly_storage_fee": 0.08,
                    "monthly_storage_fee_peak": 0.22,
                    "variable_closing_fee": 0.0,
                    "returns_processing_fee": 0.0,
                    "total_fba_fees_per_unit": 9.98,
                    "total_fba_fees_per_unit_peak": 10.12,
                    "product_dimensions": {
                        "length": ..., "width": ..., "height": ...,
                        "weight_lb": ..., "cubic_ft": ...
                    },
                }
        """
        dims = self._normalise_dims(length, width, height, weight_lb)
        tier = self._classify(dims)

        # Individual fee components
        fulfillment_fee = self.calculate_fulfillment_fee(
            length, width, height, weight_lb
        )

        referral_fee = self.calculate_referral_fee(selling_price, category)

        # Effective referral rate (percentage of selling price actually charged)
        referral_fee_pct = round(
            (referral_fee / selling_price * 100) if selling_price > 0 else 0.0, 2
        )

        # Per-unit monthly storage (1 unit for 1 month)
        storage_off = self.calculate_storage_fee(
            length, width, height, units=1, months=1, peak_season=False
        )
        storage_peak = self.calculate_storage_fee(
            length, width, height, units=1, months=1, peak_season=True
        )

        closing_fee = self._variable_closing_fee(category)
        returns_fee = self._returns_processing_fee(category)

        # Totals
        total_off = round(
            fulfillment_fee + referral_fee + storage_off + closing_fee + returns_fee,
            2,
        )
        total_peak = round(
            fulfillment_fee + referral_fee + storage_peak + closing_fee + returns_fee,
            2,
        )

        return {
            "size_tier": tier.value,
            "fulfillment_fee": fulfillment_fee,
            "referral_fee": referral_fee,
            "referral_fee_pct": referral_fee_pct,
            "monthly_storage_fee": storage_off,
            "monthly_storage_fee_peak": storage_peak,
            "variable_closing_fee": closing_fee,
            "returns_processing_fee": returns_fee,
            "total_fba_fees_per_unit": total_off,
            "total_fba_fees_per_unit_peak": total_peak,
            "product_dimensions": dims.as_dict(),
        }

    # ---- convenience / bulk -----------------------------------------------

    def estimate_profit(
        self,
        selling_price: float,
        product_cost: float,
        length: float,
        width: float,
        height: float,
        weight_lb: float,
        category: str = "default",
        monthly_units: int = 100,
        peak_season: bool = False,
    ) -> Dict:
        """
        Quick profit estimate combining cost-of-goods with FBA fees.

        Parameters
        ----------
        selling_price : float
            Retail selling price in USD.
        product_cost : float
            Landed cost per unit (product + shipping to Amazon) in USD.
        length, width, height : float
            Product dimensions in inches.
        weight_lb : float
            Product weight in pounds.
        category : str
            Category slug.
        monthly_units : int
            Expected monthly sales volume.
        peak_season : bool
            Whether to use Q4 peak storage rates.

        Returns
        -------
        dict
            Profit breakdown with ``net_profit``, ``margin_pct``, and
            ``roi_pct`` keys in addition to the full fee breakdown.
        """
        fees = self.calculate_all_fees(
            selling_price=selling_price,
            length=length,
            width=width,
            height=height,
            weight_lb=weight_lb,
            category=category,
            monthly_units=monthly_units,
        )

        total_fees = (
            fees["total_fba_fees_per_unit_peak"]
            if peak_season
            else fees["total_fba_fees_per_unit"]
        )

        net_profit = round(selling_price - product_cost - total_fees, 2)
        margin_pct = round(
            (net_profit / selling_price * 100) if selling_price > 0 else 0.0, 2
        )
        roi_pct = round(
            (net_profit / product_cost * 100) if product_cost > 0 else 0.0, 2
        )

        return {
            **fees,
            "product_cost": product_cost,
            "total_fees": total_fees,
            "net_profit": net_profit,
            "margin_pct": margin_pct,
            "roi_pct": roi_pct,
        }


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

# Pre-instantiated calculator for quick imports
calculator = FBAFeeCalculator()


def calculate_fba_fees(
    selling_price: float,
    length: float,
    width: float,
    height: float,
    weight_lb: float,
    category: str = "default",
    monthly_units: int = 100,
) -> Dict:
    """Module-level shortcut for ``FBAFeeCalculator.calculate_all_fees``."""
    return calculator.calculate_all_fees(
        selling_price=selling_price,
        length=length,
        width=width,
        height=height,
        weight_lb=weight_lb,
        category=category,
        monthly_units=monthly_units,
    )


# ---------------------------------------------------------------------------
# Quick self-test when run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    calc = FBAFeeCalculator()

    print("=" * 65)
    print("FBA Fee Calculator -- Quick Test")
    print("=" * 65)

    # Test 1: Small standard item
    result = calc.calculate_all_fees(
        selling_price=14.99,
        length=6, width=4, height=0.5,
        weight_lb=0.25,
        category="default",
    )
    print(f"\n[Small Standard] $14.99 item, 6x4x0.5 in, 4 oz")
    print(f"  Size tier:        {result['size_tier']}")
    print(f"  Fulfillment fee:  ${result['fulfillment_fee']:.2f}")
    print(f"  Referral fee:     ${result['referral_fee']:.2f} ({result['referral_fee_pct']}%)")
    print(f"  Storage (std):    ${result['monthly_storage_fee']:.2f}")
    print(f"  Storage (peak):   ${result['monthly_storage_fee_peak']:.2f}")
    print(f"  Total per unit:   ${result['total_fba_fees_per_unit']:.2f}")

    # Test 2: Large standard item
    result = calc.calculate_all_fees(
        selling_price=29.99,
        length=10, width=8, height=3,
        weight_lb=1.2,
        category="default",
    )
    print(f"\n[Large Standard] $29.99 item, 10x8x3 in, 1.2 lb")
    print(f"  Size tier:        {result['size_tier']}")
    print(f"  Fulfillment fee:  ${result['fulfillment_fee']:.2f}")
    print(f"  Referral fee:     ${result['referral_fee']:.2f} ({result['referral_fee_pct']}%)")
    print(f"  Storage (std):    ${result['monthly_storage_fee']:.2f}")
    print(f"  Total per unit:   ${result['total_fba_fees_per_unit']:.2f}")

    # Test 3: Oversize item
    result = calc.calculate_all_fees(
        selling_price=79.99,
        length=30, width=20, height=15,
        weight_lb=12.0,
        category="sports_and_outdoors",
    )
    print(f"\n[Small Oversize] $79.99 item, 30x20x15 in, 12 lb")
    print(f"  Size tier:        {result['size_tier']}")
    print(f"  Fulfillment fee:  ${result['fulfillment_fee']:.2f}")
    print(f"  Referral fee:     ${result['referral_fee']:.2f} ({result['referral_fee_pct']}%)")
    print(f"  Storage (std):    ${result['monthly_storage_fee']:.2f}")
    print(f"  Total per unit:   ${result['total_fba_fees_per_unit']:.2f}")

    # Test 4: Clothing item
    result = calc.calculate_all_fees(
        selling_price=34.99,
        length=12, width=10, height=2,
        weight_lb=0.8,
        category="clothing_and_accessories",
    )
    print(f"\n[Large Standard / Clothing] $34.99 item, 12x10x2 in, 0.8 lb")
    print(f"  Size tier:        {result['size_tier']}")
    print(f"  Fulfillment fee:  ${result['fulfillment_fee']:.2f}")
    print(f"  Referral fee:     ${result['referral_fee']:.2f} ({result['referral_fee_pct']}%)")
    print(f"  Returns fee:      ${result['returns_processing_fee']:.2f}")
    print(f"  Total per unit:   ${result['total_fba_fees_per_unit']:.2f}")

    # Test 5: Profit estimate
    profit = calc.estimate_profit(
        selling_price=29.99,
        product_cost=8.00,
        length=10, width=8, height=3,
        weight_lb=1.2,
        category="default",
        monthly_units=200,
    )
    print(f"\n[Profit Estimate] $29.99 item, cost $8.00")
    print(f"  Total FBA fees:   ${profit['total_fees']:.2f}")
    print(f"  Net profit:       ${profit['net_profit']:.2f}")
    print(f"  Margin:           {profit['margin_pct']}%")
    print(f"  ROI:              {profit['roi_pct']}%")

    print("\n" + "=" * 65)
