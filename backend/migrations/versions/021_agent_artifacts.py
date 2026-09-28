"""Store agent-written artifacts (business plans, notes, watchlists).

Lets an LLM agent (via the MCP server) persist its own work back into
Omniscient so it survives across sessions.

Revision ID: 021
Revises: 020
Create Date: 2026-09-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("niche_id", sa.BigInteger(), sa.ForeignKey("niches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(length=30), server_default="plan", nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_agent_artifacts_niche_id", "agent_artifacts", ["niche_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_artifacts_niche_id", table_name="agent_artifacts")
    op.drop_table("agent_artifacts")
