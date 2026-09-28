"""Rename niche score columns to match ScoringService names, add avg_rating,
estimated_monthly_sales, last_error, widen competitors.vulnerability_type,
and add the indexes the list endpoints filter on.

Revision ID: 013
Revises: 012
Create Date: 2026-09-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (old name, new name) — the old names described the wrong thing.
_SCORE_RENAMES = [
    ("sales_velocity_score", "revenue_score"),
    ("marketing_score", "trend_score"),
    ("review_achievability_score", "review_feasibility_score"),
    ("supplier_reliability_score", "supplier_score"),
    ("ad_profitability_score", "ppc_viability_score"),
    ("brand_building_score", "launch_feasibility_score"),
]


def upgrade() -> None:
    for old, new in _SCORE_RENAMES:
        op.alter_column("niches", old, new_column_name=new)
    op.add_column("niches", sa.Column("avg_rating", sa.Numeric(3, 2), nullable=True))
    op.add_column("niches", sa.Column("estimated_monthly_sales", sa.Integer(), nullable=True))
    op.add_column("niches", sa.Column("last_error", sa.Text(), nullable=True))

    op.alter_column("competitors", "vulnerability_type", type_=sa.String(255))

    op.create_index("ix_products_niche_id", "products", ["niche_id"], if_not_exists=True)
    op.create_index("ix_reviews_product_id", "reviews", ["product_id"], if_not_exists=True)
    op.create_index("ix_suppliers_niche_id", "suppliers", ["niche_id"], if_not_exists=True)
    op.create_index("ix_recommendations_niche_id", "recommendations", ["niche_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_recommendations_niche_id", table_name="recommendations")
    op.drop_index("ix_suppliers_niche_id", table_name="suppliers")
    op.drop_index("ix_reviews_product_id", table_name="reviews")
    op.drop_index("ix_products_niche_id", table_name="products")
    # NOTE: narrowing back to String(50) fails on a populated table if any stored
    # vulnerability_type is longer than 50 chars — exactly what upgrade() widened it
    # to allow. Postgres refuses the cast (it does not truncate), so this downgrade is
    # only safe on a database that never wrote a value longer than 50.
    op.alter_column("competitors", "vulnerability_type", type_=sa.String(50))
    op.drop_column("niches", "last_error")
    op.drop_column("niches", "estimated_monthly_sales")
    op.drop_column("niches", "avg_rating")
    for old, new in _SCORE_RENAMES:
        op.alter_column("niches", new, new_column_name=old)
