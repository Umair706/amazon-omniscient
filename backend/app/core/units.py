"""Unit conversions for values scraped from product pages."""

import re

POUNDS_PER_OUNCE = 1 / 16
POUNDS_PER_KILOGRAM = 2.20462
POUNDS_PER_GRAM = POUNDS_PER_KILOGRAM / 1000

# Unit words as Amazon writes them, mapped to "how many pounds is one of these".
_POUNDS_PER_UNIT = [
    (("kilograms", "kilogram", "kg"), POUNDS_PER_KILOGRAM),
    (("grams", "gram", "g"), POUNDS_PER_GRAM),
    (("ounces", "ounce", "oz"), POUNDS_PER_OUNCE),
    (("pounds", "pound", "lbs", "lb"), 1.0),
]

_NUMBER_THEN_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]*)")


def parse_weight_lb(text: str | float | int | None) -> float | None:
    """Convert a weight like "12 ounces" or "0.5 kg" to pounds.

    A bare number is taken to be pounds already. Returns None when the text
    has no number or its unit is not a weight unit.
    """
    if isinstance(text, (int, float)):
        return float(text)
    if not text:
        return None
    # WHY: commas are thousands separators here ("1,200 g"), never decimals.
    match = _NUMBER_THEN_UNIT.search(text.replace(",", ""))
    if match is None:
        return None
    amount = float(match.group(1))
    unit = match.group(2).lower()
    if not unit:
        return amount
    return _to_pounds(amount, unit)


def _to_pounds(amount: float, unit: str) -> float | None:
    """Multiply amount by the pound factor for unit. None for an unknown unit."""
    for unit_words, pounds_per_unit in _POUNDS_PER_UNIT:
        if unit in unit_words:
            return round(amount * pounds_per_unit, 4)
    return None
