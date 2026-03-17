"""Add subscore_breakdown and competitor_landscape JSONB columns to recommendations.

Revision ID: 007
Revises: 006
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recommendations", sa.Column("subscore_breakdown", JSONB, nullable=True))
    op.add_column("recommendations", sa.Column("competitor_landscape", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("recommendations", "competitor_landscape")
    op.drop_column("recommendations", "subscore_breakdown")
