"""Add enriched product data columns.

Adds columns for: list_price, date_first_available, star_distribution,
variation_count, category_path, seller_count, fbt_asins, qa_count,
deal_badge, amazons_choice_keyword, review_attributes, comparison_asins, weight.

Revision ID: 011
Revises: 010
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("list_price", sa.Numeric(10, 2), nullable=True))
    op.add_column("products", sa.Column("date_first_available", sa.Date(), nullable=True))
    op.add_column("products", sa.Column("star_distribution", JSONB(), nullable=True))
    op.add_column("products", sa.Column("variation_count", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("category_path", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("seller_count", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("fbt_asins", JSONB(), nullable=True))
    op.add_column("products", sa.Column("qa_count", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("deal_badge", sa.String(100), nullable=True))
    op.add_column("products", sa.Column("amazons_choice_keyword", sa.String(255), nullable=True))
    op.add_column("products", sa.Column("review_attributes", JSONB(), nullable=True))
    op.add_column("products", sa.Column("comparison_asins", JSONB(), nullable=True))
    op.add_column("products", sa.Column("weight", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "weight")
    op.drop_column("products", "comparison_asins")
    op.drop_column("products", "review_attributes")
    op.drop_column("products", "amazons_choice_keyword")
    op.drop_column("products", "deal_badge")
    op.drop_column("products", "qa_count")
    op.drop_column("products", "fbt_asins")
    op.drop_column("products", "seller_count")
    op.drop_column("products", "category_path")
    op.drop_column("products", "variation_count")
    op.drop_column("products", "star_distribution")
    op.drop_column("products", "date_first_available")
    op.drop_column("products", "list_price")
