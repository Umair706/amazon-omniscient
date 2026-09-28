"""MCP tools: what an LLM agent can call on Omniscient.

Read tools and action tools go through the REST API (so they match the app
exactly). Compute tools import the core modules directly (no running API
needed). Long-running work returns a job_id the agent polls via job_status.
"""

from __future__ import annotations

from app.mcp import mcp
from app.mcp import _client as api


def _as_job(res: dict) -> dict:
    """Wrap a dispatch response with explicit next-step polling guidance."""
    if "error" in res:
        return res
    job_id = res.get("job_id")
    return {
        "job_id": job_id,
        "status": res.get("status", "pending"),
        "next": (
            f"Call job_status('{job_id}') every few seconds until status is 'completed' "
            "(or 'failed'), then read `result`. It can take several minutes when AI steps "
            "run on a local model — keep polling."
        ),
    }


# ---- Read: niches ---------------------------------------------------------

@mcp.tool()
async def get_license() -> dict:
    """The installed license: tier (free/pro/agency), granted features, validity,
    and expiry. Omniscient is open-core — some features (export, blueprint,
    financial_report, multi_marketplace, api, white_label) require a paid license.
    A 402 error from another tool means that feature is locked; tell the user."""
    return await api.get("/license")


@mcp.tool()
async def list_niches() -> dict:
    """List analysed niches with Omniscient Score, tier, and marketplace."""
    return await api.get("/niches/")


@mcp.tool()
async def get_niche(niche_id: int) -> dict:
    """Full detail for one niche: scores, sub-scores, and market snapshot."""
    return await api.get(f"/niches/{niche_id}")


@mcp.tool()
async def get_niche_products(niche_id: int) -> dict:
    """The scraped products in a niche (ASIN, price, BSR, rating, reviews, est. sales)."""
    return await api.get(f"/niches/{niche_id}/products")


@mcp.tool()
async def get_niche_competitors(niche_id: int) -> dict:
    """Competitor analysis for a niche: listing-quality scores and vulnerabilities."""
    return await api.get(f"/niches/{niche_id}/competitors")


@mcp.tool()
async def get_niche_suppliers(niche_id: int) -> dict:
    """Suppliers found for a niche (factory price, MOQ, ratings). May be empty
    when 1688 was unreachable — treat that as a data gap, not zero suppliers."""
    return await api.get(f"/niches/{niche_id}/suppliers")


@mcp.tool()
async def get_niche_financials(niche_id: int) -> dict:
    """52-week bull/base/bear projections (units, revenue, profit, cumulative)."""
    return await api.get(f"/niches/{niche_id}/financials")


@mcp.tool()
async def get_product(asin: str) -> dict:
    """Product detail by ASIN: price, BSR, fees, estimated units, marketplace."""
    return await api.get(f"/products/{asin}")


# ---- Read: recommendations ------------------------------------------------

@mcp.tool()
async def list_recommendations() -> dict:
    """List opportunity briefs (recommendations), ranked by score."""
    return await api.get("/recommendations/")


@mcp.tool()
async def get_recommendation(recommendation_id: int) -> dict:
    """The full opportunity brief: score, financials, suppliers, PPC, blueprint,
    risk flags/data gaps, and the exact scoring rules it was scored under."""
    return await api.get(f"/recommendations/{recommendation_id}")


# ---- Action: dispatch a job, then poll job_status -------------------------

@mcp.tool()
async def discover_opportunities(seed: str, marketplace: str = "AU") -> dict:
    """Rank candidate niches from a broad seed. Returns a job_id + how to poll;
    when complete, result.candidates holds the ranked niches."""
    return _as_job(await api.post("/jobs/discover-opportunities", {"seed": seed, "marketplace": marketplace}))


@mcp.tool()
async def analyze_keyword(keyword: str, marketplace: str = "AU") -> dict:
    """Start a full analysis for a keyword (scrape -> score -> recommendation).
    Returns a job_id + how to poll; when complete, use get_recommendation."""
    return _as_job(await api.post("/jobs/analyze", {"keyword": keyword, "marketplace": marketplace}))


@mcp.tool()
async def reanalyze_niche(niche_id: int) -> dict:
    """Re-run a niche WITHOUT re-scraping (regenerate AI, suppliers, financials,
    score). Returns a job_id + how to poll."""
    return _as_job(await api.post("/jobs/reanalyze-niche", {"niche_id": niche_id}))


@mcp.tool()
async def job_status(job_id: str) -> dict:
    """Poll a background job: status, progress, and result when complete."""
    return await api.get(f"/jobs/{job_id}/status")


# ---- Compute: pure functions, no running API needed -----------------------

@mcp.tool()
def estimate_monthly_sales(bsr: int, category: str = "default", marketplace: str = "US") -> dict:
    """Estimate monthly unit sales from BSR via the category power-law model.
    AU is uncalibrated (rough); US is calibrated."""
    from app.core.bsr_regression import BSRSalesEstimator, is_calibrated_marketplace

    units = BSRSalesEstimator(marketplace).estimate_monthly_sales(int(bsr), category)
    return {
        "bsr": bsr, "category": category, "marketplace": marketplace,
        "estimated_monthly_units": units,
        "calibrated": is_calibrated_marketplace(marketplace),
    }


@mcp.tool()
async def save_plan(title: str, content: str, niche_id: int | None = None, kind: str = "plan") -> dict:
    """Save the agent's own output (a business plan, note, or watchlist) into
    Omniscient so it persists across sessions. kind is 'plan', 'note', or
    'watchlist'. Optionally link it to a niche. Returns the saved artifact."""
    body: dict = {"title": title, "content": content, "kind": kind}
    if niche_id is not None:
        body["niche_id"] = niche_id
    return await api.post("/artifacts/", body)


@mcp.tool()
async def list_plans(niche_id: int | None = None, kind: str | None = None) -> dict:
    """List saved artifacts (newest first), optionally filtered by niche or kind."""
    params: dict = {}
    if niche_id is not None:
        params["niche_id"] = niche_id
    if kind is not None:
        params["kind"] = kind
    return await api.get("/artifacts/", params or None)


@mcp.tool()
async def get_plan(artifact_id: int) -> dict:
    """Read one saved artifact by id."""
    return await api.get(f"/artifacts/{artifact_id}")


@mcp.tool()
def landed_cost_and_margin(
    unit_cost_usd: float,
    selling_price: float,
    weight_kg: float = 0.5,
    category: str = "default",
    marketplace: str = "US",
) -> dict:
    """Model the unit economics: convert a USD factory cost to a landed cost in
    the marketplace currency, then compute pre/post-PPC margin against the sale
    price. Mirrors the pipeline's own calculation."""
    from dataclasses import replace

    from app.core.currency import convert_from_usd, is_converted_marketplace
    from app.services.supplier_service import SupplierService

    svc = SupplierService(marketplace=marketplace)
    landed_usd = svc.calculate_landed_cost(unit_cost=unit_cost_usd, quantity=500, weight_kg=weight_kg, category=category)
    landed_mp = convert_from_usd(landed_usd.total_cost_to_amazon, marketplace)
    margin = svc.calculate_margins(selling_price=selling_price, landed_cost=replace(landed_usd, total_cost_to_amazon=landed_mp))
    return {
        "marketplace": marketplace,
        "landed_cost_in_marketplace_currency": round(landed_mp, 2),
        "pre_ppc_margin_pct": margin["pre_ppc_margin_pct"],
        "post_ppc_margin_pct": margin["post_ppc_margin_pct"],
        "fx_rate_assumed": is_converted_marketplace(marketplace),
    }
