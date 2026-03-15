"""Pydantic schemas for Supplier and LandedCostCalculation models."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LandedCostResponse(BaseModel):
    """Per-unit landed cost breakdown."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: int
    niche_id: int
    order_quantity: int | None = None
    shipping_mode: str | None = None

    # Per-unit cost breakdown
    unit_product_cost: Decimal | None = None
    unit_shipping_cost: Decimal | None = None
    unit_duty_cost: Decimal | None = None
    unit_customs_fee: Decimal | None = None
    unit_inspection_cost: Decimal | None = None
    unit_packaging_cost: Decimal | None = None
    unit_labeling_cost: Decimal | None = None
    unit_prep_cost: Decimal | None = None
    unit_insurance_cost: Decimal | None = None
    total_landed_cost: Decimal | None = None

    calculated_at: datetime | None = None


class SupplierResponse(BaseModel):
    """Full supplier detail response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    supplier_name: str | None = None
    alibaba_url: str | None = None
    country: str | None = None
    city: str | None = None
    years_in_business: int | None = None

    # Verification flags
    is_gold_supplier: bool | None = None
    is_verified: bool | None = None
    is_audited: bool | None = None
    trade_assurance: bool | None = None

    # Performance metrics
    transaction_volume: int | None = None
    repeat_buyer_rate: Decimal | None = None
    response_rate: Decimal | None = None
    response_time_hours: Decimal | None = None

    # Pricing & logistics
    moq: int | None = None
    moq_flexible: bool | None = None
    fob_price_min: Decimal | None = None
    fob_price_max: Decimal | None = None
    lead_time_days: int | None = None
    sample_cost: Decimal | None = None

    # Scoring
    supplier_score: Decimal | None = None
    risk_flags: list[str] | None = None
    price_tiers: dict | None = None

    last_updated_at: datetime | None = None

    # Nested landed cost calculations
    landed_cost_calculations: list[LandedCostResponse] = Field(default_factory=list)


class SupplierListResponse(BaseModel):
    """List of suppliers for a niche."""

    items: list[SupplierResponse]
    total: int = Field(ge=0)
