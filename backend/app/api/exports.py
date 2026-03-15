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
# GET /exports/recommendations/{recommendation_id}/pdf — Export as HTML report
# ---------------------------------------------------------------------------


def _fmt(value: object, prefix: str = "", suffix: str = "", default: str = "N/A") -> str:
    """Format a value for display, returning *default* when None."""
    if value is None:
        return default
    return f"{prefix}{value}{suffix}"


def _fmt_currency(value: object, default: str = "N/A") -> str:
    """Format a numeric value as USD currency."""
    if value is None:
        return default
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return default


def _fmt_pct(value: object, default: str = "N/A") -> str:
    """Format a numeric value as a percentage."""
    if value is None:
        return default
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return default


def _fmt_int(value: object, default: str = "N/A") -> str:
    """Format a numeric value as a comma-separated integer."""
    if value is None:
        return default
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return default


def _score_color(score: float) -> str:
    """Return a hex colour based on score thresholds."""
    if score > 70:
        return "#27ae60"
    if score >= 40:
        return "#f39c12"
    return "#e74c3c"


def _build_table_rows(rows: list[tuple[str, str]], zebra: bool = True) -> str:
    """Build HTML table rows with optional alternating background."""
    html_parts: list[str] = []
    for idx, (label, value) in enumerate(rows):
        bg = ' style="background:#f8f9fa;"' if zebra and idx % 2 == 0 else ""
        html_parts.append(
            f"<tr{bg}>"
            f'<td style="padding:10px 14px;font-weight:600;color:#555;'
            f'border-bottom:1px solid #eee;width:45%;">{label}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #eee;">{value}</td>'
            f"</tr>"
        )
    return "\n".join(html_parts)


def _section(title: str, content: str) -> str:
    """Wrap *content* in a styled report section with a heading."""
    return (
        f'<div style="margin-bottom:28px;">'
        f'<h2 style="font-size:18px;color:#2c3e50;border-bottom:2px solid #3498db;'
        f'padding-bottom:6px;margin-bottom:14px;">{title}</h2>'
        f"{content}"
        f"</div>"
    )


def _render_risk_flags(risk_flags: dict | list | None) -> str:
    """Render risk flags as an HTML list."""
    if not risk_flags:
        return '<p style="color:#888;">No risk flags recorded.</p>'

    items: list[str] = []
    # Handle both list-of-strings and dict formats
    if isinstance(risk_flags, list):
        for flag in risk_flags:
            if isinstance(flag, str):
                items.append(flag)
            elif isinstance(flag, dict):
                items.append(flag.get("reason", flag.get("description", str(flag))))
    elif isinstance(risk_flags, dict):
        for key, val in risk_flags.items():
            if isinstance(val, list):
                for v in val:
                    items.append(f"{key}: {v}")
            else:
                items.append(f"{key}: {val}")

    if not items:
        return '<p style="color:#888;">No risk flags recorded.</p>'

    li_html = "\n".join(
        f'<li style="padding:6px 0;border-bottom:1px solid #f0f0f0;">'
        f'<span style="color:#e74c3c;font-weight:600;">&#9888;</span> {item}</li>'
        for item in items
    )
    return f'<ul style="list-style:none;padding:0;margin:0;">{li_html}</ul>'


def _render_json_summary(data: dict | None, keys: list[str] | None = None) -> str:
    """Render selected keys from a JSONB dict as a table. If *keys* is None,
    render all top-level keys."""
    if not data or not isinstance(data, dict):
        return '<p style="color:#888;">No data available.</p>'

    target_keys = keys if keys else list(data.keys())
    rows: list[tuple[str, str]] = []
    for k in target_keys:
        val = data.get(k)
        if val is None:
            continue
        label = k.replace("_", " ").title()
        if isinstance(val, (dict, list)):
            # Render nested structures as a compact summary
            if isinstance(val, list):
                display = ", ".join(str(v) for v in val[:10])
                if len(val) > 10:
                    display += f" ... (+{len(val) - 10} more)"
            else:
                display = "; ".join(f"{sk}: {sv}" for sk, sv in list(val.items())[:8])
            rows.append((label, display))
        else:
            rows.append((label, str(val)))

    if not rows:
        return '<p style="color:#888;">No data available.</p>'

    return (
        f'<table style="width:100%;border-collapse:collapse;'
        f'font-size:14px;">{_build_table_rows(rows)}</table>'
    )


