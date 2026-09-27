"""User settings model — per-user API credentials and preferences."""

from sqlalchemy import BigInteger, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB
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
    # The seller's tuning of the scoring thesis: thresholds, weights, sales
    # multiplier, and seasonal allowance. Shape and defaults live in
    # app/services/scoring_config.py. NULL means "use the built-in defaults".
    scoring_config: Mapped[dict | None] = mapped_column(JSONB)
