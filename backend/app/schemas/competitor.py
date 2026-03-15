"""Pydantic schemas for the Competitor model."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CompetitorResponse(BaseModel):
    """Full competitor analysis response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    product_id: int

    # Rankings
    organic_rank: int | None = None
    sponsored_rank: int | None = None

    # Listing quality breakdown
    listing_quality_score: Decimal | None = None
    title_score: Decimal | None = None
    image_score: Decimal | None = None
    bullet_score: Decimal | None = None
    a_plus_score: Decimal | None = None
    video_score: Decimal | None = None
    backend_kw_score: Decimal | None = None

    # Pricing dynamics (90-day)
    price_90d_min: Decimal | None = None
    price_90d_max: Decimal | None = None
    price_90d_avg: Decimal | None = None

    # Promotions
    has_subscribe_save: bool | None = None
    coupon_frequency: int | None = None
    lightning_deal_frequency: int | None = None

    # Review metrics
    review_velocity: Decimal | None = None
    sentiment_score: Decimal | None = None

    # Vulnerability assessment
    vulnerability: str | None = None
    vulnerability_type: str | None = None

    last_analyzed_at: datetime | None = None


class CompetitorListResponse(BaseModel):
    """List of competitors for a niche."""

    items: list[CompetitorResponse]
    total: int = Field(ge=0)
