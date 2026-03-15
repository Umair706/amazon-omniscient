"""Add intelligence JSONB columns to recommendations and product_supplier_matches table.

Revision ID: 006
Revises: 005
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add intelligence JSONB columns to recommendations
    op.add_column("recommendations", sa.Column("niche_overview", JSONB, nullable=True))
    op.add_column("recommendations", sa.Column("product_overviews", JSONB, nullable=True))
    op.add_column("recommendations", sa.Column("product_ideas", JSONB, nullable=True))
    op.add_column("recommendations", sa.Column("review_intelligence", JSONB, nullable=True))
    op.add_column("recommendations", sa.Column("product_supplier_matches", JSONB, nullable=True))

    # Add image_url to products
    op.add_column("products", sa.Column("image_url", sa.Text(), nullable=True))

    # Create product_supplier_matches table
    op.create_table(
        "product_supplier_matches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            sa.BigInteger(),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("match_reasoning", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_product_supplier_matches_product_id",
        "product_supplier_matches",
        ["product_id"],
    )
    op.create_index(
        "ix_product_supplier_matches_supplier_id",
        "product_supplier_matches",
        ["supplier_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_supplier_matches_supplier_id", table_name="product_supplier_matches")
    op.drop_index("ix_product_supplier_matches_product_id", table_name="product_supplier_matches")
    op.drop_table("product_supplier_matches")

    op.drop_column("products", "image_url")

    op.drop_column("recommendations", "product_supplier_matches")
    op.drop_column("recommendations", "review_intelligence")
    op.drop_column("recommendations", "product_ideas")
    op.drop_column("recommendations", "product_overviews")
    op.drop_column("recommendations", "niche_overview")
