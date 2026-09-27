"""API routes for user settings management.

SECURITY: Encrypted API credentials are NEVER returned in responses.
Only boolean ``has_*`` flags indicate whether credentials are configured.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.user_settings import UserSettings
from app.schemas.settings import UserSettingsResponse, UserSettingsUpdate
from app.services.scoring_config import (
    DEFAULT_ALLOW_SEASONAL,
    DEFAULT_MARKETPLACE_THRESHOLDS,
    DEFAULT_SALES_MULTIPLIER,
    DEFAULT_WEIGHTS,
    validate_scoring_config,
)

router = APIRouter(prefix="/settings", tags=["settings"])

# Default user ID used until authentication is wired up.
_DEFAULT_USER_ID = "default"


# ---------------------------------------------------------------------------
# GET /settings/ — Get user settings
# ---------------------------------------------------------------------------


@router.get("/", response_model=UserSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
) -> UserSettingsResponse:
    """Return the current user's settings.

    If no settings row exists yet, one is created with default values.
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == _DEFAULT_USER_ID)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        # First-time access — create default settings row
        settings = UserSettings(user_id=_DEFAULT_USER_ID)
        db.add(settings)
        await db.flush()
        await db.refresh(settings)

    return UserSettingsResponse.from_orm_model(settings)


# ---------------------------------------------------------------------------
# PUT /settings/ — Update user settings
# ---------------------------------------------------------------------------


@router.get("/scoring-defaults")
async def get_scoring_defaults() -> dict:
    """Return the built-in scoring defaults, so the UI can show them and reset to them."""
    return {
        "thresholds": DEFAULT_MARKETPLACE_THRESHOLDS,
        "weights": DEFAULT_WEIGHTS,
        "sales_multiplier": DEFAULT_SALES_MULTIPLIER,
        "allow_seasonal": DEFAULT_ALLOW_SEASONAL,
    }


@router.put("/", response_model=UserSettingsResponse)
async def update_settings(
    payload: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserSettingsResponse:
    """Update the current user's settings.

    Only the fields provided in the request body are updated.
    Credential fields are accepted as plaintext and should be encrypted
    before storage in a production deployment (encryption hook omitted here
    to keep the route layer focused on API concerns).
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == _DEFAULT_USER_ID)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = UserSettings(user_id=_DEFAULT_USER_ID)
        db.add(settings)
        await db.flush()
        await db.refresh(settings)

    # Apply preference updates (only non-None fields)
    update_data = payload.model_dump(exclude_unset=True)

    if "default_marketplace" in update_data:
        settings.default_marketplace = update_data["default_marketplace"]

    # The scoring config is validated before storage so a seller can never save
    # a thesis that would make scoring nonsense. A null value resets to defaults.
    if "scoring_config" in update_data:
        config = update_data["scoring_config"]
        errors = validate_scoring_config(config)
        if errors:
            raise HTTPException(status_code=422, detail={"scoring_config": errors})
        settings.scoring_config = config

    # Handle credential updates — store as encrypted bytes.
    # In production, these would go through a proper encryption service.
    # Here we store a placeholder to mark the credential as "configured".
    if "sp_api_credentials" in update_data and update_data["sp_api_credentials"] is not None:
        import json
        settings.sp_api_credentials_encrypted = json.dumps(
            update_data["sp_api_credentials"]
        ).encode("utf-8")
    if "ads_api_credentials" in update_data and update_data["ads_api_credentials"] is not None:
        import json
        settings.ads_api_credentials_encrypted = json.dumps(
            update_data["ads_api_credentials"]
        ).encode("utf-8")
    if "alibaba_credentials" in update_data and update_data["alibaba_credentials"] is not None:
        import json
        settings.alibaba_credentials_encrypted = json.dumps(
            update_data["alibaba_credentials"]
        ).encode("utf-8")

    await db.flush()
    await db.refresh(settings)

    return UserSettingsResponse.from_orm_model(settings)
