"""Sales velocity tracking — stock_history hypertable, sales_velocity_snapshots, product columns.

Revision ID: 009
Revises: 008
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── stock_history (TimescaleDB hypertable) ────────────────────────
    op.create_table(
        "stock_history",
        sa.Column("time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asin", sa.String(20)),
        sa.Column("stock_level", sa.Integer(), nullable=True),
        sa.Column("stock_text", sa.String(255), nullable=True),
        sa.Column("is_in_stock", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("time", "product_id"),
    )
    op.create_index("ix_stock_history_time_product", "stock_history", ["time", "product_id"])

    # Convert to TimescaleDB hypertable
    op.execute("SELECT create_hypertable('stock_history', 'time', if_not_exists => TRUE)")

    # ── sales_velocity_snapshots ──────────────────────────────────────
    op.create_table(
        "sales_velocity_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asin", sa.String(20)),
        sa.Column("bsr_start", sa.Integer(), nullable=True),
        sa.Column("bsr_end", sa.Integer(), nullable=True),
        sa.Column("bsr_delta", sa.Integer(), nullable=True),
        sa.Column("bsr_derived_daily_sales", sa.Numeric(10, 2), nullable=True),
        sa.Column("stock_start", sa.Integer(), nullable=True),
        sa.Column("stock_end", sa.Integer(), nullable=True),
        sa.Column("stock_derived_daily_sales", sa.Numeric(10, 2), nullable=True),
        sa.Column("restock_detected", sa.Boolean(), server_default="false"),
        sa.Column("regression_daily_sales", sa.Numeric(10, 2), nullable=True),
        sa.Column("estimated_daily_sales", sa.Numeric(10, 2), nullable=True),
        sa.Column("estimation_method", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "product_id", name="uq_velocity_date_product"),
    )
    op.create_index("ix_velocity_product_date", "sales_velocity_snapshots", ["product_id", "date"])

    # ── New columns on products ───────────────────────────────────────
    op.add_column("products", sa.Column("estimated_daily_sales", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("sales_velocity_trend", sa.String(20), nullable=True))
    op.add_column("products", sa.Column("last_stock_level", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "last_stock_level")
    op.drop_column("products", "sales_velocity_trend")
    op.drop_column("products", "estimated_daily_sales")
    op.drop_table("sales_velocity_snapshots")
    op.drop_table("stock_history")
