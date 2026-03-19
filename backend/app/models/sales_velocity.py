"""Sales velocity snapshot — computed daily from BSR deltas and stock changes."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .product import Product


class SalesVelocitySnapshot(Base):
    __tablename__ = "sales_velocity_snapshots"

    __table_args__ = (
        UniqueConstraint("date", "product_id", name="uq_velocity_date_product"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    asin: Mapped[str | None] = mapped_column(String(20))

    # BSR-derived
    bsr_start: Mapped[int | None] = mapped_column(Integer)
    bsr_end: Mapped[int | None] = mapped_column(Integer)
    bsr_delta: Mapped[int | None] = mapped_column(Integer)
    bsr_derived_daily_sales: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # Stock-derived
    stock_start: Mapped[int | None] = mapped_column(Integer)
    stock_end: Mapped[int | None] = mapped_column(Integer)
    stock_derived_daily_sales: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    restock_detected: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Regression baseline
    regression_daily_sales: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # Composite estimate
    estimated_daily_sales: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    estimation_method: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # ----- Relationships -----
    product: Mapped["Product | None"] = relationship()
