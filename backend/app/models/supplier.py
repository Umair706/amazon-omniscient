"""Supplier, LandedCostCalculation, and ProductSupplierMatch models."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, BigInteger, Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TIMESTAMPTZ

if TYPE_CHECKING:
    from .niche import Niche


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    niche_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("niches.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_name: Mapped[str | None] = mapped_column(String(500))
    alibaba_url: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    years_in_business: Mapped[int | None] = mapped_column(Integer)

    # Verification flags
    is_gold_supplier: Mapped[bool | None] = mapped_column(Boolean)
    is_verified: Mapped[bool | None] = mapped_column(Boolean)
    is_audited: Mapped[bool | None] = mapped_column(Boolean)
    trade_assurance: Mapped[bool | None] = mapped_column(Boolean)

    # Performance metrics
    transaction_volume: Mapped[int | None] = mapped_column(Integer)
    repeat_buyer_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    response_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    response_time_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    # Pricing & logistics
    moq: Mapped[int | None] = mapped_column(Integer)
    moq_flexible: Mapped[bool | None] = mapped_column(Boolean)
    fob_price_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fob_price_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    sample_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # Scoring
    supplier_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    risk_flags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    price_tiers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    last_updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    # ----- Relationships -----
    niche: Mapped["Niche"] = relationship(back_populates="suppliers")
    landed_cost_calculations: Mapped[list["LandedCostCalculation"]] = relationship(
        back_populates="supplier", lazy="selectin"
    )


class LandedCostCalculation(Base):
    __tablename__ = "landed_cost_calculations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )
    niche_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("niches.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_quantity: Mapped[int | None] = mapped_column(Integer)
    shipping_mode: Mapped[str | None] = mapped_column(String(20))

    # Per-unit cost breakdown
    unit_product_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    unit_shipping_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    unit_duty_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    unit_customs_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    unit_inspection_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    unit_packaging_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    unit_labeling_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    unit_prep_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    unit_insurance_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    total_landed_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    calculated_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    # ----- Relationships -----
    supplier: Mapped["Supplier"] = relationship(
        back_populates="landed_cost_calculations"
    )
    niche: Mapped["Niche"] = relationship(back_populates="landed_cost_calculations")


class ProductSupplierMatch(Base):
    """Links individual Amazon products to their matched 1688 suppliers."""

    __tablename__ = "product_supplier_matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    match_reasoning: Mapped[str | None] = mapped_column(Text)
