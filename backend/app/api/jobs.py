"""API routes for background job management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.niche import Niche
from app.schemas.common import JobStatusResponse
from app.workers.celery_app import celery_app
from app.workers.tasks import run_full_analysis

router = APIRouter(prefix="/jobs", tags=["jobs"])

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
        min_length=1, max_length=255, description="Niche keyword to analyze"
    )
    force: bool = Field(
        default=False, description="Force re-analysis if niche already exists"
    )


# ---------------------------------------------------------------------------
# POST /jobs/analyze — Trigger analysis from a keyword
# ---------------------------------------------------------------------------


@router.post("/analyze", response_model=JobStatusResponse, status_code=202)
async def trigger_keyword_analysis(
    payload: AnalyzeKeywordRequest,
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """Trigger analysis from a keyword. Creates the niche if it doesn't exist."""
    keyword = payload.keyword.strip()

    # Check if niche already exists
    result = await db.execute(
        select(Niche).where(Niche.primary_keyword == keyword)
    )
    niche = result.scalar_one_or_none()

    if niche is not None and not payload.force:
        # Niche exists — check if already analyzed (opportunity_score is set
        # only after the scoring step completes successfully).
        if niche.opportunity_score is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Niche '{keyword}' already analyzed. Use force=true to re-analyze.",
            )

    if niche is None:
        niche = Niche(name=keyword, primary_keyword=keyword)
        db.add(niche)
        await db.flush()
        await db.refresh(niche)

    # Dispatch to Celery
    task = run_full_analysis.delay(
        niche_id=niche.id,
        keyword=niche.primary_keyword,
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
