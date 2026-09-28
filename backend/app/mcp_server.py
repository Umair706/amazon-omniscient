"""Omniscient MCP server — expose the research engine as tools an LLM can drive.

This inverts the usual flow: instead of Omniscient calling an LLM for sub-steps,
an LLM agent (Claude Desktop, etc.) connects here over MCP and uses Omniscient
as a toolbox — discovering niches, running analyses, reading scored briefs, and
computing sales/margins — then writes the strategy and business plan itself.

Why this helps an LLM's limits: the heavy data lives in Omniscient's database,
so the agent queries a tool when it needs a fact instead of holding everything
in its context. Long-running work (discovery, analysis) returns a job id the
agent polls, so a tool call never blocks.

Run it (stdio) once the stack is up:

    cd backend
    OMNISCIENT_API_URL=http://localhost:8000 python -m app.mcp_server

Point an MCP client at that command. See docs/MCP.md for the client config.
"""

from __future__ import annotations

import os

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get("OMNISCIENT_API_URL", "http://localhost:8000").rstrip("/")
API = f"{API_BASE}/api/v1"
_TIMEOUT = httpx.Timeout(30.0)

mcp = FastMCP("omniscient")


async def _get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{API}{path}", params=params)
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{API}{path}", json=body)
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Read tools — fast, backed by the REST API
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_niches() -> dict:
    """List analysed niches with their Omniscient Score, tier, and marketplace."""
    return await _get("/niches/")


@mcp.tool()
async def get_niche(niche_id: int) -> dict:
    """Full detail for one niche: scores, sub-scores, and market snapshot."""
    return await _get(f"/niches/{niche_id}")


@mcp.tool()
async def list_recommendations() -> dict:
    """List opportunity briefs (recommendations), ranked by score."""
    return await _get("/recommendations/")


@mcp.tool()
async def get_recommendation(recommendation_id: int) -> dict:
    """The full opportunity brief: score, financials, suppliers, PPC, blueprint,
    risk flags/data gaps, and the exact scoring rules it was scored under."""
    return await _get(f"/recommendations/{recommendation_id}")


# ---------------------------------------------------------------------------
# Action tools — dispatch a background job, then poll job_status
# ---------------------------------------------------------------------------

@mcp.tool()
async def discover_opportunities(seed: str, marketplace: str = "AU") -> dict:
    """Rank candidate niches from a broad seed keyword. Returns a job_id; poll
    job_status until completed, then read result.candidates."""
    return await _post("/jobs/discover-opportunities", {"seed": seed, "marketplace": marketplace})


@mcp.tool()
async def analyze_keyword(keyword: str, marketplace: str = "AU") -> dict:
    """Start a full analysis for a keyword (scrape -> score -> recommendation).
    Returns a job_id; poll job_status. Slow if AI steps run on a local model."""
    return await _post("/jobs/analyze", {"keyword": keyword, "marketplace": marketplace})


@mcp.tool()
async def reanalyze_niche(niche_id: int) -> dict:
    """Re-run analysis on an existing niche WITHOUT re-scraping (regenerates AI,
    suppliers, financials, score). Returns a job_id; poll job_status."""
    return await _post("/jobs/reanalyze-niche", {"niche_id": niche_id})


@mcp.tool()
async def job_status(job_id: str) -> dict:
    """Poll a background job: status (pending/running/completed/failed), progress, result."""
    return await _get(f"/jobs/{job_id}/status")


# ---------------------------------------------------------------------------
# Compute tools — pure functions, no running API needed
# ---------------------------------------------------------------------------

@mcp.tool()
def estimate_monthly_sales(bsr: int, category: str = "default", marketplace: str = "US") -> dict:
    """Estimate a listing's monthly unit sales from its BSR using the category
    power-law model. AU is uncalibrated (rough), US is calibrated."""
    from app.core.bsr_regression import BSRSalesEstimator, is_calibrated_marketplace

    units = BSRSalesEstimator(marketplace).estimate_monthly_sales(int(bsr), category)
    return {
        "bsr": bsr,
        "category": category,
        "marketplace": marketplace,
        "estimated_monthly_units": units,
        "calibrated": is_calibrated_marketplace(marketplace),
    }


# ---------------------------------------------------------------------------
# Prompt — a guided workflow the agent can follow
# ---------------------------------------------------------------------------

@mcp.prompt()
def build_business_plan(idea: str, marketplace: str = "AU") -> str:
    """A workflow prompt: turn a rough idea into a sourced, costed business plan."""
    return (
        f"You are helping a seller build an Amazon FBA business around: '{idea}' "
        f"in the {marketplace} marketplace. Use the Omniscient tools, do not guess:\n"
        "1. discover_opportunities(seed, marketplace) to get candidate niches; poll job_status.\n"
        "2. Pick the most promising candidate and analyze_keyword(keyword, marketplace); poll job_status.\n"
        "3. get_recommendation for the resulting niche: read the score, hard filters, financials, "
        "suppliers, and data gaps. Respect FAIL verdicts and flagged assumptions.\n"
        "4. Write a plain, honest business plan: product thesis, unit economics and margin, "
        "sourcing plan, launch/PPC budget, review strategy, a week-by-week execution roadmap, and "
        "the key risks (especially any data gaps). Recommend go / no-go with the reasoning."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
