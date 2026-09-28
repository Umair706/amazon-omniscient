"""Pydantic schemas for the Product model."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductSummary(BaseModel):
    """Lightweight product representation for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    asin: str
    niche_id: int | None = None
    title: str | None = None
    brand: str | None = None
    image_url: str | None = None
    current_price: Decimal | None = None
    current_bsr: int | None = None
    review_count: int | None = None
    rating: Decimal | None = None
    estimated_monthly_revenue: Decimal | None = None
    listing_quality_score: Decimal | None = None


class ProductResponse(BaseModel):
    """Full product detail response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    asin: str
    niche_id: int | None = None
    # The Amazon store this product's data came from (e.g. "AU"). Populated from the
    # product's niche so the product page can state which marketplace it is showing.
    marketplace: str | None = None
    title: str | None = None
    brand: str | None = None
    image_url: str | None = None
    category_id: str | None = None

    # Pricing & ranking
    current_price: Decimal | None = None
    current_bsr: int | None = None
    review_count: int | None = None
    rating: Decimal | None = None

    # Listing flags
    is_fba: bool | None = None
    is_amazon_choice: bool | None = None
    is_best_seller: bool | None = None
    is_sponsored: bool | None = None
    has_a_plus: bool | None = None
    has_video: bool | None = None
    has_brand_story: bool | None = None
    image_count: int | None = None
    bullet_count: int | None = None

    # Seller info
    seller_id: str | None = None
    brand_registered: bool | None = None
    storefront_asin_count: int | None = None

    # Estimates
    estimated_monthly_units: int | None = None
    estimated_monthly_revenue: Decimal | None = None
    listing_quality_score: Decimal | None = None

    # Cost structure
    fba_fee: Decimal | None = None
    referral_fee_pct: Decimal | None = None
    product_weight_lbs: Decimal | None = None
    product_dimensions: str | None = None

    last_scraped_at: datetime | None = None

    # Sales velocity
    estimated_daily_sales: int | None = None
    sales_velocity_trend: str | None = None
    last_stock_level: int | None = None

    # Search position
    search_position: int | None = None

    # Enriched product data
    list_price: Decimal | None = None
    date_first_available: date | None = None
    star_distribution: dict | None = None
    variation_count: int | None = None
    category_path: str | None = None
    seller_count: int | None = None
    fbt_asins: list[str] | None = None
    qa_count: int | None = None
    deal_badge: str | None = None
    amazons_choice_keyword: str | None = None
    review_attributes: list[dict] | None = None
    comparison_asins: list[str] | None = None
    weight: str | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime | None = None

    # NOTE: no ASIN-format validator here. This is a response schema; validating stored
    # data on the read path turns one malformed row into a 500 for the whole list. ASIN
    # shape is enforced at ingest, not when serving.


class ProductListItem(BaseModel):
    """Product fields a list/table shows.

    Excludes the heavy detail-only payloads (review_attributes, comparison_asins,
    fbt_asins, star_distribution, category_path, dimensions, cost structure) so a
    niche's product list stays small. The full object loads on /products/{asin}.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    asin: str
    niche_id: int | None = None
    marketplace: str | None = None
    title: str | None = None
    brand: str | None = None
    image_url: str | None = None
    current_price: Decimal | None = None
    current_bsr: int | None = None
    review_count: int | None = None
    rating: Decimal | None = None
    is_amazon_choice: bool | None = None
    is_best_seller: bool | None = None
    estimated_monthly_units: int | None = None
    estimated_monthly_revenue: Decimal | None = None
    listing_quality_score: Decimal | None = None
    sales_velocity_trend: str | None = None
    search_position: int | None = None
    seller_count: int | None = None
    variation_count: int | None = None
    deal_badge: str | None = None
    amazons_choice_keyword: str | None = None
    last_scraped_at: datetime | None = None
    created_at: datetime


class ProductListResponse(BaseModel):
    """List of products (typically scoped to a niche) — summaries only."""

    items: list[ProductListItem]
    total: int = Field(ge=0)
