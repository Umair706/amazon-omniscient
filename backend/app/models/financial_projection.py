"""Financial projection model — weekly P&L forecasts per scenario."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .niche import Niche


class FinancialProjection(Base):
    __tablename__ = "financial_projections"

    __table_args__ = (
        UniqueConstraint(
            "niche_id",
            "scenario",
            "week_number",
            name="uq_financial_projections_niche_scenario_week",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    niche_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("niches.id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario: Mapped[str | None] = mapped_column(String(10))
    week_number: Mapped[int | None] = mapped_column(Integer)

    # Weekly metrics
    estimated_organic_rank: Mapped[int | None] = mapped_column(Integer)
    estimated_units_sold: Mapped[int | None] = mapped_column(Integer)

    # Financials
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cogs: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fba_fees: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ad_spend: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    storage_fees: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    net_profit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cumulative_profit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # Projections
    review_count_projected: Mapped[int | None] = mapped_column(Integer)
    organic_traffic_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    calculated_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    # ----- Relationships -----
    niche: Mapped["Niche"] = relationship(back_populates="projections")
