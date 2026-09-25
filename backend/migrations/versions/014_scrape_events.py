"""Add scrape_events, recording the outcome of every page load so block rates
and selector rot are visible instead of only showing up as silent empty results.

Revision ID: 014
Revises: 013
Create Date: 2026-09-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scrape_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("site", sa.String(length=20), nullable=False),
        sa.Column("url_kind", sa.String(length=20), nullable=False),
        sa.Column("verdict", sa.String(length=20), nullable=False),
        sa.Column("proxy_label", sa.String(length=100), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scrape_events_time", "scrape_events", ["time"])


def downgrade() -> None:
    op.drop_index("ix_scrape_events_time", table_name="scrape_events")
    op.drop_table("scrape_events")
