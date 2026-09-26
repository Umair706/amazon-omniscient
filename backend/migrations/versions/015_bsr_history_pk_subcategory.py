"""Add is_subcategory to the bsr_history primary key.

A product's main rank and sub-category rank are recorded at the same moment.
With the old key (time, product_id) the second insert collided and poisoned
the whole analysis session.

Revision ID: 015
Revises: 014
Create Date: 2026-09-26

"""
from typing import Sequence, Union

from alembic import op


revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "bsr_history"
_PK_NAME = "bsr_history_pkey"

# WHY: the key name was chosen by Postgres in migration 001 and may differ
# between databases, so we look it up instead of hard-coding it.
_DROP_EXISTING_PK = f"""
DO $$
DECLARE pk_name text;
BEGIN
    SELECT conname INTO pk_name FROM pg_constraint
    WHERE conrelid = '{_TABLE}'::regclass AND contype = 'p';
    IF pk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE {_TABLE} DROP CONSTRAINT %I', pk_name);
    END IF;
END $$;
"""

# NOTE: the old key cannot hold a main and a sub rank taken at the same
# moment, so downgrading must drop the sub-category row of each such pair.
_DELETE_COLLIDING_SUB_RANKS = f"""
DELETE FROM {_TABLE} sub
USING {_TABLE} main
WHERE sub.is_subcategory AND NOT main.is_subcategory
  AND sub.time = main.time AND sub.product_id = main.product_id
"""


def upgrade() -> None:
    op.execute(_DROP_EXISTING_PK)
    op.create_primary_key(_PK_NAME, _TABLE, ["time", "product_id", "is_subcategory"])


def downgrade() -> None:
    op.execute(_DELETE_COLLIDING_SUB_RANKS)
    op.execute(_DROP_EXISTING_PK)
    op.create_primary_key(_PK_NAME, _TABLE, ["time", "product_id"])
