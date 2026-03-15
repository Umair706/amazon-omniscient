"""Initial schema — all Omniscient ORM tables with TimescaleDB hypertables.

Revision ID: 001
Revises: None
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── TimescaleDB extension ───────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    # ── niches ──────────────────────────────────────────────────────
    op.create_table(
        "niches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("primary_keyword", sa.String(length=255), nullable=False),
        sa.Column("category_id", sa.String(length=50), nullable=True),
        sa.Column("monthly_search_volume", sa.Integer(), nullable=True),
        sa.Column("avg_sale_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("avg_review_count", sa.Integer(), nullable=True),
        sa.Column("avg_bsr", sa.Integer(), nullable=True),
        # Scores
        sa.Column("opportunity_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("confidence_tier", sa.String(length=20), nullable=True),
        sa.Column("demand_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("competition_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("margin_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "ad_profitability_score", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column(
            "review_achievability_score",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
        sa.Column(
            "supplier_reliability_score",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
        sa.Column(
            "sales_velocity_score", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column("marketing_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "brand_building_score", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        # Flags & filters
        sa.Column(
            "is_seasonal", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column(
            "seasonality_variance", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column(
            "ad_saturation_index", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column(
            "listing_gap_score", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column(
            "hard_filter_passed", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column(
            "hard_filter_fail_reasons",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "last_scored_at",
            postgresql.TIMESTAMPTZ(),
            nullable=True,
        ),
        # Timestamps (TimestampMixin)
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("primary_keyword"),
    )

    # ── products ────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("asin", sa.String(length=20), nullable=False),
        sa.Column("niche_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("category_id", sa.String(length=50), nullable=True),
        # Pricing & ranking
        sa.Column("current_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("current_bsr", sa.Integer(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Numeric(precision=3, scale=2), nullable=True),
        # Listing flags
        sa.Column("is_fba", sa.Boolean(), nullable=True),
        sa.Column("is_amazon_choice", sa.Boolean(), nullable=True),
        sa.Column("is_best_seller", sa.Boolean(), nullable=True),
        sa.Column("is_sponsored", sa.Boolean(), nullable=True),
        sa.Column("has_a_plus", sa.Boolean(), nullable=True),
        sa.Column("has_video", sa.Boolean(), nullable=True),
        sa.Column("has_brand_story", sa.Boolean(), nullable=True),
        sa.Column("image_count", sa.Integer(), nullable=True),
        sa.Column("bullet_count", sa.Integer(), nullable=True),
        # Seller info
        sa.Column("seller_id", sa.String(length=50), nullable=True),
        sa.Column("brand_registered", sa.Boolean(), nullable=True),
        sa.Column("storefront_asin_count", sa.Integer(), nullable=True),
        # Estimates
        sa.Column("estimated_monthly_units", sa.Integer(), nullable=True),
        sa.Column(
            "estimated_monthly_revenue",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            "listing_quality_score", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        # Cost structure
        sa.Column("fba_fee", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("referral_fee_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "product_weight_lbs", sa.Numeric(precision=8, scale=2), nullable=True
        ),
        sa.Column("product_dimensions", sa.String(length=100), nullable=True),
        sa.Column("last_scraped_at", postgresql.TIMESTAMPTZ(), nullable=True),
        # Timestamps (TimestampMixin)
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asin"),
        sa.ForeignKeyConstraint(
            ["niche_id"],
            ["niches.id"],
            ondelete="SET NULL",
        ),
    )

    # ── user_settings ───────────────────────────────────────────────
    op.create_table(
        "user_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        # Encrypted credentials
        sa.Column("sp_api_credentials_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("ads_api_credentials_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("alibaba_credentials_encrypted", sa.LargeBinary(), nullable=True),
        # Preferences
        sa.Column(
            "default_marketplace",
            sa.String(length=20),
            server_default="US",
            nullable=True,
        ),
        sa.Column(
            "min_margin_threshold",
            sa.Numeric(precision=5, scale=2),
            server_default="25.00",
            nullable=True,
        ),
        sa.Column(
            "max_review_moat",
            sa.Integer(),
            server_default="2000",
            nullable=True,
        ),
        sa.Column(
            "allow_seasonal",
            sa.Boolean(),
            server_default="false",
            nullable=True,
        ),
        # Timestamps (TimestampMixin)
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # ── bsr_history (TimescaleDB hypertable) ────────────────────────
    op.create_table(
        "bsr_history",
        sa.Column("time", postgresql.TIMESTAMPTZ(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("asin", sa.String(length=20), nullable=True),
        sa.Column("bsr", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("time", "product_id"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        # implicit_returning=False is an ORM-level option, not a DDL construct
    )
    op.create_index(
        "ix_bsr_history_time_product", "bsr_history", ["time", "product_id"]
    )
    op.execute(
        "SELECT create_hypertable('bsr_history', 'time', if_not_exists => TRUE)"
    )

    # ── price_history (TimescaleDB hypertable) ──────────────────────
    op.create_table(
        "price_history",
        sa.Column("time", postgresql.TIMESTAMPTZ(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("asin", sa.String(length=20), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("has_coupon", sa.Boolean(), nullable=True),
        sa.Column("coupon_value", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("is_lightning_deal", sa.Boolean(), nullable=True),
        sa.Column("buy_box_seller_id", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("time", "product_id"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_price_history_time_product", "price_history", ["time", "product_id"]
    )
    op.execute(
        "SELECT create_hypertable('price_history', 'time', if_not_exists => TRUE)"
    )

    # ── competitors ─────────────────────────────────────────────────
    op.create_table(
        "competitors",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("niche_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        # Rankings
        sa.Column("organic_rank", sa.Integer(), nullable=True),
        sa.Column("sponsored_rank", sa.Integer(), nullable=True),
        # Listing quality breakdown
        sa.Column(
            "listing_quality_score", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column("title_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("image_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("bullet_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("a_plus_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("video_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("backend_kw_score", sa.Numeric(precision=5, scale=2), nullable=True),
        # Pricing dynamics (90-day)
        sa.Column("price_90d_min", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("price_90d_max", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("price_90d_avg", sa.Numeric(precision=10, scale=2), nullable=True),
        # Promotions
        sa.Column("has_subscribe_save", sa.Boolean(), nullable=True),
        sa.Column("coupon_frequency", sa.Integer(), nullable=True),
        sa.Column("lightning_deal_frequency", sa.Integer(), nullable=True),
        # Review metrics
        sa.Column("review_velocity", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("sentiment_score", sa.Numeric(precision=5, scale=2), nullable=True),
        # Vulnerability
        sa.Column("vulnerability", sa.String(length=20), nullable=True),
        sa.Column("vulnerability_type", sa.String(length=50), nullable=True),
        sa.Column("last_analyzed_at", postgresql.TIMESTAMPTZ(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["niche_id"],
            ["niches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "niche_id", "product_id", name="uq_competitors_niche_product"
        ),
    )

    # ── financial_projections ───────────────────────────────────────
    op.create_table(
        "financial_projections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("niche_id", sa.BigInteger(), nullable=False),
        sa.Column("scenario", sa.String(length=10), nullable=True),
        sa.Column("week_number", sa.Integer(), nullable=True),
        # Weekly metrics
        sa.Column("estimated_organic_rank", sa.Integer(), nullable=True),
        sa.Column("estimated_units_sold", sa.Integer(), nullable=True),
        # Financials
        sa.Column("revenue", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("cogs", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("fba_fees", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("ad_spend", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("storage_fees", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("net_profit", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "cumulative_profit", sa.Numeric(precision=12, scale=2), nullable=True
        ),
        # Projections
        sa.Column("review_count_projected", sa.Integer(), nullable=True),
        sa.Column(
            "organic_traffic_pct", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column("calculated_at", postgresql.TIMESTAMPTZ(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["niche_id"],
            ["niches.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "niche_id",
            "scenario",
            "week_number",
            name="uq_financial_projections_niche_scenario_week",
        ),
    )

    # ── niche_keywords ──────────────────────────────────────────────
    op.create_table(
        "niche_keywords",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("niche_id", sa.BigInteger(), nullable=False),
        sa.Column("keyword", sa.String(length=500), nullable=False),
        sa.Column("search_volume", sa.Integer(), nullable=True),
        sa.Column("search_volume_trend", sa.String(length=20), nullable=True),
        sa.Column("avg_cpc", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("cpc_trend", sa.String(length=20), nullable=True),
        sa.Column("competition_level", sa.String(length=20), nullable=True),
        sa.Column("organic_result_count", sa.Integer(), nullable=True),
        sa.Column("sponsored_result_count", sa.Integer(), nullable=True),
        sa.Column("relevance_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("last_updated_at", postgresql.TIMESTAMPTZ(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["niche_id"],
            ["niches.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("niche_id", "keyword", name="uq_niche_keywords_niche_kw"),
    )

    # ── ppc_keywords ────────────────────────────────────────────────
    op.create_table(
        "ppc_keywords",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("niche_id", sa.BigInteger(), nullable=False),
        sa.Column("keyword", sa.String(length=500), nullable=False),
        sa.Column("match_type", sa.String(length=20), nullable=False),
        sa.Column("suggested_bid", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("estimated_cpc", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("estimated_impressions_daily", sa.Integer(), nullable=True),
        sa.Column("estimated_clicks_daily", sa.Integer(), nullable=True),
        sa.Column(
            "estimated_conversion_rate",
            sa.Numeric(precision=5, scale=4),
            nullable=True,
        ),
        sa.Column("estimated_acos", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("bid_trend_30d", sa.String(length=20), nullable=True),
        sa.Column("last_updated_at", postgresql.TIMESTAMPTZ(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["niche_id"],
            ["niches.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "niche_id",
            "keyword",
            "match_type",
            name="uq_ppc_keywords_niche_kw_match",
        ),
    )

    # ── reviews ─────────────────────────────────────────────────────
    op.create_table(
        "reviews",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("asin", sa.String(length=20), nullable=True),
        sa.Column("review_id", sa.String(length=50), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("verified_purchase", sa.Boolean(), nullable=True),
        sa.Column(
            "helpful_votes", sa.Integer(), server_default="0", nullable=True
        ),
        sa.Column("is_vine", sa.Boolean(), nullable=True),
        sa.Column("scraped_at", postgresql.TIMESTAMPTZ(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("review_id"),
    )

    # ── review_pain_points ──────────────────────────────────────────
    op.create_table(
        "review_pain_points",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("niche_id", sa.BigInteger(), nullable=False),
        sa.Column("cluster_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mention_count", sa.Integer(), nullable=True),
        sa.Column("mention_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("sample_quotes", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["niche_id"],
            ["niches.id"],
            ondelete="CASCADE",
        ),
    )

    # ── suppliers ───────────────────────────────────────────────────
    op.create_table(
        "suppliers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("niche_id", sa.BigInteger(), nullable=False),
        sa.Column("supplier_name", sa.String(length=500), nullable=True),
        sa.Column("alibaba_url", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("years_in_business", sa.Integer(), nullable=True),
        # Verification flags
        sa.Column("is_gold_supplier", sa.Boolean(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=True),
        sa.Column("is_audited", sa.Boolean(), nullable=True),
        sa.Column("trade_assurance", sa.Boolean(), nullable=True),
        # Performance metrics
        sa.Column("transaction_volume", sa.Integer(), nullable=True),
        sa.Column("repeat_buyer_rate", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("response_rate", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "response_time_hours", sa.Numeric(precision=8, scale=2), nullable=True
        ),
        # Pricing & logistics
        sa.Column("moq", sa.Integer(), nullable=True),
        sa.Column("moq_flexible", sa.Boolean(), nullable=True),
        sa.Column("fob_price_min", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("fob_price_max", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("sample_cost", sa.Numeric(precision=10, scale=2), nullable=True),
        # Scoring
        sa.Column("supplier_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("risk_flags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("price_tiers", postgresql.JSONB(), nullable=True),
        sa.Column("last_updated_at", postgresql.TIMESTAMPTZ(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["niche_id"],
            ["niches.id"],
            ondelete="CASCADE",
        ),
    )

    # ── landed_cost_calculations ────────────────────────────────────
    op.create_table(
        "landed_cost_calculations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), nullable=False),
        sa.Column("niche_id", sa.BigInteger(), nullable=False),
        sa.Column("order_quantity", sa.Integer(), nullable=True),
        sa.Column("shipping_mode", sa.String(length=20), nullable=True),
        # Per-unit cost breakdown
        sa.Column(
            "unit_product_cost", sa.Numeric(precision=10, scale=4), nullable=True
        ),
        sa.Column(
            "unit_shipping_cost", sa.Numeric(precision=10, scale=4), nullable=True
        ),
        sa.Column(
            "unit_duty_cost", sa.Numeric(precision=10, scale=4), nullable=True
        ),
        sa.Column(
            "unit_customs_fee", sa.Numeric(precision=10, scale=4), nullable=True
        ),
        sa.Column(
            "unit_inspection_cost", sa.Numeric(precision=10, scale=4), nullable=True
        ),
        sa.Column(
            "unit_packaging_cost", sa.Numeric(precision=10, scale=4), nullable=True
        ),
        sa.Column(
            "unit_labeling_cost", sa.Numeric(precision=10, scale=4), nullable=True
        ),
        sa.Column(
            "unit_prep_cost", sa.Numeric(precision=10, scale=4), nullable=True
        ),
        sa.Column(
            "unit_insurance_cost", sa.Numeric(precision=10, scale=4), nullable=True
        ),
        sa.Column(
            "total_landed_cost", sa.Numeric(precision=10, scale=4), nullable=True
        ),
        sa.Column("calculated_at", postgresql.TIMESTAMPTZ(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["niche_id"],
            ["niches.id"],
            ondelete="CASCADE",
        ),
    )

    # ── recommendations ─────────────────────────────────────────────
    op.create_table(
        "recommendations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("niche_id", sa.BigInteger(), nullable=False),
        # Core scores
        sa.Column("omniscient_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("confidence_tier", sa.String(length=20), nullable=False),
        # Product strategy
        sa.Column("product_description", sa.Text(), nullable=True),
        sa.Column(
            "differentiation_features",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "top_supplier_ids",
            postgresql.ARRAY(sa.BigInteger()),
            nullable=True,
        ),
        # Unit economics
        sa.Column(
            "best_landed_cost", sa.Numeric(precision=10, scale=4), nullable=True
        ),
        sa.Column(
            "recommended_sale_price", sa.Numeric(precision=10, scale=2), nullable=True
        ),
        sa.Column(
            "estimated_net_margin_pct",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
        # Break-even timelines
        sa.Column("break_even_week_bull", sa.Integer(), nullable=True),
        sa.Column("break_even_week_base", sa.Integer(), nullable=True),
        sa.Column("break_even_week_bear", sa.Integer(), nullable=True),
        # Launch capital
        sa.Column(
            "total_launch_capital", sa.Numeric(precision=12, scale=2), nullable=True
        ),
        # Reviews strategy
        sa.Column("review_threshold", sa.Integer(), nullable=True),
        sa.Column("weeks_to_review_threshold", sa.Integer(), nullable=True),
        sa.Column("vine_recommended", sa.Boolean(), nullable=True),
        sa.Column("vine_cost", sa.Numeric(precision=10, scale=2), nullable=True),
        # PPC strategy
        sa.Column("ppc_budget_30d", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("ppc_budget_90d", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("break_even_acos", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("estimated_acos", sa.Numeric(precision=5, scale=2), nullable=True),
        # JSONB payloads
        sa.Column("marketing_channels", postgresql.JSONB(), nullable=True),
        sa.Column("risk_flags", postgresql.JSONB(), nullable=True),
        sa.Column("launch_playbook", postgresql.JSONB(), nullable=True),
        sa.Column("ppc_strategy", postgresql.JSONB(), nullable=True),
        sa.Column("generated_at", postgresql.TIMESTAMPTZ(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["niche_id"],
            ["niches.id"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("recommendations")
    op.drop_table("landed_cost_calculations")
    op.drop_table("suppliers")
    op.drop_table("review_pain_points")
    op.drop_table("reviews")
    op.drop_table("ppc_keywords")
    op.drop_table("niche_keywords")
    op.drop_table("financial_projections")
    op.drop_table("competitors")
    op.drop_index("ix_price_history_time_product", table_name="price_history")
    op.drop_table("price_history")
    op.drop_index("ix_bsr_history_time_product", table_name="bsr_history")
    op.drop_table("bsr_history")
    op.drop_table("user_settings")
    op.drop_table("products")
    op.drop_table("niches")
