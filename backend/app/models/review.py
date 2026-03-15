"""Review and ReviewPainPoint models."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .niche import Niche
    from .product import Product


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    asin: Mapped[str | None] = mapped_column(String(20))
    review_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    review_date: Mapped[date | None] = mapped_column(Date)
    verified_purchase: Mapped[bool | None] = mapped_column(Boolean)
    helpful_votes: Mapped[int | None] = mapped_column(Integer, server_default="0")
    is_vine: Mapped[bool | None] = mapped_column(Boolean)
    scraped_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    # ----- Relationships -----
    product: Mapped["Product"] = relationship(back_populates="reviews")


class ReviewPainPoint(Base):
    __tablename__ = "review_pain_points"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    niche_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("niches.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    mention_count: Mapped[int | None] = mapped_column(Integer)
    mention_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    severity: Mapped[str | None] = mapped_column(String(20))
    sample_quotes: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    suggested_fix: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # ----- Relationships -----
    niche: Mapped["Niche"] = relationship(back_populates="pain_points")
