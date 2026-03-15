"""API routes for data export (CSV, PDF)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db
from app.models.competitor import Competitor
from app.models.financial_projection import FinancialProjection
from app.models.keyword import NicheKeyword
from app.models.niche import Niche
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.review import ReviewPainPoint
from app.models.supplier import Supplier

router = APIRouter(prefix="/exports", tags=["exports"])


# ---------------------------------------------------------------------------
# GET /exports/niches/{niche_id}/csv — Export niche data as CSV
# ---------------------------------------------------------------------------


@router.get("/niches/{niche_id}/csv")
async def export_niche_csv(
    niche_id: int,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export a comprehensive CSV of niche data including products, keywords,
    competitors, suppliers, and pain points.

    Returns a streaming CSV file download.
    """
    # Verify niche exists
    niche_result = await db.execute(select(Niche).where(Niche.id == niche_id))
    niche = niche_result.scalar_one_or_none()
    if niche is None:
        raise HTTPException(status_code=404, detail=f"Niche {niche_id} not found")

    output = io.StringIO()
    writer = csv.writer(output)

    # ── Section 1: Niche overview ────────────────────────────────────────
    writer.writerow(["=== NICHE OVERVIEW ==="])
    writer.writerow([
        "ID", "Name", "Primary Keyword", "Category", "Monthly Search Volume",
        "Avg Sale Price", "Avg Review Count", "Avg BSR", "Opportunity Score",
        "Confidence Tier", "Is Seasonal", "Hard Filter Passed", "Created At",
    ])
    writer.writerow([
        niche.id, niche.name, niche.primary_keyword, niche.category_id,
        niche.monthly_search_volume, niche.avg_sale_price, niche.avg_review_count,
        niche.avg_bsr, niche.opportunity_score, niche.confidence_tier,
        niche.is_seasonal, niche.hard_filter_passed, niche.created_at,
    ])
    writer.writerow([])

    # ── Section 2: Products ──────────────────────────────────────────────
    products_result = await db.execute(
        select(Product)
        .where(Product.niche_id == niche_id)
        .order_by(Product.estimated_monthly_revenue.desc().nullslast())
    )
    products = products_result.scalars().all()

    writer.writerow(["=== PRODUCTS ==="])
    writer.writerow([
        "ASIN", "Title", "Brand", "Price", "BSR", "Review Count", "Rating",
        "Est Monthly Revenue", "Est Monthly Units", "Listing Quality Score",
        "Is FBA", "Has A+", "Has Video",
    ])
    for p in products:
        writer.writerow([
            p.asin, p.title, p.brand, p.current_price, p.current_bsr,
            p.review_count, p.rating, p.estimated_monthly_revenue,
            p.estimated_monthly_units, p.listing_quality_score,
            p.is_fba, p.has_a_plus, p.has_video,
        ])
    writer.writerow([])

    # ── Section 3: Keywords ──────────────────────────────────────────────
    keywords_result = await db.execute(
        select(NicheKeyword)
        .where(NicheKeyword.niche_id == niche_id)
        .order_by(NicheKeyword.search_volume.desc().nullslast())
    )
    keywords = keywords_result.scalars().all()

    writer.writerow(["=== KEYWORDS ==="])
    writer.writerow([
        "Keyword", "Search Volume", "Trend", "Avg CPC", "Competition Level",
        "Organic Results", "Sponsored Results", "Relevance Score",
    ])
    for k in keywords:
        writer.writerow([
            k.keyword, k.search_volume, k.search_volume_trend, k.avg_cpc,
            k.competition_level, k.organic_result_count, k.sponsored_result_count,
            k.relevance_score,
        ])
    writer.writerow([])

    # ── Section 4: Competitors ───────────────────────────────────────────
    competitors_result = await db.execute(
        select(Competitor)
        .where(Competitor.niche_id == niche_id)
        .order_by(Competitor.organic_rank.asc().nullslast())
    )
    competitors = competitors_result.scalars().all()

    writer.writerow(["=== COMPETITORS ==="])
    writer.writerow([
        "Product ID", "Organic Rank", "Sponsored Rank", "Listing Quality Score",
        "Price 90d Avg", "Review Velocity", "Sentiment Score",
        "Vulnerability", "Vulnerability Type",
    ])
    for c in competitors:
        writer.writerow([
            c.product_id, c.organic_rank, c.sponsored_rank,
            c.listing_quality_score, c.price_90d_avg, c.review_velocity,
            c.sentiment_score, c.vulnerability, c.vulnerability_type,
        ])
    writer.writerow([])

    # ── Section 5: Suppliers ─────────────────────────────────────────────
    suppliers_result = await db.execute(
        select(Supplier)
        .where(Supplier.niche_id == niche_id)
        .order_by(Supplier.supplier_score.desc().nullslast())
    )
    suppliers = suppliers_result.scalars().all()

    writer.writerow(["=== SUPPLIERS ==="])
    writer.writerow([
        "Supplier Name", "Country", "City", "Years in Business",
        "Gold Supplier", "Verified", "MOQ", "FOB Min", "FOB Max",
        "Lead Time (days)", "Supplier Score",
    ])
    for s in suppliers:
        writer.writerow([
            s.supplier_name, s.country, s.city, s.years_in_business,
            s.is_gold_supplier, s.is_verified, s.moq, s.fob_price_min,
            s.fob_price_max, s.lead_time_days, s.supplier_score,
        ])
    writer.writerow([])

    # ── Section 6: Pain Points ───────────────────────────────────────────
    pain_points_result = await db.execute(
        select(ReviewPainPoint)
        .where(ReviewPainPoint.niche_id == niche_id)
        .order_by(ReviewPainPoint.mention_count.desc().nullslast())
    )
    pain_points = pain_points_result.scalars().all()

    writer.writerow(["=== REVIEW PAIN POINTS ==="])
    writer.writerow([
        "Cluster Name", "Description", "Mention Count", "Mention %",
        "Severity", "Suggested Fix",
    ])
    for pp in pain_points:
        writer.writerow([
            pp.cluster_name, pp.description, pp.mention_count,
            pp.mention_pct, pp.severity, pp.suggested_fix,
        ])

    # Build streaming response
    output.seek(0)
    safe_name = niche.primary_keyword.replace(" ", "_").lower()
    filename = f"niche_{niche.id}_{safe_name}_{datetime.utcnow():%Y%m%d}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# GET /exports/recommendations/{recommendation_id}/pdf — Export as PDF
# ---------------------------------------------------------------------------


@router.get("/recommendations/{recommendation_id}/pdf")
async def export_recommendation_pdf(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Export a recommendation report as PDF.

    This is a placeholder endpoint. In production this would generate a
    full PDF report using a library like WeasyPrint or ReportLab. For now
    it returns the recommendation data as JSON with instructions.
    """
    result = await db.execute(
        select(Recommendation).where(Recommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=f"Recommendation {recommendation_id} not found",
        )

    # In production, generate a PDF here.  For now return a structured
    # placeholder so callers know the endpoint exists and what data it covers.
    return {
        "status": "placeholder",
        "message": (
            "PDF generation is not yet implemented. "
            "This endpoint will produce a full recommendation report."
        ),
        "recommendation_id": rec.id,
        "niche_id": rec.niche_id,
        "omniscient_score": float(rec.omniscient_score),
        "confidence_tier": rec.confidence_tier,
        "generated_at": rec.generated_at.isoformat() if rec.generated_at else None,
    }
