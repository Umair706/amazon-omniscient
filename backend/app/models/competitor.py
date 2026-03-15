"""Competitor model — per-product competitive analysis within a niche."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TIMESTAMPTZ

if TYPE_CHECKING:
    from .niche import Niche
    from .product import Product


class Competitor(Base):
    __tablename__ = "competitors"

    __table_args__ = (
        UniqueConstraint(
            "niche_id", "product_id", name="uq_competitors_niche_product"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    niche_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("niches.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Rankings
    organic_rank: Mapped[int | None] = mapped_column(Integer)
    sponsored_rank: Mapped[int | None] = mapped_column(Integer)

    # Listing quality breakdown
    listing_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    title_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    image_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    bullet_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    a_plus_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    video_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    backend_kw_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Pricing dynamics (90-day)
    price_90d_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    price_90d_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    price_90d_avg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # Promotions
    has_subscribe_save: Mapped[bool | None] = mapped_column(Boolean)
    coupon_frequency: Mapped[int | None] = mapped_column(Integer)
    lightning_deal_frequency: Mapped[int | None] = mapped_column(Integer)

    # Review metrics
    review_velocity: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    estimated_monthly_sales: Mapped[int | None] = mapped_column(Integer)

    # Vulnerability assessment
    vulnerability: Mapped[str | None] = mapped_column(String(20))
    vulnerability_type: Mapped[str | None] = mapped_column(String(50))

    last_analyzed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    # ----- Relationships -----
    niche: Mapped["Niche"] = relationship(back_populates="competitors")
    product: Mapped["Product"] = relationship(back_populates="competitor_entries")
