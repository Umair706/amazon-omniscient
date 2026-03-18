"""Add marketplace column to niches table.

Changes the unique constraint from primary_keyword alone to a composite
(primary_keyword, marketplace) so the same keyword can be analyzed in
different marketplaces.

Revision ID: 008
Revises: 007
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add marketplace column with default "US"
    op.add_column(
        "niches",
        sa.Column("marketplace", sa.String(10), nullable=False, server_default="US"),
    )

    # Drop old unique constraint on primary_keyword
    # The constraint name may vary — use batch mode for safety
    op.drop_constraint("niches_primary_keyword_key", "niches", type_="unique")

    # Create composite unique constraint
    op.create_unique_constraint(
        "uq_niches_keyword_marketplace",
        "niches",
        ["primary_keyword", "marketplace"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_niches_keyword_marketplace", "niches", type_="unique")
    op.create_unique_constraint(
        "niches_primary_keyword_key", "niches", ["primary_keyword"]
    )
    op.drop_column("niches", "marketplace")
