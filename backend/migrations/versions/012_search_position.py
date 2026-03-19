"""Add search_position column to products table.

Tracks the organic rank position of a product in Amazon search results
for its niche keyword.

Revision ID: 012
Revises: 011
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("search_position", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "search_position")
