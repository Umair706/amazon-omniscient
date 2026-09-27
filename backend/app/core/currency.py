"""Convert supplier costs (quoted in USD) into a marketplace's currency.

Suppliers on 1688/Alibaba quote in USD, but a listing on Amazon AU sells in AUD.
The landed cost must be in the same currency as the sale price before we compute
a margin, or the margin is nonsense (a US$8 cost read as A$8 understates COGS).

These are fixed, approximate rates — not live FX. They are good enough to stop
the currency mismatch, and any result that used one is flagged as a data gap so
a seller knows to sanity-check it against the real rate on the day.
"""

from __future__ import annotations

# Units of the marketplace currency per 1 USD. US is 1.0 by definition.
# AU rate is an approximate USD->AUD (update if it drifts far).
USD_TO_MARKETPLACE_RATE: dict[str, float] = {
    "US": 1.0,
    "AU": 1.52,
}


def usd_to_marketplace_rate(marketplace: str) -> float:
    """Return the units-of-marketplace-currency per USD (1.0 for US/unknown)."""
    return USD_TO_MARKETPLACE_RATE.get((marketplace or "US").strip().upper(), 1.0)


def convert_from_usd(amount_usd: float, marketplace: str) -> float:
    """Convert a USD amount into the marketplace's currency."""
    return amount_usd * usd_to_marketplace_rate(marketplace)


def convert_to_usd(amount_marketplace: float, marketplace: str) -> float:
    """Convert an amount in the marketplace's currency back into USD."""
    rate = usd_to_marketplace_rate(marketplace)
    return amount_marketplace / rate if rate else amount_marketplace


def is_converted_marketplace(marketplace: str) -> bool:
    """True when the marketplace uses a non-USD currency, so a rate was applied."""
    return usd_to_marketplace_rate(marketplace) != 1.0
