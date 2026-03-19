"""API routes for niche management and sub-resource queries."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db
from app.models.competitor import Competitor
from app.models.financial_projection import FinancialProjection
from app.models.keyword import NicheKeyword
from app.models.niche import Niche
from app.models.product import Product
from app.models.review import ReviewPainPoint
from app.models.supplier import Supplier
from app.schemas.competitor import CompetitorListResponse, CompetitorResponse
from app.schemas.financial import FinancialProjectionResponse, ProjectionListResponse
from app.schemas.keyword import KeywordResearchSummary, KeywordResponse
from app.schemas.niche import NicheCreate, NicheListResponse, NicheResponse, NicheSummary
from app.schemas.product import ProductListResponse, ProductResponse
from app.schemas.review import ReviewPainPointResponse
from app.schemas.supplier import SupplierListResponse, SupplierResponse

router = APIRouter(prefix="/niches", tags=["niches"])


# ---------------------------------------------------------------------------
# POST /niches/ — Create a new niche analysis job
# ---------------------------------------------------------------------------


@router.post("/", response_model=NicheResponse, status_code=201)
async def create_niche(
    payload: NicheCreate,
    db: AsyncSession = Depends(get_db),
) -> NicheResponse:
    """Create a new niche analysis entry.

    The niche is stored immediately with the primary keyword.  A background
    analysis job should be triggered separately via ``POST /api/jobs/analyze-niche``.
    """
    # Check for duplicate keyword+marketplace combo
    existing = await db.execute(
        select(Niche).where(
            Niche.primary_keyword == payload.keyword,
            Niche.marketplace == payload.marketplace,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A niche with keyword '{payload.keyword}' already exists for marketplace {payload.marketplace}",
        )

    niche = Niche(
        name=payload.keyword,
        primary_keyword=payload.keyword,
        marketplace=payload.marketplace,
    )
    db.add(niche)
    await db.flush()
    await db.refresh(niche)
    return NicheResponse.model_validate(niche)


# ---------------------------------------------------------------------------
# GET /niches/ — List all niches (paginated)
# ---------------------------------------------------------------------------


@router.get("/", response_model=NicheListResponse)
async def list_niches(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by keyword or name"),
    marketplace: str | None = Query(None, description="Filter by marketplace code (e.g. US, AU)"),
    min_score: float | None = Query(None, ge=0, le=100, description="Minimum opportunity score"),
    confidence_tier: str | None = Query(None, description="Filter by confidence tier (e.g. HIGH, MEDIUM, LOW, FAIL)"),
    status: str | None = Query(None, description="Filter by status (e.g. pending, analyzing, completed, failed)"),
    sort_by: str | None = Query(None, description="Sort field (opportunity_score, avg_sale_price, monthly_search_volume, avg_review_count, name, created_at)"),
    sort_dir: str | None = Query("desc", description="Sort direction (asc, desc)"),
    db: AsyncSession = Depends(get_db),
) -> NicheListResponse:
    """Return a paginated list of niche summaries ordered by most recent first."""
    # Build filter conditions
    conditions: list = []
    if marketplace is not None:
        conditions.append(Niche.marketplace == marketplace.strip().upper())
    if search is not None:
        conditions.append(
            or_(
                Niche.primary_keyword.ilike(f"%{search}%"),
                Niche.name.ilike(f"%{search}%"),
            )
        )
    if min_score is not None:
        conditions.append(Niche.opportunity_score >= min_score)
    if confidence_tier is not None:
        conditions.append(Niche.confidence_tier == confidence_tier)
    if status is not None:
        conditions.append(Niche.status == status)

    # Sorting
    SORTABLE_FIELDS = {
        "opportunity_score": Niche.opportunity_score,
        "avg_sale_price": Niche.avg_sale_price,
        "monthly_search_volume": Niche.monthly_search_volume,
        "avg_review_count": Niche.avg_review_count,
        "name": Niche.name,
        "created_at": Niche.created_at,
    }

    sort_column = SORTABLE_FIELDS.get(sort_by, Niche.created_at)
    if sort_dir == "asc":
        order_clause = sort_column.asc().nullslast()
    else:
        order_clause = sort_column.desc().nullslast()

    # Total count
    count_stmt = select(func.count(Niche.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    count_result = await db.execute(count_stmt)
    total: int = count_result.scalar_one()

    total_pages = math.ceil(total / per_page) if total > 0 else 0
    offset = (page - 1) * per_page

    # Fetch page
    fetch_stmt = select(Niche)
    if conditions:
        fetch_stmt = fetch_stmt.where(*conditions)
    fetch_stmt = fetch_stmt.order_by(order_clause).offset(offset).limit(per_page)

    result = await db.execute(fetch_stmt)
    niches = result.scalars().all()

    return NicheListResponse(
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        items=[NicheSummary.model_validate(n) for n in niches],
    )


# ---------------------------------------------------------------------------
# GET /niches/{niche_id} — Get niche detail
# ---------------------------------------------------------------------------


@router.get("/{niche_id}", response_model=NicheResponse)
async def get_niche(
    niche_id: int,
    db: AsyncSession = Depends(get_db),
) -> NicheResponse:
    """Return full detail for a single niche."""
    result = await db.execute(select(Niche).where(Niche.id == niche_id))
    niche = result.scalar_one_or_none()
    if niche is None:
        raise HTTPException(status_code=404, detail=f"Niche {niche_id} not found")
    return NicheResponse.model_validate(niche)


# ---------------------------------------------------------------------------
# DELETE /niches/{niche_id} — Delete a niche
# ---------------------------------------------------------------------------


@router.delete("/{niche_id}", status_code=204)
async def delete_niche(
    niche_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a niche and all its related data (cascades via FK)."""
    result = await db.execute(select(Niche).where(Niche.id == niche_id))
    niche = result.scalar_one_or_none()
    if niche is None:
        raise HTTPException(status_code=404, detail=f"Niche {niche_id} not found")
    await db.delete(niche)
    await db.flush()


