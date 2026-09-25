"""Tests for the pure SP-API catalog normalisers used instead of scraping when credentials exist."""

import pytest

from app.services.spapi_service import SPAPIService, normalise_catalog_item

ITEM = {
    "asin": "B0A",
    "summaries": [{"marketplaceId": "ATVPDKIKX0DER", "itemName": "Garlic Press", "brand": "Acme", "mainImage": {"link": "https://img/x.jpg"}}],
    "salesRanks": [{"marketplaceId": "ATVPDKIKX0DER", "displayGroupRanks": [{"title": "Home & Kitchen", "rank": 2345}],
                    "classificationRanks": [{"title": "Garlic Presses", "rank": 12}]}],
}


def test_normalise_catalog_item():
    n = normalise_catalog_item(ITEM, "ATVPDKIKX0DER")
    assert n["asin"] == "B0A" and n["title"] == "Garlic Press" and n["brand"] == "Acme"
    assert n["image_url"] == "https://img/x.jpg"
    assert n["bsr"] == 2345 and n["bsr_category"] == "Home & Kitchen"
    assert n["current_subcategory_bsr"] == 12 and n["subcategory_name"] == "Garlic Presses"
    assert n["price"] is None  # pricing comes from the Pricing API, not Catalog


def test_normalise_catalog_item_missing_marketplace_data():
    """An item with no data for the requested marketplace normalises to all-None fields, not a KeyError."""
    n = normalise_catalog_item({"asin": "B0B", "summaries": [], "salesRanks": []}, "ATVPDKIKX0DER")
    assert n["asin"] == "B0B"
    assert n["title"] is None and n["bsr"] is None and n["current_subcategory_bsr"] is None


@pytest.mark.asyncio
async def test_get_rank_snapshot_shape(monkeypatch):
    """get_rank_snapshot normalises a single-ASIN catalog lookup to scrape_rank_snapshot's dict shape."""
    svc = SPAPIService(client_id="id", client_secret="secret", refresh_token="token", marketplace="US")

    async def fake_get_catalog_item(asin):
        assert asin == "B0A"
        return ITEM

    monkeypatch.setattr(svc, "get_catalog_item", fake_get_catalog_item)

    try:
        snapshot = await svc.get_rank_snapshot("B0A")
    finally:
        await svc.close()

    assert snapshot == {
        "asin": "B0A",
        "price": None,
        "current_bsr": 2345,
        "bsr_category": "Home & Kitchen",
        "current_subcategory_bsr": 12,
        "subcategory_name": "Garlic Presses",
        "stock_level": None,
        "stock_text": None,
        "is_in_stock": True,
    }
