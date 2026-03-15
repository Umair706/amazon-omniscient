"""Price history — TimescaleDB hypertable pattern (no PK)."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .product import Product


class PriceHistory(Base):
    __tablename__ = "price_history"

    __table_args__ = (
        Index("ix_price_history_time_product", "time", "product_id"),
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
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    has_coupon: Mapped[bool | None] = mapped_column(Boolean)
    coupon_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    is_lightning_deal: Mapped[bool | None] = mapped_column(Boolean)
    buy_box_seller_id: Mapped[str | None] = mapped_column(String(50))

    # ----- Relationships -----
    product: Mapped["Product | None"] = relationship(back_populates="price_history")
