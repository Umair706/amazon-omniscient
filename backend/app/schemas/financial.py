"""Pydantic schemas for the FinancialProjection model."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FinancialProjectionResponse(BaseModel):
    """Single weekly financial projection row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    scenario: str | None = None
    week_number: int | None = None

    # Weekly metrics
    estimated_organic_rank: int | None = None
    estimated_units_sold: int | None = None

    # Financials
    revenue: Decimal | None = None
    cogs: Decimal | None = None
    fba_fees: Decimal | None = None
    ad_spend: Decimal | None = None
    storage_fees: Decimal | None = None
    net_profit: Decimal | None = None
    cumulative_profit: Decimal | None = None

    # Projections
    review_count_projected: int | None = None
    organic_traffic_pct: Decimal | None = None

    calculated_at: datetime | None = None


class ProjectionListResponse(BaseModel):
    """List of financial projections (typically all weeks for a scenario)."""

    items: list[FinancialProjectionResponse]
    total: int = Field(ge=0)
