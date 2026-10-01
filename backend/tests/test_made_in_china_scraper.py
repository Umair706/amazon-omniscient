"""Tests for the Made-in-China supplier parser (pure functions, no network)."""

from app.services.made_in_china_scraper import (
    parse_price_usd,
    parse_moq,
    build_supplier_record,
)

# Real card text captured from made-in-china.com (newlines are how innerText joins the fields).
CARD_RANGE = "Adjustable Drawer Organizer, Expandable Divider\nUS$1.24-1.34\n(FOB Price)\n3,000 Pieces\n(MOQ)\nMaterial: Plastic+Sponge\nCertification: BSCI"
CARD_SINGLE = "Bamboo Drawer Organizer\nUS$7.00\n(FOB Price)\n500 Pieces\n(MOQ)"


class TestParsePriceUsd:
    def test_range_price_returns_low_and_high(self):
        assert parse_price_usd(CARD_RANGE) == (1.24, 1.34)

    def test_single_price_repeats_as_low_and_high(self):
        assert parse_price_usd(CARD_SINGLE) == (7.00, 7.00)

    def test_price_with_thousands_comma(self):
        assert parse_price_usd("US$1,250.50") == (1250.50, 1250.50)

    def test_no_price_returns_none_pair(self):
        assert parse_price_usd("No price listed, contact supplier") == (None, None)


class TestParseMoq:
    def test_moq_with_comma(self):
        assert parse_moq(CARD_RANGE) == 3000

    def test_moq_plain(self):
        assert parse_moq(CARD_SINGLE) == 500

    def test_moq_sets_unit(self):
        assert parse_moq("Min. order 200 Sets") == 200

    def test_no_moq_returns_none(self):
        assert parse_moq("US$5.00 (FOB Price)") is None


class TestBuildSupplierRecord:
    def test_maps_all_fields_with_usd_prices(self):
        raw = {
            "title": "Adjustable Drawer Organizer",
            "url": "https://okhomeware.en.made-in-china.com/product/abc.html",
            "company": "Ningbo OK Homeware Co., Ltd.",
            "text": CARD_RANGE + "\nAudited Supplier",
        }
        rec = build_supplier_record(raw)
        assert rec["supplier_name"] == "Ningbo OK Homeware Co., Ltd."
        assert rec["product_title"] == "Adjustable Drawer Organizer"
        assert rec["price_min"] == 1.24  # USD, not CNY
        assert rec["price_max"] == 1.34
        assert rec["moq"] == 3000
        assert rec["is_verified"] is True
        assert rec["product_url"] == "https://okhomeware.en.made-in-china.com/product/abc.html"

    def test_unverified_card_is_not_flagged(self):
        rec = build_supplier_record({"title": "x", "url": "y", "company": "z", "text": CARD_SINGLE})
        assert rec["is_verified"] is False

    def test_record_has_the_same_keys_the_pipeline_expects(self):
        rec = build_supplier_record({"text": CARD_SINGLE})
        expected = {
            "supplier_name", "product_title", "price_min", "price_max", "moq", "location",
            "years_in_business", "is_verified", "transaction_count", "response_rate",
            "product_url", "image_url",
        }
        assert set(rec.keys()) == expected
