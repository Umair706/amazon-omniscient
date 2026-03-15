"""BSR (Best Seller Rank) history — TimescaleDB hypertable pattern (no PK)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TIMESTAMPTZ

if TYPE_CHECKING:
    from .product import Product


class BSRHistory(Base):
    __tablename__ = "bsr_history"

    # TimescaleDB hypertable — composite PK used as surrogate since SQLAlchemy
    # requires at least one PK column.  The real uniqueness comes from the
    # (time, product_id) composite index which TimescaleDB uses for chunking.
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
        Boolean, nullable=False, server_default="false"
    )

    # ----- Relationships -----
    product: Mapped["Product | None"] = relationship(back_populates="bsr_history")
