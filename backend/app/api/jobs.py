"""API routes for background job management."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.niche import Niche
from app.schemas.common import JobStatusResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])

# ---------------------------------------------------------------------------
# In-memory job store (replace with Redis/Celery in production)
# ---------------------------------------------------------------------------
# Keys: job_id (str) -> dict with status info
_job_store: dict[str, dict] = {}


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


# ---------------------------------------------------------------------------
# POST /jobs/analyze-niche — Trigger full niche analysis
# ---------------------------------------------------------------------------


@router.post("/analyze-niche", response_model=JobStatusResponse, status_code=202)
async def trigger_niche_analysis(
    payload: AnalyzeNicheRequest,
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """Trigger the full analysis pipeline for a niche.

    This enqueues the analysis as a background job and returns immediately
    with a ``job_id`` that can be polled for progress.

    Pipeline stages (executed asynchronously):
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

    # Create job record
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    _job_store[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "result": {
            "niche_id": payload.niche_id,
            "force": payload.force,
        },
        "error": None,
        "created_at": now,
        "updated_at": now,
    }

    # In production, this is where you would dispatch the job to Celery / ARQ:
    #   await enqueue_niche_analysis(niche_id=payload.niche_id, force=payload.force)
    #
    # For now, the job sits in "pending" state until a worker picks it up.

    return JobStatusResponse(
        job_id=job_id,
        status="pending",
        progress=0,
        result={"niche_id": payload.niche_id, "force": payload.force},
        error=None,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/status — Check job status
# ---------------------------------------------------------------------------


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
) -> JobStatusResponse:
    """Return the current status and progress of a background job."""
    job = _job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found",
        )

    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        result=job["result"],
        error=job["error"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )
