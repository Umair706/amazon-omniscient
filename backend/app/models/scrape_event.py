"""Per-page scrape outcome, so block rates and selector rot are visible."""

from datetime import datetime

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TIMESTAMPTZ


class ScrapeEvent(Base):
    __tablename__ = "scrape_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # index=True matches migration 014's explicit ix_scrape_events_time.
    time: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, index=True)
    site: Mapped[str] = mapped_column(String(20), nullable=False)       # amazon | 1688
    url_kind: Mapped[str] = mapped_column(String(20), nullable=False)   # serp | product | reviews | serp_meta | rank
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)    # ok | captcha | soft_block | server_error | timeout | wrong_marketplace
    proxy_label: Mapped[str | None] = mapped_column(String(100))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
