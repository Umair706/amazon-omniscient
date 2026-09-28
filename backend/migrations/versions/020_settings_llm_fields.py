"""Store the seller's LLM provider, model, and key on their settings.

The Settings LLM card used to discard what the user typed — there was nowhere
to put it. These columns give it a home, and the pipeline overlays them onto
the server defaults when building the LLM client.

Revision ID: 020
Revises: 019
Create Date: 2026-09-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("llm_provider", sa.String(length=30), nullable=True))
    op.add_column("user_settings", sa.Column("llm_model", sa.String(length=100), nullable=True))
    op.add_column("user_settings", sa.Column("llm_api_key_encrypted", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "llm_api_key_encrypted")
    op.drop_column("user_settings", "llm_model")
    op.drop_column("user_settings", "llm_provider")
