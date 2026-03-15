"""Add BSR sub-category columns and review velocity gap support.

Revision ID: 002
Revises: 001
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- BSR sub-category distinction --
    # bsr_history: add category_name and is_subcategory
    op.add_column("bsr_history", sa.Column("category_name", sa.String(255), nullable=True))
    op.add_column("bsr_history", sa.Column("is_subcategory", sa.Boolean(), nullable=False, server_default="false"))

    # products: add subcategory BSR fields
    op.add_column("products", sa.Column("current_subcategory_bsr", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("bsr_category", sa.String(255), nullable=True))
    op.add_column("products", sa.Column("subcategory_name", sa.String(255), nullable=True))

    # -- Review Velocity Gap --
    # competitors: add estimated_monthly_sales for gap calculation
    op.add_column("competitors", sa.Column("estimated_monthly_sales", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("competitors", "estimated_monthly_sales")
    op.drop_column("products", "subcategory_name")
    op.drop_column("products", "bsr_category")
    op.drop_column("products", "current_subcategory_bsr")
    op.drop_column("bsr_history", "is_subcategory")
    op.drop_column("bsr_history", "category_name")
