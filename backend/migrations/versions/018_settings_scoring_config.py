"""Replace the individual threshold columns with one scoring_config JSON.

A seller can now tune the whole scoring thesis (all hard-filter thresholds
per marketplace, the sub-score weights, the sales multiplier, and the seasonal
allowance), not just three values. Storing that as one JSON column keeps the
schema flat instead of sprouting a column per knob. NULL means "use the
built-in defaults".

The three old columns (min_margin_threshold, max_review_moat, allow_seasonal)
are folded into that config and dropped.

Revision ID: 018
Revises: 017
Create Date: 2026-09-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("scoring_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.drop_column("user_settings", "min_margin_threshold")
    op.drop_column("user_settings", "max_review_moat")
    op.drop_column("user_settings", "allow_seasonal")


def downgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("allow_seasonal", sa.Boolean(), server_default="false", nullable=True),
    )
    op.add_column(
        "user_settings",
        sa.Column("max_review_moat", sa.Integer(), nullable=True),
    )
    op.add_column(
        "user_settings",
        sa.Column("min_margin_threshold", sa.Numeric(5, 2), nullable=True),
    )
    op.drop_column("user_settings", "scoring_config")
