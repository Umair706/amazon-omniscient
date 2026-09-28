"""Store the review count on main-rank BSR snapshots.

The periodic tracker already visits every product page; recording the review
count each time gives a time series from which a recent review velocity can
be derived. Lifetime review counts over-count launch bursts, so the
review-velocity hard filter needs this window.

Revision ID: 016
Revises: 015
Create Date: 2026-09-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bsr_history", sa.Column("review_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("bsr_history", "review_count")
