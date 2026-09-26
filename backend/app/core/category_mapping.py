"""Map Amazon's BSR category display names onto the duty and FBA fee vocabularies used internally."""

# WHY: SupplierService duty tables and FBAFeeCalculator referral tables use two different slug sets.
# (duty_slug, fee_slug) per Amazon top-level category name as it appears in "#123 in Home & Kitchen".
_CATEGORY_SLUGS: dict[str, tuple[str, str]] = {
    "home & kitchen": ("home", "home"),
    "kitchen & dining": ("kitchen", "kitchen"),
    "sports & outdoors": ("sports", "sports_and_outdoors"),
    "tools & home improvement": ("home", "tools_and_home_improvement"),
    "health & household": ("health", "health_and_personal_care"),
    "beauty & personal care": ("beauty", "beauty"),
    "baby": ("default", "baby_products"),
    "baby products": ("default", "baby_products"),
    "pet supplies": ("pet", "pet_supplies"),
    "patio, lawn & garden": ("garden", "lawn_and_garden"),
    "office products": ("office", "office_products"),
    "toys & games": ("toys", "toys_and_games"),
    "automotive": ("automotive", "automotive"),
    "electronics": ("electronics", "consumer_electronics"),
    "cell phones & accessories": ("electronics", "electronics_accessories"),
    "clothing, shoes & jewelry": ("clothing", "clothing_and_accessories"),
    "industrial & scientific": ("default", "industrial_and_scientific"),
    "grocery & gourmet food": ("default", "grocery_and_gourmet"),
}

DEFAULT_SLUGS = ("default", "default")


def category_slugs(bsr_category: str | None) -> tuple[str, str]:
    """Return (duty_slug, fee_slug) for an Amazon category name; ("default","default") if unknown."""
    if not bsr_category:
        return DEFAULT_SLUGS
    return _CATEGORY_SLUGS.get(bsr_category.strip().lower(), DEFAULT_SLUGS)
