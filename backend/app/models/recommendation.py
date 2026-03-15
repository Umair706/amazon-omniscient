"""Recommendation model — final Omniscient output for a niche."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, BigInteger, Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .niche import Niche


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    niche_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("niches.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Core scores
    omniscient_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    confidence_tier: Mapped[str] = mapped_column(String(20), nullable=False)

    # Product strategy
    product_description: Mapped[str | None] = mapped_column(Text)
    differentiation_features: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    top_supplier_ids: Mapped[list[int] | None] = mapped_column(
        ARRAY(BigInteger), nullable=True
    )

    # Unit economics
    best_landed_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    recommended_sale_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    estimated_net_margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Break-even timelines
    break_even_week_bull: Mapped[int | None] = mapped_column(Integer)
    break_even_week_base: Mapped[int | None] = mapped_column(Integer)
    break_even_week_bear: Mapped[int | None] = mapped_column(Integer)

    # Launch capital
    total_launch_capital: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # Reviews strategy
    review_threshold: Mapped[int | None] = mapped_column(Integer)
    weeks_to_review_threshold: Mapped[int | None] = mapped_column(Integer)
    vine_recommended: Mapped[bool | None] = mapped_column(Boolean)
    vine_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # PPC strategy
    ppc_budget_30d: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ppc_budget_90d: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    break_even_acos: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    estimated_acos: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Rich JSONB payloads
    marketing_channels: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    risk_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    launch_playbook: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ppc_strategy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    product_blueprint: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    financial_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    generated_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    # ----- Relationships -----
    niche: Mapped["Niche"] = relationship(back_populates="recommendations")
