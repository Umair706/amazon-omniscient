"""Load a seller's own scoring settings and apply them to the metrics.

A seller can tune two hard filters (minimum margin, maximum review moat) and
the seasonal allowance in Settings. This step reads those and injects them
into the metrics dict so ScoringService honours them. When a setting is NULL,
we leave it out so the marketplace default applies.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_settings import UserSettings

# Single-user id until authentication is wired up. Matches app/api/settings.py.
_DEFAULT_USER_ID = "default"


def overrides_from_settings(settings: UserSettings | None) -> dict:
    """Map a settings row to scoring overrides. Pure — no database access.

    Keys, when present: allow_seasonal (bool), min_margin_override (float),
    review_moat_override (int). A None settings row yields an empty dict.
    """
    if settings is None:
        return {}

    overrides: dict = {}

    # allow_seasonal is a real preference even when False, so always carry it.
    if settings.allow_seasonal is not None:
        overrides["allow_seasonal"] = bool(settings.allow_seasonal)

    # A NULL threshold means "use the marketplace default" — skip it.
    if settings.min_margin_threshold is not None:
        overrides["min_margin_override"] = float(settings.min_margin_threshold)

    if settings.max_review_moat is not None:
        overrides["review_moat_override"] = int(settings.max_review_moat)

    return overrides


async def load_seller_overrides(db: AsyncSession, user_id: str = _DEFAULT_USER_ID) -> dict:
    """Return the seller's scoring overrides, or empty when none are set."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    return overrides_from_settings(result.scalar_one_or_none())


def apply_seller_overrides(metrics: dict, overrides: dict) -> None:
    """Copy the seller's overrides into the metrics dict, in place."""
    for key, value in overrides.items():
        metrics[key] = value
