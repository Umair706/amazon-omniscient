"""Keyword models — NicheKeyword and PPCKeyword."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TIMESTAMPTZ

if TYPE_CHECKING:
    from .niche import Niche


class NicheKeyword(Base):
    __tablename__ = "niche_keywords"

    __table_args__ = (
        UniqueConstraint("niche_id", "keyword", name="uq_niche_keywords_niche_kw"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    niche_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("niches.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    search_volume: Mapped[int | None] = mapped_column(Integer)
    search_volume_trend: Mapped[str | None] = mapped_column(String(20))
    avg_cpc: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    cpc_trend: Mapped[str | None] = mapped_column(String(20))
    competition_level: Mapped[str | None] = mapped_column(String(20))
    organic_result_count: Mapped[int | None] = mapped_column(Integer)
    sponsored_result_count: Mapped[int | None] = mapped_column(Integer)
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    source: Mapped[str | None] = mapped_column(String(50))
    autocomplete_depth: Mapped[int | None] = mapped_column(Integer)
    last_updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    # ----- Relationships -----
    niche: Mapped["Niche"] = relationship(back_populates="keywords")


class PPCKeyword(Base):
    __tablename__ = "ppc_keywords"

    __table_args__ = (
        UniqueConstraint(
            "niche_id",
            "keyword",
            "match_type",
            name="uq_ppc_keywords_niche_kw_match",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    niche_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("niches.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    match_type: Mapped[str] = mapped_column(String(20), nullable=False)
    suggested_bid: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    estimated_cpc: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    estimated_impressions_daily: Mapped[int | None] = mapped_column(Integer)
    estimated_clicks_daily: Mapped[int | None] = mapped_column(Integer)
    estimated_conversion_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    estimated_acos: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    bid_trend_30d: Mapped[str | None] = mapped_column(String(20))
    last_updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    # ----- Relationships -----
    niche: Mapped["Niche"] = relationship(back_populates="ppc_keywords")
