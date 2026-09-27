"""Load the seller's scoring config for an analysis run.

The config tunes the scoring thesis: hard-filter thresholds, sub-score weights,
the sales multiplier, and the seasonal allowance. It is stored as one JSON blob
on the user's settings row (shape and defaults in app/services/scoring_config.py).
The full-analysis task loads it once, threads the sales multiplier into the
BSR-to-sales estimates, and passes the raw config to ScoringService.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_settings import UserSettings

# Single-user id until authentication is wired up. Matches app/api/settings.py.
_DEFAULT_USER_ID = "default"


async def load_scoring_config(db: AsyncSession, user_id: str = _DEFAULT_USER_ID) -> dict | None:
    """Return the seller's stored scoring config, or None when none is set.

    None tells the scoring layer to use the built-in defaults.
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        return None
    return settings.scoring_config
