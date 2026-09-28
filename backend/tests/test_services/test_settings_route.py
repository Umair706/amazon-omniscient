"""The settings route validates and stores the scoring config, and exposes defaults."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.settings import get_scoring_defaults, update_settings
from app.models.user_settings import UserSettings
from app.schemas.settings import UserSettingsUpdate


def _fake_db(existing: UserSettings):
    """A fake AsyncSession that returns `existing` and no-ops writes."""
    result = SimpleNamespace(scalar_one_or_none=lambda: existing)

    async def execute(*_args, **_kwargs):
        return result

    async def flush():
        return None

    async def refresh(_obj):
        return None

    return SimpleNamespace(execute=execute, add=lambda _obj: None, flush=flush, refresh=refresh)


async def test_valid_config_is_stored():
    settings = UserSettings(id=1, user_id="default")
    payload = UserSettingsUpdate(scoring_config={"thresholds": {"AU": {"price_max": 150}}})
    await update_settings(payload, db=_fake_db(settings))
    assert settings.scoring_config["thresholds"]["AU"]["price_max"] == 150


async def test_invalid_config_is_rejected_with_422():
    settings = UserSettings(id=1, user_id="default")
    payload = UserSettingsUpdate(scoring_config={"thresholds": {"AU": {"price_min": 90, "price_max": 30}}})
    with pytest.raises(HTTPException) as raised:
        await update_settings(payload, db=_fake_db(settings))
    assert raised.value.status_code == 422
    assert "scoring_config" in raised.value.detail


async def test_null_config_resets_to_defaults():
    settings = UserSettings(id=1, user_id="default")
    settings.scoring_config = {"sales_multiplier": {"AU": 2.0}}
    payload = UserSettingsUpdate(scoring_config=None)
    await update_settings(payload, db=_fake_db(settings))
    assert settings.scoring_config is None


async def test_scoring_defaults_expose_a_valid_weight_set():
    defaults = await get_scoring_defaults()
    assert defaults["thresholds"]["AU"]["price_max"] == 100
    assert abs(sum(defaults["weights"].values()) - 1.0) < 0.001
