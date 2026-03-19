"""Stock level history — TimescaleDB hypertable (same pattern as BSRHistory)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TIMESTAMPTZ

if TYPE_CHECKING:
    from .product import Product


class StockHistory(Base):
    __tablename__ = "stock_history"

    __table_args__ = (
        Index("ix_stock_history_time_product", "time", "product_id"),
        {"implicit_returning": False},
    )

    time: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, primary_key=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    asin: Mapped[str | None] = mapped_column(String(20))
    stock_level: Mapped[int | None] = mapped_column(Integer)
    stock_text: Mapped[str | None] = mapped_column(String(255))
    is_in_stock: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # ----- Relationships -----
    product: Mapped["Product | None"] = relationship()
