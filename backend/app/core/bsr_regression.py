"""BSR-to-sales regression model for estimating Amazon product sales volume."""


# AU market is approximately 8% of US volume.
# A_au = A_us * 0.08, same B exponent (power law shape is preserved).
_AU_MARKET_SCALE = 0.08


class BSRSalesEstimator:
    """
    Converts Best Sellers Rank (BSR) to estimated monthly unit sales.

    Uses a power law regression model: sales = A * BSR^(-B)
    Where A and B are category-specific constants calibrated from historical data.

    Supports multiple marketplaces. For AU, US coefficients are scaled by
    the market size ratio (~8% of US volume).
    """

    # US category models (fitted from historical data)
    US_CATEGORY_MODELS: dict[str, tuple[float, float]] = {
        "Home & Kitchen":       (52000, 0.80),
        "Kitchen & Dining":     (48000, 0.78),
        "Sports & Outdoors":    (43000, 0.79),
        "Tools & Home Improvement": (38000, 0.77),
        "Health & Household":   (60000, 0.82),
        "Beauty & Personal Care": (55000, 0.81),
        "Baby":                 (35000, 0.76),
        "Pet Supplies":         (40000, 0.78),
        "Patio, Lawn & Garden": (30000, 0.75),
        "Office Products":      (42000, 0.79),
        "Toys & Games":         (50000, 0.80),
        "Automotive":           (35000, 0.76),
        "Arts, Crafts & Sewing": (28000, 0.74),
        "Industrial & Scientific": (25000, 0.73),
        "Grocery & Gourmet Food": (45000, 0.79),
        "Electronics":          (55000, 0.81),
        "Cell Phones & Accessories": (50000, 0.80),
        "Clothing, Shoes & Jewelry": (65000, 0.83),
    }

    # AU models: same B exponent, A scaled by market size ratio
    AU_CATEGORY_MODELS: dict[str, tuple[float, float]] = {
        cat: (round(a * _AU_MARKET_SCALE), b)
        for cat, (a, b) in US_CATEGORY_MODELS.items()
    }

    US_DEFAULT_MODEL: tuple[float, float] = (45000, 0.79)
    AU_DEFAULT_MODEL: tuple[float, float] = (round(45000 * _AU_MARKET_SCALE), 0.79)

    # Keep CATEGORY_MODELS as alias for backward compatibility
    CATEGORY_MODELS = US_CATEGORY_MODELS
    DEFAULT_MODEL = US_DEFAULT_MODEL

    def __init__(self, marketplace: str = "US"):
        self._marketplace = marketplace.strip().upper()

    def _get_model(self, category: str) -> tuple[float, float]:
        """Look up (A, B) coefficients for a category, marketplace-aware."""
        if self._marketplace == "AU":
            models = self.AU_CATEGORY_MODELS
            default = self.AU_DEFAULT_MODEL
        else:
            models = self.US_CATEGORY_MODELS
            default = self.US_DEFAULT_MODEL

        if category in models:
            return models[category]
        # Try partial match
        category_lower = category.lower()
        for key, model in models.items():
            if key.lower() in category_lower or category_lower in key.lower():
                return model
        return default

    # Sub-category BSR typically runs ~10x lower than main-category BSR
    # for the same product.  The CATEGORY_MODELS coefficients are calibrated
    # against main-category BSR, so feeding a sub-category rank directly
    # would massively overestimate sales.  This multiplier converts a
    # sub-category BSR into an approximate main-category-equivalent BSR.
    SUBCATEGORY_SCALING_FACTOR: float = 10.0

    def estimate_monthly_sales(
        self,
        bsr: int,
        category: str,
        *,
        is_subcategory: bool = False,
    ) -> int:
        """
        Estimate monthly unit sales from BSR.

        Args:
            bsr: Current Best Sellers Rank
            category: Amazon category name
            is_subcategory: If True, *bsr* is a sub-category rank and will be
                scaled up before applying the main-category regression model.

        Returns:
            Estimated monthly unit sales (clamped 1-100000)
        """
        if bsr <= 0:
            return 0
        effective_bsr = bsr
        if is_subcategory:
            effective_bsr = round(bsr * self.SUBCATEGORY_SCALING_FACTOR)
        a, b = self._get_model(category)
        sales = a * (effective_bsr ** (-b))
        return max(1, min(100000, round(sales)))

    def estimate_weekly_sales(
        self, bsr: int, category: str, *, is_subcategory: bool = False,
    ) -> int:
        """Estimate weekly unit sales from BSR."""
        monthly = self.estimate_monthly_sales(bsr, category, is_subcategory=is_subcategory)
        return max(1, round(monthly / 4.33))

    def estimate_daily_sales(
        self, bsr: int, category: str, *, is_subcategory: bool = False,
    ) -> int:
        """Estimate daily unit sales from BSR."""
        monthly = self.estimate_monthly_sales(bsr, category, is_subcategory=is_subcategory)
        return max(0, round(monthly / 30))

    def estimate_sales_at_rank(
        self,
        organic_rank: int,
        niche_avg_bsr: int,
        category: str,
    ) -> int:
        """
        Estimate monthly sales for a product at a given organic search rank.

        Maps organic rank to approximate BSR using multipliers:
            Rank 1-3:   BSR = niche_avg_bsr * 0.3  (top performers)
            Rank 4-10:  BSR = niche_avg_bsr * 0.8
            Rank 11-20: BSR = niche_avg_bsr * 2.0  (page 2)
            Rank 21-48: BSR = niche_avg_bsr * 5.0
            Rank 49+:   BSR = niche_avg_bsr * 10.0
        """
        if niche_avg_bsr <= 0:
            return 0

        if organic_rank <= 3:
            estimated_bsr = niche_avg_bsr * 0.3
        elif organic_rank <= 10:
            estimated_bsr = niche_avg_bsr * 0.8
        elif organic_rank <= 20:
            estimated_bsr = niche_avg_bsr * 2.0
        elif organic_rank <= 48:
            estimated_bsr = niche_avg_bsr * 5.0
        else:
            estimated_bsr = niche_avg_bsr * 10.0

        return self.estimate_monthly_sales(max(1, round(estimated_bsr)), category)


# Singleton instance
bsr_estimator = BSRSalesEstimator()
