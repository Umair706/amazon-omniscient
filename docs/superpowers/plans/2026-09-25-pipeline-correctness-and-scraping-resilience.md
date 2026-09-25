# Pipeline Correctness, Stability & Scraping Resilience — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every number the Opportunity Brief shows come from real scraped data instead of silent defaults, make the worker survive multi-hour runs, and make Amazon scraping survivable at low volume without paying for engineering we don't need yet.

**Architecture:** Three independent parts, each shippable on its own. Part A rewires services that already exist but were never called (no new algorithms). Part B fixes worker lifecycle and re-run hygiene. Part C replaces "new Chromium per page" with one fingerprint-consistent browser session per run, adds block detection + proxy failover + per-domain pacing, and routes tracked-ASIN refreshes to SP-API when the seller has credentials. New code goes into small focused modules (`app/workers/pipeline_steps/`, `app/services/market_signals.py`, `app/scraping/`) — `tasks.py` is already 1800 lines and must not grow.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Celery 5, Playwright, pytest (+ `pytest-asyncio` auto mode, `AsyncMock`), Next.js 14 / TypeScript.

**Spec:** This plan is derived from the code review in this session (see "Findings" below). There is no separate spec document; the findings table is the spec.

## Global Constraints

- Python `>=3.12`; keep `pyproject.toml` dependency floors as they are. Only new dependency: `python-dateutil>=2.9.0` (already a transitive import in `tasks.py:1288`).
- Follow the repo's engineering rules in `~/.claude/CLAUDE.md`: functions < 30 lines, files < 200 lines for **new** files, no magic numbers (named constants), `// WHY:` / `# WHY:` style comments only where the reason is non-obvious.
- Every new Alembic migration continues the numeric chain: next is `"013"`, `down_revision = "012"`, file `backend/migrations/versions/013_<slug>.py`, same header style as `011_enriched_product_fields.py`.
- Run tests from `backend/`: `pytest -q`. All existing 71 tests must stay green after every task.
- Do not change the meaning of `ScoringService` thresholds or weights — Part A only changes *inputs*.
- Commit after every task with a message that states the *why*.

---

## Findings this plan fixes (the spec)

| ID | Finding | Business impact |
|----|---------|-----------------|
| F1 | `tasks.py:425` calls `analyze_reviews(list[str])`; signature needs `(list[dict], product_title, category)` → always throws, swallowed → product spec & ideas always get "No pain points identified" | The two most valuable LLM outputs (spec, ideas) are built on nothing |
| F2 | `CompetitorService.save_competitor` never called → `competitors` table empty; Niche "Competitors" tab always blank; `CompetitorResponse` lacks the `asin/title/vulnerabilities` fields the UI reads | Whole UI tab dead |
| F3 | Frontend niche detail reads `revenue_score`, `trend_score`, `keyword`, `avg_price`, `estimated_monthly_sales`, `top_keyword_search_volume`…; backend exposes `sales_velocity_score`, `marketing_score`, `primary_keyword`, `avg_sale_price`; `ProductResponse` has no `image_url` | Radar chart and stat cards render 0/— |
| F4 | `_enrich_metrics` reads PPC metrics from the LLM JSON which lacks those keys → `relevant_keyword_count` overwritten to 0, `ppc_budget_90d`/`break_even_acos` saved as 0; `plan_budget`/`save_ppc_keywords` never called; PPC prompt shows `$0/month` | PPC sub-score wrong, PPC overview blank |
| F5 | `calculate_review_velocity_gap` never called → hard filter #9 never runs | Grey-hat niches not flagged |
| F6 | Real 1688 prices scraped but landed cost uses `avg_price * 0.15`; supplier sub-score uses constants (`supplier_count=5`, `best_supplier_score=70`, `min_moq=500`); FOB for financial report is `landed * 0.55` | Margin, supplier score, launch capital are fiction |
| F7 | `strong_seller_count`, `amazon_seller_pct`, `category` never derived → competition/Amazon-dominance filter never fire; category-specific BSR/fee/duty tables never selected | Amazon-dominated niches pass; wrong fees |
| F8 | `niche_intelligence.py` reads `c["vulnerability"]`, `listing_scores["overall"]`, iterates `vulnerabilities` as list of `{type}` — landscape has `vulnerabilities.vulnerability_level`, `overall_score` | LLM market report told "no vulnerabilities" |
| F9 | `marketing_channels` saved as whole `{channels:[…]}` dict; `financial_summary` lacks `marketplace`/`total_launch_capital` read by marketing prompt; exec summary lacks the expert system prompt | Marketing tab dumps raw JSON |
| F10 | `_get_session_factory()` creates a new engine per task and never disposes; no Celery time limits | Worker leaks connections, stuck scrapes block forever |
| F11 | `force=true` re-run appends suppliers/recommendations; niche error text stored in `hard_filter_fail_reasons` | Duplicate rows, misleading UI |
| F12 | `track_bsr_prices` re-inserts stale `product.current_bsr` without scraping; no snapshot at analysis time | BSR/price charts are flat lines |
| F13 | Scraper launches a fresh Chromium + cookie jar per page with a random UA that mismatches `navigator.platform`; no block detection; no pacing; no telemetry | Blocked quickly; images cost proxy GB |
| F14 | `SPAPIService` fully written, never used | Free, legal data source unused |

Deferred deliberately (see "Decisions" at the end): auth/multi-tenancy, API pagination, prompt-injection hardening beyond keyword sanitising, monitoring stack, CAPTCHA-solving vendor integration.

---

# Part A — Make the numbers real

Order matters: A1 → A5 build on the same `metrics` dict; A3 introduces migration 013 which later tasks also use.

## File structure for Part A

```
backend/app/workers/pipeline_steps/__init__.py        (new, empty)
backend/app/workers/pipeline_steps/reviews.py         (new) collect + analyze reviews
backend/app/workers/pipeline_steps/ppc.py             (new) deterministic PPC plan + metrics
backend/app/services/market_signals.py                (new) pure functions: category, strong sellers, Amazon %, review-velocity gap, supplier summary
backend/app/core/category_mapping.py                  (new) Amazon category name → duty slug + fee slug
backend/migrations/versions/013_scoring_columns_and_indexes.py (new)
backend/app/models/niche.py                           (rename 6 score columns; add avg_rating, estimated_monthly_sales, last_error)
backend/app/schemas/niche.py, competitor.py, product.py
backend/app/api/niches.py                             (competitors join)
backend/app/services/competitor_service.py            (persist_landscape, search_position)
backend/app/services/niche_intelligence.py            (key fixes)
backend/app/services/recommendation_engine.py         (column renames, marketing_channels, system prompt)
backend/app/services/financial_report.py              (fee_category param)
backend/app/core/marketplace.py                       (amazon_seller_id)
backend/app/workers/tasks.py                          (call the new modules; delete dead helpers)
frontend/src/app/niches/[nicheId]/page.tsx, frontend/src/types/index.ts
backend/tests/test_services/test_reviews_step.py, test_ppc_step.py, test_market_signals.py, test_competitor_persist.py, test_niche_intelligence.py, test_category_mapping.py
```

---

### Task A1: Review analysis actually runs (F1)

**Files:**
- Create: `backend/app/workers/pipeline_steps/__init__.py` (empty)
- Create: `backend/app/workers/pipeline_steps/reviews.py`
- Modify: `backend/app/workers/tasks.py:416-451` (steps 4/4b) and delete `_collect_reviews` (`:1338-1350`) and `_collect_competitor_reviews` (`:1353-1381`)
- Test: `backend/tests/test_services/test_reviews_step.py`

**Interfaces:**
- Produces: `collect_reviews_by_asin(db, niche_id) -> dict[str, list[dict]]`, `flatten_reviews(reviews_by_asin) -> list[dict]`, `run_review_analysis(llm_client, reviews_by_asin, keyword) -> dict | None`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_services/test_reviews_step.py
import pytest
from unittest.mock import AsyncMock

from app.workers.pipeline_steps.reviews import flatten_reviews, run_review_analysis

REVIEWS_BY_ASIN = {
    "B0A": [{"rating": 2, "title": "Broke", "body": "Handle snapped after a week", "verified_purchase": True, "helpful_votes": 3}],
    "B0B": [{"rating": 5, "title": "Great", "body": "Crushes garlic fine", "verified_purchase": True, "helpful_votes": 0}],
}


def test_flatten_reviews_keeps_every_review():
    flat = flatten_reviews(REVIEWS_BY_ASIN)
    assert len(flat) == 2
    assert {r["body"] for r in flat} == {"Handle snapped after a week", "Crushes garlic fine"}


async def test_run_review_analysis_passes_dicts_and_keyword_to_llm():
    llm = AsyncMock()
    llm.generate_json = AsyncMock(return_value={"sentiment_score": 60, "pain_points": [{"theme": "handle breaks"}], "positive_themes": []})
    result = await run_review_analysis(llm, REVIEWS_BY_ASIN, keyword="garlic press")
    prompt = llm.generate_json.call_args.args[0]
    assert "garlic press" in prompt
    assert "Handle snapped after a week" in prompt
    assert result["pain_points"][0]["theme"] == "handle breaks"


async def test_run_review_analysis_returns_none_without_reviews_or_llm():
    assert await run_review_analysis(None, REVIEWS_BY_ASIN, keyword="x") is None
    assert await run_review_analysis(AsyncMock(), {}, keyword="x") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_services/test_reviews_step.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.workers.pipeline_steps'`

- [ ] **Step 3: Create the step module**

```python
# backend/app/workers/pipeline_steps/reviews.py
"""Pipeline step: collect stored reviews for a niche and run the LLM review analysis."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.review import Review
from app.services.review_analyzer import ReviewAnalyzer

logger = logging.getLogger(__name__)

# WHY: 30 reviews per ASIN keeps the blueprint/intelligence prompts under ~8K tokens.
MAX_REVIEWS_PER_ASIN = 30


async def collect_reviews_by_asin(db: AsyncSession, niche_id: int) -> dict[str, list[dict]]:
    """Return {asin: [review dicts]} for every product in the niche, most helpful first."""
    stmt = (
        select(Product.asin, Review.rating, Review.title, Review.body, Review.verified_purchase, Review.helpful_votes)
        .join(Review, Review.product_id == Product.id)
        .where(Product.niche_id == niche_id)
        .order_by(Product.asin, Review.helpful_votes.desc())
    )
    rows = (await db.execute(stmt)).all()

    reviews_by_asin: dict[str, list[dict]] = {}
    for asin, rating, title, body, verified, helpful in rows:
        bucket = reviews_by_asin.setdefault(asin, [])
        if len(bucket) >= MAX_REVIEWS_PER_ASIN:
            continue
        bucket.append({
            "rating": rating,
            "title": title,
            "body": body,
            "verified_purchase": verified,
            "helpful_votes": helpful or 0,
        })
    return reviews_by_asin


def flatten_reviews(reviews_by_asin: dict[str, list[dict]]) -> list[dict]:
    """Merge the per-ASIN buckets into one list for the sentiment analyzer."""
    flat: list[dict] = []
    for reviews in reviews_by_asin.values():
        flat.extend(reviews)
    return flat


async def run_review_analysis(llm_client, reviews_by_asin: dict[str, list[dict]], keyword: str) -> dict | None:
    """Run sentiment + pain-point analysis. Returns None when there is nothing to analyze or no LLM."""
    reviews = flatten_reviews(reviews_by_asin)
    if not reviews or llm_client is None:
        return None
    analyzer = ReviewAnalyzer(llm_client)
    try:
        return await analyzer.analyze_reviews(reviews, product_title=keyword, category=keyword)
    except Exception as e:
        logger.warning("Review analysis failed: %s", e)
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_services/test_reviews_step.py -v`
Expected: 3 PASS

- [ ] **Step 5: Wire it into `tasks.py`**

Replace steps 4 and 4b (`tasks.py:416-451`) with:

```python
        # ── Step 4: Collect reviews + sentiment/pain-point analysis ─────
        task.update_state(state="PROGRESS", meta={"step": "review_analysis", "progress": 38})
        from app.workers.pipeline_steps.reviews import collect_reviews_by_asin, flatten_reviews, run_review_analysis

        competitor_reviews_map = await collect_reviews_by_asin(db, niche_id)
        review_insights = await run_review_analysis(llm_client, competitor_reviews_map, keyword)

        # ── Step 4b: Review Intelligence (deep cross-product synthesis) ──
        task.update_state(state="PROGRESS", meta={"step": "review_intelligence", "progress": 42})
        review_intelligence = None
        product_titles_map = {
            p.get("asin", ""): p.get("title", "")
            for p in detailed_products if p.get("asin")
        }
        if competitor_reviews_map and llm_client:
            try:
                review_intelligence = await ReviewAnalyzer(llm_client).generate_review_intelligence(
                    all_reviews=flatten_reviews(competitor_reviews_map),
                    product_reviews=competitor_reviews_map,
                    niche_keyword=keyword,
                    product_titles=product_titles_map,
                )
            except Exception as e:
                logger.warning("Review intelligence failed: %s", e)
```

Keep `from app.services.review_analyzer import ReviewAnalyzer` at the top of the step. In step 4d (`tasks.py:488-489`) delete the two lines `if not competitor_reviews_map: competitor_reviews_map = await _collect_competitor_reviews(db, niche_id)`. Delete `_collect_reviews` and `_collect_competitor_reviews` at the bottom of the file.

- [ ] **Step 6: Run the whole suite and commit**

Run: `cd backend && pytest -q`
Expected: all green.

```bash
git add backend/app/workers/pipeline_steps backend/app/workers/tasks.py backend/tests/test_services/test_reviews_step.py
git commit -m "fix: run review sentiment analysis with the dict/title/category signature it requires"
```

---

### Task A2: Persist competitor analysis and expose it to the UI (F2)

**Files:**
- Modify: `backend/app/services/competitor_service.py:238-349` (add `search_position` to details; add `persist_landscape`)
- Modify: `backend/app/schemas/competitor.py`
- Modify: `backend/app/api/niches.py:227-252`
- Modify: `backend/app/workers/tasks.py` step 3 (`:403-414`)
- Test: `backend/tests/test_services/test_competitor_persist.py`

