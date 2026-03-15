"""API routes for recommendation retrieval."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.niche import Niche
from app.models.recommendation import Recommendation
from app.schemas.recommendation import (
    RecommendationListResponse,
    RecommendationResponse,
    RecommendationSummary,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


# ---------------------------------------------------------------------------
# GET /recommendations/ — List all recommendations (paginated)
# ---------------------------------------------------------------------------


@router.get("/", response_model=RecommendationListResponse)
async def list_recommendations(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    min_score: float | None = Query(
        None, ge=0, le=100, description="Minimum Omniscient score filter"
    ),
    db: AsyncSession = Depends(get_db),
) -> RecommendationListResponse:
    """Return a paginated list of recommendations, optionally filtered by score."""
    # Build base filter
    filters = []
    if min_score is not None:
        filters.append(Recommendation.omniscient_score >= min_score)

    # Total count
    count_stmt = select(func.count(Recommendation.id))
    for f in filters:
        count_stmt = count_stmt.where(f)
    count_result = await db.execute(count_stmt)
    total: int = count_result.scalar_one()

    total_pages = math.ceil(total / per_page) if total > 0 else 0
    offset = (page - 1) * per_page

    # Fetch page
    stmt = (
        select(Recommendation)
        .order_by(Recommendation.omniscient_score.desc())
        .offset(offset)
        .limit(per_page)
    )
    for f in filters:
        stmt = stmt.where(f)

    result = await db.execute(stmt)
    recs = result.scalars().all()

    # Fetch niche names for all recommendations
    niche_ids = list({r.niche_id for r in recs})
    niche_names: dict[int, str] = {}
    if niche_ids:
        niche_result = await db.execute(
            select(Niche.id, Niche.name).where(Niche.id.in_(niche_ids))
        )
        niche_names = {row.id: row.name for row in niche_result.all()}

    items = []
    for r in recs:
        data = RecommendationResponse.model_validate(r)
        data.niche_name = niche_names.get(r.niche_id)
        items.append(data)

    return RecommendationListResponse(
        items=items,
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /recommendations/{recommendation_id} — Recommendation detail
# ---------------------------------------------------------------------------


@router.get("/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
) -> RecommendationResponse:
    """Return full detail for a single recommendation."""
    result = await db.execute(
        select(Recommendation).where(Recommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=f"Recommendation {recommendation_id} not found",
        )
    data = RecommendationResponse.model_validate(rec)
    # Fetch niche name
    niche_result = await db.execute(
        select(Niche.name).where(Niche.id == rec.niche_id)
    )
    niche_row = niche_result.scalar_one_or_none()
    if niche_row:
        data.niche_name = niche_row
    return data
