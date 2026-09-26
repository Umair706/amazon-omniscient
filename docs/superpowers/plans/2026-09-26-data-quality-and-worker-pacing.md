# Data Quality & Worker Pacing — Implementation Plan (tranche 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Omniscient Score admit what it does not know (no more fabricated supplier inputs), arm the review-velocity hard filter on a real recent-window signal, stop every niche query from dragging its whole object graph out of Postgres, give the dashboard server-side numbers, and make scrape pacing hold across all Celery worker processes.

**Architecture:** Five independent parts, each shippable on its own. Part D (data honesty) adds a `data_gaps` list that travels with the scoring metrics into the recommendation's existing `risk_flags` JSONB (no migration) and replaces the silent `setdefault` block with one named module. Part E (velocity) records `review_count` on main-rank BSR snapshots (migration 016) and derives reviews-per-month from the first and last snapshot ≥ 14 days apart. Part F (ORM/API) flips `lazy="selectin"` to `lazy="raise"` so accidental graph loads fail loudly, adds the first HTTP-level tests, and a `/niches/stats` endpoint. Part G (pacing) adds a Redis-backed pacer with the same `wait_turn` contract, injected wherever a browser is built.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Celery 5, Playwright, redis-py asyncio, pytest (`asyncio_mode=auto`, `AsyncMock`), httpx `ASGITransport`, Next.js 14 / TypeScript.

