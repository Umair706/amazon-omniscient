"""Niche discovery: turn a broad seed into ranked candidate niches to analyse.

This is the front door a seller needs — instead of guessing a keyword, they enter a
broad seed ("kitchen") and get candidate niches ranked by a cheap opportunity pre-score.
It reuses the autocomplete expansion and SERP-metadata scraping the pipeline already has;
the pre-score is a quick pre-screen (demand vs. ease of entry), NOT the full Omniscient
Score — a good candidate still gets a full analysis before any decision.
"""

import logging

from app.services.keyword_research import KeywordResearchService

logger = logging.getLogger(__name__)

# How much of the score is "is there demand" vs "can a newcomer get in". Even split:
# a crowded high-demand niche and a dead easy no-demand one are both poor for a new seller.
DEMAND_WEIGHT = 0.5
EASE_WEIGHT = 0.5

# Demand points per SERP volume tier (from estimate_volume_from_serp).
_DEMAND_BY_TIER = {"very_high": 85, "high": 72, "medium": 55, "low": 35, "very_low": 15}

# A candidate needs at least this many results to be a real market, not a typo/dead term.
MIN_VIABLE_RESULTS = 100
# Above this, the shelf is saturated and a newcomer is fighting an entrenched crowd.
SATURATED_RESULTS = 20000


def _ease_of_entry(total_results: int, sponsored_count: int, brand_count: int) -> int:
    """0-100: how open a niche looks to a new seller. Fewer listings, brands and ads = easier."""
    if total_results < MIN_VIABLE_RESULTS:
        base = 30  # thin — easy to rank but likely little demand
    elif total_results < 2000:
        base = 85
    elif total_results < 8000:
        base = 65
    elif total_results < SATURATED_RESULTS:
        base = 45
    else:
        base = 20
    # Dominant brands and heavy sponsoring make entry harder.
    base -= min(20, brand_count)
    base -= min(15, sponsored_count * 2)
    return max(0, min(100, base))


def opportunity_prescore(
    *, volume_tier: str, total_results: int, sponsored_count: int, brand_count: int
) -> dict:
    """Quick 0-100 opportunity pre-score with a label and a one-line reason."""
    demand = _DEMAND_BY_TIER.get(volume_tier, 30)
    ease = _ease_of_entry(total_results, sponsored_count, brand_count)
    score = round(DEMAND_WEIGHT * demand + EASE_WEIGHT * ease)

    if score >= 65:
        label, reason = "Promising", "Healthy demand with room for a new entrant."
    elif score >= 45:
        label, reason = "Worth a look", "Mixed — some demand, some competition."
    elif total_results < MIN_VIABLE_RESULTS:
        label, reason = "Too thin", "Very few listings — likely not enough demand."
    else:
        label, reason = "Crowded", "Demand exists but the shelf is saturated or brand-dominated."
    return {"score": score, "label": label, "reason": reason}


class DiscoveryService:
    """Expands a seed into candidate niches and ranks them by opportunity pre-score."""

    def __init__(self, scraper):
        self.scraper = scraper

    async def discover(self, seed: str, max_candidates: int = 15) -> list[dict]:
        """Return candidate niches for `seed`, best opportunity first."""
        candidates = await KeywordResearchService(
            session=None, scraper=self.scraper
        ).discover_keywords_autocomplete(seed, max_variations=max_candidates * 3)
        picked = self._pick_candidates(seed, candidates, max_candidates)
        # Sequential on purpose: the shared pacer serialises requests to Amazon anyway, and
        # this avoids opening a dozen browser tabs at once.
        results = []
        for keyword in picked:
            scored = await self._score_candidate(keyword)
            if scored is not None:
                results.append(scored)
        results.sort(key=lambda r: r["opportunity_score"], reverse=True)
        return results

    @staticmethod
    def _pick_candidates(seed: str, candidates: list[dict], limit: int) -> list[str]:
        """Keep the most niche-like autocomplete suggestions: multi-word, not the bare seed."""
        keywords: list[str] = []
        for candidate in candidates:
            keyword = candidate["keyword"].strip()
            # A useful niche term is more specific than the seed itself.
            if keyword.lower() == seed.strip().lower() or len(keyword.split()) < 2:
                continue
            keywords.append(keyword)
            if len(keywords) >= limit:
                break
        return keywords

    async def _score_candidate(self, keyword: str) -> dict | None:
        """Scrape one candidate's SERP metadata and pre-score it. None if the scrape failed."""
        try:
            meta = await self.scraper.scrape_serp_metadata(keyword)
        except Exception as e:
            logger.warning("Discovery: SERP metadata failed for '%s': %s", keyword, e)
            return None
        volume = KeywordResearchService.estimate_volume_from_serp(meta)
        prescore = opportunity_prescore(
            volume_tier=volume["tier"],
            total_results=meta.get("total_result_count", 0),
            sponsored_count=meta.get("sponsored_count", 0),
            brand_count=meta.get("brand_count", 0),
        )
        return {
            "keyword": keyword,
            "opportunity_score": prescore["score"],
            "label": prescore["label"],
            "reason": prescore["reason"],
            "volume_tier": volume["tier"],
            "volume_estimate": volume["volume_estimate"],
            "total_results": meta.get("total_result_count", 0),
            "sponsored_count": meta.get("sponsored_count", 0),
            "brand_count": meta.get("brand_count", 0),
        }