**Interfaces:**
- Produces: `CompetitorService.persist_landscape(niche_id: int, landscape: dict) -> int` (rows saved). `CompetitorResponse` gains `asin, title, review_count, rating, vulnerabilities: list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_services/test_competitor_persist.py
from unittest.mock import AsyncMock, MagicMock

from app.models.competitor import Competitor
from app.services.competitor_service import CompetitorService


def _result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


async def test_persist_landscape_saves_one_row_per_known_product(mock_db):
    # First execute = product lookup (found, id 42); second = existing competitor (none)
    mock_db.execute = AsyncMock(side_effect=[_result(42), _result(None)])
    svc = CompetitorService(mock_db)
    landscape = {
        "competitor_details": [{
            "asin": "B0A",
            "search_position": 7,
            "listing_scores": {"overall_score": 61.5, "title_score": 70, "image_score": 60, "bullet_score": 80,
                               "a_plus_score": 0, "video_score": 0, "backend_kw_score": 50, "review_score": 40},
            "vulnerabilities": {"vulnerability_level": "medium", "vulnerability_types": ["no_a_plus", "no_video"]},
        }]
    }
    saved = await svc.persist_landscape(niche_id=1, landscape=landscape)
    assert saved == 1
    comp = mock_db.add.call_args.args[0]
    assert isinstance(comp, Competitor)
    assert comp.organic_rank == 7
    assert float(comp.listing_quality_score) == 61.5
    assert comp.vulnerability == "medium"
    assert comp.vulnerability_type == "no_a_plus,no_video"


async def test_persist_landscape_skips_unknown_asin(mock_db):
    mock_db.execute = AsyncMock(side_effect=[_result(None)])
    svc = CompetitorService(mock_db)
    saved = await svc.persist_landscape(1, {"competitor_details": [{"asin": "NOPE", "listing_scores": {}, "vulnerabilities": {}}]})
    assert saved == 0
    mock_db.add.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_services/test_competitor_persist.py -v`
Expected: FAIL with `AttributeError: 'CompetitorService' object has no attribute 'persist_landscape'`

- [ ] **Step 3: Implement**

In `analyze_landscape` (`competitor_service.py:340-348`) add `"search_position": p.get("position")` to each `competitor_details` entry. Then add after `save_competitor`:

```python
    async def persist_landscape(self, niche_id: int, landscape: dict) -> int:
        """Save every competitor_details entry as a Competitor row. Returns rows saved."""
        saved = 0
        for fallback_rank, detail in enumerate(landscape.get("competitor_details", []), start=1):
            asin = detail.get("asin")
            if not asin:
                continue
            product_id = (
                await self.db.execute(select(Product.id).where(Product.asin == asin))
            ).scalar_one_or_none()
            if product_id is None:
                continue
            await self.save_competitor(
                niche_id=niche_id,
                product_id=product_id,
                organic_rank=detail.get("search_position") or fallback_rank,
                listing_scores=detail.get("listing_scores", {}),
                vulnerability_info=detail.get("vulnerabilities", {}),
            )
            saved += 1
        return saved
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_services/test_competitor_persist.py -v`
Expected: 2 PASS

- [ ] **Step 5: Call it from the pipeline**

In `tasks.py` step 3, after `competitor_landscape["marketplace"] = marketplace`:

```python
        if competitor_landscape:
            competitor_landscape["marketplace"] = marketplace
            try:
                saved_competitors = await competitor_svc.persist_landscape(niche_id, competitor_landscape)
                await db.flush()
                logger.info("Persisted %d competitor rows for niche %d", saved_competitors, niche_id)
            except Exception as e:
                logger.warning("Persisting competitors failed: %s", e)
```

- [ ] **Step 6: Expose product fields on the competitor response**

`backend/app/schemas/competitor.py` — add after `vulnerability_type`:

```python
    # Joined from Product for the UI
    asin: str | None = None
    title: str | None = None
    review_count: int | None = None
    rating: Decimal | None = None
    vulnerabilities: list[str] = Field(default_factory=list)
```

`backend/app/api/niches.py:242-252` — replace the fetch with a join:

```python
    result = await db.execute(
        select(Competitor, Product)
        .join(Product, Competitor.product_id == Product.id)
        .where(Competitor.niche_id == niche_id)
        .order_by(Competitor.organic_rank.asc().nullslast())
    )
    items = []
    for competitor, product in result.all():
        item = CompetitorResponse.model_validate(competitor)
        item.asin = product.asin
        item.title = product.title
        item.review_count = product.review_count
        item.rating = product.rating
        item.vulnerabilities = [v for v in (competitor.vulnerability_type or "").split(",") if v]
        items.append(item)

    return CompetitorListResponse(items=items, total=total)
```

- [ ] **Step 7: Run suite, commit**

Run: `cd backend && pytest -q`

```bash
git add backend/app/services/competitor_service.py backend/app/schemas/competitor.py backend/app/api/niches.py backend/app/workers/tasks.py backend/tests/test_services/test_competitor_persist.py
git commit -m "feat: persist competitor listing analysis so the Competitors tab has data"
```

---

### Task A3: One schema for scores across DB, API and UI (F3) — migration 013

**Files:**
- Create: `backend/migrations/versions/013_scoring_columns_and_indexes.py`
- Modify: `backend/app/models/niche.py:43-54`, `backend/app/schemas/niche.py:93-104`, `backend/app/schemas/product.py` (add `image_url`), `backend/app/services/recommendation_engine.py:309-326`, `backend/app/workers/tasks.py:1135-1145` (`_update_niche_status`)
- Modify: `frontend/src/types/index.ts:27-62`, `frontend/src/app/niches/[nicheId]/page.tsx:25-52,195-244,290`
- Test: `backend/tests/test_recommendation_engine.py` (existing tests reference the old column names — update them)

**Interfaces:**
- Produces: `Niche.revenue_score, trend_score, review_feasibility_score, supplier_score, ppc_viability_score, launch_feasibility_score, avg_rating, estimated_monthly_sales, last_error`. `competitors.vulnerability_type` widened to 255.

- [ ] **Step 1: Write the migration**

```python
# backend/migrations/versions/013_scoring_columns_and_indexes.py
"""Rename niche score columns to match ScoringService names, add avg_rating,
estimated_monthly_sales, last_error, widen competitors.vulnerability_type,
and add the indexes the list endpoints filter on.

Revision ID: 013
Revises: 012
Create Date: 2026-09-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (old name, new name) — the old names described the wrong thing.
_SCORE_RENAMES = [
    ("sales_velocity_score", "revenue_score"),
    ("marketing_score", "trend_score"),
    ("review_achievability_score", "review_feasibility_score"),
    ("supplier_reliability_score", "supplier_score"),
    ("ad_profitability_score", "ppc_viability_score"),
    ("brand_building_score", "launch_feasibility_score"),
]


def upgrade() -> None:
    for old, new in _SCORE_RENAMES:
        op.alter_column("niches", old, new_column_name=new)
    op.add_column("niches", sa.Column("avg_rating", sa.Numeric(3, 2), nullable=True))
    op.add_column("niches", sa.Column("estimated_monthly_sales", sa.Integer(), nullable=True))
    op.add_column("niches", sa.Column("last_error", sa.Text(), nullable=True))

    op.alter_column("competitors", "vulnerability_type", type_=sa.String(255))

    op.create_index("ix_products_niche_id", "products", ["niche_id"], if_not_exists=True)
    op.create_index("ix_reviews_product_id", "reviews", ["product_id"], if_not_exists=True)
    op.create_index("ix_suppliers_niche_id", "suppliers", ["niche_id"], if_not_exists=True)
    op.create_index("ix_recommendations_niche_id", "recommendations", ["niche_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_recommendations_niche_id", table_name="recommendations")
    op.drop_index("ix_suppliers_niche_id", table_name="suppliers")
    op.drop_index("ix_reviews_product_id", table_name="reviews")
    op.drop_index("ix_products_niche_id", table_name="products")
    op.alter_column("competitors", "vulnerability_type", type_=sa.String(50))
    op.drop_column("niches", "last_error")
    op.drop_column("niches", "estimated_monthly_sales")
    op.drop_column("niches", "avg_rating")
    for old, new in _SCORE_RENAMES:
        op.alter_column("niches", new, new_column_name=old)
```

- [ ] **Step 2: Update the model**

`backend/app/models/niche.py:43-54` becomes:

```python
    # Scores — names match ScoringService.WEIGHTS keys
    opportunity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    confidence_tier: Mapped[str | None] = mapped_column(String(20))
    demand_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    competition_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    revenue_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    margin_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    trend_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    review_feasibility_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    supplier_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ppc_viability_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    launch_feasibility_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Market snapshot
    avg_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    estimated_monthly_sales: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 3: Update the engine write-back**

`recommendation_engine.py:309-326` becomes:

```python
        sub = score_result["sub_scores"]
        niche.demand_score = Decimal(str(sub.get("demand", 0)))
        niche.competition_score = Decimal(str(sub.get("competition", 0)))
        niche.revenue_score = Decimal(str(sub.get("revenue", 0)))
        niche.margin_score = Decimal(str(sub.get("margin", 0)))
        niche.trend_score = Decimal(str(sub.get("trend", 0)))
        niche.review_feasibility_score = Decimal(str(sub.get("review_feasibility", 0)))
        niche.supplier_score = Decimal(str(sub.get("supplier", 0)))
        niche.ppc_viability_score = Decimal(str(sub.get("ppc_viability", 0)))
        niche.launch_feasibility_score = Decimal(str(sub.get("launch_feasibility", 0)))

        niche.avg_bsr = metrics.get("avg_bsr")
        niche.avg_sale_price = Decimal(str(metrics.get("avg_price", 0))) if metrics.get("avg_price") else None
        niche.avg_review_count = metrics.get("avg_review_count")
        niche.avg_rating = Decimal(str(metrics.get("avg_rating", 0))) if metrics.get("avg_rating") else None
        niche.estimated_monthly_sales = metrics.get("estimated_monthly_sales")
        niche.monthly_search_volume = metrics.get("search_volume")
        niche.is_seasonal = metrics.get("is_seasonal", False)
        niche.last_error = None
```

And `tasks.py:_update_niche_status` — replace `values["hard_filter_fail_reasons"] = [error]` with `values["last_error"] = error[:2000]`.

- [ ] **Step 4: Update schemas**

`schemas/niche.py:93-104` — same rename as the model; add `avg_rating: Decimal | None = None`, `estimated_monthly_sales: int | None = None`, `last_error: str | None = None`.

`schemas/product.py` — add `image_url: str | None = None` to **both** `ProductSummary` and `ProductResponse` (after `brand`).

- [ ] **Step 5: Fix existing engine tests, then run**

Open `backend/tests/test_recommendation_engine.py`; replace any assertion on `sales_velocity_score`, `marketing_score`, `review_achievability_score`, `supplier_reliability_score`, `ad_profitability_score`, `brand_building_score` with the new names.

Run: `cd backend && pytest -q` → green. Then `alembic upgrade head` against the dev DB → succeeds.

- [ ] **Step 6: Fix the frontend contract**

`frontend/src/types/index.ts:27-62` `NicheDetail` — rename the six score fields to match, add `avg_rating: string | null; estimated_monthly_sales: number | null; last_error: string | null;`. Add `image_url: string | null;` to `ProductSummary`.

`frontend/src/app/niches/[nicheId]/page.tsx`:
- Delete the local `NicheDetail` interface (`:25-52`) and `import type { NicheDetail } from "@/types"`.
- `:195-205` becomes:

```ts
  const num = (v: string | number | null) => (v == null ? 0 : Number(v));
  const subScores: Record<string, number> = {
    demand: num(niche.demand_score),
    competition: num(niche.competition_score),
    revenue: num(niche.revenue_score),
    margin: num(niche.margin_score),
    trend: num(niche.trend_score),
    review_feasibility: num(niche.review_feasibility_score),
    supplier: num(niche.supplier_score),
    ppc_viability: num(niche.ppc_viability_score),
    launch_feasibility: num(niche.launch_feasibility_score),
  };
