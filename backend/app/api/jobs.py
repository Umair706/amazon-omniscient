"""API routes for background job management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_license
from app.licensing import FEATURE_MULTI_MARKETPLACE, License
from app.models.niche import Niche
from app.models.product import Product
from app.schemas.common import JobStatusResponse
from app.workers.celery_app import celery_app
from app.workers.tasks import run_full_analysis, run_discovery, discover_opportunities

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _guard_marketplace(db: AsyncSession, marketplace: str, license: License) -> None:
    """Free tier may analyse one marketplace; a second distinct one needs multi_marketplace.

    Raises 402 when the requested marketplace would be the account's second and the
    license does not grant it. The first marketplace a user ever analyses is always free.
    """
    if FEATURE_MULTI_MARKETPLACE in license.features:
        return
    used = (await db.execute(select(distinct(Niche.marketplace)))).scalars().all()
    existing = {m for m in used if m}
    if existing and marketplace not in existing:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "feature_locked",
                "feature": FEATURE_MULTI_MARKETPLACE,
                "message": (
                    f"The free tier analyses one marketplace ({', '.join(sorted(existing))}). "
                    f"Analysing '{marketplace}' too needs a license with multi_marketplace. See docs/LICENSING.md."
                ),
            },
        )

# Keywords are interpolated into LLM prompts and Amazon URLs, so we cap
# their length well below the DB column limit to keep prompts small.
MAX_KEYWORD_LENGTH = 100

# ---------------------------------------------------------------------------
# Celery state -> API status mapping
# ---------------------------------------------------------------------------

_CELERY_STATE_MAP: dict[str, str] = {
    "PENDING": "pending",
    "STARTED": "running",
    "PROGRESS": "running",
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "RETRY": "running",
    "REVOKED": "failed",
}


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class AnalyzeNicheRequest(BaseModel):
    """Payload to trigger a full niche analysis pipeline."""

    niche_id: int = Field(description="ID of the niche to analyse")
    force: bool = Field(
        default=False,
        description="Force re-analysis even if data already exists",
    )


class AnalyzeKeywordRequest(BaseModel):
    """Payload to trigger analysis from a keyword (creates niche automatically)."""

    keyword: str = Field(
        min_length=1, max_length=MAX_KEYWORD_LENGTH, description="Niche keyword to analyze"
    )
    marketplace: str = Field(
        default="AU",
        max_length=10,
        description="Amazon marketplace code (e.g. AU, US). Defaults to AU.",
    )
    force: bool = Field(
        default=False, description="Force re-analysis if niche already exists"
    )

    @field_validator("keyword")
    @classmethod
    def normalise_keyword(cls, v: str) -> str:
        # WHY: the keyword is interpolated into LLM prompts and URLs; collapse whitespace/control chars.
        v = " ".join(v.split())
        # NOTE: min_length ran before collapsing, so "   " got past it.
        if not v:
            raise ValueError("keyword must not be blank")
        return v


class DiscoverOpportunitiesRequest(BaseModel):
    """Payload to discover candidate niches from a broad seed keyword."""

    seed: str = Field(min_length=1, max_length=MAX_KEYWORD_LENGTH, description="Broad seed, e.g. 'kitchen'")
    marketplace: str = Field(default="AU", max_length=10, description="Amazon marketplace code (default AU).")

    @field_validator("seed")
    @classmethod
    def normalise_seed(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("seed must not be blank")
        return v


class AnalyzeSubNicheRequest(BaseModel):
    """Payload to trigger full analysis on a selected sub-niche."""

    parent_niche_id: int = Field(description="ID of the parent (discovery) niche")
    sub_niche_label: str = Field(min_length=1, max_length=255, description="Label of the selected sub-niche")
    product_asins: list[str] = Field(description="ASINs belonging to the selected sub-niche")


# ---------------------------------------------------------------------------
# POST /jobs/analyze — Trigger analysis from a keyword
# ---------------------------------------------------------------------------


@router.post("/analyze", response_model=JobStatusResponse, status_code=202)
async def trigger_keyword_analysis(
    payload: AnalyzeKeywordRequest,
    db: AsyncSession = Depends(get_db),
    license: License = Depends(get_license),
) -> JobStatusResponse:
    """Trigger analysis from a keyword. Creates the niche if it doesn't exist."""
    keyword = payload.keyword.strip()
    marketplace = payload.marketplace.strip().upper()
    await _guard_marketplace(db, marketplace, license)

    # Check if niche already exists for this marketplace
    result = await db.execute(
        select(Niche).where(
            Niche.primary_keyword == keyword,
            Niche.marketplace == marketplace,
        )
    )
    niche = result.scalar_one_or_none()

    if niche is not None and not payload.force:
        if niche.opportunity_score is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Niche '{keyword}' ({marketplace}) already analyzed. Use force=true to re-analyze.",
            )

    if niche is None:
        niche = Niche(name=keyword, primary_keyword=keyword, marketplace=marketplace)
        db.add(niche)
        await db.flush()
        await db.refresh(niche)

    # Dispatch to Celery
    task = run_full_analysis.delay(
        niche_id=niche.id,
        keyword=niche.primary_keyword,
        marketplace=marketplace,
        options={"force": payload.force},
    )

    now = datetime.now(timezone.utc)

    return JobStatusResponse(
        job_id=task.id,
        status="pending",
        progress=0,
        result={"niche_id": niche.id, "keyword": keyword},
        error=None,
        created_at=now,
        updated_at=None,
    )