**Spec:** The findings table below (derived from the post-merge survey of PR #1) is the spec. There is no separate spec document.

## Global Constraints

- Python `>=3.12`; no new dependencies. `httpx>=0.28.0` is already in the dev extras.
- Follow the repo's engineering rules in `~/.claude/CLAUDE.md`: functions < 30 lines, new files < 200 lines, no magic numbers, `# WHY:` / `# NOTE:` comments only where the reason is non-obvious.
- Next Alembic migration is `"016"`, `down_revision = "015"`, file `backend/migrations/versions/016_<slug>.py`, header style copied from `015_bsr_history_pk_subcategory.py`.
- Run tests from `backend/` with `pytest -q`. All 232 currently collected tests must stay green after every task. DB-backed tests skip unless `TEST_DATABASE_URL` is set (see `tests/test_db/test_bsr_snapshot_db.py`).
- `ScoringService` weights and thresholds do not change. The only scoring-logic change is the explicit "supplier data unknown" path in Task D1.
- `tasks.py` must not grow: new logic goes in `app/workers/pipeline_steps/` or `app/services/`.
- Frontend changes must pass `npx tsc --noEmit` from `frontend/`. Never commit `frontend/tsconfig.tsbuildinfo`.
- Commit after every task with a message that states the *why*.

---

## Findings this plan fixes (the spec)

| ID | Finding | Business impact |
|----|---------|-----------------|
| F15 | `_enrich_metrics` (`tasks.py:1881-1890`) injects `supplier_count=5`, `best_supplier_score=70`, `min_moq=500` when 1688 returned nothing → `_score_supplier` returns a fabricated 66/100. Nothing records that these were assumptions. Same for `search_volume=3000`, `monthly_revenue_per_seller=5000`, `break_even_week_base=16`, and FOB estimated as 15 % of price. | The brief presents guesses as measurements; a seller cannot tell a real supplier landscape from an outage |
| F16 | `average_review_velocity_gap` is never called; hard filter #9 never runs. Lifetime review/months-listed over-counts launch bursts, so it cannot simply be wired in. | Grey-hat review niches are never flagged |
| F17 | `bsr_history` has no `review_count`; `scrape_rank_snapshot` does not parse it. There is no time series from which a recent review velocity could be derived. | Blocks F16 |
| F18 | All 10 `Niche` relationships and 4 `Product` collections are `lazy="selectin"`. Every `select(Niche)` (list, get, delete, every "exists" pre-check) fans out into up to 10 extra queries pulling products, projections, keywords, etc. that the response never uses. `list_niches` at 20/page can issue ~200 queries. | API latency grows with data volume; DB load |
| F19 | The dashboard fetches 100 niches and averages scores in the browser → wrong once there are > 100 niches; `recent-niches-table` sorts by a field the API does not know. | Dashboard numbers silently wrong |
| F20 | `Pacer` state is per worker process; with `--concurrency=4` Amazon sees ~4× the configured rate. `SupplierScraper` has its own private sleeps and never uses the pacer at all. | The pacing built in PR #1 does not hold in production |
| F21 | Zero HTTP-level tests; no way to catch a route regression (including the `lazy="raise"` change) without running the stack. | Blocks safe change to F18 |

Deferred deliberately (see "Decisions" at the end): pagination on niche sub-resource lists, authentication, rate limiting, prompt-injection hardening, BSR coefficient calibration for AU.

---

# Part D — Say what we don't know

## File structure for Part D

```
backend/app/workers/pipeline_steps/assumptions.py   (new) apply_assumed_defaults(metrics) -> list[str]; GAP_* constants
backend/app/services/scoring_service.py             (_score_supplier: explicit unknown path)
backend/app/workers/tasks.py                        (_enrich_metrics uses assumptions; _analyze_suppliers marks estimated FOB)
backend/app/services/recommendation_engine.py       (data_gaps into recommendation_data and risk_flags)
frontend/src/lib/data-gaps.ts                       (new) DATA_GAP_LABELS
frontend/src/app/recommendations/[id]/page.tsx      (Risk Flags card shows data gaps)
backend/tests/test_workers/test_assumptions.py      (new)
backend/tests/test_scoring_service.py               (unknown-supplier test)
```

### Task D1: Data gaps replace fabricated supplier defaults (F15)

**Files:**
- Create: `backend/app/workers/pipeline_steps/assumptions.py`
- Modify: `backend/app/services/scoring_service.py:381-416` (`_score_supplier`)
- Modify: `backend/app/workers/tasks.py:1567-1607` (`_analyze_suppliers`), `backend/app/workers/tasks.py:1881-1890` (`_enrich_metrics` tail)
- Modify: `backend/app/services/recommendation_engine.py:66-73`, `:271`
- Create: `frontend/src/lib/data-gaps.ts`
- Modify: `frontend/src/app/recommendations/[id]/page.tsx:355-392`
- Test: `backend/tests/test_workers/test_assumptions.py`, `backend/tests/test_scoring_service.py`

**Interfaces:**
- Produces: `apply_assumed_defaults(metrics: dict) -> list[str]` — fills the assumed values that scoring needs, records every assumption in `metrics["data_gaps"]`, returns that list.
- Produces: gap-name constants `GAP_SUPPLIER_DATA`, `GAP_FOB_ESTIMATED`, `GAP_SEARCH_VOLUME`, `GAP_REVENUE_PER_SELLER`, `GAP_BREAK_EVEN`, `GAP_REVIEW_VELOCITY` (Task E2 sets the metric that clears the last one).
- Produces: `recommendation.risk_flags["data_gaps"]: list[str]` (JSONB, no migration).
- Contract for `_analyze_suppliers`: sets `metrics["fob_unit_cost_estimated"] = True` when it had no scraped FOB and used `FOB_FALLBACK_SHARE_OF_PRICE`.

- [x] **Step 1: Write the failing tests**

`backend/tests/test_workers/test_assumptions.py`:
```python
from app.workers.pipeline_steps.assumptions import (
    ASSUMED_BREAK_EVEN_WEEK, ASSUMED_REVENUE_PER_SELLER, ASSUMED_SEARCH_VOLUME,
    GAP_BREAK_EVEN, GAP_FOB_ESTIMATED, GAP_REVENUE_PER_SELLER, GAP_REVIEW_VELOCITY,
    GAP_SEARCH_VOLUME, GAP_SUPPLIER_DATA, apply_assumed_defaults,
)


def test_no_supplier_data_is_a_gap_not_a_default():
    metrics = {"search_volume": 1200, "monthly_revenue_per_seller": 8000,
               "break_even_week_base": 10, "avg_review_velocity_gap_ratio": 1.2}
    gaps = apply_assumed_defaults(metrics)
    assert gaps == [GAP_SUPPLIER_DATA]
    assert "supplier_count" not in metrics
    assert "best_supplier_score" not in metrics
    assert "min_moq" not in metrics
    assert metrics["data_gaps"] == [GAP_SUPPLIER_DATA]


def test_every_assumed_value_is_recorded():
    metrics = {"supplier_count": 4, "fob_unit_cost_estimated": True}
    gaps = apply_assumed_defaults(metrics)
    assert metrics["search_volume"] == ASSUMED_SEARCH_VOLUME
    assert metrics["monthly_revenue_per_seller"] == ASSUMED_REVENUE_PER_SELLER
    assert metrics["break_even_week_base"] == ASSUMED_BREAK_EVEN_WEEK
    assert gaps == [GAP_FOB_ESTIMATED, GAP_BREAK_EVEN, GAP_SEARCH_VOLUME,
                    GAP_REVENUE_PER_SELLER, GAP_REVIEW_VELOCITY]


def test_zero_search_volume_counts_as_missing():
    metrics = {"supplier_count": 1, "search_volume": 0, "monthly_revenue_per_seller": 1,
               "break_even_week_base": 1, "avg_review_velocity_gap_ratio": 0.5}
    assert apply_assumed_defaults(metrics) == [GAP_SEARCH_VOLUME]
    assert metrics["search_volume"] == ASSUMED_SEARCH_VOLUME
```

Append to `backend/tests/test_scoring_service.py`:
```python
def test_supplier_score_is_neutral_when_no_supplier_data(sample_metrics):
    from app.services.scoring_service import SUPPLIER_UNKNOWN_SCORE, ScoringService
    metrics = {k: v for k, v in sample_metrics.items()
               if k not in ("supplier_count", "best_supplier_score", "min_moq")}
    assert ScoringService._score_supplier(metrics) == SUPPLIER_UNKNOWN_SCORE


def test_supplier_score_uses_real_data_when_present(sample_metrics):
    from app.services.scoring_service import SUPPLIER_UNKNOWN_SCORE, ScoringService
    metrics = {**sample_metrics, "supplier_count": 0, "best_supplier_score": 0, "min_moq": 5000}
    assert ScoringService._score_supplier(metrics) == 2  # 0 availability + 0 quality + 2 MOQ
    assert ScoringService._score_supplier(metrics) != SUPPLIER_UNKNOWN_SCORE
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest -q tests/test_workers/test_assumptions.py tests/test_scoring_service.py -k "supplier or assumed or gap"`
Expected: FAIL — `ModuleNotFoundError: app.workers.pipeline_steps.assumptions`; `ImportError: SUPPLIER_UNKNOWN_SCORE`.

- [x] **Step 3: Implement `assumptions.py`**

```python
"""Fills the scoring inputs we could not measure, and records each one as a data gap.

WHY: the score must run even when 1688 is blocked or keyword research came back empty,
but the brief must say which numbers are assumptions. Before this module the same
values were injected silently and looked like measurements.
"""

# Names shown to the user (see frontend/src/lib/data-gaps.ts) — keep them stable.
GAP_SUPPLIER_DATA = "supplier_data_unavailable"
GAP_FOB_ESTIMATED = "fob_estimated_from_price"
GAP_BREAK_EVEN = "break_even_assumed"
GAP_SEARCH_VOLUME = "search_volume_assumed"
GAP_REVENUE_PER_SELLER = "revenue_per_seller_assumed"
GAP_REVIEW_VELOCITY = "review_velocity_unavailable"

# Typical values for a mid-range niche; used only when the real signal is missing.
ASSUMED_BREAK_EVEN_WEEK = 16
ASSUMED_SEARCH_VOLUME = 3000
ASSUMED_REVENUE_PER_SELLER = 5000


def apply_assumed_defaults(metrics: dict) -> list[str]:
    """Fill missing scoring inputs with assumed values; return the list of gaps recorded in metrics["data_gaps"]."""
    gaps: list[str] = []
    # NOTE: supplier inputs get no default on purpose. ScoringService scores a missing
    # supplier_count as "unknown" (neutral) instead of pretending five suppliers exist.
    if metrics.get("supplier_count") is None:
        gaps.append(GAP_SUPPLIER_DATA)
    if metrics.get("fob_unit_cost_estimated"):
        gaps.append(GAP_FOB_ESTIMATED)
    if metrics.get("break_even_week_base") is None:
        metrics["break_even_week_base"] = ASSUMED_BREAK_EVEN_WEEK
        gaps.append(GAP_BREAK_EVEN)
    if not metrics.get("search_volume"):
        metrics["search_volume"] = ASSUMED_SEARCH_VOLUME
        gaps.append(GAP_SEARCH_VOLUME)
    if metrics.get("monthly_revenue_per_seller") is None:
        metrics["monthly_revenue_per_seller"] = ASSUMED_REVENUE_PER_SELLER
        gaps.append(GAP_REVENUE_PER_SELLER)
    if metrics.get("avg_review_velocity_gap_ratio") is None:
        gaps.append(GAP_REVIEW_VELOCITY)
    metrics["data_gaps"] = gaps
    return gaps
```

- [x] **Step 4: Explicit unknown path in `_score_supplier`**

In `backend/app/services/scoring_service.py`, add near the other module constants:
```python
# Sub-score used when 1688 returned no suppliers at all. WHY 50: neutral, so an
# outage neither sinks nor inflates the niche; the brief shows the data gap instead.
SUPPLIER_UNKNOWN_SCORE = 50.0
```
and change the top of `_score_supplier` to:
```python
    @staticmethod
    def _score_supplier(m: dict) -> float:
        """Supplier availability and costs. Neutral score when no supplier data exists."""
        if m.get("supplier_count") is None:
            return SUPPLIER_UNKNOWN_SCORE
        score = 0
        supplier_count = m["supplier_count"]
        best_supplier_score = m.get("best_supplier_score", 0)
        moq = m.get("min_moq", 9999)
        ...  # rest unchanged
```

- [x] **Step 5: Wire `tasks.py`**

Replace lines 1881-1890 of `_enrich_metrics` with:
```python
    from app.workers.pipeline_steps.assumptions import apply_assumed_defaults
    apply_assumed_defaults(metrics)
```
In `_analyze_suppliers`, right after `unit_cost = fob_unit_cost or avg_price * FOB_FALLBACK_SHARE_OF_PRICE`, add:
```python
    metrics["fob_unit_cost_estimated"] = fob_unit_cost is None
```

- [x] **Step 6: Carry gaps into the recommendation**

`backend/app/services/recommendation_engine.py`: in `recommendation_data` (line ~66) add `"data_gaps": metrics.get("data_gaps", [])`. At line ~271 change to:
```python
            risk_flags={
                "fail_reasons": data.get("fail_reasons", []),
                "hard_filters": data.get("hard_filters", []),
                "data_gaps": data.get("data_gaps", []),
            },
```
Add a test in `backend/tests/test_recommendation_engine.py` that passes `metrics={"data_gaps": ["supplier_data_unavailable"], ...}` through the existing generate path used by the file's other tests and asserts the saved `risk_flags["data_gaps"]` equals it. Follow the file's existing fixture style.

- [x] **Step 7: Frontend**

`frontend/src/lib/data-gaps.ts`:
```ts
// Human labels for the backend's data-gap names (backend/app/workers/pipeline_steps/assumptions.py).
export const DATA_GAP_LABELS: Record<string, string> = {
  supplier_data_unavailable: "No 1688 supplier data — supplier score is neutral, not measured",
  fob_estimated_from_price: "Factory cost estimated from listing price (no supplier quotes)",
  break_even_assumed: "Break-even week assumed (no PPC plan data)",
  search_volume_assumed: "Search volume assumed (keyword research returned nothing)",
  revenue_per_seller_assumed: "Revenue per seller assumed",
  review_velocity_unavailable: "Review velocity not yet measurable — needs 14 days of tracking",
};

export function labelForDataGap(gap: string): string {
  return DATA_GAP_LABELS[gap] ?? gap.replace(/_/g, " ");
}
```
In the Risk Flags card of `frontend/src/app/recommendations/[id]/page.tsx` (after the hard-filter block, inside the same `CardContent`) add:
```tsx
{rec.risk_flags?.data_gaps?.length > 0 && (
  <div className="mt-4 pt-4 border-t space-y-2">
    <p className="text-xs font-medium text-muted-foreground mb-2">Data gaps — these inputs are assumptions</p>
    {rec.risk_flags.data_gaps.map((gap: string) => (
      <div key={gap} className="flex items-start gap-2 text-xs text-muted-foreground">
        <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
        <span>{labelForDataGap(gap)}</span>
      </div>
    ))}
  </div>
)}
```
Import `labelForDataGap` from `@/lib/data-gaps` (check how other `@/lib/...` imports are written in that file and match).

- [x] **Step 8: Run tests, typecheck, commit**

Run: `pytest -q` (expect all green, +5 tests) and `cd frontend && npx tsc --noEmit && git checkout -- tsconfig.tsbuildinfo`.
Commit: `feat(scoring): record data gaps instead of faking supplier inputs`

---

# Part E — Review velocity from real snapshots

## File structure for Part E

```
backend/migrations/versions/016_bsr_history_review_count.py   (new)
backend/app/models/bsr_history.py                             (+ review_count)
backend/app/services/bsr_tracker.py                           (record_bsr / record_product_snapshot accept review_count)
backend/app/services/scraper_service.py                       (scrape_rank_snapshot parses review count; _extract_review_count)
backend/app/workers/tasks.py                                  (_record_snapshot forwards review_count)
backend/app/workers/pipeline_steps/product_details.py         (_record_first_snapshots forwards review_count)
backend/app/services/market_signals.py                        (recent_review_velocity_per_month, average_recent_velocity_gap; delete lifetime version)
backend/app/workers/pipeline_steps/review_velocity.py         (new) load windows from bsr_history, compute gap for a niche
backend/app/workers/tasks.py                                  (set metrics["avg_review_velocity_gap_ratio"])
```

### Task E1: Review count travels with every rank snapshot (F17) — migration 016

**Files:**
- Create: `backend/migrations/versions/016_bsr_history_review_count.py`
- Modify: `backend/app/models/bsr_history.py`, `backend/app/services/bsr_tracker.py:30-52, 92-132`, `backend/app/services/scraper_service.py:716-726, 1317-1334`, `backend/app/workers/tasks.py:1004-1029`, `backend/app/workers/pipeline_steps/product_details.py:103-110`
- Test: `backend/tests/test_workers/test_tracking.py`, `backend/tests/test_workers/test_product_details.py`, `backend/tests/test_db/test_bsr_snapshot_db.py`, `backend/tests/test_services/test_review_count_parse.py`

**Interfaces:**
- Produces: `BSRHistory.review_count: int | None` — set on main-rank rows only (`is_subcategory=False`).
- Produces: `BSRTracker.record_product_snapshot(..., review_count: int | None = None)` and `record_bsr(..., review_count: int | None = None)`.
- Produces: `scrape_rank_snapshot()` result gains `"review_count": int | None`.
- Produces: `ScraperService._extract_review_count(page) -> int | None` (shared by the full product scrape and the rank snapshot).

- [x] **Step 1: Failing tests**

`tests/test_workers/test_tracking.py` — extend `_snapshot()` helper to include `"review_count": 1543` and add:
```python
async def test_snapshot_forwards_review_count_to_tracker():
    context = _context([_snapshot("ok")])
    await tasks._track_one_product(_product(), context)
    kwargs = context.tracker.record_product_snapshot.await_args.kwargs
    assert kwargs["review_count"] == 1543
```
`tests/test_workers/test_product_details.py` — add a test that `_record_first_snapshots` passes `review_count=detail["review_count"]` (patch `BSRTracker` the way the file already patches collaborators; if it uses a fake db, assert on the `record_product_snapshot` await kwargs).
`tests/test_db/test_bsr_snapshot_db.py` — add:
```python
async def test_review_count_is_stored_on_main_rank_only():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection)
        try:
            product = await _add_product(session)
            await BSRTracker(session).record_product_snapshot(
                product_id=product.id, asin=product.asin, bsr=118, subcategory_bsr=1, review_count=1543,
            )
            rows = (await session.execute(
                select(BSRHistory.is_subcategory, BSRHistory.review_count).where(BSRHistory.product_id == product.id)
            )).all()
            assert sorted(rows) == [(False, 1543), (True, None)]
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()
```
Scraper: in `tests/test_services/test_review_count_parse.py` add a test for `_extract_review_count` with a fake page whose `_safe_text` returns `None` for the first selector and `"1,543 ratings"` for the second → `1543`. Build the fake with `SimpleNamespace`/`AsyncMock` the way `test_sold_by_amazon.py` fakes pages.

- [x] **Step 2: Run, expect failures** (`KeyError: 'review_count'`, `TypeError: unexpected keyword 'review_count'`, `AttributeError: _extract_review_count`).

- [x] **Step 3: Migration 016**

```python
"""Store the review count on main-rank BSR snapshots.

The periodic tracker already visits every product page; recording the review
count each time gives a time series from which a recent review velocity can
be derived. Lifetime review counts over-count launch bursts, so the
review-velocity hard filter needs this window.

Revision ID: 016
Revises: 015
Create Date: 2026-09-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bsr_history", sa.Column("review_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("bsr_history", "review_count")
```

- [x] **Step 4: Model + tracker**

`bsr_history.py`: add `review_count: Mapped[int | None] = mapped_column(Integer)` with `# NOTE: only set on main-rank rows; the sub-rank row recorded at the same moment leaves it NULL.`
`bsr_tracker.py`: `record_bsr(..., review_count: int | None = None)` sets it on the `BSRHistory(...)`; `record_product_snapshot(..., review_count: int | None = None)` passes `review_count=review_count` only to the main-rank `record_bsr` call.

- [x] **Step 5: Scraper**

Extract the loop at `scraper_service.py:722-726` into:
```python
    async def _extract_review_count(self, page: Page) -> int | None:
        """Review count from the first product-page selector that yields a number."""
        for selector in _PRODUCT_REVIEW_COUNT_SELECTORS:
            count = self.parse_review_count_text(await self._safe_text(page, selector))
            if count is not None:
                return count
        return None
```
Use it in the full product scrape (replace the loop) and in `scrape_rank_snapshot` (`review_count = await self._extract_review_count(page)`; include `"review_count": review_count` in the returned dict). Update the `scrape_rank_snapshot` docstring: "…BSR, price, stock and review count…".

- [x] **Step 6: Forward in workers**

`tasks.py:_record_snapshot`: add `review_count=snapshot.get("review_count"),` to the `record_product_snapshot` call. `_track_bsr_via_spapi` is unchanged (SP-API has no review count; the row stays NULL).
`product_details.py:_record_first_snapshots`: add `review_count=detail.get("review_count"),`.

- [x] **Step 7: Migrate the test DB, run everything, commit**

Run (Docker): `alembic upgrade head` against the test database, then `pytest -q` with `TEST_DATABASE_URL` set, then `alembic downgrade 015` and `upgrade head` once more to prove the round trip.
Commit: `feat(tracking): record review count on rank snapshots (migration 016)`

### Task E2: Recent review velocity arms hard filter #9 (F16)

**Files:**
- Modify: `backend/app/services/market_signals.py:12-15, 48-78` (delete `_months_listed` and `average_review_velocity_gap`; add the two functions below)
- Create: `backend/app/workers/pipeline_steps/review_velocity.py`
- Modify: `backend/app/workers/tasks.py:~736` (after `_build_base_metrics`)
- Test: `backend/tests/test_services/test_market_signals.py` (replace the lifetime test), `backend/tests/test_workers/test_review_velocity.py` (new)

**Interfaces:**
- Consumes: `BSRHistory.review_count` (E1), `CompetitorService.calculate_review_velocity_gap(estimated_monthly_sales, review_velocity_per_month) -> {"gap_ratio", ...}`, `BSRSalesEstimator(marketplace).estimate_monthly_sales(bsr, category)`.
- Produces: `recent_review_velocity_per_month(first: Snapshot, last: Snapshot) -> float | None` where `Snapshot = tuple[datetime, int]`.
- Produces: `average_recent_velocity_gap(windows: list[dict], estimator, category) -> float | None`; each window is `{"bsr": int, "first": Snapshot, "last": Snapshot}`.
- Produces: `review_velocity_gap_for_niche(db, niche_id, estimator, category) -> float | None`.
- Sets `metrics["avg_review_velocity_gap_ratio"]` when a value exists; `ScoringService` hard filter #9 then runs unchanged (`scoring_service.py:598-611`). When absent, Task D1 records `GAP_REVIEW_VELOCITY`.

- [x] **Step 1: Failing tests**

Replace `test_average_review_velocity_gap_skips_products_without_dates_or_bsr` in `tests/test_services/test_market_signals.py` with:
```python
from datetime import datetime, timedelta, timezone

from app.services.market_signals import (
    MIN_PRODUCTS_FOR_VELOCITY, MIN_VELOCITY_WINDOW_DAYS,
    average_recent_velocity_gap, recent_review_velocity_per_month,
)

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _snap(days: float, count: int):
    return (T0 + timedelta(days=days), count)


def test_velocity_needs_a_two_week_window():
    assert recent_review_velocity_per_month(_snap(0, 100), _snap(MIN_VELOCITY_WINDOW_DAYS - 1, 130)) is None
    assert recent_review_velocity_per_month(_snap(0, 100), _snap(30.4, 130)) == 30.0


def test_removed_reviews_count_as_zero_velocity():
    assert recent_review_velocity_per_month(_snap(0, 100), _snap(20, 90)) == 0.0


def test_gap_needs_enough_products():
    estimator = BSRSalesEstimator("US")
    window = {"bsr": 1000, "first": _snap(0, 100), "last": _snap(30.4, 130)}
    assert average_recent_velocity_gap([window] * (MIN_PRODUCTS_FOR_VELOCITY - 1), estimator, "Home & Kitchen") is None
    gap = average_recent_velocity_gap([window] * MIN_PRODUCTS_FOR_VELOCITY, estimator, "Home & Kitchen")
    monthly_sales = estimator.estimate_monthly_sales(1000, "Home & Kitchen")
    assert gap == round(30.0 / monthly_sales * 100, 2)
```
`tests/test_workers/test_review_velocity.py`:
```python
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
```
(rows are `(product_id, current_bsr, time, review_count)` ordered by product then time; products without a BSR are skipped.)

- [x] **Step 2: Run, expect ImportError.**

- [x] **Step 3: market_signals**

Delete `_months_listed`, `average_review_velocity_gap`, the `NOTE: not wired…` comment and the `DAYS_PER_MONTH` constant if nothing else uses it (grep first). Add:
```python
Snapshot = tuple[datetime, int]  # (recorded at, review count)

# WHY 14 days: Amazon updates the visible review count in batches; shorter windows read as noise.
MIN_VELOCITY_WINDOW_DAYS = 14
# Fewer products than this and one grey-hat listing would decide the whole niche.
MIN_PRODUCTS_FOR_VELOCITY = 3
DAYS_PER_MONTH = 30.4


def recent_review_velocity_per_month(first: Snapshot, last: Snapshot) -> float | None:
    """Reviews gained per month between two snapshots. None if the window is shorter than MIN_VELOCITY_WINDOW_DAYS."""
    days = (last[0] - first[0]).total_seconds() / 86400
    if days < MIN_VELOCITY_WINDOW_DAYS:
        return None
    # Amazon removes reviews too; a shrinking count is "no growth", not negative growth.
    gained = max(0, last[1] - first[1])
    return round(gained / days * DAYS_PER_MONTH, 2)


def average_recent_velocity_gap(windows: list[dict], estimator: BSRSalesEstimator, category: str) -> float | None:
    """Mean reviews-per-100-sales across products with a long-enough window. None below MIN_PRODUCTS_FOR_VELOCITY."""
    ratios = []
    for window in windows:
        velocity = recent_review_velocity_per_month(window["first"], window["last"])
        if velocity is None:
            continue
        monthly_sales = estimator.estimate_monthly_sales(int(window["bsr"]), category)
        ratios.append(CompetitorService.calculate_review_velocity_gap(monthly_sales, velocity)["gap_ratio"])
    if len(ratios) < MIN_PRODUCTS_FOR_VELOCITY:
        return None
    return round(sum(ratios) / len(ratios), 2)
```

- [x] **Step 4: `pipeline_steps/review_velocity.py`**

```python
"""Derives the niche's recent review velocity from stored rank snapshots."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bsr_regression import BSRSalesEstimator
from app.models.bsr_history import BSRHistory
from app.models.product import Product
from app.services.market_signals import average_recent_velocity_gap

# Older snapshots describe a listing that may have changed hands or relaunched.
VELOCITY_LOOKBACK_DAYS = 90


def windows_from_rows(rows: list[tuple]) -> list[dict]:
    """Group (product_id, bsr, time, review_count) rows, ordered by product then time, into first/last windows."""
    windows: dict[int, dict] = {}
    for product_id, bsr, recorded_at, review_count in rows:
        if not bsr:
            continue
        snapshot = (recorded_at, review_count)
        window = windows.setdefault(product_id, {"bsr": bsr, "first": snapshot, "last": snapshot})
        window["last"] = snapshot
    return list(windows.values())


async def load_review_count_rows(db: AsyncSession, niche_id: int) -> list[tuple]:
    """Main-rank snapshots with a review count for every product in the niche, oldest first."""
    since = datetime.now(timezone.utc) - timedelta(days=VELOCITY_LOOKBACK_DAYS)
    query = (
        select(Product.id, Product.current_bsr, BSRHistory.time, BSRHistory.review_count)
        .join(BSRHistory, BSRHistory.product_id == Product.id)
        .where(Product.niche_id == niche_id, BSRHistory.is_subcategory.is_(False),
               BSRHistory.review_count.is_not(None), BSRHistory.time >= since)
        .order_by(Product.id, BSRHistory.time)
    )
    return [tuple(row) for row in (await db.execute(query)).all()]


async def review_velocity_gap_for_niche(
    db: AsyncSession, niche_id: int, estimator: BSRSalesEstimator, category: str,
) -> float | None:
    """Reviews-per-100-sales for the niche, or None until enough products have two weeks of snapshots."""
    rows = await load_review_count_rows(db, niche_id)
    return average_recent_velocity_gap(windows_from_rows(rows), estimator, category)
```

- [x] **Step 5: Wire into the pipeline**

In `tasks.py` right after `metrics = _build_base_metrics(...)` (line ~736):
```python
        from app.workers.pipeline_steps.review_velocity import review_velocity_gap_for_niche
        velocity_gap = await review_velocity_gap_for_niche(
            db, niche_id, BSRSalesEstimator(marketplace), metrics.get("category", "default"),
        )
        if velocity_gap is not None:
            metrics["avg_review_velocity_gap_ratio"] = velocity_gap
```
Import `BSRSalesEstimator` the way the file already does for other uses (grep `BSRSalesEstimator` in tasks.py and reuse that import). Also confirm `Product.current_bsr` is the column name used by the model (grep `current_bsr` in `app/models/product.py`); if it is `bsr`, use that.

- [x] **Step 6: Run `pytest -q`, commit.** `feat(scoring): arm the review-velocity filter on recent snapshot windows`

---

# Part F — ORM loading, HTTP tests, dashboard stats

### Task F1: HTTP test harness (F21)

**Files:**
- Create: `backend/tests/test_api/conftest.py`, `backend/tests/test_api/test_niche_routes.py`

**Interfaces:**
- Produces: fixture `client` (httpx `AsyncClient` over `ASGITransport(app)`) whose `get_db` dependency yields a session bound to one outer transaction that is rolled back after each test; fixture `seeded_niche` that inserts one `Niche` with two `Product`s, one `Competitor`, one `Supplier`, one `FinancialProjection`, one `NicheKeyword`, one `ReviewPainPoint`, one `Recommendation` via the ORM and flushes.
- Skips the whole directory unless `TEST_DATABASE_URL` is set.

- [x] **Step 1: conftest**

```python
"""HTTP-level tests against the real FastAPI app and a real (rolled back) database."""

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.dependencies import get_db
from app.main import create_app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set; needs a real TimescaleDB")


@pytest.fixture
async def db_session():
    """One session inside one transaction that is always rolled back."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def client(db_session):
    # WHY: no lifespan — it would open Redis and a second engine. Routes only need get_db.
    app = create_app()

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
```
Add a `seeded_niche` fixture in the same file that builds the rows listed in Interfaces (use only columns that exist on each model; read the models first) and returns the `Niche`. `db.commit()` inside routes must not end the outer transaction: check how `get_db` commits (`app/dependencies.py:25-40`) and, if the route layer calls `commit()`, use `connection.begin_nested()`/`join_transaction_mode="create_savepoint"` on the session so the outer transaction survives.

- [x] **Step 2: Route tests**

```python
async def test_list_niches_returns_envelope(client, seeded_niche):
    response = await client.get("/api/v1/niches/", params={"per_page": 5})
    assert response.status_code == 200
    body = response.json()
    assert {"items", "total", "page", "per_page", "total_pages"} <= body.keys()
    assert any(item["id"] == seeded_niche.id for item in body["items"])


@pytest.mark.parametrize("suffix", ["", "/products", "/competitors", "/keywords", "/reviews", "/financials", "/suppliers"])
async def test_niche_sub_resources_respond(client, seeded_niche, suffix):
    response = await client.get(f"/api/v1/niches/{seeded_niche.id}{suffix}")
    assert response.status_code == 200, response.text


async def test_recommendations_list(client, seeded_niche):
    response = await client.get("/api/v1/recommendations/")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_unknown_niche_is_404(client):
    assert (await client.get("/api/v1/niches/999999999")).status_code == 404
```

- [x] **Step 3: Run with `TEST_DATABASE_URL` in Docker, then without (expect skips). Commit.** `test(api): first HTTP-level route tests against a real database`

### Task F2: Relationships load only when asked (F18)

**Files:**
- Modify: `backend/app/models/niche.py:82-111`, `backend/app/models/product.py:96-108`, `backend/app/models/supplier.py:62`
- Modify: `backend/app/api/exports.py:13` (drop unused `selectinload` import)
- Test: `backend/tests/test_api/test_niche_routes.py` (F1 suite is the regression net), plus a query-count assertion

**Interfaces:**
- Every relationship listed above becomes `lazy="raise"`. Any code that needs a collection must ask with `.options(selectinload(Model.relation))` — `niches.py:402` already does for `Supplier.landed_cost_calculations`.

- [x] **Step 1: Failing test — count queries**

Add to `test_niche_routes.py`:
```python
from sqlalchemy import event


async def test_get_niche_runs_one_query(client, seeded_niche, db_session):
    statements: list[str] = []
    sync_engine = db_session.bind.sync_engine if hasattr(db_session.bind, "sync_engine") else db_session.bind.engine.sync_engine
    event.listen(sync_engine, "before_cursor_execute", lambda *a: statements.append(a[2]))
    try:
        assert (await client.get(f"/api/v1/niches/{seeded_niche.id}")).status_code == 200
    finally:
        event.remove(sync_engine, "before_cursor_execute", statements.append)  # see note
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1, selects
```
NOTE for the implementer: `event.remove` needs the same callable that was registered — keep the lambda in a variable. Getting the sync engine from an `AsyncConnection`-bound session: `db_session.bind` is an `AsyncConnection`; use `db_session.bind.sync_connection.engine`. Adjust until the listener fires; the assertion should fail before Step 2 with ~11 SELECTs.

- [x] **Step 2: Flip the strategies**

In `niche.py` change every `lazy="selectin"` to `lazy="raise"`, and add one comment above the block:
```python
    # NOTE: relationships never load on their own. A query that needs one must say so
    # with .options(selectinload(...)); accessing an unloaded one raises instead of
    # silently issuing ten extra queries (that is what selectin did here before).
```
Same in `product.py` (four collections) and `supplier.py:62`. Grep `app/` for attribute access to any of these relationship names (the survey found none outside `niches.py:402`); if you find one, add the explicit `selectinload` at that query site.

- [x] **Step 3: Run the F1 suite with the DB, then full `pytest -q`. Commit.** `perf(models): stop eager-loading the whole niche graph on every query`

### Task F3: Dashboard numbers come from the server (F19)

**Files:**
- Modify: `backend/app/api/niches.py` (new route **above** `/{niche_id}`, next to `scrape-health`), `backend/app/schemas/niche.py`
- Modify: `frontend/src/app/page.tsx:20-45`, `frontend/src/components/recent-niches-table.tsx:22`, `frontend/src/types/index.ts`
- Test: `backend/tests/test_api/test_niche_routes.py`

**Interfaces:**
- Produces: `GET /api/v1/niches/stats` → `NicheStatsResponse {total_niches: int, avg_score: float | None, high_confidence_count: int, total_recommendations: int}`.

- [x] **Step 1: Failing test**
```python
async def test_niche_stats(client, seeded_niche):
    body = (await client.get("/api/v1/niches/stats")).json()
    assert body["total_niches"] >= 1
    assert body["total_recommendations"] >= 1
    assert set(body) == {"total_niches", "avg_score", "high_confidence_count", "total_recommendations"}
```
- [x] **Step 2: Implement**

Schema:
```python
class NicheStatsResponse(BaseModel):
    total_niches: int
    avg_score: float | None
    high_confidence_count: int
    total_recommendations: int
```
Route (declare before `@router.get("/{niche_id}")`):
```python
HIGH_CONFIDENCE_TIER = "HIGH"


@router.get("/stats", response_model=NicheStatsResponse)
async def niche_stats(db: AsyncSession = Depends(get_db)) -> NicheStatsResponse:
    """Dashboard headline numbers, computed in the database so they stay right past 100 niches."""
    totals = (await db.execute(select(
        func.count(Niche.id),
        func.avg(Niche.opportunity_score),
        func.count(Niche.id).filter(Niche.confidence_tier == HIGH_CONFIDENCE_TIER),
    ))).one()
    recommendation_count = (await db.execute(select(func.count(Recommendation.id)))).scalar_one()
    return NicheStatsResponse(
        total_niches=totals[0], avg_score=round(float(totals[1]), 1) if totals[1] is not None else None,
        high_confidence_count=totals[2], total_recommendations=recommendation_count,
    )
```
Frontend: `page.tsx` replaces the three requests with `api.get<NicheStats>("/api/v1/niches/stats")` and sets `stats` from the body (round `avg_score` for display, treat `null` as 0). Add `NicheStats` to `types/index.ts`. In `recent-niches-table.tsx` change `sort_by: "analyzed_at"` to `"created_at"` (the only time field the API sorts by — `niches.py:111-118`).

- [x] **Step 3: pytest (with DB) + `npx tsc --noEmit` + restore tsbuildinfo. Commit.** `feat(dashboard): compute headline stats server-side`

### Task F4: Server-side failures are logged 500s, not silent 400s (found by F1)

**Files:**
- Modify: `backend/app/core/middleware.py:62-80` (`GlobalExceptionMiddleware`)
- Test: `backend/tests/test_api/test_exception_middleware.py` (new; no DB needed)

**Why:** `GlobalExceptionMiddleware` maps every `ValueError` to an unlogged 400. Pydantic's `ValidationError` subclasses `ValueError`, so one stored row that fails a response model (e.g. an ASIN that is not 10 characters) makes `GET /niches/{id}/products` answer "400 client error" with no log line. The only intentional `ValueError` in the API (`jobs.py:76`) sits inside a Pydantic validator and is already a 422 before any middleware runs, so the 400 branch protects nothing.

**Interfaces:**
- `PermissionError` → 403 and `FileNotFoundError` → 404 stay, but are logged at WARNING with the path. Every other exception (including `ValueError`/`ValidationError`) → `logger.exception(...)` + 500 `{"detail": "Internal server error"}`.

- [x] **Step 1: Failing test**

```python
"""GlobalExceptionMiddleware turns server-side failures into logged 500s, never silent 400s."""

import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.middleware import GlobalExceptionMiddleware


class Asin(BaseModel):
    asin: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if len(self.asin) != 10:
            raise ValueError(f"ASIN must be 10 characters, got {self.asin!r}")


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(GlobalExceptionMiddleware)

    @app.get("/bad-row")
    async def bad_row():
        return Asin(asin="SHORT")

    @app.get("/forbidden")
    async def forbidden():
        raise PermissionError("no")

    return app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as http:
        yield http


async def test_value_error_from_bad_data_is_a_logged_500(client, caplog):
    with caplog.at_level(logging.ERROR, logger="app.core.middleware"):
        response = await client.get("/bad-row")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "ASIN must be 10 characters" in caplog.text


async def test_permission_error_is_a_logged_403(client, caplog):
    with caplog.at_level(logging.WARNING, logger="app.core.middleware"):
        response = await client.get("/forbidden")
    assert response.status_code == 403
    assert "/forbidden" in caplog.text
```

- [x] **Step 2: Run, expect the first test to fail with 400.**

- [x] **Step 3: Implement**

```python
class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    """Turn unhandled exceptions into structured error responses. Every one is logged.

    NOTE: ValueError is deliberately NOT mapped to 400. Pydantic's ValidationError
    is a ValueError, so a bad stored row would otherwise be reported as the
    client's fault and never logged. Input validation already answers 422 before
    any middleware runs.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except PermissionError as exc:
            logger.warning("Forbidden %s %s: %s", request.method, request.url.path, exc)
            return JSONResponse(status_code=403, content={"detail": str(exc)})
        except FileNotFoundError as exc:
            logger.warning("Not found %s %s: %s", request.method, request.url.path, exc)
            return JSONResponse(status_code=404, content={"detail": str(exc)})
        except Exception as exc:
            logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

- [x] **Step 4: `pytest -q`; commit.** `fix(api): log server-side failures as 500s instead of blaming the client with a silent 400`

---

# Part G — Pacing that holds across worker processes

### Task G1: Redis-backed pacer with local fallback (F20)

**Files:**
- Modify: `backend/app/scraping/pacing.py`
- Modify: `backend/app/scraping/session.py:46-52, 139-162`
- Test: `backend/tests/test_scraping/test_pacing.py`, `backend/tests/test_scraping/test_session_policy.py`

**Interfaces:**
- Produces: `class SharedPacer` with `async def wait_turn(self, domain: str) -> None` (same contract as `Pacer`), constructed as `SharedPacer(redis, min_gap_s, max_gap_s, fallback: Pacer)`.
- Produces: `BrowserSession(marketplace, proxy_manager, site="amazon", pacer: Pacer | SharedPacer | None = None)`; `load()` uses `self.pacer`, which defaults to `pacer_for(site)`.
- Redis key: `pace:{domain}`; a run that holds the key for one gap length is "the last request". Any Redis error switches that `SharedPacer` instance to its local fallback for the rest of the process and logs once.

- [x] **Step 1: Failing tests**

`tests/test_scraping/test_pacing.py` add:
```python
import time

from app.scraping.pacing import Pacer, SharedPacer


class FakeRedis:
    """Just enough of redis.asyncio for SharedPacer: SET NX PX and PTTL."""

    def __init__(self):
        self.expires_at: dict[str, float] = {}

    async def set(self, key, value, nx=False, px=None):
        now = time.monotonic()
        if nx and self.expires_at.get(key, 0) > now:
            return None
        self.expires_at[key] = now + px / 1000
        return True

    async def pttl(self, key):
        remaining = self.expires_at.get(key, 0) - time.monotonic()
        return int(remaining * 1000) if remaining > 0 else -2


class BrokenRedis:
    async def set(self, *a, **k):
        raise ConnectionError("redis down")

    async def pttl(self, *a, **k):
        raise ConnectionError("redis down")


async def test_two_shared_pacers_take_turns():
    redis = FakeRedis()
    a = SharedPacer(redis, 0.2, 0.2, fallback=Pacer(0, 0))
    b = SharedPacer(redis, 0.2, 0.2, fallback=Pacer(0, 0))
    await a.wait_turn("amazon.com")
    start = time.monotonic()
    await b.wait_turn("amazon.com")
    assert time.monotonic() - start >= 0.19


async def test_redis_failure_falls_back_to_local_pacing():
    pacer = SharedPacer(BrokenRedis(), 0.2, 0.2, fallback=Pacer(0.2, 0.2))
    await pacer.wait_turn("amazon.com")
    start = time.monotonic()
    await pacer.wait_turn("amazon.com")
    assert time.monotonic() - start >= 0.19
    assert pacer.using_fallback is True
```
`tests/test_scraping/test_session_policy.py`: add a test that `BrowserSession(marketplace, proxy_manager, pacer=custom)` stores `custom` on `.pacer`, and that the default is `pacer_for("amazon")` (identity check). Follow that file's existing construction helpers.

- [x] **Step 2: Run, expect ImportError.**

- [x] **Step 3: Implement `SharedPacer`** (append to `pacing.py`; keep the file under 200 lines)

```python
# Poll granularity while another process holds the slot. Short enough to feel
# immediate, long enough not to hammer Redis.
_RETRY_SLEEP_SECONDS = 0.05


class SharedPacer:
    """Pacer whose 'last request' lives in Redis, so every worker process shares one gap.

    WHY: with Celery concurrency=4 the in-process Pacer let four workers hit a domain at
    once. The slot is a SET NX key that expires after one random gap; whoever sets it goes.
    """

    def __init__(self, redis, min_gap_s: float, max_gap_s: float, fallback: Pacer):
        self.redis = redis
        self.min_gap_s = min_gap_s
        self.max_gap_s = max_gap_s
        self.fallback = fallback
        self.using_fallback = False

    async def wait_turn(self, domain: str) -> None:
        """Block until this process may make the next request to domain."""
        if self.using_fallback:
            await self.fallback.wait_turn(domain)
            return
        try:
            await self._claim_slot(domain)
        except Exception as e:
            logger.warning("Shared pacing unavailable (%s); pacing %s per process from now on", e, domain)
            self.using_fallback = True
            await self.fallback.wait_turn(domain)

    async def _claim_slot(self, domain: str) -> None:
        key = f"pace:{domain}"
        while True:
            gap_ms = int(random.uniform(self.min_gap_s, self.max_gap_s) * 1000)
            if await self.redis.set(key, "1", nx=True, px=gap_ms):
                return
            remaining_ms = await self.redis.pttl(key)
            await asyncio.sleep(max(remaining_ms, 0) / 1000 or _RETRY_SLEEP_SECONDS)
```
Add `import logging` and `logger = logging.getLogger(__name__)` at the top. Replace the `NOTE: this registry lives in one worker process…` comment with one sentence: "Local fallback pacers; the pipeline injects a SharedPacer (Redis) so all worker processes share the gap."

- [x] **Step 4: Inject into `BrowserSession`**

Constructor gains `pacer: "Pacer | SharedPacer | None" = None` and sets `self.pacer = pacer or pacer_for(site)`. `load()` line 151 becomes `await self.pacer.wait_turn(self.marketplace.domain)`.

- [x] **Step 5: `pytest -q`, commit.** `feat(scraping): Redis-backed pacer shared by every worker process`

### Task G2: Every browser in the pipeline uses the shared pacer — including 1688

**Files:**
- Modify: `backend/app/workers/tasks.py:160-187, 277-285, 386, 689, 1059, 1149`
- Modify: `backend/app/services/supplier_scraper.py:53-69, 290, 610`
- Test: `backend/tests/test_workers/test_worker_runtime.py` or a new `tests/test_workers/test_run_redis.py`; `tests/test_services/test_supplier_scraper_pacing.py` (new)

**Interfaces:**
- Produces: `@asynccontextmanager async def _redis_for_run()` yielding one `redis.asyncio.Redis` for the run (closed on exit). `_page_cache_for_run(force)` becomes `_page_cache_for(redis, force) -> PageCache | None` (pure, no context manager).
- Produces: `_shared_pacer(redis, site: str) -> SharedPacer` using `AMAZON_GAP_SECONDS` / `ALIBABA_GAP_SECONDS` with `pacer_for(site)` as fallback.
- Produces: `_build_browser_session(marketplace, pacer=None)`.
- Produces: `SupplierScraper(proxy_manager=None, cookie_manager=None, pacer=None)`; `self.pacer = pacer or pacer_for("1688")`; both `page.goto(...)` calls at 290 and 610 are preceded by `await self.pacer.wait_turn("1688.com")`. `_random_delay` stays only for the intra-page scroll/expand waits (lines 333, 375, 716); the fixed render sleeps (296, 312, 611) stay.

- [x] **Step 1: Failing tests**

`tests/test_services/test_supplier_scraper_pacing.py`:
```python
from unittest.mock import AsyncMock

from app.scraping.pacing import pacer_for
from app.services.supplier_scraper import SupplierScraper


def test_supplier_scraper_defaults_to_the_1688_pacer():
    assert SupplierScraper().pacer is pacer_for("1688")


def test_supplier_scraper_accepts_injected_pacer():
    custom = AsyncMock()
    assert SupplierScraper(pacer=custom).pacer is custom
```
In `tests/test_workers/` add:
```python
from app.scraping.pacing import ALIBABA_GAP_SECONDS, AMAZON_GAP_SECONDS, SharedPacer, pacer_for
from app.workers import tasks


def test_shared_pacer_uses_site_gaps_and_local_fallback():
    amazon = tasks._shared_pacer(object(), "amazon")
    alibaba = tasks._shared_pacer(object(), "1688")
    assert isinstance(amazon, SharedPacer)
    assert (amazon.min_gap_s, amazon.max_gap_s) == AMAZON_GAP_SECONDS
    assert (alibaba.min_gap_s, alibaba.max_gap_s) == ALIBABA_GAP_SECONDS
    assert amazon.fallback is pacer_for("amazon")


def test_page_cache_is_skipped_on_forced_rerun():
    assert tasks._page_cache_for(object(), force=True) is None
    assert tasks._page_cache_for(object(), force=False) is not None
```

- [x] **Step 2: Run, expect AttributeError / TypeError.**

- [x] **Step 3: Implement in `tasks.py`**

```python
@asynccontextmanager
async def _redis_for_run():
    """Yield one Redis client for this run; the page cache and the shared pacer both use it."""
    from redis.asyncio import Redis

    redis = Redis.from_url(Settings().REDIS_URL, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


def _page_cache_for(redis, force: bool) -> "PageCache | None":
    """WHY None on force: a forced re-run exists to get fresh data, not last run's cached pages."""
    if force:
        return None
    from app.scraping.page_cache import PageCache
    return PageCache(redis)


def _shared_pacer(redis, site: str) -> "SharedPacer":
    """Pacer for `site` ('amazon' or '1688') shared across worker processes through Redis."""
    from app.scraping.pacing import ALIBABA_GAP_SECONDS, AMAZON_GAP_SECONDS, SharedPacer, pacer_for

    gaps = {"amazon": AMAZON_GAP_SECONDS, "1688": ALIBABA_GAP_SECONDS}[site]
    return SharedPacer(redis, *gaps, fallback=pacer_for(site))


def _build_browser_session(marketplace: str, pacer=None) -> "BrowserSession":
    """Return an unopened BrowserSession for this marketplace, behind the proxy configured in settings."""
    ...
    return BrowserSession(get_marketplace(marketplace), build_proxy_manager_from_settings(), pacer=pacer)
```
`run_full_analysis` block (277-285) becomes:
```python
    async with session_factory() as db, _redis_for_run() as redis:
        page_cache = _page_cache_for(redis, options.get("force", False))
        async with _build_browser_session(marketplace, pacer=_shared_pacer(redis, "amazon")) as browser:
            scraper = ScraperService(...)  # unchanged args
```
(Keep nesting ≤ 3 levels: if the existing body is already deep, extract the inner part into a named helper.) Line 689: `SupplierScraper(cookie_manager=cookie_manager, pacer=_shared_pacer(redis, "1688"))`. The tracker (1059) and competitor refresh (1149) also open `_redis_for_run()` and pass `_shared_pacer(redis, "amazon")`; line 386 (sub-niche) reuses the outer run's `redis`.
Delete `_page_cache_for_run`.

- [x] **Step 4: `SupplierScraper`** — constructor and the two `wait_turn` calls as in Interfaces. Import `pacer_for` from `app.scraping.pacing`.

- [x] **Step 5: Full `pytest -q`; run one `run_full_analysis` in Docker with Redis down and confirm the log line "Shared pacing unavailable" appears once and the run completes. Commit.** `feat(workers): all browsers pace through the shared Redis pacer, 1688 included`

---

### Task H1: Docs catch-up

**Files:** `CLAUDE.md`, `README.md`, `GUIDE.md`, `TODO.md`, `docs/superpowers/plans/2026-09-26-data-quality-and-worker-pacing.md` (this file: tick boxes)

- [x] `CLAUDE.md`: Database section → 15 migrations, migration 016 adds `bsr_history.review_count`; Scoring bullet: supplier sub-score is neutral (50) when no supplier data, recommendation `risk_flags.data_gaps` lists assumptions; hard filter #9 arms once ≥ 3 products have ≥ 14 days of review-count snapshots; relationships are `lazy="raise"`; pacing is Redis-shared with per-process fallback. Add `app/workers/pipeline_steps/{assumptions,review_velocity}.py`, `tests/test_api/` to the file tables.
- [x] `GUIDE.md` scraping section: shared pacing paragraph; note the `pace:{domain}` key.
- [x] `TODO.md`: check off "Review velocity hard filter not armed", "Niche eager loading", "Pacer/rotation state is per worker process", "Supplier sub-score uses assumed defaults"; update "Unbounded API responses" with the rationale in Decisions.
- [x] Commit: `docs: tranche 2 — data gaps, review velocity, lazy loading, shared pacing`

---

## Decisions and deliberately deferred work

- **Supplier unknown = neutral 50, not 0 and not the old 66.** Zero would rank every niche analysed during a 1688 outage last regardless of merit; 66 was a fabricated "decent supplier base". Neutral plus a visible data gap keeps rankings comparable and honest. Cost if wrong: a niche with truly no suppliers gets 50 instead of ~2 on a 10 %-weight sub-score (≈ 5 points).
- **Lifetime velocity function deleted, not kept "for later".** It was dead code with a known miscalibration; the recent-window version replaces it.
- **Velocity needs tracker history.** Filter #9 only fires on a re-analysis ≥ 14 days after the first, for niches the 6-hourly tracker has been visiting (`TRACKING_WINDOW_DAYS = 30`). That is the honest behaviour: no window, no verdict, and the brief says so via `review_velocity_unavailable`.
- **`lazy="raise"` over `lazy="select"`.** In async SQLAlchemy both fail on unloaded access, but `raise` says *why* ("lazy load … cannot proceed") instead of `MissingGreenlet`.
- **Sub-resource pagination stays deferred.** Every niche sub-list is bounded by the pipeline itself (≤ ~150 products, ≤ 100 keywords, 156 projections which the chart needs in full). Paginating would add envelopes the UI must page through for lists that never exceed one page. Revisit if a niche can ever hold > 500 products.
- **Auth / rate limiting / prompt hardening** remain deferred — deployment decisions, not correctness.
- **Pacing key holds for one gap, not a sliding window.** Simplest thing that makes four processes behave like one; a token bucket would let bursts through, which is exactly what blocks get us.

## Self-review

- Spec coverage: F15→D1, F16→E2, F17→E1, F18→F2, F19→F3, F20→G1+G2, F21→F1, middleware defect found by F1→F4. ✔
- Placeholder scan: no TBD/TODO; each step has code or an exact edit. ✔
- Type consistency: `Snapshot = tuple[datetime, int]` used by E2's two functions and `windows_from_rows`; `SharedPacer(redis, min, max, fallback)` matches G1 tests, G2 helper and `BrowserSession(pacer=)`; `_page_cache_for(redis, force)` matches its test; `risk_flags["data_gaps"]` matches frontend read. ✔
