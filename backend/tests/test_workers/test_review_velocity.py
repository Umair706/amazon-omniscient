from datetime import datetime, timedelta, timezone

from app.workers.pipeline_steps.review_velocity import windows_from_rows

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_windows_take_first_and_last_snapshot_per_product():
    rows = [
        (1, 500, T0, 100), (1, 500, T0 + timedelta(days=10), 110), (1, 500, T0 + timedelta(days=20), 125),
        (2, 800, T0, 40),
        (3, None, T0, 10), (3, None, T0 + timedelta(days=20), 12),
    ]
    windows = windows_from_rows(rows)
    assert windows == [{"bsr": 500, "first": (T0, 100), "last": (T0 + timedelta(days=20), 125)},
                       {"bsr": 800, "first": (T0, 40), "last": (T0, 40)}]
