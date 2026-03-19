"""Add keyword research columns to niche_keywords.

Revision ID: 010
Revises: 009
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("niche_keywords", sa.Column("source", sa.String(50), nullable=True))
    op.add_column("niche_keywords", sa.Column("autocomplete_depth", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("niche_keywords", "autocomplete_depth")
    op.drop_column("niche_keywords", "source")
