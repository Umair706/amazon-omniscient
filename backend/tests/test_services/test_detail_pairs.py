"""_detail_value / _clean_detail_text: pick the right label across marketplace layouts."""

from app.services.scraper_service import _clean_detail_text, _detail_value


def test_clean_strips_directional_marks_and_whitespace():
    assert _clean_detail_text("Item Weight ‏ : ‎ 363 Grams") == "Item Weight : 363 Grams"


def test_detail_value_matches_au_labels():
    # AU labels the weight "Item Weight" and dimensions "Item Dimensions L x W".
    pairs = {"Item Weight": "363 Grams", "Item Dimensions L x W": "26.5L x 4W centimetres", "Brand Name": "OXO"}
    assert _detail_value(pairs, ("item weight", "weight")) == "363 Grams"
    assert _detail_value(pairs, ("item dimensions", "dimensions")) == "26.5L x 4W centimetres"


def test_detail_value_prefers_earlier_keyword():
    pairs = {"Shipping Weight": "1 kg", "Item Weight": "363 Grams"}
    assert _detail_value(pairs, ("item weight", "shipping weight")) == "363 Grams"


def test_detail_value_returns_none_when_absent():
    assert _detail_value({"Brand Name": "OXO"}, ("date first available",)) is None
    assert _detail_value({"Item Weight": ""}, ("item weight",)) is None
