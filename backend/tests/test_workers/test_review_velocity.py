from datetime import datetime, timedelta, timezone

import pytest

from app.workers.pipeline_steps import review_velocity
from app.workers.pipeline_steps.review_velocity import apply_review_velocity, windows_from_rows

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
OBSERVED_GAP = 7.5


def test_windows_take_first_and_last_snapshot_per_product():
    rows = [
        (1, 500, T0, 100), (1, 500, T0 + timedelta(days=10), 110), (1, 500, T0 + timedelta(days=20), 125),
        (2, 800, T0, 40),
        (3, None, T0, 10), (3, None, T0 + timedelta(days=20), 12),
    ]
    windows = windows_from_rows(rows)
    assert windows == [{"bsr": 500, "first": (T0, 100), "last": (T0 + timedelta(days=20), 125)},
                       {"bsr": 800, "first": (T0, 40), "last": (T0, 40)}]


def _stub_gap(monkeypatch, gap):
    async def fake_gap_for_niche(db, niche_id, *, estimator, category):
        return gap
    monkeypatch.setattr(review_velocity, "review_velocity_gap_for_niche", fake_gap_for_niche)


@pytest.mark.asyncio
async def test_filter_off_stores_only_the_observed_ratio(monkeypatch):
    _stub_gap(monkeypatch, OBSERVED_GAP)
    metrics = {}
    await apply_review_velocity(None, 1, metrics, marketplace="US", filter_enabled=False)
    assert metrics == {"review_velocity_gap_ratio": OBSERVED_GAP}


@pytest.mark.asyncio
async def test_filter_on_also_feeds_the_hard_filter(monkeypatch):
    _stub_gap(monkeypatch, OBSERVED_GAP)
    metrics = {}
    await apply_review_velocity(None, 1, metrics, marketplace="US", filter_enabled=True)
    assert metrics == {"review_velocity_gap_ratio": OBSERVED_GAP, "avg_review_velocity_gap_ratio": OBSERVED_GAP}


@pytest.mark.asyncio
async def test_no_window_yet_sets_nothing(monkeypatch):
    _stub_gap(monkeypatch, None)
    metrics = {}
    await apply_review_velocity(None, 1, metrics, marketplace="US", filter_enabled=True)
    assert metrics == {}
