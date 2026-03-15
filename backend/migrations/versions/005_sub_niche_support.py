"""Add sub-niche support columns to niches.

Revision ID: 005
Revises: 004
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "niches",
        sa.Column("parent_niche_id", sa.BigInteger(), sa.ForeignKey("niches.id"), nullable=True),
    )
    op.add_column(
        "niches",
        sa.Column("sub_niche_label", sa.String(255), nullable=True),
    )
    op.add_column(
        "niches",
        sa.Column("sub_niche_metadata", sa.JSON(), nullable=True),
    )
    op.create_index("ix_niches_parent_niche_id", "niches", ["parent_niche_id"])


def downgrade() -> None:
    op.drop_index("ix_niches_parent_niche_id", table_name="niches")
    op.drop_column("niches", "sub_niche_metadata")
    op.drop_column("niches", "sub_niche_label")
    op.drop_column("niches", "parent_niche_id")