# ---------------------------------------------------------------------------
# POST /jobs/analyze-niche — Trigger full niche analysis (by niche ID)
# ---------------------------------------------------------------------------


@router.post("/analyze-niche", response_model=JobStatusResponse, status_code=202)
async def trigger_niche_analysis(
    payload: AnalyzeNicheRequest,
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """Trigger the full analysis pipeline for a niche.

    This dispatches the analysis as a Celery task and returns immediately
    with a ``job_id`` that can be polled for progress.

    Pipeline stages (executed asynchronously by Celery worker):
    1. Product scraping & enrichment
    2. Keyword research
    3. Competitor analysis
    4. Review scraping & pain-point clustering
    5. Supplier sourcing & landed-cost calculation
    6. Financial modelling
    7. Final scoring & recommendation generation
    """
    # Validate niche exists
    result = await db.execute(select(Niche).where(Niche.id == payload.niche_id))
    niche = result.scalar_one_or_none()
    if niche is None:
        raise HTTPException(
            status_code=404,
            detail=f"Niche {payload.niche_id} not found",
        )

    # Dispatch to Celery
    task = run_full_analysis.delay(
        niche_id=payload.niche_id,
        keyword=niche.primary_keyword,
        marketplace=niche.marketplace or "US",
        options={"force": payload.force},
    )

    now = datetime.now(timezone.utc)

    return JobStatusResponse(
        job_id=task.id,
        status="pending",
        progress=0,
        result=None,
        error=None,
        created_at=now,
        updated_at=None,
    )


# ---------------------------------------------------------------------------
# POST /jobs/reanalyze-niche — Re-run analysis on an existing niche, no re-scrape
# ---------------------------------------------------------------------------


@router.post("/reanalyze-niche", response_model=JobStatusResponse, status_code=202)
async def trigger_niche_reanalysis(
    payload: AnalyzeNicheRequest,
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """Re-run the analysis on an existing niche WITHOUT re-scraping Amazon.

    Reuses the products already scraped for the niche and regenerates the
    derived work — competitor analysis, AI intelligence, suppliers, financials,
    and the Omniscient Score. Useful after configuring an LLM or changing the
    scoring rules, when a fresh scrape would be wasteful (or blocked).
    """
    niche = (await db.execute(select(Niche).where(Niche.id == payload.niche_id))).scalar_one_or_none()
    if niche is None:
        raise HTTPException(status_code=404, detail=f"Niche {payload.niche_id} not found")

    asins = (
        await db.execute(select(Product.asin).where(Product.niche_id == payload.niche_id))
    ).scalars().all()
    if not asins:
        raise HTTPException(
            status_code=409,
            detail="This niche has no scraped products to reuse. Run a full analysis first.",
        )

    # force=True clears the derived rows (competitors, suppliers, financials,
    # recommendations) so the re-run does not duplicate them; products and
    # reviews are kept. product_asins makes the pipeline load those products
    # instead of scraping the search + product pages again.
    task = run_full_analysis.delay(
        niche_id=niche.id,
        keyword=niche.primary_keyword,
        marketplace=niche.marketplace or "US",
        options={"force": True},
        product_asins=list(asins),
    )

    now = datetime.now(timezone.utc)
    return JobStatusResponse(
        job_id=task.id, status="pending", progress=0, result=None, error=None,
        created_at=now, updated_at=None,
    )


# ---------------------------------------------------------------------------
# POST /jobs/discover — Run discovery phase (sub-niche detection)
# ---------------------------------------------------------------------------


@router.post("/discover", response_model=JobStatusResponse, status_code=202)
async def trigger_discovery(
    payload: AnalyzeKeywordRequest,
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """Run discovery phase only — returns sub-niche options if keyword is broad."""
    keyword = payload.keyword.strip()
    marketplace = payload.marketplace.strip().upper()

    # Check if niche already exists for this marketplace
    result = await db.execute(
        select(Niche).where(
            Niche.primary_keyword == keyword,
            Niche.marketplace == marketplace,
        )
    )
    niche = result.scalar_one_or_none()

    if niche is not None and not payload.force:
        if niche.opportunity_score is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Niche '{keyword}' ({marketplace}) already analyzed. Use force=true to re-analyze.",
            )

    if niche is None:
        niche = Niche(name=keyword, primary_keyword=keyword, marketplace=marketplace)
        db.add(niche)
        await db.flush()
        await db.refresh(niche)

    # Dispatch discovery task
    task = run_discovery.delay(
        niche_id=niche.id,
        keyword=niche.primary_keyword,
        marketplace=marketplace,
        options={"force": payload.force},
    )

    now = datetime.now(timezone.utc)

    return JobStatusResponse(
        job_id=task.id,
        status="pending",
        progress=0,
        result={"niche_id": niche.id, "keyword": keyword},
        error=None,
        created_at=now,
        updated_at=None,
    )


# ---------------------------------------------------------------------------
# POST /jobs/analyze-sub-niche — Create child niche and run full analysis
# ---------------------------------------------------------------------------


@router.post("/analyze-sub-niche", response_model=JobStatusResponse, status_code=202)
async def trigger_sub_niche_analysis(
    payload: AnalyzeSubNicheRequest,
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """Create child niche from selected sub-niche and run full analysis on subset."""
    # Validate parent niche exists
    result = await db.execute(
        select(Niche).where(Niche.id == payload.parent_niche_id)
    )
    parent_niche = result.scalar_one_or_none()
    if parent_niche is None:
        raise HTTPException(
            status_code=404,
            detail=f"Parent niche {payload.parent_niche_id} not found",
        )

    # Create child niche with composite primary_keyword
    child_keyword = f"{parent_niche.primary_keyword} :: {payload.sub_niche_label}"

    # Check if child already exists
    result = await db.execute(
        select(Niche).where(Niche.primary_keyword == child_keyword)
    )
    child_niche = result.scalar_one_or_none()

    if child_niche is None:
        child_niche = Niche(
            name=payload.sub_niche_label,
            primary_keyword=child_keyword,
            marketplace=parent_niche.marketplace or "US",
            parent_niche_id=payload.parent_niche_id,
            sub_niche_label=payload.sub_niche_label,
        )
        db.add(child_niche)
        await db.flush()
        await db.refresh(child_niche)

    # Dispatch full analysis with product_asins filter
    task = run_full_analysis.delay(
        niche_id=child_niche.id,
        keyword=parent_niche.primary_keyword,
        marketplace=parent_niche.marketplace or "US",
        options={"force": True},
        product_asins=payload.product_asins,
    )

    now = datetime.now(timezone.utc)

    return JobStatusResponse(
        job_id=task.id,
        status="pending",
        progress=0,
        result={"niche_id": child_niche.id, "keyword": child_keyword},
        error=None,
        created_at=now,
        updated_at=None,
    )


# ---------------------------------------------------------------------------
# POST /jobs/discover-opportunities — Rank candidate niches from a broad seed
# ---------------------------------------------------------------------------


@router.post("/discover-opportunities", response_model=JobStatusResponse, status_code=202)
async def trigger_opportunity_discovery(
    payload: DiscoverOpportunitiesRequest,
) -> JobStatusResponse:
    """Expand a broad seed into ranked candidate niches. No niche is created; results come
    back in the job's `result.candidates`. Not marketplace-gated — exploring is always free."""
    marketplace = payload.marketplace.strip().upper()
    task = discover_opportunities.delay(seed=payload.seed, marketplace=marketplace)
    now = datetime.now(timezone.utc)
    return JobStatusResponse(
        job_id=task.id, status="pending", progress=0,
        result={"seed": payload.seed, "marketplace": marketplace}, error=None,
        created_at=now, updated_at=None,
    )


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/status — Check job status
# ---------------------------------------------------------------------------


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
) -> JobStatusResponse:
    """Return the current status and progress of a background job."""
    result = celery_app.AsyncResult(job_id)
    state = result.state
    status = _CELERY_STATE_MAP.get(state, "pending")

    progress: int | None = None
    task_result: dict | None = None
    error: str | None = None

    if state == "PROGRESS":
        # Worker reports progress via self.update_state(state="PROGRESS", meta={...})
        info = result.info or {}
        progress = info.get("progress", 0)
        task_result = {"step": info.get("step", "unknown")}
    elif state == "SUCCESS":
        progress = 100
        raw = result.result
        task_result = raw if isinstance(raw, dict) else {"result": raw}
    elif state == "FAILURE":
        progress = None
        error = str(result.result)
    elif state in ("STARTED", "RETRY"):
        progress = 0

    now = datetime.now(timezone.utc)

    return JobStatusResponse(
        job_id=job_id,
        status=status,
        progress=progress,
        result=task_result,
        error=error,
        created_at=now,
        updated_at=now if state != "PENDING" else None,
    )
