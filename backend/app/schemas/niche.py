"""Pydantic schemas for the Niche model."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .common import PaginatedResponse


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class NicheCreate(BaseModel):
    """Payload to create a new niche analysis."""

    keyword: str = Field(
        min_length=1,
        max_length=255,
        description="Primary keyword / search term to analyse",
    )
    marketplace: str = Field(
        default="US",
        max_length=20,
        description="Amazon marketplace code (e.g. US, UK, DE)",
    )

    @field_validator("keyword")
    @classmethod
    def keyword_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("keyword must not be blank")
        return stripped

    @field_validator("marketplace")
    @classmethod
    def marketplace_upper(cls, v: str) -> str:
        return v.strip().upper()


class NicheUpdate(BaseModel):
    """Payload to partially update a niche (admin / manual override)."""

    name: str | None = Field(default=None, max_length=255)
    category_id: str | None = Field(default=None, max_length=50)
    opportunity_score: Decimal | None = Field(default=None, ge=0, le=100)
    confidence_tier: str | None = Field(default=None, max_length=20)
    is_seasonal: bool | None = None
    hard_filter_passed: bool | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class NicheSummary(BaseModel):
    """Lightweight niche representation for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    primary_keyword: str
    marketplace: str = "US"
    monthly_search_volume: int | None = None
    avg_sale_price: Decimal | None = None
    opportunity_score: Decimal | None = None
    confidence_tier: str | None = None
    is_seasonal: bool | None = None
    hard_filter_passed: bool | None = None
    created_at: datetime


class NicheResponse(BaseModel):
    """Full niche detail response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    primary_keyword: str
    marketplace: str = "US"
    category_id: str | None = None
    monthly_search_volume: int | None = None
    avg_sale_price: Decimal | None = None
    avg_review_count: int | None = None
    avg_bsr: int | None = None

    # Scores
    opportunity_score: Decimal | None = None
    confidence_tier: str | None = None
    demand_score: Decimal | None = None
    competition_score: Decimal | None = None
    margin_score: Decimal | None = None
    ad_profitability_score: Decimal | None = None
    review_achievability_score: Decimal | None = None
    supplier_reliability_score: Decimal | None = None
    sales_velocity_score: Decimal | None = None
    marketing_score: Decimal | None = None
    brand_building_score: Decimal | None = None

    # Flags & filters
    is_seasonal: bool | None = None
    seasonality_variance: Decimal | None = None
    ad_saturation_index: Decimal | None = None
    listing_gap_score: Decimal | None = None
    hard_filter_passed: bool | None = None
    hard_filter_fail_reasons: list[str] | None = None
    last_scored_at: datetime | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime | None = None


class NicheListResponse(PaginatedResponse):
    """Paginated list of niche summaries."""

    items: list[NicheSummary]
