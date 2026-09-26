"""Mapping seller settings to scoring overrides, and applying them."""

from decimal import Decimal
from types import SimpleNamespace

from app.workers.pipeline_steps.seller_overrides import (
    apply_seller_overrides,
    overrides_from_settings,
)


def _settings(**kwargs):
    # A stand-in for a UserSettings row with just the fields we read.
    base = {"allow_seasonal": None, "min_margin_threshold": None, "max_review_moat": None}
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_no_settings_row_yields_no_overrides():
    assert overrides_from_settings(None) == {}


def test_null_thresholds_are_skipped_so_marketplace_default_applies():
    result = overrides_from_settings(_settings(allow_seasonal=False))
    assert "min_margin_override" not in result
    assert "review_moat_override" not in result
    assert result["allow_seasonal"] is False


def test_set_thresholds_become_overrides_with_the_right_types():
    result = overrides_from_settings(
        _settings(min_margin_threshold=Decimal("40.00"), max_review_moat=5000, allow_seasonal=True)
    )
    assert result["min_margin_override"] == 40.0
    assert isinstance(result["min_margin_override"], float)
    assert result["review_moat_override"] == 5000
    assert result["allow_seasonal"] is True


def test_apply_copies_overrides_into_metrics():
    metrics = {"avg_price": 30}
    apply_seller_overrides(metrics, {"min_margin_override": 40.0})
    assert metrics["min_margin_override"] == 40.0
    assert metrics["avg_price"] == 30