def _generate_report_html(rec: "Recommendation", niche: "Niche") -> str:
    """Generate a complete, self-contained HTML report document."""

    score = float(rec.omniscient_score)
    score_clr = _score_color(score)
    generated_date = (
        rec.generated_at.strftime("%B %d, %Y at %H:%M UTC")
        if rec.generated_at
        else datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
    )

    # ── Verdict from product_blueprint ──────────────────────────────────
    verdict = ""
    if rec.product_blueprint and isinstance(rec.product_blueprint, dict):
        verdict = rec.product_blueprint.get(
            "verdict",
            rec.product_blueprint.get("summary", ""),
        )

    # ── Build sections ──────────────────────────────────────────────────

    # 1. Executive Summary
    exec_rows = [
        ("Omniscient Score", f'<span style="color:{score_clr};font-weight:700;'
         f'font-size:20px;">{score:.1f}</span> / 100'),
        ("Confidence Tier", f'<span style="font-weight:700;">'
         f'{rec.confidence_tier.upper()}</span>'),
    ]
    if verdict:
        exec_rows.append(("Verdict", verdict))
    if rec.product_description:
        exec_rows.append(("Product Description", rec.product_description))
    if rec.differentiation_features:
        features = ", ".join(rec.differentiation_features)
        exec_rows.append(("Differentiation Features", features))
    exec_section = _section(
        "Executive Summary",
        f'<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f"{_build_table_rows(exec_rows)}</table>",
    )

    # 2. Market Overview
    market_rows = [
        ("Niche Name", niche.name),
        ("Primary Keyword", niche.primary_keyword),
        ("Average BSR", _fmt_int(niche.avg_bsr)),
        ("Average Sale Price", _fmt_currency(niche.avg_sale_price)),
        ("Average Review Count", _fmt_int(niche.avg_review_count)),
        ("Monthly Search Volume", _fmt_int(niche.monthly_search_volume)),
        ("Opportunity Score", _fmt(niche.opportunity_score, suffix="/100")),
    ]
    market_section = _section(
        "Market Overview",
        f'<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f"{_build_table_rows(market_rows)}</table>",
    )

    # 3. Unit Economics
    econ_rows = [
        ("Best Landed Cost", _fmt_currency(rec.best_landed_cost)),
        ("Recommended Sale Price", _fmt_currency(rec.recommended_sale_price)),
        ("Estimated Net Margin", _fmt_pct(rec.estimated_net_margin_pct)),
    ]
    econ_section = _section(
        "Unit Economics",
        f'<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f"{_build_table_rows(econ_rows)}</table>",
    )

    # 4. Financial Projections
    fin_rows = [
        ("Break-Even Week (Bull)", _fmt(rec.break_even_week_bull, suffix=" weeks")),
        ("Break-Even Week (Base)", _fmt(rec.break_even_week_base, suffix=" weeks")),
        ("Break-Even Week (Bear)", _fmt(rec.break_even_week_bear, suffix=" weeks")),
        ("Total Launch Capital", _fmt_currency(rec.total_launch_capital)),
    ]
    fin_section = _section(
        "Financial Projections",
        f'<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f"{_build_table_rows(fin_rows)}</table>",
    )

    # 5. PPC Strategy
    ppc_rows = [
        ("PPC Budget (30 days)", _fmt_currency(rec.ppc_budget_30d)),
        ("PPC Budget (90 days)", _fmt_currency(rec.ppc_budget_90d)),
        ("Break-Even ACOS", _fmt_pct(rec.break_even_acos)),
        ("Estimated ACOS", _fmt_pct(rec.estimated_acos)),
    ]
    ppc_section = _section(
        "PPC Strategy",
        f'<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f"{_build_table_rows(ppc_rows)}</table>",
    )

    # 6. Review Strategy
    rev_rows = [
        ("Review Threshold", _fmt_int(rec.review_threshold)),
        ("Weeks to Threshold", _fmt(rec.weeks_to_review_threshold, suffix=" weeks")),
        ("Vine Recommended", "Yes" if rec.vine_recommended else
         ("No" if rec.vine_recommended is False else "N/A")),
        ("Vine Cost", _fmt_currency(rec.vine_cost)),
    ]
    rev_section = _section(
        "Review Strategy",
        f'<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f"{_build_table_rows(rev_rows)}</table>",
    )

    # 7. Risk Flags
    risk_section = _section("Risk Flags", _render_risk_flags(rec.risk_flags))

    # 8. Product Blueprint Summary
    blueprint_section = _section(
        "Product Blueprint Summary",
        _render_json_summary(rec.product_blueprint),
    )

    # 9. Financial Report Summary
    finreport_section = _section(
        "Financial Report Summary",
        _render_json_summary(rec.financial_report),
    )

    # ── Assemble full HTML document ─────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Omniscient Report — {niche.name}</title>
