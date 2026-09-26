"""Let seller threshold settings fall back to per-marketplace defaults.

The scoring service has different hard-filter thresholds per marketplace
(e.g. AU tolerates a review moat of 500, the US 2000). The two tunable
settings columns used to carry US-centric server defaults (25.00 and 2000),
so a fresh settings row silently forced US thresholds onto AU analyses.

We now treat NULL as "use the marketplace default" and a real value as a
deliberate seller override. This drops the server defaults and clears any
existing rows that still hold the old implicit defaults, so untouched
settings fall back to the correct per-marketplace values.

Revision ID: 017
Revises: 016
Create Date: 2026-09-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The old server defaults. A row still holding these was never touched by a
# seller, so it should fall back to the marketplace default (NULL).
_OLD_DEFAULT_MARGIN = "25.00"
_OLD_DEFAULT_REVIEW_MOAT = "2000"


def upgrade() -> None:
    op.alter_column("user_settings", "min_margin_threshold", server_default=None)
    op.alter_column("user_settings", "max_review_moat", server_default=None)
    op.execute(
        f"UPDATE user_settings SET min_margin_threshold = NULL "
        f"WHERE min_margin_threshold = {_OLD_DEFAULT_MARGIN}"
    )
    op.execute(
        f"UPDATE user_settings SET max_review_moat = NULL "
        f"WHERE max_review_moat = {_OLD_DEFAULT_REVIEW_MOAT}"
    )


def downgrade() -> None:
    op.alter_column(
        "user_settings", "min_margin_threshold", server_default=_OLD_DEFAULT_MARGIN
    )
    op.alter_column(
        "user_settings", "max_review_moat", server_default=_OLD_DEFAULT_REVIEW_MOAT
    )
