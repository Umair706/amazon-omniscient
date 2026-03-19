"""Product model — an individual Amazon ASIN."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, TIMESTAMPTZ

if TYPE_CHECKING:
    from .bsr_history import BSRHistory
    from .competitor import Competitor
    from .niche import Niche
    from .price_history import PriceHistory
    from .review import Review


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    asin: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    niche_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("niches.id", ondelete="SET NULL")
    )
    title: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(255))
    category_id: Mapped[str | None] = mapped_column(String(50))

    # Pricing & ranking
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    current_bsr: Mapped[int | None] = mapped_column(Integer)
    current_subcategory_bsr: Mapped[int | None] = mapped_column(Integer)
    bsr_category: Mapped[str | None] = mapped_column(String(255))
    subcategory_name: Mapped[str | None] = mapped_column(String(255))
    review_count: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))

    # Listing flags
    is_fba: Mapped[bool | None] = mapped_column(Boolean)
    is_amazon_choice: Mapped[bool | None] = mapped_column(Boolean)
    is_best_seller: Mapped[bool | None] = mapped_column(Boolean)
    is_sponsored: Mapped[bool | None] = mapped_column(Boolean)
    has_a_plus: Mapped[bool | None] = mapped_column(Boolean)
    has_video: Mapped[bool | None] = mapped_column(Boolean)
    has_brand_story: Mapped[bool | None] = mapped_column(Boolean)
    image_url: Mapped[str | None] = mapped_column(Text)
    image_count: Mapped[int | None] = mapped_column(Integer)
    bullet_count: Mapped[int | None] = mapped_column(Integer)

    # Seller info
    seller_id: Mapped[str | None] = mapped_column(String(50))
    brand_registered: Mapped[bool | None] = mapped_column(Boolean)
    storefront_asin_count: Mapped[int | None] = mapped_column(Integer)

    # Estimates
    estimated_monthly_units: Mapped[int | None] = mapped_column(Integer)
    estimated_monthly_revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    listing_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Cost structure
    fba_fee: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    referral_fee_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    product_weight_lbs: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    product_dimensions: Mapped[str | None] = mapped_column(String(100))

    last_scraped_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    # Sales velocity
    estimated_daily_sales: Mapped[int | None] = mapped_column(Integer)
    sales_velocity_trend: Mapped[str | None] = mapped_column(String(20))
    last_stock_level: Mapped[int | None] = mapped_column(Integer)

    # Search position (organic rank in SERP)
    search_position: Mapped[int | None] = mapped_column(Integer)

    # Enriched product data
    list_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    date_first_available: Mapped[date | None] = mapped_column(Date)
    star_distribution: Mapped[dict | None] = mapped_column(JSONB)
    variation_count: Mapped[int | None] = mapped_column(Integer)
    category_path: Mapped[str | None] = mapped_column(Text)
    seller_count: Mapped[int | None] = mapped_column(Integer)
    fbt_asins: Mapped[list | None] = mapped_column(JSONB)
    qa_count: Mapped[int | None] = mapped_column(Integer)
    deal_badge: Mapped[str | None] = mapped_column(String(100))
    amazons_choice_keyword: Mapped[str | None] = mapped_column(String(255))
    review_attributes: Mapped[list | None] = mapped_column(JSONB)
    comparison_asins: Mapped[list | None] = mapped_column(JSONB)
    weight: Mapped[str | None] = mapped_column(String(100))

    # ----- Relationships -----
    niche: Mapped["Niche | None"] = relationship(back_populates="products")
    bsr_history: Mapped[list["BSRHistory"]] = relationship(
        back_populates="product", lazy="selectin"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="product", lazy="selectin"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="product", lazy="selectin"
    )
    competitor_entries: Mapped[list["Competitor"]] = relationship(
        back_populates="product", lazy="selectin"
    )