```

- Header (`:228-229`): `niche.name` / `niche.primary_keyword`.
- Stat cards (`:238-243`): `niche.avg_sale_price`, `niche.avg_bsr`, `niche.estimated_monthly_sales`, `niche.monthly_search_volume`, `niche.avg_rating`, `niche.avg_review_count`.
- `:290` text → `All 9 hard disqualification filters passed.`
- Add above the tabs: `{niche.last_error && <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">Last run failed: {niche.last_error}</div>}`
- Products table image: `p.image_url` only (drop `main_image_url`).

Run: `cd frontend && npx tsc --noEmit` → no errors.

- [ ] **Step 7: Commit**

```bash
git add backend/migrations/versions/013_scoring_columns_and_indexes.py backend/app/models/niche.py backend/app/schemas backend/app/services/recommendation_engine.py backend/app/workers/tasks.py backend/tests/test_recommendation_engine.py frontend/src/types/index.ts "frontend/src/app/niches/[nicheId]/page.tsx"
git commit -m "fix: align niche score columns with ScoringService names so the UI radar shows real values"
```

---

### Task A4: Deterministic PPC plan feeds scoring and the brief (F4, F9-partial)

**Files:**
- Create: `backend/app/workers/pipeline_steps/ppc.py`
- Modify: `backend/app/workers/tasks.py` step 8 (`:629-656`), step 10 (`:677-703`), `_enrich_metrics` (`:1709-1714`)
- Test: `backend/tests/test_services/test_ppc_step.py`

**Interfaces:**
- Produces: `build_ppc_strategy(ppc_svc, *, niche_id, keyword, metrics, competitor_landscape) -> dict` returning `{**plan_budget(), "break_even": {...}, "top_keywords": [...], "llm_strategy": dict|None}` and `ppc_metrics_from_strategy(ppc_strategy) -> dict` with keys `avg_cpc, break_even_acos, relevant_keyword_count, ppc_budget_90d, estimated_acos, ppc_daily_budget`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_services/test_ppc_step.py
from unittest.mock import AsyncMock, MagicMock

from app.workers.pipeline_steps.ppc import build_ppc_strategy, ppc_metrics_from_strategy


def _fake_ppc_service():
    from app.services.ppc_service import PPCService
    svc = PPCService(db=MagicMock(), llm_client=None)
    svc.build_keyword_portfolio = AsyncMock(return_value={
        "exact_match": [{"keyword": "garlic press", "search_volume": 3000, "avg_cpc": 1.2, "competition": "high", "relevance_score": 90}],
        "phrase_match": [], "broad_match": [], "negative_candidates": [],
        "total_keywords": 1, "estimated_daily_spend": 3.6, "estimated_monthly_spend": 108,
    })
    svc.save_ppc_keywords = AsyncMock(return_value=1)
    return svc


async def test_build_ppc_strategy_uses_deterministic_budget_and_saves_keywords():
    svc = _fake_ppc_service()
    metrics = {"avg_price": 30, "landed_cost": 8, "fba_fees": 5, "ppc_daily_budget": 30}
    strategy = await build_ppc_strategy(svc, niche_id=1, keyword="garlic press", metrics=metrics, competitor_landscape=None)
    assert strategy["phases"]["launch"]["monthly_budget"] > 0
    assert strategy["break_even"]["break_even_acos"] > 0
    assert strategy["top_keywords"] == ["garlic press"]
    assert strategy["llm_strategy"] is None
    svc.save_ppc_keywords.assert_awaited_once()


def test_ppc_metrics_from_strategy_maps_real_keys():
    strategy = {
        "avg_cpc": 1.2, "total_keywords": 12, "total_90_day_budget": 2700,
        "phases": {"launch": {"daily_budget": 45, "estimated_acos": 62.5}},
        "break_even": {"break_even_acos": 41.0},
    }
    m = ppc_metrics_from_strategy(strategy)
    assert m == {
        "avg_cpc": 1.2, "break_even_acos": 41.0, "relevant_keyword_count": 12,
        "ppc_budget_90d": 2700, "estimated_acos": 62.5, "ppc_daily_budget": 45,
    }


def test_ppc_metrics_from_strategy_omits_zero_cpc_so_keyword_research_estimate_survives():
    m = ppc_metrics_from_strategy({"avg_cpc": 0, "total_keywords": 0, "phases": {}, "break_even": {}})
    assert "avg_cpc" not in m
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_services/test_ppc_step.py -v`
Expected: FAIL `ModuleNotFoundError ... pipeline_steps.ppc`

- [ ] **Step 3: Implement**

```python
# backend/app/workers/pipeline_steps/ppc.py
"""Pipeline step: build the PPC plan from keyword data (deterministic) plus an optional LLM narrative."""

import logging

from app.services.ppc_service import PPCService

logger = logging.getLogger(__name__)

DEFAULT_SELLING_PRICE = 30.0
DEFAULT_LANDED_COST = 8.0
DEFAULT_FBA_FEES = 5.0
DEFAULT_DAILY_BUDGET = 30.0
TOP_KEYWORDS_SHOWN = 10


async def build_ppc_strategy(
    ppc_svc: PPCService, *, niche_id: int, keyword: str, metrics: dict, competitor_landscape: dict | None,
) -> dict:
    """Return the budget plan (numbers we computed) merged with break-even data and the LLM narrative."""
    selling_price = metrics.get("avg_price") or DEFAULT_SELLING_PRICE
    break_even = ppc_svc.calculate_break_even_acos(
        selling_price=selling_price,
        landed_cost=metrics.get("landed_cost") or DEFAULT_LANDED_COST,
        fba_fees=metrics.get("fba_fees") or DEFAULT_FBA_FEES,
    )
    portfolio = await ppc_svc.build_keyword_portfolio(niche_id=niche_id)
    budget_plan = ppc_svc.plan_budget(
        keyword_portfolio=portfolio,
        target_acos=break_even["target_acos"],
        selling_price=selling_price,
        daily_budget_cap=metrics.get("ppc_daily_budget") or DEFAULT_DAILY_BUDGET,
    )
    await ppc_svc.save_ppc_keywords(niche_id, portfolio)

    llm_strategy = None
    if ppc_svc.llm:
        try:
            llm_strategy = await ppc_svc.generate_ppc_strategy(
                niche_keyword=keyword,
                keyword_portfolio=portfolio,
                budget_plan=budget_plan,
                break_even_acos=break_even,
                competitor_landscape=competitor_landscape,
            )
        except Exception as e:
            logger.warning("LLM PPC strategy failed: %s", e)

    return {
        **budget_plan,
        "break_even": break_even,
        "top_keywords": [k["keyword"] for k in portfolio.get("exact_match", [])[:TOP_KEYWORDS_SHOWN]],
        "llm_strategy": llm_strategy,
    }


def ppc_metrics_from_strategy(ppc_strategy: dict) -> dict:
    """Extract the scoring inputs from a build_ppc_strategy() result. Zero CPC is omitted, not written."""
    launch = ppc_strategy.get("phases", {}).get("launch", {})
    metrics = {
        "break_even_acos": ppc_strategy.get("break_even", {}).get("break_even_acos", 0),
        "relevant_keyword_count": ppc_strategy.get("total_keywords", 0),
        "ppc_budget_90d": ppc_strategy.get("total_90_day_budget", 0),
        "estimated_acos": launch.get("estimated_acos", 0),
        "ppc_daily_budget": launch.get("daily_budget", 0),
    }
    if ppc_strategy.get("avg_cpc"):
        metrics["avg_cpc"] = ppc_strategy["avg_cpc"]
    return metrics
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_services/test_ppc_step.py -v` → 3 PASS

- [ ] **Step 5: Wire into `tasks.py`**

Step 8 (`:629-656`) becomes:

```python
        # ── Step 8: PPC strategy ───────────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "ppc_strategy", "progress": 65})
        from app.services.ppc_service import PPCService
        from app.workers.pipeline_steps.ppc import build_ppc_strategy

        ppc_strategy = None
        try:
            ppc_strategy = await build_ppc_strategy(
                PPCService(db, llm_client),
                niche_id=niche_id, keyword=keyword, metrics=metrics, competitor_landscape=competitor_landscape,
            )
            await db.flush()
        except Exception as e:
            logger.warning("PPC strategy generation failed: %s", e)
```

`_enrich_metrics` (`:1709-1714`) becomes:

```python
    if ppc_strategy:
        from app.workers.pipeline_steps.ppc import ppc_metrics_from_strategy
        metrics.update(ppc_metrics_from_strategy(ppc_strategy))
```

Step 10: after `metrics["total_launch_capital"] = launch_capital["total_launch_capital"]` add:

```python
            financial_summary["marketplace"] = marketplace
            financial_summary["total_launch_capital"] = launch_capital["total_launch_capital"]
```

(`marketing_service.generate_launch_playbook` reads exactly these two keys.)

- [ ] **Step 6: Run suite, commit**

```bash
git add backend/app/workers/pipeline_steps/ppc.py backend/app/workers/tasks.py backend/tests/test_services/test_ppc_step.py
git commit -m "fix: compute PPC budget/keywords deterministically and feed real values into scoring"
```

---

### Task A5: Derive market signals from scraped data (F5, F6, F7)

**Files:**
- Create: `backend/app/services/market_signals.py`
- Create: `backend/app/core/category_mapping.py`
- Modify: `backend/app/core/marketplace.py:44-72,171-208` (add `amazon_seller_id`)
- Modify: `backend/app/services/financial_report.py:98-121,175-191` (add `fee_category`)
- Modify: `backend/app/workers/tasks.py` `_build_base_metrics` (`:1596-1690`), `_analyze_suppliers` (`:1454-1483`), step 6a/6b (`:541-610`), step 12 (`:723-746`), `_enrich_metrics` (`:1728-1731`)
- Modify: `backend/pyproject.toml` (add `python-dateutil>=2.9.0`)
- Modify: `backend/tests/test_scoring_service.py:135-137` (filter count)
- Test: `backend/tests/test_services/test_market_signals.py`, `backend/tests/test_services/test_category_mapping.py`

**Interfaces:**
- Produces (all pure):
  - `derive_category(products: list[dict]) -> str` — most common `bsr_category`, else `"default"`
  - `count_strong_sellers(products) -> int`
  - `amazon_seller_pct(products, amazon_seller_id: str) -> float`
  - `average_review_velocity_gap(products, estimator, category) -> float | None`
  - `summarize_suppliers(suppliers: list[dict]) -> dict` with `count, best_score, min_moq, median_fob_usd`
  - `category_slugs(bsr_category) -> tuple[duty_slug, fee_slug]`
- `MarketplaceConfig.amazon_seller_id: str`
- `FinancialReportService.generate_full_report(..., fee_category: str | None = None)`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_services/test_market_signals.py
from app.core.bsr_regression import BSRSalesEstimator
from app.services.market_signals import (
    amazon_seller_pct, average_review_velocity_gap, count_strong_sellers, derive_category, summarize_suppliers,
)

PRODUCTS = [
    {"asin": "A", "bsr_category": "Home & Kitchen", "review_count": 2500, "rating": 4.6, "seller_id": "ATVPDKIKX0DER",
     "current_bsr": 1200, "date_first_available": "January 5, 2024"},
    {"asin": "B", "bsr_category": "Home & Kitchen", "review_count": 40, "rating": 4.1, "seller_id": "A1XYZ",
     "current_bsr": 30000, "date_first_available": "March 1, 2025"},
    {"asin": "C", "bsr_category": "Kitchen & Dining", "review_count": 1500, "rating": 3.9, "seller_id": "A2ABC",
     "current_bsr": None, "date_first_available": None},
]


def test_derive_category_picks_most_common():
    assert derive_category(PRODUCTS) == "Home & Kitchen"
    assert derive_category([]) == "default"


def test_count_strong_sellers_requires_reviews_and_rating():
    assert count_strong_sellers(PRODUCTS) == 1  # only A: 2500 reviews AND 4.6


def test_amazon_seller_pct():
    assert amazon_seller_pct(PRODUCTS, "ATVPDKIKX0DER") == round(100 / 3, 1)
    assert amazon_seller_pct([], "ATVPDKIKX0DER") == 0.0


def test_average_review_velocity_gap_skips_products_without_dates_or_bsr():
    estimator = BSRSalesEstimator("US")
    gap = average_review_velocity_gap(PRODUCTS, estimator, "Home & Kitchen")
    assert gap is not None and gap > 0
    assert average_review_velocity_gap([PRODUCTS[2]], estimator, "Home & Kitchen") is None


def test_summarize_suppliers():
    suppliers = [
        {"supplier_name": "X", "moq": 500, "price_min": 20.0, "supplier_score": 60},
        {"supplier_name": "Y", "moq": 100, "price_min": 30.0, "supplier_score": 85},
        {"supplier_name": "Z", "moq": None, "price_min": None, "supplier_score": 20},
    ]
    s = summarize_suppliers(suppliers, cny_to_usd_rate=10.0)
    assert s == {"count": 3, "best_score": 85, "min_moq": 100, "median_fob_usd": 2.5}
    assert summarize_suppliers([], cny_to_usd_rate=10.0) == {"count": 0, "best_score": None, "min_moq": None, "median_fob_usd": None}
```

```python
# backend/tests/test_services/test_category_mapping.py
from app.core.category_mapping import category_slugs


def test_known_category():
    assert category_slugs("Home & Kitchen") == ("home", "home")
    assert category_slugs("Sports & Outdoors") == ("sports", "sports_and_outdoors")


def test_unknown_category_falls_back_to_default():
    assert category_slugs("Musical Instruments") == ("default", "default")
    assert category_slugs(None) == ("default", "default")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_services/test_market_signals.py tests/test_services/test_category_mapping.py -v`
Expected: FAIL with ModuleNotFoundError (both modules).

- [ ] **Step 3: Implement `category_mapping.py`**

```python
# backend/app/core/category_mapping.py
"""Map Amazon's BSR category display names onto the duty and FBA fee vocabularies used internally."""

# WHY: SupplierService duty tables and FBAFeeCalculator referral tables use two different slug sets.
# (duty_slug, fee_slug) per Amazon top-level category name as it appears in "#123 in Home & Kitchen".
_CATEGORY_SLUGS: dict[str, tuple[str, str]] = {
    "home & kitchen": ("home", "home"),
    "kitchen & dining": ("kitchen", "kitchen"),
    "sports & outdoors": ("sports", "sports_and_outdoors"),
    "tools & home improvement": ("home", "tools_and_home_improvement"),
    "health & household": ("health", "health_and_personal_care"),
    "beauty & personal care": ("beauty", "beauty"),
    "baby": ("default", "baby_products"),
    "baby products": ("default", "baby_products"),
    "pet supplies": ("pet", "pet_supplies"),
    "patio, lawn & garden": ("garden", "lawn_and_garden"),
    "office products": ("office", "office_products"),
    "toys & games": ("toys", "toys_and_games"),
    "automotive": ("automotive", "automotive"),
    "electronics": ("electronics", "consumer_electronics"),
    "cell phones & accessories": ("electronics", "electronics_accessories"),
    "clothing, shoes & jewelry": ("clothing", "clothing_and_accessories"),
    "industrial & scientific": ("default", "industrial_and_scientific"),
    "grocery & gourmet food": ("default", "grocery_and_gourmet"),
}

DEFAULT_SLUGS = ("default", "default")


def category_slugs(bsr_category: str | None) -> tuple[str, str]:
    """Return (duty_slug, fee_slug) for an Amazon category name; ("default","default") if unknown."""
    if not bsr_category:
        return DEFAULT_SLUGS
    return _CATEGORY_SLUGS.get(bsr_category.strip().lower(), DEFAULT_SLUGS)
```

- [ ] **Step 4: Implement `market_signals.py`**

```python
# backend/app/services/market_signals.py
"""Pure functions that turn scraped product/supplier dicts into ScoringService inputs."""

from collections import Counter
from datetime import date, datetime
from statistics import median

from dateutil.parser import parse as parse_date

from app.core.bsr_regression import BSRSalesEstimator
from app.services.competitor_service import CompetitorService

# A listing with this many reviews at this rating is an entrenched brand a new entrant must out-spend.
STRONG_SELLER_MIN_REVIEWS = 1000
STRONG_SELLER_MIN_RATING = 4.3
DAYS_PER_MONTH = 30.4


def derive_category(products: list[dict]) -> str:
    """Most common main-category BSR label across products, or 'default'."""
    labels = [p["bsr_category"] for p in products if p.get("bsr_category")]
    if not labels:
        return "default"
    return Counter(labels).most_common(1)[0][0]


def count_strong_sellers(products: list[dict]) -> int:
    """Count listings that are both heavily reviewed and highly rated."""
    return sum(
        1 for p in products
        if (p.get("review_count") or 0) >= STRONG_SELLER_MIN_REVIEWS
        and float(p.get("rating") or 0) >= STRONG_SELLER_MIN_RATING
    )


def amazon_seller_pct(products: list[dict], amazon_seller_id: str) -> float:
    """Percentage of products whose Buy Box seller is Amazon itself."""
    if not products:
        return 0.0
    amazon_count = sum(1 for p in products if p.get("seller_id") == amazon_seller_id)
    return round(amazon_count / len(products) * 100, 1)


def _months_listed(date_first_available) -> float | None:
    if not date_first_available:
        return None
    try:
        listed = date_first_available if isinstance(date_first_available, date) else parse_date(str(date_first_available)).date()
    except (ValueError, OverflowError):
        return None
    days = (datetime.now().date() - listed).days
    return max(days / DAYS_PER_MONTH, 1.0)


def average_review_velocity_gap(products: list[dict], estimator: BSRSalesEstimator, category: str) -> float | None:
    """Mean reviews-per-100-sales ratio across products with a BSR and a listing date. None if no data."""
    ratios = []
    for p in products:
        months = _months_listed(p.get("date_first_available"))
        bsr = p.get("current_bsr") or p.get("bsr")
        if not months or not bsr:
            continue
        monthly_sales = estimator.estimate_monthly_sales(int(bsr), category)
        reviews_per_month = (p.get("review_count") or 0) / months
        ratios.append(CompetitorService.calculate_review_velocity_gap(monthly_sales, reviews_per_month)["gap_ratio"])
    if not ratios:
        return None
    return round(sum(ratios) / len(ratios), 2)


def summarize_suppliers(suppliers: list[dict], cny_to_usd_rate: float) -> dict:
    """Aggregate scraped 1688 listings into the supplier sub-score inputs. Prices in the input are CNY."""
    if not suppliers:
        return {"count": 0, "best_score": None, "min_moq": None, "median_fob_usd": None}
    moqs = [s["moq"] for s in suppliers if s.get("moq")]
    fob_usd = [round(s["price_min"] / cny_to_usd_rate, 4) for s in suppliers if s.get("price_min")]
    scores = [s.get("supplier_score") or 0 for s in suppliers]
    return {
        "count": len(suppliers),
        "best_score": max(scores) if scores else None,
        "min_moq": min(moqs) if moqs else None,
        "median_fob_usd": round(median(fob_usd), 4) if fob_usd else None,
    }
```

Add `"python-dateutil>=2.9.0",` under `# Utilities` in `pyproject.toml`, then `pip install -e ".[dev]"`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_services/test_market_signals.py tests/test_services/test_category_mapping.py -v` → all PASS

- [ ] **Step 6: Add `amazon_seller_id` to marketplace config**

`core/marketplace.py` `MarketplaceConfig` — add field after `sp_api_endpoint`: `amazon_seller_id: str  # Amazon's own merchant ID; used to detect Amazon-as-seller`. In the registry: US `amazon_seller_id="ATVPDKIKX0DER"`, AU `amazon_seller_id="ANEGB3WVEVKZB"`.

> NOTE: verify the AU value once by scraping any ASIN whose Buy Box says "Sold by Amazon AU" and reading `seller=` from `#sellerProfileTriggerId` href. The US value is well known.

- [ ] **Step 7: Let `FinancialReportService` take a fee category**

`financial_report.py:98-121` — add parameter `fee_category: str | None = None,` after `category`. In `generate_full_report` step 2 (`:184-191`) pass `category=fee_category or category` to `calculate_all_fees`. (`calculate_landed_cost` keeps `category` = duty slug.)

- [ ] **Step 8: Feed the signals in `tasks.py`**

In `_build_base_metrics` (`:1596`), change the signature to `_build_base_metrics(competitor_landscape, detailed_products, keyword_research_summary=None, marketplace="US")` and add, right after the `metrics = {...}` literal:

```python
    from app.core.marketplace import get_marketplace
    from app.services.market_signals import amazon_seller_pct, count_strong_sellers, derive_category

    metrics["marketplace"] = marketplace
    metrics["category"] = derive_category(detailed_products)
    metrics["strong_seller_count"] = count_strong_sellers(detailed_products)
    metrics["amazon_seller_pct"] = amazon_seller_pct(detailed_products, get_marketplace(marketplace).amazon_seller_id)
    ratings = [float(p["rating"]) for p in detailed_products if p.get("rating")]
    metrics["avg_rating"] = round(sum(ratings) / len(ratings), 2) if ratings else 0
```

In the `if competitor_landscape:` block delete the two lines that overwrite `strong_seller_count` and `amazon_seller_pct` from the landscape (the landscape never had them). After the `estimated_monthly_sales` fallback add:

```python
    from app.services.market_signals import average_review_velocity_gap
    from app.core.bsr_regression import BSRSalesEstimator
    gap = average_review_velocity_gap(detailed_products, BSRSalesEstimator(marketplace=marketplace), metrics["category"])
    if gap is not None:
        metrics["avg_review_velocity_gap_ratio"] = gap
```

Update both call sites (`:464` and `:604`) to pass `marketplace=marketplace`; delete the now-redundant `metrics["marketplace"] = marketplace` at `:605`.

Step 6a, after `_save_suppliers`:

```python
        from app.services.market_signals import summarize_suppliers
        supplier_summary = summarize_suppliers(scraped_suppliers, cny_to_usd_rate=_CNY_TO_USD_RATE)
```

`_save_suppliers` must also write the computed score into each dict so the summary can read it: after `score = _calculate_supplier_score(s)` add `s["supplier_score"] = score`.

Step 6b: build metrics, then:

```python
        metrics = _build_base_metrics(competitor_landscape, detailed_products, keyword_research_summary, marketplace=marketplace)
        if supplier_summary["count"]:
            metrics["supplier_count"] = supplier_summary["count"]
            metrics["best_supplier_score"] = supplier_summary["best_score"]
            metrics["min_moq"] = supplier_summary["min_moq"]
        product_dims = _extract_avg_dimensions(detailed_products)
        supplier_data = None
        try:
            supplier_data = await _analyze_suppliers(
                db, niche_id, metrics, marketplace=marketplace,
                fob_unit_cost=supplier_summary["median_fob_usd"], weight_kg=product_dims["weight_lb"] * LB_TO_KG,
            )
        except Exception as e:
            logger.warning("Supplier analysis failed: %s", e)
```

Add module constants near `_CNY_TO_USD_RATE`: `LB_TO_KG = 0.4536` and `FOB_FALLBACK_SHARE_OF_PRICE = 0.15`.

`_analyze_suppliers` becomes:

```python
async def _analyze_suppliers(db, niche_id, metrics, marketplace="US", fob_unit_cost=None, weight_kg=0.5):
    """Landed cost + margins. Uses the median scraped 1688 FOB price when we have one."""
    from app.core.category_mapping import category_slugs
    from app.services.supplier_service import SupplierService

    svc = SupplierService(marketplace=marketplace)
    avg_price = metrics.get("avg_price", 30)
    unit_cost = fob_unit_cost or avg_price * FOB_FALLBACK_SHARE_OF_PRICE
    if fob_unit_cost is None:
        logger.info("No supplier prices scraped; estimating FOB as %.0f%% of price", FOB_FALLBACK_SHARE_OF_PRICE * 100)
    duty_slug, _ = category_slugs(metrics.get("category"))

    landed = svc.calculate_landed_cost(unit_cost=unit_cost, quantity=500, weight_kg=weight_kg, category=duty_slug)
    margin = svc.calculate_margins(
        selling_price=avg_price, landed_cost=landed,
        fba_fulfillment_fee=metrics.get("fba_fees", 5),
        ppc_cost_per_unit=metrics.get("avg_cpc", 1.5) / 0.12,
    )
    metrics["fob_unit_cost"] = round(unit_cost, 4)
    metrics["landed_cost"] = landed.total_cost_to_amazon
    metrics["pre_ppc_margin_pct"] = margin["pre_ppc_margin_pct"]
    metrics["post_ppc_margin_pct"] = margin["post_ppc_margin_pct"]
    return {"landed_cost": {"total_landed_cost_usd_per_unit": landed.total_cost_to_amazon}, "margins": margin}
```

Step 12 (`:730-744`): replace the FOB reverse-engineering and category with:

```python
            from app.core.category_mapping import category_slugs
            duty_slug, fee_slug = category_slugs(metrics.get("category"))
            financial_report = await fin_report_svc.generate_full_report(
                selling_price=metrics.get("avg_price") or 30,
                unit_cost_fob=metrics.get("fob_unit_cost") or (metrics.get("landed_cost") or 8) * 0.55,
                product_dims=product_dims,
                category=duty_slug,
                fee_category=fee_slug,
                weight_kg_per_unit=product_dims["weight_lb"] * LB_TO_KG,
                order_quantity=metrics.get("initial_order_qty") or 500,
                estimated_monthly_sales=metrics.get("estimated_monthly_sales") or 200,
                avg_cpc=metrics.get("avg_cpc") or 1.50,
                launch_ppc_daily=metrics.get("ppc_daily_budget") or 30,
                hard_filter_results=hard_filter_results,
                confidence_tier=confidence_tier,
            )
```

(`product_dims` is now computed in step 6b; delete the duplicate `_extract_avg_dimensions` call in step 12.)

`_enrich_metrics` (`:1728-1731`): the `setdefault` lines for `supplier_count`, `best_supplier_score`, `min_moq` stay — they are now only fallbacks.

- [ ] **Step 9: Update the filter-count test**

`tests/test_scoring_service.py:135-137` — rename `test_eight_filters_returned` to `test_eight_filters_without_velocity_data` (assertion unchanged) and add:

```python
    def test_nine_filters_when_velocity_gap_known(self, scorer, sample_metrics):
        sample_metrics["avg_review_velocity_gap_ratio"] = 7.0
        result = scorer.compute_score(sample_metrics)
        assert len(result["hard_filters"]) == 9
        assert result["confidence_tier"] == "FAIL"
```

- [ ] **Step 10: Run suite, commit**

Run: `cd backend && pytest -q` → green.

```bash
git add backend/app/services/market_signals.py backend/app/core/category_mapping.py backend/app/core/marketplace.py backend/app/services/financial_report.py backend/app/workers/tasks.py backend/pyproject.toml backend/tests
git commit -m "feat: derive category, strong sellers, Amazon share, review-velocity gap and real FOB from scraped data"
```

---

### Task A6: Prompt/plumbing fixes (F8, F9)

**Files:**
- Modify: `backend/app/services/niche_intelligence.py:47-52,133-136,144-145`
- Modify: `backend/app/services/recommendation_engine.py:10,218,267`
- Test: `backend/tests/test_services/test_niche_intelligence.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_services/test_niche_intelligence.py
from unittest.mock import AsyncMock

from app.services.niche_intelligence import NicheIntelligenceService

LANDSCAPE = {
    "price_stats": {"min": 10, "max": 40}, "review_stats": {"min": 5, "max": 900},
    "competitor_details": [{
        "asin": "B0A",
        "listing_scores": {"overall_score": 72.5},
        "vulnerabilities": {"vulnerability_level": "high", "vulnerability_types": ["few_reviews", "no_video"]},
    }],
}
PRODUCTS = [{"asin": "B0A", "title": "Press", "price": 20, "rating": 4.0, "review_count": 30, "current_bsr": 5000}]


async def test_niche_overview_counts_high_vulnerability_competitors():
    llm = AsyncMock(); llm.generate_json = AsyncMock(return_value={})
    await NicheIntelligenceService(llm).generate_niche_overview("garlic press", PRODUCTS, LANDSCAPE, {"avg_price": 20})
    assert "High vulnerability competitors: 1" in llm.generate_json.call_args.args[0]


async def test_product_overviews_prompt_shows_score_and_vulnerabilities():
    llm = AsyncMock(); llm.generate_json = AsyncMock(return_value=[{"asin": "B0A"}])
    await NicheIntelligenceService(llm).generate_product_overviews(PRODUCTS, LANDSCAPE["competitor_details"])
    prompt = llm.generate_json.call_args.args[0]
    assert "Listing quality: 72.5/100" in prompt
    assert "Vulnerabilities: few_reviews, no_video" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_services/test_niche_intelligence.py -v` → both FAIL on the assertions.

- [ ] **Step 3: Fix the key reads**

`niche_intelligence.py:49-52`:
```python
        high_vuln_count = sum(
            1 for c in competitor_details
            if c.get("vulnerabilities", {}).get("vulnerability_level") == "high"
        )
```
`:133-136`:
```python
            detail = detail_by_asin.get(asin, {})
            listing_scores = detail.get("listing_scores", {}) or {}
            vuln_types = detail.get("vulnerabilities", {}).get("vulnerability_types", [])
```
`:144` → `f"  Listing quality: {listing_scores.get('overall_score', 'N/A')}/100\n"`.

- [ ] **Step 4: Run test to verify it passes** → 2 PASS

- [ ] **Step 5: Recommendation engine plumbing**

`recommendation_engine.py`:
- `:10` → `from app.llm.base_client import BaseLLMClient, EXPERT_SYSTEM_PROMPT`
- `:218` → `return await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)`
- `:267` → `marketing_channels=data.get("marketing_plan", {}).get("channels", {}).get("channels") if data.get("marketing_plan") else None,`

(`recommend_channels` returns `{"channels": [...], ...}`; the UI branches on `Array.isArray`.)

- [ ] **Step 6: Run suite, commit**

```bash
git add backend/app/services/niche_intelligence.py backend/app/services/recommendation_engine.py backend/tests/test_services/test_niche_intelligence.py
git commit -m "fix: read landscape keys correctly in intelligence prompts; store marketing channels as an array"
```

---

### Task A7: Docs catch-up for Part A

**Files:** Modify `CLAUDE.md` (Database section, Important files table), `TODO.md`, `README.md` API table.

- [ ] **Step 1:** In `CLAUDE.md` replace "Migrations in `backend/migrations/versions/` (4 versions)" and the 001–004 list with "13 migrations; 013 renames niche score columns to the ScoringService names". Update "14 tables" → "16 tables (+ `stock_history`, `sales_velocity_snapshots`)". Add rows for `app/services/market_signals.py` and `app/workers/pipeline_steps/`.
- [ ] **Step 2:** In `TODO.md` tick: "Metrics dict mutation" (still true — leave), "No DB migrations" (false — delete), "Test coverage — No test files" (false — delete), ".env in repo root" (already gitignored — delete). Add a line under HIGH: "`track_bsr_prices` re-inserts stale values (see Part B5 of the 2026-09-25 plan)".
- [ ] **Step 3:** `README.md` API table: add `POST /api/v1/jobs/discover`, `POST /api/v1/jobs/analyze-sub-niche`, `GET /api/v1/niches/{id}/velocity`, `GET /api/v1/products/{asin}/velocity`, `POST /api/v1/niches/{id}/keywords/research`.
- [ ] **Step 4:** Commit: `git commit -am "docs: sync CLAUDE.md, TODO.md and README with current schema and endpoints"`

---

# Part B — Worker stability and re-run hygiene

### Task B1: One event loop and one engine per worker process; time limits (F10)

**Files:**
- Modify: `backend/app/workers/tasks.py:24-53` and every `@celery_app.task(...)` decorator
- Modify: `backend/app/workers/celery_app.py:16-30`
- Test: `backend/tests/test_workers/test_worker_runtime.py`

**Interfaces:**
- Produces: `_get_session_factory()` returns the same factory on repeated calls in one process; `_run_async(coro)` reuses one loop.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_workers/test_worker_runtime.py
import asyncio

from app.workers import tasks


def test_session_factory_is_cached_per_process():
    tasks._reset_runtime_for_tests()
    assert tasks._get_session_factory() is tasks._get_session_factory()


def test_run_async_reuses_one_loop():
    tasks._reset_runtime_for_tests()

    async def loop_id():
        return id(asyncio.get_running_loop())

    assert tasks._run_async(loop_id()) == tasks._run_async(loop_id())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workers/test_worker_runtime.py -v`
Expected: FAIL `AttributeError: module 'app.workers.tasks' has no attribute '_reset_runtime_for_tests'`

- [ ] **Step 3: Implement the cached runtime**

Replace `tasks.py:18-53` with:

```python
# ---------------------------------------------------------------------------
# Worker runtime — one event loop and one async engine per worker *process*.
# WHY: asyncpg pools are bound to the loop that created them. Creating a new
# loop per task forced a new engine per task, which leaked connections.
# Keeping a single loop alive for the process lifetime lets us keep one engine.
# ---------------------------------------------------------------------------
_loop: asyncio.AbstractEventLoop | None = None
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

WORKER_POOL_SIZE = 5
WORKER_POOL_OVERFLOW = 5


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session factory, creating the engine on first use."""
    global _engine, _session_factory
    if _session_factory is None:
        _get_loop()
        _engine = create_async_engine(
            Settings().DATABASE_URL, echo=False,
            pool_size=WORKER_POOL_SIZE, max_overflow=WORKER_POOL_OVERFLOW, pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)
    return _session_factory


def _run_async(coro):
    """Run a coroutine on the process-wide loop."""
    return _get_loop().run_until_complete(coro)


def _dispose_runtime() -> None:
    """Close the engine and loop. Called on worker shutdown."""
    global _engine, _session_factory, _loop
    if _engine is not None:
        _get_loop().run_until_complete(_engine.dispose())
    if _loop is not None and not _loop.is_closed():
        _loop.close()
    _engine = _session_factory = _loop = None


def _reset_runtime_for_tests() -> None:
    _dispose_runtime()
```

In `celery_app.py` add at the bottom:

```python
from celery.signals import worker_process_shutdown


@worker_process_shutdown.connect
def _close_worker_runtime(**_kwargs):
    from app.workers.tasks import _dispose_runtime
    _dispose_runtime()
```

- [ ] **Step 4: Add time limits**

`celery_app.py` `conf.update(...)` add:

```python
    # A full analysis scrapes ~60 pages + ~20 LLM calls; 90 min is generous, 100 min kills a hung browser.
    task_soft_time_limit=90 * 60,
    task_time_limit=100 * 60,
```

Per-task overrides in `tasks.py`: `track_bsr_prices` and `scrape_reviews` get `soft_time_limit=20*60, time_limit=25*60` in their decorators; `refresh_competitor_data` `soft_time_limit=10*60, time_limit=12*60`.

- [ ] **Step 5: Run tests, commit**

Run: `cd backend && pytest -q` → green (the runtime test creates an engine object but never connects).

```bash
git add backend/app/workers/tasks.py backend/app/workers/celery_app.py backend/tests/test_workers/test_worker_runtime.py
git commit -m "fix: reuse one event loop and engine per worker process; add Celery time limits"
```

---

### Task B2: `force=true` re-runs start clean (F11)

**Files:**
- Create: `backend/app/workers/pipeline_steps/reset.py`
- Modify: `backend/app/workers/tasks.py` (start of `_run_full_analysis_async`, `:227-232`)
- Test: `backend/tests/test_workers/test_reset_niche.py`

**Interfaces:**
- Produces: `reset_niche_analysis_data(db, niche_id) -> None` deletes `Competitor, Supplier, LandedCostCalculation, FinancialProjection, Recommendation, PPCKeyword` rows for the niche. Products, reviews and organic `NicheKeyword` rows are kept (they are upserted).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_workers/test_reset_niche.py
from unittest.mock import AsyncMock

from app.workers.pipeline_steps.reset import RESET_TABLES, reset_niche_analysis_data


async def test_reset_deletes_one_statement_per_table(mock_db):
    mock_db.execute = AsyncMock()
    await reset_niche_analysis_data(mock_db, niche_id=7)
    assert mock_db.execute.await_count == len(RESET_TABLES)
    mock_db.flush.assert_awaited_once()
```

- [ ] **Step 2: Run to verify it fails** → ModuleNotFoundError

- [ ] **Step 3: Implement**

```python
# backend/app/workers/pipeline_steps/reset.py
"""Pipeline step: delete derived rows so a forced re-analysis does not duplicate them."""

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor
from app.models.financial_projection import FinancialProjection
from app.models.keyword import PPCKeyword
from app.models.recommendation import Recommendation
from app.models.supplier import LandedCostCalculation, Supplier

# Order matters: landed_cost_calculations references suppliers.
RESET_TABLES = (LandedCostCalculation, Supplier, Competitor, FinancialProjection, Recommendation, PPCKeyword)


async def reset_niche_analysis_data(db: AsyncSession, niche_id: int) -> None:
    """Remove everything a previous run derived for this niche. Products and reviews are kept."""
    for model in RESET_TABLES:
        await db.execute(delete(model).where(model.niche_id == niche_id))
    await db.flush()
```

- [ ] **Step 4: Run to verify it passes**

- [ ] **Step 5: Wire it in**

`tasks.py` in `_run_full_analysis_async`, right after setting status to `analyzing`:

```python
        if options.get("force"):
            from app.workers.pipeline_steps.reset import reset_niche_analysis_data
            await reset_niche_analysis_data(db, niche_id)
            await db.commit()
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/workers/pipeline_steps/reset.py backend/app/workers/tasks.py backend/tests/test_workers/test_reset_niche.py
git commit -m "fix: forced re-analysis deletes derived rows first so suppliers/recommendations don't duplicate"
```

---

### Task B3: LLM calls retry on transport errors

**Files:**
- Modify: `backend/app/llm/base_client.py:54-81`
- Test: `backend/tests/test_services/test_llm_retry.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_services/test_llm_retry.py
import httpx
import pytest

from app.core.exceptions import LLMError
from app.llm.base_client import BaseLLMClient


class FlakyClient(BaseLLMClient):
    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    async def generate(self, prompt, max_tokens=4096, temperature=0.3, system_message=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise httpx.ConnectError("boom")
        return '{"ok": true}'


async def test_generate_json_retries_transport_errors(monkeypatch):
    monkeypatch.setattr("app.llm.base_client.RETRY_BACKOFF_SECONDS", 0)
    client = FlakyClient(failures=2)
    assert await client.generate_json("hi") == {"ok": True}
    assert client.calls == 3


async def test_generate_json_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr("app.llm.base_client.RETRY_BACKOFF_SECONDS", 0)
    with pytest.raises(LLMError):
        await FlakyClient(failures=5).generate_json("hi")
```

- [ ] **Step 2: Run to verify it fails** → first test raises `httpx.ConnectError`.

- [ ] **Step 3: Implement**

In `base_client.py` add imports `import asyncio`, `import httpx` and constants:

```python
# Transport-level failures (timeouts, connection resets, 5xx) are retried; bad JSON is handled separately.
MAX_TRANSPORT_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0
```

Add a method and route `generate_json` through it:

```python
    async def _generate_with_retry(self, prompt, max_tokens, system_message) -> str:
        last_error: Exception | None = None
        for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
            try:
                return await self.generate(prompt, max_tokens, system_message=system_message)
            except (httpx.TransportError, httpx.HTTPStatusError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < MAX_TRANSPORT_ATTEMPTS:
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
        raise LLMError(f"LLM call failed after {MAX_TRANSPORT_ATTEMPTS} attempts: {last_error}")
```

Replace both `await self.generate(...)` calls inside `generate_json` with `await self._generate_with_retry(prompt, max_tokens, system_message)` / `(retry_prompt, ...)`.

> NOTE: `openai`/`anthropic`/`dashscope` SDK exceptions wrap httpx; check `qwen_client.py`, `openai_client.py`, `anthropic_client.py` — if they catch and re-raise as `LLMError`, add `LLMError` to the retried tuple **only** for messages containing "timeout", "rate limit" or "overloaded" (check `str(e).lower()`).

- [ ] **Step 4: Run tests, commit**

```bash
git add backend/app/llm/base_client.py backend/tests/test_services/test_llm_retry.py
git commit -m "fix: retry LLM transport failures with backoff instead of failing the whole step"
```

---

### Task B4: Small hardening — CORS allow-list and keyword sanitising

**Files:**
- Modify: `backend/app/config.py` (add `ALLOWED_ORIGINS: str = "http://localhost:3000"`), `backend/app/main.py:89-96`, `backend/app/api/jobs.py:50-64`
- Test: `backend/tests/test_api/test_keyword_validation.py`

- [ ] **Step 1: Test**

```python
# backend/tests/test_api/test_keyword_validation.py
import pytest
from pydantic import ValidationError

from app.api.jobs import AnalyzeKeywordRequest


def test_keyword_is_trimmed_and_control_chars_removed():
    req = AnalyzeKeywordRequest(keyword="  garlic\npress\t ")
    assert req.keyword == "garlic press"


def test_keyword_too_long_rejected():
    with pytest.raises(ValidationError):
        AnalyzeKeywordRequest(keyword="x" * 101)
```

- [ ] **Step 2: Run** → first test fails (newline retained).

- [ ] **Step 3: Implement**

`jobs.py` `AnalyzeKeywordRequest`: change `max_length=255` to `max_length=100` and add:

```python
    @field_validator("keyword")
    @classmethod
    def normalise_keyword(cls, v: str) -> str:
        # WHY: the keyword is interpolated into LLM prompts and URLs; collapse whitespace/control chars.
        return " ".join(v.split())
```
(import `field_validator` from pydantic.)

`main.py`: `allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]` — build `settings = Settings()` inside `create_app()`. Add `ALLOWED_ORIGINS=http://localhost:3000` to `.env.example` and to the `backend` service environment in `docker-compose.yml`.

- [ ] **Step 4: Run tests, commit**

```bash
git commit -am "fix: restrict CORS to configured origins; normalise analysis keywords"
```

---

### Task B5: BSR/price history that actually moves (F12)

**Files:**
- Modify: `backend/app/services/scraper_service.py` (new `scrape_rank_snapshot`, extracted BSR parser)
- Modify: `backend/app/workers/tasks.py:828-893` (`_track_bsr_niche_async`), `:1224-1335` (`_scrape_product_details` records initial snapshot)
- Test: `backend/tests/test_services/test_bsr_parse.py`

**Interfaces:**
- Produces: `ScraperService.parse_bsr_text(details_text: str) -> dict` with `current_bsr, bsr_category, current_subcategory_bsr, subcategory_name`; `ScraperService.scrape_rank_snapshot(asin) -> dict` with those four keys plus `price, stock_level, stock_text, is_in_stock`.

- [ ] **Step 1: Test the parser (pure)**

```python
# backend/tests/test_services/test_bsr_parse.py
from app.services.scraper_service import ScraperService

DETAILS = "Best Sellers Rank #2,345 in Home & Kitchen (See Top 100 in Home & Kitchen) #12 in Garlic Presses"


def test_parse_bsr_text_extracts_main_and_sub():
    parsed = ScraperService.parse_bsr_text(DETAILS)
    assert parsed == {
        "current_bsr": 2345, "bsr_category": "Home & Kitchen",
        "current_subcategory_bsr": 12, "subcategory_name": "Garlic Presses",
    }


def test_parse_bsr_text_handles_missing():
    assert ScraperService.parse_bsr_text("") == {
        "current_bsr": None, "bsr_category": None, "current_subcategory_bsr": None, "subcategory_name": None,
    }
```

- [ ] **Step 2: Run** → AttributeError `parse_bsr_text`.

- [ ] **Step 3: Extract the parser and add the light scraper**

In `scraper_service.py` add a static method (and use it from `scrape_product_page` in place of `:513-537`):

```python
    _BSR_PATTERN = re.compile(r"#([\d,]+)\s+in\s+([A-Za-z &',\-]+?)(?=\s*\(|\s*#|$)")

    @staticmethod
    def parse_bsr_text(details_text: str | None) -> dict:
        """Parse '#N in Category' pairs. First match is the main category, second the sub-category."""
        empty = {"current_bsr": None, "bsr_category": None, "current_subcategory_bsr": None, "subcategory_name": None}
        if not details_text:
            return empty
        matches = ScraperService._BSR_PATTERN.findall(details_text)
        if not matches:
            return empty
        parsed = dict(empty)
        parsed["current_bsr"] = ScraperService._safe_int(matches[0][0])
        parsed["bsr_category"] = matches[0][1].strip()
        if len(matches) > 1:
            parsed["current_subcategory_bsr"] = ScraperService._safe_int(matches[1][0])
            parsed["subcategory_name"] = matches[1][1].strip()
        return parsed
```

Then add `scrape_rank_snapshot(asin)` modelled on `scrape_stock_level` (`:1234-1292`): same retry/browser structure, but after `page.goto` it reads price via the same selector list as `:455-469`, the details block via the three selectors at `:514-518` → `parse_bsr_text`, and the `#availability` block. Return `{"asin", "price", **parsed_bsr, "stock_level", "stock_text", "is_in_stock"}`.

- [ ] **Step 4: Run parser tests** → PASS

- [ ] **Step 5: Use it in the beat task and at analysis time**

`_track_bsr_niche_async` body inside the `for product in products:` loop becomes:

```python
            try:
                snapshot = await scraper.scrape_rank_snapshot(product.asin)
                await tracker.record_product_snapshot(
                    product_id=product.id, asin=product.asin,
                    bsr=snapshot["current_bsr"], category_name=snapshot["bsr_category"],
                    subcategory_bsr=snapshot["current_subcategory_bsr"], subcategory_name=snapshot["subcategory_name"],
                    price=snapshot["price"],
                )
                if snapshot["current_bsr"]:
                    product.current_bsr = snapshot["current_bsr"]
                if snapshot["price"]:
                    product.current_price = snapshot["price"]
                await velocity_svc.record_stock_snapshot(
                    product_id=product.id, asin=product.asin,
                    stock_level=snapshot["stock_level"], stock_text=snapshot["stock_text"], is_in_stock=snapshot["is_in_stock"],
                )
                if snapshot["stock_level"] is not None:
                    product.last_stock_level = snapshot["stock_level"]
            except Exception as e:
                logger.warning("Failed to track product %s: %s", product.asin, e)
```

with `scraper = ScraperService(marketplace=niche_marketplace)` and `velocity_svc = SalesVelocityService(db)` created once above the loop. Limit tracked products: `stmt = select(Product).where(Product.niche_id == niche_id).order_by(Product.search_position.asc().nullslast()).limit(TRACKED_PRODUCTS_PER_NICHE)` with `TRACKED_PRODUCTS_PER_NICHE = 20`. In `_track_bsr_all_async` only select niches with `Niche.last_scored_at >= now - 30 days` (constant `TRACKING_WINDOW_DAYS = 30`) — WHY: every tracked product costs one page load per 6 h.

In `_scrape_product_details`, after the enriched fields are written, add the initial snapshot:

```python
                    from app.services.bsr_tracker import BSRTracker
                    await BSRTracker(db).record_product_snapshot(
                        product_id=existing.id, asin=asin,
                        bsr=detail.get("current_bsr"), category_name=detail.get("bsr_category"),
                        subcategory_bsr=detail.get("current_subcategory_bsr"), subcategory_name=detail.get("subcategory_name"),
                        price=detail.get("price"),
                    )
```

- [ ] **Step 6: Run suite, commit**

```bash
git commit -am "feat: record real BSR/price snapshots at analysis time and re-scrape on the 6h tracker"
```

---

# Part C — Scraping resilience (Amazon & 1688 anti-bot)

## What we are actually up against

"Arbitrage online protection" in practice means Amazon's automated-traffic defences. They are layered, and each layer is defeated by a *different* discipline:

| Layer | What Amazon looks at | What our scraper does today | What defeats it |
|---|---|---|---|
| IP reputation | Datacenter ranges, request volume per IP, geo vs marketplace | Direct IP or one proxy session per *page* | Residential/ISP proxies, **sticky** session per browsing session, geo matched to marketplace |
| TLS / HTTP2 fingerprint (JA3/JA4, header order) | Non-browser clients | Fine — we use real Chromium | Keep using a real browser; never `httpx` for product pages |
| Browser fingerprint | `navigator.webdriver`, UA vs platform vs `Accept-Language` vs timezone coherence, plugin/WebGL noise, headless markers | Random UA (a Mac UA on Linux Chromium, `navigator.plugins` faked to `[1,2,3,4,5]`), new context per page | One coherent persona per session: UA from the *actual* Chromium version, matching platform, locale = marketplace, `headless="new"` |
| Session/behaviour | Cold requests to `/dp/` with no cookies, no referer, no homepage visit, machine-regular timing, 20 detail pages in 60 s | Exactly that | Warm-up (home → search → product), referer chain, jittered 3–8 s pacing, 1 browser per pipeline run, scroll a little |
| Challenge pages | `/errors/validateCaptcha` (image captcha), HTTP 503 "Sorry! Something went wrong", "Robot Check", soft blocks (empty SERP) | Not detected — we log "no results" and move on | Detect → mark proxy session bad → rotate → backoff; optional solver |
| Bandwidth cost | n/a | Downloads every image/font/video (residential proxies bill per GB) | Abort image/media/font requests |
| 1688 | Alibaba "baxia" slider captcha, login wall for prices | Cookie persistence exists | Keep cookie persistence; treat empty results as blocked (already has circuit breaker); accept that 1688 needs a logged-in session and low volume |

The senior-engineer answer is **not** "build a better evader". It is:

1. **Scrape less.** Use the free/legal sources first: the autocomplete API (already), **SP-API Catalog Items** (`searchCatalogItems` for keyword search + `getCatalogItem` for rank/dimensions/images) when the seller has credentials — that is F14 and costs nothing per call. Cache SERP (6 h) and product pages (24 h) in Redis so re-runs and sub-niche flows don't re-hit Amazon.
2. **Look like one shopper, not sixty bots.** One browser session per pipeline run with a coherent persona and a sticky proxy session.
3. **Notice when you're blocked.** Detect challenge pages, rotate, back off, and record outcomes so selector rot and block rates are visible.
4. **Pay for what's cheaper than engineering.** Residential proxy at ~$1/analysis and, if block rates stay high, a data API (Keepa ~€19/mo for BSR history; Rainforest/Oxylabs Amazon endpoints ~$50/mo) beat weeks of cat-and-mouse. Keep a clear seam so those can be dropped in.

Volume sanity: one analysis ≈ 3 SERP + 20 detail + 20 SERP-metadata pages ≈ 45 loads. Ten analyses a day is 450 loads — well under what a single residential session tolerates if paced. We do not need a distributed scraping fleet.

> Legal note (unchanged from `GUIDE.md`): scraping is against Amazon's ToS; this is a private research tool at hobby volume. Nothing below touches login, other users' data, or rate-limit circumvention beyond behaving like a normal browser.

## File structure for Part C

```
backend/app/scraping/__init__.py
backend/app/scraping/persona.py         (new) coherent UA/platform/locale/viewport per session
backend/app/scraping/block_detection.py (new) classify a loaded page: ok | captcha | soft_block | error
backend/app/scraping/pacing.py          (new) per-domain jittered pacing (in-process)
backend/app/scraping/session.py         (new) BrowserSession: one Chromium + context per run, resource blocking, proxy failover
backend/app/scraping/page_cache.py      (new) Redis HTML cache for SERP/product pages
backend/app/scraping/events.py          (new) ScrapeEvent recording
backend/app/models/scrape_event.py      (new) + migration 014
backend/app/services/scraper_service.py (modify) use BrowserSession instead of async_playwright() per call
backend/app/workers/tasks.py            (modify) open one session per pipeline run; SP-API path
backend/app/services/spapi_service.py   (modify) add search_catalog_items
```

---

### Task C1: Coherent browser persona

**Files:**
- Create: `backend/app/scraping/__init__.py` (empty), `backend/app/scraping/persona.py`
- Test: `backend/tests/test_scraping/__init__.py` (empty), `backend/tests/test_scraping/test_persona.py`

**Interfaces:**
- Produces: `Persona` dataclass `(user_agent, platform, viewport: dict, locale, timezone_id, accept_language)`; `build_persona(chromium_version: str, marketplace) -> Persona`; `Persona.init_script() -> str`.

- [ ] **Step 1: Test**

```python
# backend/tests/test_scraping/test_persona.py
from app.core.marketplace import get_marketplace
from app.scraping.persona import build_persona


def test_persona_ua_matches_platform_and_browser_version():
    p = build_persona("124.0.6367.60", get_marketplace("AU"))
    assert "Chrome/124.0.0.0" in p.user_agent
    assert (("Windows" in p.user_agent) == (p.platform == "Win32"))
    assert p.locale == "en-AU" and p.timezone_id == "Australia/Sydney"
    assert p.accept_language.startswith("en-AU")
    assert 1280 <= p.viewport["width"] <= 1920


def test_init_script_sets_matching_platform():
    p = build_persona("124.0.6367.60", get_marketplace("US"))
    assert f"'{p.platform}'" in p.init_script()
    assert "webdriver" in p.init_script()
```

- [ ] **Step 2: Run** → ModuleNotFoundError

- [ ] **Step 3: Implement**

```python
# backend/app/scraping/persona.py
"""One coherent browser identity per scraping session.

WHY: Amazon scores mismatches (a macOS user-agent on a Linux Chromium, en-US
headers on amazon.com.au). Every value here is derived from one choice so they agree.
"""

import random
from dataclasses import dataclass

from app.core.marketplace import MarketplaceConfig

_PLATFORMS = [
    # (UA platform token, navigator.platform)
    ("Windows NT 10.0; Win64; x64", "Win32"),
    ("Macintosh; Intel Mac OS X 10_15_7", "MacIntel"),
]
_VIEWPORTS = [(1366, 768), (1440, 900), (1536, 864), (1920, 1080)]


@dataclass(frozen=True)
class Persona:
    user_agent: str
    platform: str
    viewport: dict
    locale: str
    timezone_id: str
    accept_language: str

    def init_script(self) -> str:
        """JS run before any page script; hides automation markers and aligns navigator.platform."""
        return f"""
            Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
            Object.defineProperty(navigator, 'platform', {{get: () => '{self.platform}'}});
            Object.defineProperty(navigator, 'languages', {{get: () => ['{self.locale}', 'en']}});
            window.chrome = window.chrome || {{ runtime: {{}} }};
        """


def build_persona(chromium_version: str, marketplace: MarketplaceConfig) -> Persona:
    """Pick a platform + viewport and derive every other value from it and the marketplace."""
    ua_platform, nav_platform = random.choice(_PLATFORMS)
    major = chromium_version.split(".")[0]
    width, height = random.choice(_VIEWPORTS)
    return Persona(
        user_agent=(
            f"Mozilla/5.0 ({ua_platform}) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{major}.0.0.0 Safari/537.36"
        ),
        platform=nav_platform,
        viewport={"width": width, "height": height},
        locale=marketplace.locale,
        timezone_id=marketplace.timezone,
        accept_language=f"{marketplace.locale},en;q=0.9",
    )
```

- [ ] **Step 4: Run tests, commit** — `git commit -m "feat(scraping): coherent per-session browser persona"`

---

### Task C2: Block detection

**Files:**
- Create: `backend/app/scraping/block_detection.py`
- Test: `backend/tests/test_scraping/test_block_detection.py`

**Interfaces:**
- Produces: `PageVerdict = Literal["ok", "captcha", "soft_block", "server_error"]`; `classify_page(status: int | None, title: str, body_text: str, expected_selector_found: bool) -> PageVerdict`.

- [ ] **Step 1: Test**

```python
# backend/tests/test_scraping/test_block_detection.py
from app.scraping.block_detection import classify_page


def test_captcha_page():
    assert classify_page(200, "Amazon.com", "Enter the characters you see below ... api-services-support@amazon.com", False) == "captcha"


def test_robot_check_title():
    assert classify_page(200, "Robot Check", "", False) == "captcha"


def test_server_error():
    assert classify_page(503, "Sorry! Something went wrong!", "", False) == "server_error"


def test_soft_block_when_expected_content_missing():
    assert classify_page(200, "Amazon.com : garlic press", "Results", False) == "soft_block"


def test_ok():
    assert classify_page(200, "Amazon.com : garlic press", "Results", True) == "ok"
```

- [ ] **Step 2: Run** → ModuleNotFoundError

- [ ] **Step 3: Implement**

```python
# backend/app/scraping/block_detection.py
"""Classify a loaded Amazon page so callers can rotate proxies instead of parsing an empty page."""

from typing import Literal

PageVerdict = Literal["ok", "captcha", "soft_block", "server_error"]

# Phrases Amazon puts on its automated-traffic challenge page.
_CAPTCHA_MARKERS = (
    "enter the characters you see below",
    "api-services-support@amazon.com",
    "validatecaptcha",
)
_CAPTCHA_TITLES = ("robot check", "bot check")


def classify_page(status: int | None, title: str, body_text: str, expected_selector_found: bool) -> PageVerdict:
    """Return what kind of page we got. 'soft_block' = 200 OK but the content we wanted is absent."""
    lowered_title = (title or "").lower()
    lowered_body = (body_text or "").lower()
    if any(t in lowered_title for t in _CAPTCHA_TITLES) or any(m in lowered_body for m in _CAPTCHA_MARKERS):
        return "captcha"
    if status is not None and status >= 500:
        return "server_error"
    if not expected_selector_found:
        return "soft_block"
    return "ok"
```

- [ ] **Step 4: Run tests, commit** — `git commit -m "feat(scraping): classify captcha/soft-block/error pages"`

---

### Task C3: Per-domain pacing

**Files:**
- Create: `backend/app/scraping/pacing.py`
- Test: `backend/tests/test_scraping/test_pacing.py`

**Interfaces:**
- Produces: `class Pacer(min_gap_s: float, max_gap_s: float)` with `async wait_turn(domain: str) -> None`; `pacer_for(domain) -> Pacer` module-level registry with defaults `amazon: 3–7 s`, `1688: 5–10 s`.

- [ ] **Step 1: Test**

```python
# backend/tests/test_scraping/test_pacing.py
import time

from app.scraping.pacing import Pacer


async def test_second_request_waits_at_least_min_gap():
    pacer = Pacer(min_gap_s=0.2, max_gap_s=0.2)
    await pacer.wait_turn("example.com")
    start = time.monotonic()
    await pacer.wait_turn("example.com")
    assert time.monotonic() - start >= 0.19


async def test_different_domains_do_not_block_each_other():
    pacer = Pacer(min_gap_s=0.5, max_gap_s=0.5)
    await pacer.wait_turn("a.com")
    start = time.monotonic()
    await pacer.wait_turn("b.com")
    assert time.monotonic() - start < 0.1
```

- [ ] **Step 2: Run** → ModuleNotFoundError

- [ ] **Step 3: Implement**

```python
# backend/app/scraping/pacing.py
"""Jittered minimum gap between page loads to the same site, shared by every scraper in the process."""

import asyncio
import random
import time

AMAZON_GAP_SECONDS = (3.0, 7.0)
ALIBABA_GAP_SECONDS = (5.0, 10.0)


class Pacer:
    def __init__(self, min_gap_s: float, max_gap_s: float):
        self.min_gap_s = min_gap_s
        self.max_gap_s = max_gap_s
        self._last_request: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait_turn(self, domain: str) -> None:
        """Sleep until at least a random gap has passed since the last request to this domain."""
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            gap = random.uniform(self.min_gap_s, self.max_gap_s)
            elapsed = time.monotonic() - self._last_request.get(domain, 0.0)
            if elapsed < gap:
                await asyncio.sleep(gap - elapsed)
            self._last_request[domain] = time.monotonic()


_PACERS = {
    "amazon": Pacer(*AMAZON_GAP_SECONDS),
    "1688": Pacer(*ALIBABA_GAP_SECONDS),
}


def pacer_for(site: str) -> Pacer:
    """'amazon' or '1688'."""
    return _PACERS[site]
```

- [ ] **Step 4: Run tests, commit** — `git commit -m "feat(scraping): per-domain jittered pacing"`

---

### Task C4: `BrowserSession` — one browser per run, resource blocking, proxy failover

**Files:**
- Create: `backend/app/scraping/session.py`
- Modify: `backend/app/core/proxy_manager.py` (add `current_session_id` tracking to `get_next()` so failover can `mark_failed` it)
- Test: `backend/tests/test_scraping/test_session_policy.py` (pure parts only; Playwright itself is not unit-tested)

**Interfaces:**
- Produces:
  ```python
  class BrowserSession:
      def __init__(self, marketplace: MarketplaceConfig, proxy_manager: ProxyManager, site: str = "amazon")
      async def __aenter__(self) -> "BrowserSession"; async def __aexit__(...)
      async def load(self, url: str, expected_selector: str, wait_ms: int = 15_000) -> tuple[Page, PageVerdict]
      async def rotate(self) -> None   # close context+browser, mark proxy session failed, reopen with new persona
  ```
  `should_block_request(resource_type: str, url: str) -> bool` (pure), `MAX_ROTATIONS_PER_SESSION = 3`.

- [ ] **Step 1: Test the pure policy**

```python
# backend/tests/test_scraping/test_session_policy.py
from app.scraping.session import should_block_request


def test_blocks_images_media_fonts():
    assert should_block_request("image", "https://m.media-amazon.com/images/I/x.jpg")
    assert should_block_request("media", "https://x/video.mp4")
    assert should_block_request("font", "https://x/f.woff2")


def test_allows_documents_scripts_xhr():
    assert not should_block_request("document", "https://www.amazon.com/dp/B0A")
    assert not should_block_request("script", "https://www.amazon.com/x.js")
    assert not should_block_request("xhr", "https://www.amazon.com/api")


def test_never_blocks_captcha_image():
    # WHY: if we ever add a solver it needs the challenge image.
    assert not should_block_request("image", "https://images-na.ssl-images-amazon.com/captcha/abc.jpg")
```

- [ ] **Step 2: Run** → ModuleNotFoundError

- [ ] **Step 3: Implement**

```python
# backend/app/scraping/session.py
"""One Chromium browser + context for a whole scraping run.

WHY: launching a fresh browser per page (the old behaviour) means every request
arrives with an empty cookie jar and a new fingerprint — the strongest bot
signal we were sending. Residential proxies also bill per GB, so we drop images.
"""

import logging

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.core.marketplace import MarketplaceConfig
from app.core.proxy_manager import ProxyManager
from app.scraping.block_detection import PageVerdict, classify_page
from app.scraping.pacing import pacer_for
from app.scraping.persona import Persona, build_persona

logger = logging.getLogger(__name__)

_BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}
MAX_ROTATIONS_PER_SESSION = 3


def should_block_request(resource_type: str, url: str) -> bool:
    """Drop bandwidth-heavy resources we never parse. Captcha images are kept."""
    if "/captcha/" in url:
        return False
    return resource_type in _BLOCKED_RESOURCE_TYPES


class BrowserSession:
    def __init__(self, marketplace: MarketplaceConfig, proxy_manager: ProxyManager, site: str = "amazon"):
        self.marketplace = marketplace
        self.proxy_manager = proxy_manager
        self.site = site
        self.rotations = 0
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._proxy_conf: dict = {}
        self.persona: Persona | None = None

    async def __aenter__(self) -> "BrowserSession":
        self._pw = await async_playwright().start()
        await self._open()
        return self

    async def __aexit__(self, *_exc) -> None:
        await self._close()
        if self._pw:
            await self._pw.stop()

    async def _open(self) -> None:
        self._proxy_conf = self.proxy_manager.get_playwright_proxy()
        launch_kwargs = {"headless": True, "args": ["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--no-sandbox"]}
        if self._proxy_conf.get("server"):
            launch_kwargs["proxy"] = self._proxy_conf
        self._browser = await self._pw.chromium.launch(**launch_kwargs)
        self.persona = build_persona(self._browser.version, self.marketplace)
        self._context = await self._browser.new_context(
            user_agent=self.persona.user_agent,
            viewport=self.persona.viewport,
            locale=self.persona.locale,
            timezone_id=self.persona.timezone_id,
            extra_http_headers={"Accept-Language": self.persona.accept_language},
            ignore_https_errors=True,
        )
        await self._context.add_init_script(self.persona.init_script())
        await self._context.route("**/*", self._route)

    async def _route(self, route) -> None:
        request = route.request
        if should_block_request(request.resource_type, request.url):
            await route.abort()
        else:
            await route.continue_()

    async def _close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        self._context = self._browser = None

    async def rotate(self) -> None:
        """Abandon the current proxy session + persona and start over. Raises after MAX_ROTATIONS_PER_SESSION."""
        self.rotations += 1
        if self.rotations > MAX_ROTATIONS_PER_SESSION:
            raise RuntimeError(f"Blocked {self.rotations} times in one session; giving up")
        if self._proxy_conf.get("username"):
            self.proxy_manager.mark_failed(self._proxy_conf["username"])
        elif self._proxy_conf.get("server"):
            self.proxy_manager.mark_failed(self._proxy_conf["server"])
        logger.warning("Rotating browser session (%d/%d)", self.rotations, MAX_ROTATIONS_PER_SESSION)
        await self._close()
        await self._open()

    async def load(self, url: str, expected_selector: str, wait_ms: int = 15_000) -> tuple[Page, PageVerdict]:
        """Open url in a new tab after pacing; return the page and what kind of page it is."""
        await pacer_for(self.site).wait_turn(self.marketplace.domain)
        page = await self._context.new_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        found = True
        try:
            await page.wait_for_selector(expected_selector, timeout=wait_ms)
        except Exception:
            found = False
        title = await page.title()
        body = "" if found else (await page.locator("body").inner_text())[:4000]
        verdict = classify_page(response.status if response else None, title, body, found)
        return page, verdict
```

- [ ] **Step 4: Run tests, commit** — `git commit -m "feat(scraping): BrowserSession with persona, resource blocking and proxy rotation"`

---

### Task C5: `ScraperService` uses the session; block → rotate → retry

**Files:**
- Modify: `backend/app/services/scraper_service.py` — `__init__` accepts an optional `session: BrowserSession`; `scrape_search_results`, `scrape_product_page`, `scrape_serp_metadata`, `scrape_reviews`, `scrape_stock_level`/`scrape_rank_snapshot` use `self._session.load(...)` and close the page in `finally`
- Modify: `backend/app/workers/tasks.py` — `_run_full_analysis_async` and `_run_discovery_async` open one `BrowserSession` and pass one `ScraperService` to every step; `_track_bsr_niche_async` opens one session per niche
- Modify: `backend/app/services/keyword_research.py:25` — accept the shared scraper (already does)

**Interfaces:**
- `ScraperService(marketplace="US", session: BrowserSession | None = None)`. When `session` is `None` the service opens a temporary session per call (keeps `test_scraping.py`-style ad-hoc use working).

- [ ] **Step 1: Add the session-aware loader**

In `ScraperService`:

```python
    def __init__(self, proxy_manager: ProxyManager | None = None, marketplace: str = "US", session: "BrowserSession | None" = None):
        ...existing proxy_manager setup...
        self._session = session

    async def _load(self, url: str, expected_selector: str):
        """Load through the shared session, rotating on a block. Returns (page, verdict) or raises ScrapingError."""
        for _ in range(MAX_ROTATIONS_PER_SESSION + 1):
            page, verdict = await self._session.load(url, expected_selector)
            if verdict in ("ok", "soft_block"):
                return page, verdict
            await page.close()
            logger.warning("Blocked (%s) loading %s — rotating", verdict, url)
            await self._session.rotate()
        raise ScrapingError(f"Still blocked after {MAX_ROTATIONS_PER_SESSION} rotations: {url}")
```

Add an async context helper used when no session was injected:

```python
    @asynccontextmanager
    async def _ensure_session(self):
        if self._session is not None:
            yield self._session
            return
        async with BrowserSession(self._marketplace, self.proxy_manager) as session:
            self._session = session
            try:
                yield session
            finally:
                self._session = None
```

- [ ] **Step 2: Convert each scraper method**

Pattern (shown for `scrape_product_page`; apply the same to the other five): replace the `for attempt ... async_playwright().start() ... finally browser.close()` scaffolding with

```python
    async def scrape_product_page(self, asin: str) -> dict:
        url = f"https://www.{self._marketplace.domain}/dp/{asin}"
        async with self._ensure_session():
            page, verdict = await self._load(url, "#productTitle, h1#title, span#productTitle, h1[class*='title']")
            try:
                if verdict == "soft_block":
                    logger.warning("Product title not found for ASIN %s", asin)
                ...existing extraction body unchanged (everything from `title` to `result = {...}`)...
                return result
            finally:
                await page.close()
```

Expected selectors per method: search → `div[data-component-type="s-search-result"]`; SERP metadata → same; reviews → `div[data-hook="review"]`; rank snapshot → `#productTitle`. `_MAX_RETRIES` and the per-call `async_playwright()` code are deleted. Delete `_launch_browser`, `_new_page`, `_USER_AGENTS`, `_get_random_user_agent` from `scraper_service.py` (persona owns that now); `fetch_autocomplete` keeps a plain UA string constant `_AUTOCOMPLETE_UA`.

- [ ] **Step 3: One session per pipeline run**

In `tasks.py` `_run_full_analysis_async`, wrap the scraping steps:

```python
    from app.core.marketplace import get_marketplace
    from app.scraping.session import BrowserSession
    from app.services.scraper_service import ScraperService

    async with session_factory() as db, BrowserSession(get_marketplace(marketplace), ScraperService(marketplace=marketplace).proxy_manager) as browser:
        scraper = ScraperService(marketplace=marketplace, session=browser)
        ...
```

and pass `scraper` into `_scrape_search_results(scraper, keyword)`, `_scrape_product_details(db, niche_id, products, scraper)` and `KeywordResearchService(db, scraper=scraper, marketplace=marketplace)` (change those helper signatures to take the scraper instead of building their own). Same in `_run_discovery_async` and `_track_bsr_niche_async`.

- [ ] **Step 4: Manual verification (no unit test can cover Playwright)**

Run from `backend/` with a real marketplace and no proxy:

```bash
python - <<'EOF'
import asyncio
from app.services.scraper_service import ScraperService
async def main():
    s = ScraperService(marketplace="AU")
    results = await s.scrape_search_results("garlic press", pages=1)
    print(len(results), results[0]["asin"], results[0]["title"][:40])
    d = await s.scrape_product_page(results[0]["asin"])
    print(d["price"], d["current_bsr"], d["bsr_category"], len(d["page_reviews"]))
asyncio.run(main())
EOF
```
Expected: ≥ 16 results, a price, a BSR, and > 0 page reviews. Watch the log: exactly one "Rotating browser session" at most.

- [ ] **Step 5: Run suite, commit** — `git commit -m "refactor(scraping): one browser session per run; rotate proxy on captcha/503"`

---

### Task C6: Page cache and scrape telemetry

**Files:**
- Create: `backend/app/scraping/page_cache.py`, `backend/app/scraping/events.py`, `backend/app/models/scrape_event.py`, `backend/migrations/versions/014_scrape_events.py`
- Modify: `backend/app/models/__init__.py` (export `ScrapeEvent`), `backend/app/services/scraper_service.py` (`_load` records an event; search/product results cached), `backend/app/api/niches.py` (add `GET /niches/scrape-health` — last 24 h counts by verdict)
- Test: `backend/tests/test_scraping/test_page_cache.py`

**Interfaces:**
- `PageCache(redis)` with `async get(kind, key) -> dict | None`, `async set(kind, key, value)`; TTLs `SERP_TTL_SECONDS = 6*3600`, `PRODUCT_TTL_SECONDS = 24*3600`.
- `ScrapeEvent` table: `id, time, site, url_kind ('serp'|'product'|'reviews'|'serp_meta'|'rank'), verdict, proxy_label, duration_ms`.
- `record_scrape_event(db_session_factory, **fields)` fire-and-forget (own short session; never raises).

- [ ] **Step 1: Test the cache with fakeredis**

```python
# backend/tests/test_scraping/test_page_cache.py
import fakeredis.aioredis

from app.scraping.page_cache import PRODUCT_TTL_SECONDS, PageCache


async def test_set_then_get_roundtrip_and_ttl():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache = PageCache(redis)
    await cache.set("product", "US:B0A", {"asin": "B0A", "price": 9.99})
    assert await cache.get("product", "US:B0A") == {"asin": "B0A", "price": 9.99}
    assert 0 < await redis.ttl("scrape:product:US:B0A") <= PRODUCT_TTL_SECONDS


async def test_miss_returns_none():
    cache = PageCache(fakeredis.aioredis.FakeRedis(decode_responses=True))
    assert await cache.get("serp", "US:nothing") is None
```

- [ ] **Step 2: Run** → ModuleNotFoundError

- [ ] **Step 3: Implement the cache**

```python
# backend/app/scraping/page_cache.py
"""Redis cache for parsed scrape results. WHY: sub-niche flows and forced re-runs re-request the same pages."""

import json

from redis.asyncio import Redis

SERP_TTL_SECONDS = 6 * 3600
PRODUCT_TTL_SECONDS = 24 * 3600
_TTL_BY_KIND = {"serp": SERP_TTL_SECONDS, "product": PRODUCT_TTL_SECONDS, "serp_meta": SERP_TTL_SECONDS}


class PageCache:
    def __init__(self, redis: Redis):
        self.redis = redis

    @staticmethod
    def _key(kind: str, key: str) -> str:
        return f"scrape:{kind}:{key}"

    async def get(self, kind: str, key: str) -> dict | list | None:
        raw = await self.redis.get(self._key(kind, key))
        return json.loads(raw) if raw else None

    async def set(self, kind: str, key: str, value: dict | list) -> None:
        await self.redis.set(self._key(kind, key), json.dumps(value, default=str), ex=_TTL_BY_KIND[kind])
```

`ScraperService.__init__` gains `page_cache: PageCache | None = None`; `scrape_search_results` checks `cache.get("serp", f"{code}:{keyword}:{pages}")` first and sets on success; `scrape_product_page` the same with `("product", f"{code}:{asin}")`. `tasks.py` builds one `PageCache(Redis.from_url(Settings().REDIS_URL, decode_responses=True))` per run and passes it. Forced re-runs (`options["force"]`) pass `page_cache=None` so they re-scrape.

- [ ] **Step 4: Events model + migration 014**

```python
# backend/app/models/scrape_event.py
"""Per-page scrape outcome, so block rates and selector rot are visible."""

from datetime import datetime

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TIMESTAMPTZ


class ScrapeEvent(Base):
    __tablename__ = "scrape_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    time: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    site: Mapped[str] = mapped_column(String(20), nullable=False)       # amazon | 1688
    url_kind: Mapped[str] = mapped_column(String(20), nullable=False)   # serp | product | reviews | serp_meta | rank
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)    # ok | captcha | soft_block | server_error | timeout
    proxy_label: Mapped[str | None] = mapped_column(String(100))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
```

Migration `014_scrape_events.py` (revision "014", down "013"): `op.create_table("scrape_events", ...)` with those columns and `op.create_index("ix_scrape_events_time", "scrape_events", ["time"])`.

```python
# backend/app/scraping/events.py
"""Fire-and-forget recording of scrape outcomes."""

import logging
from datetime import datetime, timezone

from app.models.scrape_event import ScrapeEvent

logger = logging.getLogger(__name__)


async def record_scrape_event(session_factory, *, site: str, url_kind: str, verdict: str, proxy_label: str | None, duration_ms: int) -> None:
    """Insert one row in its own transaction. Never raises — telemetry must not break scraping."""
    try:
        async with session_factory() as db:
            db.add(ScrapeEvent(time=datetime.now(timezone.utc), site=site, url_kind=url_kind, verdict=verdict,
                               proxy_label=proxy_label, duration_ms=duration_ms))
            await db.commit()
    except Exception as e:
        logger.debug("scrape event not recorded: %s", e)
```

`ScraperService._load(url, expected_selector, url_kind)` times the load and calls `record_scrape_event(...)` when `self._event_sink` (a session factory passed from `tasks.py`) is set.

Health endpoint in `niches.py` (before the `/{niche_id}` route so it isn't shadowed):

```python
@router.get("/scrape-health")
async def scrape_health(db: AsyncSession = Depends(get_db)) -> dict:
    """Counts of scrape outcomes in the last 24 hours, by site and verdict."""
    from datetime import datetime, timedelta, timezone
    from app.models.scrape_event import ScrapeEvent
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = (await db.execute(
        select(ScrapeEvent.site, ScrapeEvent.verdict, func.count()).where(ScrapeEvent.time >= since)
        .group_by(ScrapeEvent.site, ScrapeEvent.verdict)
    )).all()
    return {"since": since.isoformat(), "counts": [{"site": s, "verdict": v, "count": c} for s, v, c in rows]}
```

- [ ] **Step 5: Run suite, `alembic upgrade head`, commit** — `git commit -m "feat(scraping): Redis page cache and scrape_events telemetry with health endpoint"`

---

### Task C7: SP-API as the preferred source when credentials exist (F14)

**Files:**
- Modify: `backend/app/services/spapi_service.py` (add `search_catalog_items(keywords, page_size=20) -> list[dict]` normalised to the scraper's search-result dict shape; add `get_rank_snapshot(asin) -> dict` normalised to `scrape_rank_snapshot`'s shape)
- Create: `backend/app/workers/pipeline_steps/product_source.py`
- Modify: `backend/app/workers/tasks.py` (`_scrape_search_results`, `_track_bsr_niche_async`)
- Test: `backend/tests/test_services/test_spapi_normalise.py`

**Interfaces:**
- `normalise_catalog_item(item: dict, marketplace_id: str) -> dict` (pure) → `{asin, title, price, rating: None, review_count: None, image_url, bsr, bsr_category, is_sponsored: False, ...}`.
- `product_source_for(settings, marketplace) -> "spapi" | "scrape"`: `"spapi"` iff `SP_API_CLIENT_ID and SP_API_CLIENT_SECRET and SP_API_REFRESH_TOKEN` are all set.

- [ ] **Step 1: Test the normaliser against a real Catalog Items v2022-04-01 payload shape**

```python
# backend/tests/test_services/test_spapi_normalise.py
from app.services.spapi_service import normalise_catalog_item

ITEM = {
    "asin": "B0A",
    "summaries": [{"marketplaceId": "ATVPDKIKX0DER", "itemName": "Garlic Press", "brand": "Acme", "mainImage": {"link": "https://img/x.jpg"}}],
    "salesRanks": [{"marketplaceId": "ATVPDKIKX0DER", "displayGroupRanks": [{"title": "Home & Kitchen", "rank": 2345}],
                    "classificationRanks": [{"title": "Garlic Presses", "rank": 12}]}],
}


def test_normalise_catalog_item():
    n = normalise_catalog_item(ITEM, "ATVPDKIKX0DER")
    assert n["asin"] == "B0A" and n["title"] == "Garlic Press" and n["brand"] == "Acme"
    assert n["image_url"] == "https://img/x.jpg"
    assert n["bsr"] == 2345 and n["bsr_category"] == "Home & Kitchen"
    assert n["current_subcategory_bsr"] == 12 and n["subcategory_name"] == "Garlic Presses"
    assert n["price"] is None  # pricing comes from the Pricing API, not Catalog
```

- [ ] **Step 2: Run** → ImportError

- [ ] **Step 3: Implement**

Module-level in `spapi_service.py`:

```python
def normalise_catalog_item(item: dict, marketplace_id: str) -> dict:
    """Map a Catalog Items v2022-04-01 item onto the dict shape ScraperService.scrape_search_results returns."""
    summary = next((s for s in item.get("summaries", []) if s.get("marketplaceId") == marketplace_id), {})
    ranks = next((r for r in item.get("salesRanks", []) if r.get("marketplaceId") == marketplace_id), {})
    main = (ranks.get("displayGroupRanks") or [{}])[0]
    sub = (ranks.get("classificationRanks") or [{}])[0]
    return {
        "asin": item.get("asin"),
        "title": summary.get("itemName"),
        "brand": summary.get("brand"),
        "image_url": (summary.get("mainImage") or {}).get("link"),
        "price": None, "rating": None, "review_count": None,
        "bsr": main.get("rank"), "bsr_category": main.get("title"),
        "current_subcategory_bsr": sub.get("rank"), "subcategory_name": sub.get("title"),
        "is_sponsored": False, "is_amazon_choice": False, "is_best_seller": False, "is_fba": None,
    }
```

Add to `SPAPIService`:

```python
    async def search_catalog_items(self, keywords: str, page_size: int = 20) -> list[dict]:
        """GET /catalog/2022-04-01/items?keywords=... normalised to search-result dicts."""
        params = {"marketplaceIds": self.marketplace_id, "keywords": keywords, "pageSize": page_size,
                  "includedData": "summaries,salesRanks,images"}
        data = await self._request("GET", "/catalog/2022-04-01/items", params=params)
        return [normalise_catalog_item(i, self.marketplace_id) for i in data.get("items", [])]

    async def get_rank_snapshot(self, asin: str) -> dict:
        data = await self._request("GET", f"/catalog/2022-04-01/items/{asin}",
                                   params={"marketplaceIds": self.marketplace_id, "includedData": "salesRanks"})
        n = normalise_catalog_item(data, self.marketplace_id)
        return {"asin": asin, "price": None, "current_bsr": n["bsr"], "bsr_category": n["bsr_category"],
                "current_subcategory_bsr": n["current_subcategory_bsr"], "subcategory_name": n["subcategory_name"],
                "stock_level": None, "stock_text": None, "is_in_stock": True}
```

(`_request` is the existing signed-request helper in the file; if it is named differently, use that name.)

```python
# backend/app/workers/pipeline_steps/product_source.py
"""Decide where product data comes from: SP-API when configured (legal, unblockable), else scraping."""

from app.config import Settings


def product_source_for(settings: Settings) -> str:
    if settings.SP_API_CLIENT_ID and settings.SP_API_CLIENT_SECRET and settings.SP_API_REFRESH_TOKEN:
        return "spapi"
    return "scrape"
```

In `tasks.py`:
- `_scrape_search_results(scraper, keyword, marketplace)`: if `product_source_for(Settings()) == "spapi"`, call `SPAPIService(...).search_catalog_items(keyword, page_size=40)`; if it returns ≥ 10 items use them (positions = index+1) and **still** scrape page 1 of the SERP for sponsored/badge/price/rating enrichment (merge by ASIN). Otherwise fall back to scraping 3 pages.
- `_track_bsr_niche_async`: use `get_rank_snapshot` for BSR when `"spapi"`, and only scrape the page for price/stock on products with `last_stock_level < 20` (existing rule).

- [ ] **Step 4: Run suite, commit** — `git commit -m "feat: use SP-API catalog search and ranks when credentials exist; scrape only for enrichment"`

---

### Task C8: Docs for scraping operations

- [ ] Add a "Scraping resilience" section to `GUIDE.md` §4 describing: one session per run, pacing constants (`app/scraping/pacing.py`), what `GET /api/v1/niches/scrape-health` shows and the thresholds to act on (captcha > 20 % of loads in 24 h → switch `PROXY_PROVIDER` or lower volume), and the SP-API-first behaviour. Update the Proxy System Architecture mermaid to include `BrowserSession → Pacer → classify_page → rotate`.
- [ ] Commit: `git commit -am "docs: scraping resilience operations guide"`

---

## Decisions and deliberately deferred work

| Item | Decision | Why |
|---|---|---|
| Whole-pipeline transaction ("atomicity") | **Not doing it.** Keep per-step commits + `status=failed` + `last_error` + reset-on-force (B2). | A 20–90 min transaction holds locks and connections; partial data is useful for debugging; the UI already shows status. |
| Authentication / multi-tenancy | Defer. Add a single `X-API-Key` middleware only when the app is exposed beyond localhost. | Single-user tool on a private machine; CORS allow-list (B4) is the proportionate step now. |
| API pagination on sub-resource lists | Defer. | Lists are ≤ 60 products / ≤ 100 keywords per niche. |
| CAPTCHA solving vendor (2captcha/CapSolver) | Defer; keep `/captcha/` images unblocked (C4) so it can be added behind `classify_page == "captcha"` later. | Rotation + pacing + SP-API-first should keep captcha rate low at our volume; measure with C6 first. |
| Third-party data APIs (Keepa, Rainforest) | Defer; `product_source_for()` (C7) is the seam. | Decide with 2 weeks of `scrape_events` data. |
| Trend sub-score inputs (`bsr_velocity_pct`, `search_volume_trend`, `is_seasonal`) | Defer until B5 has produced ≥ 30 days of history; then compute from `BSRTracker.get_bsr_trend`. | No history exists yet; defaults are neutral (score 55). |
| `tasks.py` full decomposition | Incremental only — every step touched in this plan moves into `pipeline_steps/`. | A big-bang refactor of an 1800-line orchestrator without integration tests is riskier than the bugs it would fix. |
| Prompt-injection hardening beyond keyword normalisation | Defer. | Only the keyword and scraped review text reach prompts; outputs are JSON-validated and rendered as text, never executed. |
| Structured logging everywhere / monitoring stack | Defer; `scrape_events` (C6) covers the one metric that matters today. | |

## Self-review

- Spec coverage: F1→A1, F2→A2, F3→A3, F4→A4, F5/F6/F7→A5, F8/F9→A6, F10→B1, F11→B2, F12→B5, F13→C1–C6, F14→C7. TODO.md CRITICAL/HIGH items: engine leak (B1), timeouts (B1), atomicity (decision), auth (deferred, decision), CORS (B4), idempotency (B2), indexes (A3), eager loading (deferred — `selectin` only fires when relationships are accessed; the list endpoints use scalar queries), LLM retry (B3), pagination (deferred).
- Placeholder scan: every step has code or an exact edit location; the two "manual verification" steps (C5 step 4) are explicit because Playwright cannot be unit-tested.
- Type consistency: `persist_landscape(niche_id, landscape)` in A2 matches its call in A2 step 5; `build_ppc_strategy`/`ppc_metrics_from_strategy` names match between A4 steps 3 and 5; `summarize_suppliers(suppliers, cny_to_usd_rate)` matches A5 steps 1/4/8; `scrape_rank_snapshot` shape (B5) matches `get_rank_snapshot` (C7); `_get_session_factory`/`_run_async`/`_reset_runtime_for_tests` match between B1 test and implementation; `should_block_request`, `classify_page`, `pacer_for`, `build_persona` names match across C1–C5.
