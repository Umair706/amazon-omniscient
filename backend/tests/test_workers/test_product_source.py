"""Tests for product_source_for and merge_serp_enrichment (backend/app/workers/pipeline_steps/product_source.py)."""

from types import SimpleNamespace

from app.workers.pipeline_steps.product_source import merge_serp_enrichment, product_source_for


def _settings(client_id="", client_secret="", refresh_token=""):
    """A Settings-like stand-in carrying only the three fields product_source_for reads."""
    return SimpleNamespace(
        SP_API_CLIENT_ID=client_id,
        SP_API_CLIENT_SECRET=client_secret,
        SP_API_REFRESH_TOKEN=refresh_token,
    )


def test_product_source_is_spapi_when_all_three_credentials_are_set():
    settings = _settings("client", "secret", "token")
    assert product_source_for(settings) == "spapi"


def test_product_source_is_scrape_when_no_credentials_are_set():
    settings = _settings()
    assert product_source_for(settings) == "scrape"


def test_product_source_is_scrape_when_one_credential_is_missing():
    """All three of client id, secret and refresh token are required — a partial config still means scrape."""
    settings = _settings("client", "secret", refresh_token="")
    assert product_source_for(settings) == "scrape"


def test_merge_serp_enrichment_fills_price_rating_and_badges_by_asin():
    catalog_items = [
        {"asin": "B0A", "title": "Garlic Press", "price": None, "rating": None, "review_count": None,
         "is_sponsored": False, "is_amazon_choice": False, "is_best_seller": False, "is_fba": None, "image_url": None},
    ]
    serp_items = [
        {"asin": "B0A", "price": 12.99, "rating": 4.5, "review_count": 300,
         "is_sponsored": True, "is_amazon_choice": False, "is_best_seller": True, "is_fba": True, "image_url": "https://img/serp.jpg"},
    ]

    merged = merge_serp_enrichment(catalog_items, serp_items)

    assert merged[0]["price"] == 12.99
    assert merged[0]["rating"] == 4.5
    assert merged[0]["review_count"] == 300
    assert merged[0]["is_sponsored"] is True
    assert merged[0]["is_best_seller"] is True
    assert merged[0]["is_fba"] is True
    assert merged[0]["image_url"] == "https://img/serp.jpg"


def test_merge_serp_enrichment_keeps_catalog_image_when_serp_has_none():
    """image_url only fills in when the catalog item is missing one — SP-API's own image is authoritative."""
    catalog_items = [{"asin": "B0A", "image_url": "https://img/catalog.jpg", "price": None}]
    serp_items = [{"asin": "B0A", "image_url": None, "price": 9.99}]

    merged = merge_serp_enrichment(catalog_items, serp_items)

    assert merged[0]["image_url"] == "https://img/catalog.jpg"
    assert merged[0]["price"] == 9.99


def test_merge_serp_enrichment_preserves_catalog_order_and_unmatched_items():
    """A catalog item with no matching SERP card (not on page 1) keeps its catalog defaults, in catalog order."""
    catalog_items = [
        {"asin": "B0A", "position": 1, "price": None},
        {"asin": "B0B", "position": 2, "price": None},
    ]
    serp_items = [{"asin": "B0B", "price": 19.99}]

    merged = merge_serp_enrichment(catalog_items, serp_items)

    assert [m["asin"] for m in merged] == ["B0A", "B0B"]
    assert merged[0]["position"] == 1 and merged[0]["price"] is None
    assert merged[1]["position"] == 2 and merged[1]["price"] == 19.99
