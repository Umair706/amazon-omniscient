"""Niche model — core entity representing an Amazon product niche."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, BigInteger, Boolean, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, TIMESTAMPTZ

if TYPE_CHECKING:
    from .competitor import Competitor
    from .financial_projection import FinancialProjection
    from .keyword import NicheKeyword, PPCKeyword
    from .product import Product
    from .recommendation import Recommendation
    from .review import ReviewPainPoint
    from .supplier import LandedCostCalculation, Supplier


class Niche(TimestampMixin, Base):
    __tablename__ = "niches"
    __table_args__ = (
        UniqueConstraint("primary_keyword", "marketplace", name="uq_niches_keyword_marketplace"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    marketplace: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="US"
    )
    status: Mapped[str | None] = mapped_column(
        String(20), server_default="pending"
    )
    category_id: Mapped[str | None] = mapped_column(String(50))
    monthly_search_volume: Mapped[int | None] = mapped_column(Integer)
    avg_sale_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    avg_review_count: Mapped[int | None] = mapped_column(Integer)
    avg_bsr: Mapped[int | None] = mapped_column(Integer)

    # Scores
    opportunity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    confidence_tier: Mapped[str | None] = mapped_column(String(20))
    demand_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    competition_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    margin_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ad_profitability_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    review_achievability_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    supplier_reliability_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    sales_velocity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    marketing_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    brand_building_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Flags & filters
    is_seasonal: Mapped[bool | None] = mapped_column(Boolean, server_default="false")
    seasonality_variance: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ad_saturation_index: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    listing_gap_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    hard_filter_passed: Mapped[bool | None] = mapped_column(
        Boolean, server_default="false"
    )
    hard_filter_fail_reasons: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    last_scored_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    # Sub-niche support
    parent_niche_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("niches.id"), nullable=True
    )
    sub_niche_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sub_niche_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ----- Relationships -----
    parent_niche: Mapped["Niche | None"] = relationship(
        "Niche", remote_side=[id], foreign_keys=[parent_niche_id], lazy="selectin"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="niche", lazy="selectin"
    )
    keywords: Mapped[list["NicheKeyword"]] = relationship(
        back_populates="niche", lazy="selectin"
    )
    ppc_keywords: Mapped[list["PPCKeyword"]] = relationship(
        back_populates="niche", lazy="selectin"
    )
    competitors: Mapped[list["Competitor"]] = relationship(
        back_populates="niche", lazy="selectin"
    )
    suppliers: Mapped[list["Supplier"]] = relationship(
        back_populates="niche", lazy="selectin"
    )
    pain_points: Mapped[list["ReviewPainPoint"]] = relationship(
        back_populates="niche", lazy="selectin"
    )
    projections: Mapped[list["FinancialProjection"]] = relationship(
        back_populates="niche", lazy="selectin"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="niche", lazy="selectin"
    )
    landed_cost_calculations: Mapped[list["LandedCostCalculation"]] = relationship(
        back_populates="niche", lazy="selectin"
    )
