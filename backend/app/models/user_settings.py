"""User settings model — per-user API credentials and preferences."""

from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Integer, LargeBinary, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class UserSettings(TimestampMixin, Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )

    # Encrypted API credentials (stored as raw bytes)
    sp_api_credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    ads_api_credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    alibaba_credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)

    # Preferences
    default_marketplace: Mapped[str | None] = mapped_column(
        String(20), server_default="US"
    )
    min_margin_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), server_default="25.00"
    )
    max_review_moat: Mapped[int | None] = mapped_column(
        Integer, server_default="2000"
    )
    allow_seasonal: Mapped[bool | None] = mapped_column(
        Boolean, server_default="false"
    )
