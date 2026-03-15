"""Pydantic schemas for the Recommendation model."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RecommendationSummary(BaseModel):
    """Lightweight recommendation for list/dashboard views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    omniscient_score: Decimal = Field(ge=0, le=100)
    confidence_tier: str
    recommended_sale_price: Decimal | None = None
    estimated_net_margin_pct: Decimal | None = None
    total_launch_capital: Decimal | None = None
    generated_at: datetime | None = None


class RecommendationResponse(BaseModel):
    """Full recommendation detail response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int

    # Core scores
    omniscient_score: Decimal = Field(ge=0, le=100)
    confidence_tier: str

    # Product strategy
    product_description: str | None = None
    differentiation_features: list[str] | None = None
    top_supplier_ids: list[int] | None = None

    # Unit economics
    best_landed_cost: Decimal | None = None
    recommended_sale_price: Decimal | None = None
    estimated_net_margin_pct: Decimal | None = None

    # Break-even timelines
    break_even_week_bull: int | None = None
    break_even_week_base: int | None = None
    break_even_week_bear: int | None = None

    # Launch capital
    total_launch_capital: Decimal | None = None

    # Reviews strategy
    review_threshold: int | None = None
    weeks_to_review_threshold: int | None = None
    vine_recommended: bool | None = None
    vine_cost: Decimal | None = None

    # PPC strategy
    ppc_budget_30d: Decimal | None = None
    ppc_budget_90d: Decimal | None = None
    break_even_acos: Decimal | None = None
    estimated_acos: Decimal | None = None

    # Rich JSONB payloads
    marketing_channels: dict | None = None
    risk_flags: dict | None = None
    launch_playbook: dict | None = None
    ppc_strategy: dict | None = None

    generated_at: datetime | None = None


class RecommendationListResponse(BaseModel):
    """List of recommendations for a niche."""

    items: list[RecommendationResponse]
    total: int = Field(ge=0)
