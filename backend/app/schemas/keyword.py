"""Pydantic schemas for NicheKeyword and PPCKeyword models."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class KeywordResponse(BaseModel):
    """Niche keyword (organic search data)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    keyword: str
    search_volume: int | None = None
    search_volume_trend: str | None = None
    avg_cpc: Decimal | None = None
    cpc_trend: str | None = None
    competition_level: str | None = None
    organic_result_count: int | None = None
    sponsored_result_count: int | None = None
    relevance_score: Decimal | None = None
    last_updated_at: datetime | None = None


class PPCKeywordResponse(BaseModel):
    """PPC keyword with bid and performance estimates."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    keyword: str
    match_type: str
    suggested_bid: Decimal | None = None
    estimated_cpc: Decimal | None = None
    estimated_impressions_daily: int | None = None
    estimated_clicks_daily: int | None = None
    estimated_conversion_rate: Decimal | None = None
    estimated_acos: Decimal | None = None
    bid_trend_30d: str | None = None
    last_updated_at: datetime | None = None
