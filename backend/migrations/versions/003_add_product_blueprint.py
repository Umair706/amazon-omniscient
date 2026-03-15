"""Add product_blueprint and financial_report JSONB columns to recommendations.

Revision ID: 003
Revises: 002
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column("product_blueprint", JSONB, nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column("financial_report", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recommendations", "financial_report")
    op.drop_column("recommendations", "product_blueprint")
