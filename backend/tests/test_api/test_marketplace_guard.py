"""The multi_marketplace gate: one marketplace free, a second distinct one needs the feature."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.jobs import _guard_marketplace
from app.licensing import FEATURE_MULTI_MARKETPLACE, License


def _db_with_marketplaces(values: list) -> SimpleNamespace:
    """A fake AsyncSession whose execute(...).scalars().all() returns `values`."""
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: values))
    return SimpleNamespace(execute=AsyncMock(return_value=result))


def _free() -> License:
    return License.free("no license configured")


def _multi() -> License:
    return License.licensed(
        customer="x", tier="agency", features=frozenset({FEATURE_MULTI_MARKETPLACE}),
        issued_at=0, expires_at=9_999_999_999,
    )


async def test_first_marketplace_is_free():
    await _guard_marketplace(_db_with_marketplaces([]), "US", _free())  # no rows yet -> allowed


async def test_same_marketplace_again_is_free():
    await _guard_marketplace(_db_with_marketplaces(["US"]), "US", _free())


async def test_second_distinct_marketplace_is_blocked_on_free_tier():
    with pytest.raises(HTTPException) as raised:
        await _guard_marketplace(_db_with_marketplaces(["US"]), "AU", _free())
    assert raised.value.status_code == 402
    assert raised.value.detail["feature"] == FEATURE_MULTI_MARKETPLACE


async def test_second_marketplace_allowed_with_the_feature():
    await _guard_marketplace(_db_with_marketplaces(["US"]), "AU", _multi())