# ---------------------------------------------------------------------------
# GET /niches/{niche_id}/products — Products in this niche
# ---------------------------------------------------------------------------


@router.get("/{niche_id}/products", response_model=ProductListResponse)
async def list_niche_products(
    niche_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProductListResponse:
    """Return all products belonging to a niche."""
    # Verify niche exists
    niche_exists = await db.execute(select(Niche.id).where(Niche.id == niche_id))
    if niche_exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Niche {niche_id} not found")

    count_result = await db.execute(
        select(func.count(Product.id)).where(Product.niche_id == niche_id)
    )
    total: int = count_result.scalar_one()

    result = await db.execute(
        select(Product)
        .where(Product.niche_id == niche_id)
        .order_by(Product.estimated_monthly_revenue.desc().nullslast())
    )
    products = result.scalars().all()

    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /niches/{niche_id}/competitors — Competitors in this niche
# ---------------------------------------------------------------------------


@router.get("/{niche_id}/competitors", response_model=CompetitorListResponse)
async def list_niche_competitors(
    niche_id: int,
    db: AsyncSession = Depends(get_db),
) -> CompetitorListResponse:
    """Return all competitor analyses for a niche."""
    niche_exists = await db.execute(select(Niche.id).where(Niche.id == niche_id))
    if niche_exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Niche {niche_id} not found")

    count_result = await db.execute(
        select(func.count(Competitor.id)).where(Competitor.niche_id == niche_id)
    )
    total: int = count_result.scalar_one()

    result = await db.execute(
        select(Competitor)
        .where(Competitor.niche_id == niche_id)
        .order_by(Competitor.organic_rank.asc().nullslast())
    )
    competitors = result.scalars().all()

    return CompetitorListResponse(
        items=[CompetitorResponse.model_validate(c) for c in competitors],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /niches/{niche_id}/keywords — Keywords for this niche
# ---------------------------------------------------------------------------


@router.get("/{niche_id}/keywords", response_model=list[KeywordResponse])
async def list_niche_keywords(
    niche_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[KeywordResponse]:
    """Return all organic keywords for a niche, ordered by search volume."""
    niche_exists = await db.execute(select(Niche.id).where(Niche.id == niche_id))
    if niche_exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Niche {niche_id} not found")

    result = await db.execute(
        select(NicheKeyword)
        .where(NicheKeyword.niche_id == niche_id)
        .order_by(NicheKeyword.search_volume.desc().nullslast())
    )
    keywords = result.scalars().all()
    return [KeywordResponse.model_validate(k) for k in keywords]


# ---------------------------------------------------------------------------
# GET /niches/{niche_id}/reviews — Review pain points for this niche
# ---------------------------------------------------------------------------


@router.get("/{niche_id}/reviews", response_model=list[ReviewPainPointResponse])
async def list_niche_reviews(
    niche_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[ReviewPainPointResponse]:
    """Return clustered review pain points for a niche, ordered by mention count."""
    niche_exists = await db.execute(select(Niche.id).where(Niche.id == niche_id))
    if niche_exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Niche {niche_id} not found")

    result = await db.execute(
        select(ReviewPainPoint)
        .where(ReviewPainPoint.niche_id == niche_id)
        .order_by(ReviewPainPoint.mention_count.desc().nullslast())
    )
    pain_points = result.scalars().all()
    return [ReviewPainPointResponse.model_validate(pp) for pp in pain_points]


# ---------------------------------------------------------------------------
# GET /niches/{niche_id}/financials — Financial projections for this niche
# ---------------------------------------------------------------------------


@router.get("/{niche_id}/financials", response_model=ProjectionListResponse)
async def get_niche_financials(
    niche_id: int,
    scenario: str | None = Query(
        None, description="Filter by scenario (bull, base, bear)"
    ),
    db: AsyncSession = Depends(get_db),
) -> ProjectionListResponse:
    """Return weekly financial projections for a niche, optionally filtered by scenario."""
    niche_exists = await db.execute(select(Niche.id).where(Niche.id == niche_id))
    if niche_exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Niche {niche_id} not found")

    stmt = select(FinancialProjection).where(
        FinancialProjection.niche_id == niche_id
    )
    if scenario is not None:
        stmt = stmt.where(FinancialProjection.scenario == scenario)

    stmt = stmt.order_by(
        FinancialProjection.scenario,
        FinancialProjection.week_number,
    )

    count_stmt = select(func.count(FinancialProjection.id)).where(
        FinancialProjection.niche_id == niche_id
    )
    if scenario is not None:
        count_stmt = count_stmt.where(FinancialProjection.scenario == scenario)

    count_result = await db.execute(count_stmt)
    total: int = count_result.scalar_one()

    result = await db.execute(stmt)
    projections = result.scalars().all()

    return ProjectionListResponse(
        items=[FinancialProjectionResponse.model_validate(fp) for fp in projections],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /niches/{niche_id}/suppliers — Suppliers for this niche
# ---------------------------------------------------------------------------


@router.get("/{niche_id}/suppliers", response_model=SupplierListResponse)
async def list_niche_suppliers(
    niche_id: int,
    db: AsyncSession = Depends(get_db),
) -> SupplierListResponse:
    """Return all suppliers for a niche with their landed cost breakdowns."""
    niche_exists = await db.execute(select(Niche.id).where(Niche.id == niche_id))
    if niche_exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Niche {niche_id} not found")

    count_result = await db.execute(
        select(func.count(Supplier.id)).where(Supplier.niche_id == niche_id)
    )
    total: int = count_result.scalar_one()

    result = await db.execute(
        select(Supplier)
        .where(Supplier.niche_id == niche_id)
        .options(selectinload(Supplier.landed_cost_calculations))
        .order_by(Supplier.supplier_score.desc().nullslast())
    )
    suppliers = result.scalars().unique().all()

    return SupplierListResponse(
        items=[SupplierResponse.model_validate(s) for s in suppliers],
        total=total,
    )


# ---------------------------------------------------------------------------
# POST /niches/{niche_id}/keywords/research — Trigger keyword research
# ---------------------------------------------------------------------------


@router.post("/{niche_id}/keywords/research", response_model=KeywordResearchSummary)
async def trigger_keyword_research(
    niche_id: int,
    db: AsyncSession = Depends(get_db),
) -> KeywordResearchSummary:
    """Trigger keyword research for a niche using autocomplete + SERP analysis."""
    result = await db.execute(select(Niche).where(Niche.id == niche_id))
    niche = result.scalar_one_or_none()
    if niche is None:
        raise HTTPException(status_code=404, detail=f"Niche {niche_id} not found")

    from app.services.keyword_research import KeywordResearchService

    marketplace = niche.marketplace or "US"
    research_svc = KeywordResearchService(db, marketplace=marketplace)
    summary = await research_svc.research_keywords(
        niche_id=niche_id,
        seed_keyword=niche.primary_keyword,
    )
    await db.commit()
    return KeywordResearchSummary(**summary)


# ---------------------------------------------------------------------------
# GET /niches/{niche_id}/velocity — Niche-level sales velocity
# ---------------------------------------------------------------------------


@router.get("/{niche_id}/velocity")
async def get_niche_velocity(
    niche_id: int,
    days: int = Query(7, ge=1, le=90, description="Days to aggregate over"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return niche-level aggregated sales velocity data."""
    niche_result = await db.execute(select(Niche).where(Niche.id == niche_id))
    niche = niche_result.scalar_one_or_none()
    if niche is None:
        raise HTTPException(status_code=404, detail=f"Niche {niche_id} not found")

    from app.services.sales_velocity_service import SalesVelocityService

    velocity_svc = SalesVelocityService(db)
    category = niche.primary_keyword
    result = await velocity_svc.compute_niche_velocity(
        niche_id=niche_id,
        category=category,
        days=days,
    )
    return result
