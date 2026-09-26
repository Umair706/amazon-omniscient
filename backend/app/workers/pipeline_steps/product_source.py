"""Decide where product data comes from: SP-API when configured (legal, unblockable), else scraping."""

from app.config import Settings

# Fields the SERP scrape carries that the SP-API Catalog Items response never does.
# Catalog items always start with these as None/False, so a matching SERP card's
# value is always the better one.
SERP_ONLY_FIELDS = ("price", "rating", "review_count", "is_sponsored", "is_amazon_choice", "is_best_seller", "is_fba")


def product_source_for(settings: Settings) -> str:
    """Return "spapi" when all three Amazon SP-API credentials are configured, else "scrape"."""
    if settings.SP_API_CLIENT_ID and settings.SP_API_CLIENT_SECRET and settings.SP_API_REFRESH_TOKEN:
        return "spapi"
    return "scrape"


def merge_serp_enrichment(catalog_items: list[dict], serp_items: list[dict]) -> list[dict]:
    """Overlay a page-1 SERP scrape's price/rating/badge fields onto SP-API catalog items, matched by ASIN.

    Catalog items keep their own order and position; a catalog item with no matching
    SERP card (not on page 1) is returned unchanged.
    """
    serp_by_asin = {item["asin"]: item for item in serp_items if item.get("asin")}
    return [_merge_one(item, serp_by_asin.get(item.get("asin"), {})) for item in catalog_items]


def _merge_one(catalog_item: dict, enrichment: dict) -> dict:
    """Fill one catalog item's SERP-only fields from its matching SERP card, if there is one."""
    merged = dict(catalog_item)
    if not enrichment:
        return merged

    for field in SERP_ONLY_FIELDS:
        merged[field] = enrichment.get(field)

    # image_url can come from either source, so only take the SERP one when the catalog lacks it.
    if merged.get("image_url") is None and enrichment.get("image_url") is not None:
        merged["image_url"] = enrichment["image_url"]

    return merged