<style>
  @media print {{
    body {{ margin: 0; }}
    .no-print {{ display: none; }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    color: #333;
    background: #fff;
    line-height: 1.6;
  }}
  .header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    color: #fff;
    padding: 40px 48px;
    margin-bottom: 32px;
  }}
  .header h1 {{
    font-size: 28px;
    letter-spacing: 1px;
    margin-bottom: 4px;
  }}
  .header .subtitle {{
    font-size: 16px;
    opacity: 0.85;
    margin-bottom: 16px;
  }}
  .header .meta {{
    font-size: 13px;
    opacity: 0.7;
  }}
  .score-badge {{
    display: inline-block;
    background: {score_clr};
    color: #fff;
    font-size: 32px;
    font-weight: 700;
    padding: 12px 24px;
    border-radius: 8px;
    margin-top: 12px;
  }}
  .container {{
    max-width: 900px;
    margin: 0 auto;
    padding: 0 32px 48px;
  }}
  .print-note {{
    background: #eef6ff;
    border: 1px solid #b3d4fc;
    border-radius: 6px;
    padding: 12px 16px;
    font-size: 13px;
    color: #31587a;
    margin-bottom: 28px;
  }}
  table {{ border-radius: 6px; overflow: hidden; }}
  ul {{ margin: 0; }}
</style>
</head>
<body>
<div class="header">
  <h1>Omniscient Report</h1>
  <div class="subtitle">{niche.name}</div>
  <div class="meta">Generated on {generated_date} &middot; Recommendation #{rec.id}</div>
  <div class="score-badge">{score:.1f}</div>
</div>
<div class="container">
  <div class="print-note no-print">
    <strong>Tip:</strong> Press <kbd>Ctrl+P</kbd> (or <kbd>Cmd+P</kbd> on Mac) to save
    this report as a PDF.
  </div>
  {exec_section}
  {market_section}
  {econ_section}
  {fin_section}
  {ppc_section}
  {rev_section}
  {risk_section}
  {blueprint_section}
  {finreport_section}
  <div style="text-align:center;color:#aaa;font-size:12px;margin-top:40px;
              border-top:1px solid #eee;padding-top:16px;">
    Omniscient &mdash; Amazon Product Research Engine &middot; Confidential
  </div>
</div>
</body>
</html>"""
    return html


@router.get("/recommendations/{recommendation_id}/pdf")
async def export_recommendation_pdf(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export a recommendation report as a downloadable HTML document.

    Generates a self-contained, print-friendly HTML report with inline CSS
    that can be opened in any browser and printed/saved as PDF via Ctrl+P.
    """
    # Fetch recommendation
    result = await db.execute(
        select(Recommendation).where(Recommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=f"Recommendation {recommendation_id} not found",
        )

    # Fetch associated niche
    niche_result = await db.execute(
        select(Niche).where(Niche.id == rec.niche_id)
    )
    niche = niche_result.scalar_one_or_none()
    if niche is None:
        raise HTTPException(
            status_code=404,
            detail=f"Niche {rec.niche_id} not found for recommendation {recommendation_id}",
        )

    html_content = _generate_report_html(rec, niche)

    safe_name = niche.primary_keyword.replace(" ", "_").lower()
    filename = f"omniscient_report_{rec.id}_{safe_name}_{datetime.utcnow():%Y%m%d}.html"

    return StreamingResponse(
        iter([html_content]),
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
