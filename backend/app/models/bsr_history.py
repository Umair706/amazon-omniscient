"""BSR (Best Seller Rank) history — TimescaleDB hypertable keyed by (time, product_id, is_subcategory)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TIMESTAMPTZ

if TYPE_CHECKING:
    from .product import Product


class BSRHistory(Base):
    __tablename__ = "bsr_history"

    # NOTE: the key includes is_subcategory because a product's main rank and
    # sub-category rank are recorded with the same timestamp (migration 015).
    # TimescaleDB requires the time column to be part of any unique key.
    __table_args__ = (
        Index("ix_bsr_history_time_product", "time", "product_id"),
        {"implicit_returning": False},
    )

    time: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, primary_key=True
    )
    product_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    asin: Mapped[str | None] = mapped_column(String(20))
    bsr: Mapped[int] = mapped_column(Integer, nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(50))
    category_name: Mapped[str | None] = mapped_column(String(255))
    is_subcategory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", primary_key=True
    )
    # NOTE: only set on main-rank rows; the sub-rank row recorded at the same moment leaves it NULL.
    review_count: Mapped[int | None] = mapped_column(Integer)

    # ----- Relationships -----
    product: Mapped["Product | None"] = relationship(back_populates="bsr_history")
