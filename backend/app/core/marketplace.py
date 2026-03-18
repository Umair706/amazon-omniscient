"""Marketplace configuration registry for multi-marketplace support.

Each marketplace defines domain, currency, fees, duty profiles, shipping
routes, and BSR regression scaling factors needed by downstream services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class DutyProfile:
    """Import duty and tariff configuration for a marketplace."""

    name: str
    default_duty_rate: float
    category_rates: Dict[str, float]
    # Tariff surcharge (e.g. Section 301 for US, none for AU under ChAFTA)
    surcharge_name: str | None = None
    surcharge_default_rate: float = 0.0
    surcharge_category_rates: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ShippingProfile:
    """Shipping cost estimates from origin (China) to marketplace country."""

    route_name: str  # e.g. "China → US", "China → AU"
    sea_lcl_per_unit: float
    sea_fcl_20ft_per_unit: float
    sea_fcl_40ft_per_unit: float
    air_standard_per_unit: float
    air_express_per_unit: float
    # Transit times in days
    sea_transit_min: int
    sea_transit_max: int
    air_transit_min: int
    air_transit_max: int


@dataclass(frozen=True)
class MarketplaceConfig:
    """Full configuration for a single Amazon marketplace."""

    code: str  # e.g. "US", "AU"
    name: str  # e.g. "United States", "Australia"
    domain: str  # e.g. "amazon.com", "amazon.com.au"
    marketplace_id: str  # SP-API marketplace ID
    currency: str  # e.g. "USD", "AUD"
    currency_symbol: str  # e.g. "$", "A$"
    locale: str  # browser locale for scraping
    timezone: str  # IANA timezone
    sp_api_endpoint: str  # SP-API regional endpoint base URL

    # Fee structure
    referral_fee_pct: float  # default referral fee (e.g. 0.15)
    fba_base_fee: float  # base fulfillment fee in local currency
    storage_fee_monthly: float  # per-cubic-foot storage in local currency

    # Tax
    gst_rate: float  # GST/VAT rate (0.0 for US, 0.10 for AU)

    # Import profiles
    duty_profile: DutyProfile
    shipping_profile: ShippingProfile

    # BSR regression scaling: AU market is ~8% of US volume
    # A_au = A_us * bsr_market_scale, same B exponent
    bsr_market_scale: float = 1.0


# ---------------------------------------------------------------------------
# Duty profiles
# ---------------------------------------------------------------------------

_US_DUTY_PROFILE = DutyProfile(
    name="US HTS + Section 301",
    default_duty_rate=0.035,
    category_rates={
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
    },
    surcharge_name="Section 301",
    surcharge_default_rate=0.25,
    surcharge_category_rates={
        "list_1": 0.25,
        "list_2": 0.25,
        "list_3": 0.25,
        "list_4a": 0.075,
        "exempt": 0.0,
    },
)

_AU_DUTY_PROFILE = DutyProfile(
    name="AU Customs + ChAFTA",
    # ChAFTA (China-Australia Free Trade Agreement) reduced rates
    # Most consumer goods 0-5% under ChAFTA preferential rates
    default_duty_rate=0.05,
    category_rates={
        "electronics": 0.0,
        "toys": 0.0,
        "kitchen": 0.0,
        "home": 0.05,
        "beauty": 0.0,
        "health": 0.0,
        "sports": 0.05,
        "clothing": 0.05,
        "shoes": 0.05,
        "bags": 0.05,
        "jewelry": 0.05,
        "pet": 0.0,
        "garden": 0.0,
        "office": 0.0,
        "automotive": 0.05,
    },
    # No Section 301-equivalent surcharge for AU
    surcharge_name=None,
    surcharge_default_rate=0.0,
    surcharge_category_rates={},
)

# ---------------------------------------------------------------------------
# Shipping profiles
# ---------------------------------------------------------------------------

_US_SHIPPING = ShippingProfile(
    route_name="China → US (West Coast)",
    sea_lcl_per_unit=1.50,
    sea_fcl_20ft_per_unit=0.80,
    sea_fcl_40ft_per_unit=0.60,
    air_standard_per_unit=4.50,
    air_express_per_unit=8.00,
    sea_transit_min=25,
    sea_transit_max=40,
    air_transit_min=3,
    air_transit_max=14,
)

_AU_SHIPPING = ShippingProfile(
    route_name="China → Australia (Sydney/Melbourne)",
    sea_lcl_per_unit=1.80,
    sea_fcl_20ft_per_unit=1.00,
    sea_fcl_40ft_per_unit=0.75,
    air_standard_per_unit=5.50,
    air_express_per_unit=9.50,
    sea_transit_min=18,
    sea_transit_max=30,
    air_transit_min=3,
    air_transit_max=10,
)

# ---------------------------------------------------------------------------
# Marketplace registry
# ---------------------------------------------------------------------------

MARKETPLACES: Dict[str, MarketplaceConfig] = {
    "US": MarketplaceConfig(
        code="US",
        name="United States",
        domain="amazon.com",
        marketplace_id="ATVPDKIKX0DER",
        currency="USD",
        currency_symbol="$",
        locale="en-US",
        timezone="America/New_York",
        sp_api_endpoint="https://sellingpartnerapi-na.amazon.com",
        referral_fee_pct=0.15,
        fba_base_fee=3.22,
        storage_fee_monthly=0.87,
        gst_rate=0.0,
        duty_profile=_US_DUTY_PROFILE,
        shipping_profile=_US_SHIPPING,
        bsr_market_scale=1.0,
    ),
    "AU": MarketplaceConfig(
        code="AU",
        name="Australia",
        domain="amazon.com.au",
        marketplace_id="A39IBJ37TRP1C6",
        currency="AUD",
        currency_symbol="A$",
        locale="en-AU",
        timezone="Australia/Sydney",
        sp_api_endpoint="https://sellingpartnerapi-fe.amazon.com",
        referral_fee_pct=0.15,
        fba_base_fee=4.50,  # AUD — AU FBA base fee is higher
        storage_fee_monthly=1.10,  # AUD per cubic foot
        gst_rate=0.10,  # 10% GST
        duty_profile=_AU_DUTY_PROFILE,
        shipping_profile=_AU_SHIPPING,
        bsr_market_scale=0.08,  # AU market ~8% of US volume
    ),
}


def get_marketplace_prompt_context(code: str = "US") -> str:
    """Return LLM prompt context for marketplace-specific analysis.

    Returns an empty string for US (default), or a paragraph of context
    for non-US marketplaces that should be prepended to LLM prompts.
    """
    if code.strip().upper() == "US":
        return ""

    mp = MARKETPLACES.get(code.strip().upper())
    if not mp:
        return ""

    if mp.code == "AU":
        return (
            f"IMPORTANT MARKETPLACE CONTEXT: This analysis is for Amazon {mp.name} "
            f"(amazon.com.au), NOT the US marketplace. Key differences:\n"
            f"- All prices and financial figures are in {mp.currency} ({mp.currency_symbol})\n"
            f"- The AU market is approximately 8% the size of the US market\n"
            f"- {mp.gst_rate*100:.0f}% GST applies to all sales (included in selling price)\n"
            f"- Fewer sellers and lower review counts are normal — 50-200 reviews is considered "
            f"'high' in AU (vs 1000+ in US)\n"
            f"- Average monthly sales per seller are much lower than US benchmarks\n"
            f"- Import duties use ChAFTA (China-Australia FTA) reduced rates (0-5% vs "
            f"US Section 301 tariffs of 7.5-25%)\n"
            f"- Shipping routes are China → Australia (shorter transit than China → US West Coast)\n"
            f"- PPC costs tend to be lower but conversion rates vary\n"
            f"- Brand Registry and Vine are available but with smaller participant pools\n"
            f"- Consumer preferences differ: eco-consciousness, outdoor lifestyle, "
            f"local/native products valued\n"
            f"- Marketing channels: Instagram and TikTok popular; Facebook Groups "
            f"effective for niche products\n\n"
            f"Adjust all benchmarks, thresholds, and recommendations for the AU market context.\n\n"
        )

    return f"Note: This analysis is for Amazon {mp.name} ({mp.domain}).\n\n"


def get_marketplace(code: str = "US") -> MarketplaceConfig:
    """Look up a marketplace by code (case-insensitive).

    Raises ``KeyError`` if the marketplace code is not registered.
    """
    key = code.strip().upper()
    if key not in MARKETPLACES:
        raise KeyError(
            f"Unknown marketplace '{code}'. "
            f"Available: {', '.join(MARKETPLACES.keys())}"
        )
    return MARKETPLACES[key]
