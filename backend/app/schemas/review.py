"""Pydantic schemas for Review and ReviewPainPoint models."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ReviewResponse(BaseModel):
    """Individual product review."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    asin: str | None = None
    review_id: str | None = None
    # NOTE: no ge/le bound and no validator on this response field. A scraper mis-parse
    # that stored a rating outside 1-5 must not 500 the whole reviews list on read.
    rating: int
    title: str | None = None
    body: str | None = None
    review_date: date | None = None
    verified_purchase: bool | None = None
    helpful_votes: int | None = None
    is_vine: bool | None = None
    scraped_at: datetime | None = None


class ReviewPainPointResponse(BaseModel):
    """Clustered pain point extracted from reviews."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    cluster_name: str | None = None
    description: str | None = None
    mention_count: int | None = None
    mention_pct: Decimal | None = None
    severity: str | None = None
    sample_quotes: list[str] | None = None
    suggested_fix: str | None = None
    created_at: datetime
