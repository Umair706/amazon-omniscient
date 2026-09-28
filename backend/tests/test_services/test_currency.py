"""USD-to-marketplace currency conversion for supplier costs."""

from app.core.currency import (
    convert_from_usd,
    convert_to_usd,
    is_converted_marketplace,
    usd_to_marketplace_rate,
)


def test_us_is_identity():
    assert usd_to_marketplace_rate("US") == 1.0
    assert convert_from_usd(8.0, "US") == 8.0
    assert convert_to_usd(8.0, "US") == 8.0
    assert is_converted_marketplace("US") is False


def test_au_applies_a_rate_above_one():
    # A US$8 landed cost should be more than 8 in AUD.
    assert usd_to_marketplace_rate("AU") > 1.0
    assert convert_from_usd(8.0, "AU") > 8.0
    assert is_converted_marketplace("AU") is True


def test_round_trip_returns_the_original():
    assert round(convert_to_usd(convert_from_usd(10.0, "AU"), "AU"), 6) == 10.0


def test_unknown_marketplace_is_identity():
    assert usd_to_marketplace_rate("ZZ") == 1.0
