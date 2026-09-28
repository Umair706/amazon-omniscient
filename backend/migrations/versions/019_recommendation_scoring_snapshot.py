"""Record the scoring rules each recommendation was computed under.

Scores now depend on the seller's tunable config, so a stored recommendation
is only meaningful alongside the rules it was scored under. We snapshot the
fully-resolved config (defaults + overrides) and a short fingerprint of it onto
each recommendation, so results stay reproducible and comparable after the
settings change.

Revision ID: 019
Revises: 018
Create Date: 2026-09-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column("scoring_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column("scoring_fingerprint", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recommendations", "scoring_fingerprint")
    op.drop_column("recommendations", "scoring_snapshot")
