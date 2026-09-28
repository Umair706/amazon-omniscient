"""Keyword research service — autocomplete discovery + SERP volume estimation."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.scraper_service import ScraperService

logger = logging.getLogger(__name__)


class KeywordResearchService:
    """Orchestrates keyword discovery and search volume estimation."""

    def __init__(
        self,
        session: AsyncSession,
        scraper: ScraperService | None = None,
        marketplace: str = "US",
    ):
        self.session = session
        self.scraper = scraper or ScraperService(marketplace=marketplace)
        self.marketplace = marketplace

    # ------------------------------------------------------------------
    # 1. Autocomplete discovery
    # ------------------------------------------------------------------

    async def discover_keywords_autocomplete(
        self,
        seed_keyword: str,
        max_variations: int = 100,
    ) -> list[dict]:
        """Discover keywords using Amazon's autocomplete API.

        Queries the seed keyword directly, then appends each letter a-z
        to generate alphabet expansions.  Returns a deduplicated list
        of keyword dicts with autocomplete position metadata.
        """
        seen: set[str] = set()
        results: list[dict] = []

        # Expand from the seed AND its shorter word-prefixes. A long specific
        # phrase ("bean bags for adults") has no autocomplete children, but its
        # roots ("bean bags") have many — so a single seed still yields a real
        # keyword set. Candidates arrive in discovery order (the exact seed first);
        # autocomplete_depth is that rank, used later as a rough volume signal.
        for keyword in await self._autocomplete_candidates(seed_keyword):
            normalised = keyword.strip().lower()
            if not normalised or normalised in seen:
                continue
            seen.add(normalised)
            results.append({
                "keyword": keyword.strip(),
                "autocomplete_depth": len(results),
                "position": len(results),
            })
            if len(results) >= max_variations:
                break

        logger.info(
            "Autocomplete discovery for '%s': %d keywords found",
            seed_keyword, len(results),
        )
        return results

    @staticmethod
    def _seed_roots(seed_keyword: str, min_words: int = 2) -> list[str]:
        """The seed plus its shorter word-prefixes, longest first, down to
        `min_words` words. Autocomplete returns little for a long specific phrase
        but a lot for its shorter roots, so we harvest from both."""
        words = seed_keyword.split()
        if len(words) <= min_words:
            return [seed_keyword]
        return [" ".join(words[:n]) for n in range(len(words), min_words - 1, -1)]

    async def _autocomplete_candidates(self, seed_keyword: str) -> list[str]:
        """Every autocomplete suggestion for the seed and its roots, in order.
        For each root, queries the root itself plus the a-z letter expansions."""
        letters = "abcdefghijklmnopqrstuvwxyz"
        candidates: list[str] = []
        for root in self._seed_roots(seed_keyword):
            queries = [root] + [f"{root} {letter}" for letter in letters]
            responses = await asyncio.gather(
                *(self.scraper.fetch_autocomplete(query) for query in queries),
                return_exceptions=True,
            )
            for suggestions in responses:
                if not isinstance(suggestions, Exception):
                    candidates.extend(suggestions)
        return candidates

    # ------------------------------------------------------------------
    # 2. SERP-based volume estimation
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_volume_from_serp(serp_metadata: dict) -> dict:
        """Estimate search volume tier from SERP metadata.

        Uses total result count and sponsored density to place the
        keyword into a volume tier.
        """
        total = serp_metadata.get("total_result_count", 0)
        sponsored = serp_metadata.get("sponsored_count", 0)

        if total > 10000 and sponsored > 8:
            volume_estimate = 10000
            tier = "very_high"
        elif total > 3000 and sponsored > 5:
            volume_estimate = 7500
            tier = "high"
        elif total > 1000 and sponsored > 3:
            volume_estimate = 3000
            tier = "medium"
        elif total > 300:
            volume_estimate = 600
            tier = "low"
        else:
            volume_estimate = 200
            tier = "very_low"

        # Estimate CPC from sponsored density
        if sponsored >= 8:
            estimated_cpc = 2.50
        elif sponsored >= 5:
            estimated_cpc = 1.80
        elif sponsored >= 3:
            estimated_cpc = 1.20
        else:
            estimated_cpc = 0.80

        return {
            "volume_estimate": volume_estimate,
            "tier": tier,
            "estimated_cpc": estimated_cpc,
            "total_results": total,
            "sponsored_count": sponsored,
        }

    # ------------------------------------------------------------------
    # 3. Relevance scoring
    # ------------------------------------------------------------------

    @staticmethod
    def compute_relevance_score(
        keyword: str,
        seed_keyword: str,
        autocomplete_depth: int,
        volume_tier: str,
        sponsored_count: int,
    ) -> float:
        """Compute a relevance score (0-100) for a keyword.

        Scoring breakdown:
          - Word overlap with seed keyword: 0-30 pts
          - Autocomplete depth (lower = better): 0-20 pts
          - Estimated volume tier: 0-30 pts
          - Sponsored density / commercial intent: 0-20 pts
        """
        score = 0.0

        # Word overlap (0-30)
        seed_words = set(seed_keyword.lower().split())
        kw_words = set(keyword.lower().split())
        if seed_words:
            overlap = len(seed_words & kw_words) / len(seed_words)
            score += overlap * 30

        # Autocomplete depth (0-20): position 0 = 20pts, position 50+ = 2pts
        if autocomplete_depth <= 5:
            score += 20
        elif autocomplete_depth <= 15:
            score += 15
        elif autocomplete_depth <= 30:
            score += 10
        elif autocomplete_depth <= 50:
            score += 5
        else:
            score += 2

        # Volume tier (0-30)
        tier_scores = {
            "very_high": 30,
            "high": 24,
            "medium": 18,
            "low": 10,
            "very_low": 4,
        }
        score += tier_scores.get(volume_tier, 4)

        # Sponsored density (0-20)
        if sponsored_count >= 8:
            score += 20
        elif sponsored_count >= 5:
            score += 15
        elif sponsored_count >= 3:
            score += 10
        elif sponsored_count >= 1:
            score += 5

        return min(round(score, 2), 100.0)

    # ------------------------------------------------------------------
    # 4. Full research pipeline
    # ------------------------------------------------------------------

    async def research_keywords(
        self,
        niche_id: int,
        seed_keyword: str,
        top_serp_count: int = 20,
    ) -> dict:
        """Run the full keyword research pipeline for a niche.

        1. Discover keywords via autocomplete (~5 sec)
        2. Estimate volume for top N keywords via SERP scraping (~60-90 sec)
        3. Score and rank keywords
        4. Upsert into niche_keywords table

        Returns a summary dict with counts and top keywords.
        """
        from app.models.keyword import NicheKeyword

        # Step 1: Autocomplete discovery
        discovered = await self.discover_keywords_autocomplete(seed_keyword)
        if not discovered:
            logger.warning("No keywords discovered for '%s'", seed_keyword)
            return {
                "total_keywords_discovered": 0,
                "top_keywords": [],
                "avg_search_volume": 0,
                "volume_tier_distribution": {},
            }

        # Step 2: SERP estimation for top keywords by autocomplete depth
        sorted_by_depth = sorted(discovered, key=lambda x: x["autocomplete_depth"])
        top_keywords = sorted_by_depth[:top_serp_count]

        serp_results: list[dict] = []
        for kw_data in top_keywords:
            try:
                serp = await self.scraper.scrape_serp_metadata(kw_data["keyword"])
                volume_data = self.estimate_volume_from_serp(serp)
                serp_results.append({**kw_data, **volume_data})
            except Exception as e:
                logger.warning("SERP estimation failed for '%s': %s", kw_data["keyword"], e)
                serp_results.append({
                    **kw_data,
                    "volume_estimate": 200,
                    "tier": "very_low",
                    "estimated_cpc": 0.80,
                    "total_results": 0,
                    "sponsored_count": 0,
                })
            # Brief delay between SERP scrapes
            await asyncio.sleep(1.5)

        # For remaining keywords (not SERP-scraped), assign default volume
        serp_kw_set = {r["keyword"].lower() for r in serp_results}
        for kw_data in discovered:
            if kw_data["keyword"].lower() not in serp_kw_set:
                serp_results.append({
                    **kw_data,
                    "volume_estimate": 200,
                    "tier": "very_low",
                    "estimated_cpc": 0.80,
                    "total_results": 0,
                    "sponsored_count": 0,
                })

        # Step 3: Compute relevance scores
        for kw in serp_results:
            kw["relevance_score"] = self.compute_relevance_score(
                keyword=kw["keyword"],
                seed_keyword=seed_keyword,
                autocomplete_depth=kw["autocomplete_depth"],
                volume_tier=kw.get("tier", "very_low"),
                sponsored_count=kw.get("sponsored_count", 0),
            )

        # Sort by relevance score descending
        serp_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        # Step 4: Upsert into niche_keywords
        now = datetime.now(timezone.utc)
        saved_count = 0
        for kw in serp_results:
            keyword_text = kw["keyword"]
            stmt = select(NicheKeyword).where(
                NicheKeyword.niche_id == niche_id,
                NicheKeyword.keyword == keyword_text,
            )
            existing = (await self.session.execute(stmt)).scalar_one_or_none()

            competition = "high" if kw.get("sponsored_count", 0) >= 8 else (
                "medium" if kw.get("sponsored_count", 0) >= 4 else "low"
            )

            if existing:
                existing.search_volume = kw.get("volume_estimate")
                existing.avg_cpc = kw.get("estimated_cpc")
                existing.competition_level = competition
                existing.organic_result_count = kw.get("total_results")
                existing.sponsored_result_count = kw.get("sponsored_count")
                existing.relevance_score = kw.get("relevance_score")
                existing.source = "autocomplete"
                existing.autocomplete_depth = kw.get("autocomplete_depth")
                existing.last_updated_at = now
            else:
                new_kw = NicheKeyword(
                    niche_id=niche_id,
                    keyword=keyword_text,
                    search_volume=kw.get("volume_estimate"),
                    avg_cpc=kw.get("estimated_cpc"),
                    competition_level=competition,
                    organic_result_count=kw.get("total_results"),
                    sponsored_result_count=kw.get("sponsored_count"),
                    relevance_score=kw.get("relevance_score"),
                    source="autocomplete",
                    autocomplete_depth=kw.get("autocomplete_depth"),
                    last_updated_at=now,
                )
                self.session.add(new_kw)
            saved_count += 1

        await self.session.flush()

        # Build summary
        tier_distribution: dict[str, int] = {}
        volumes: list[int] = []
        for kw in serp_results:
            tier = kw.get("tier", "very_low")
            tier_distribution[tier] = tier_distribution.get(tier, 0) + 1
            volumes.append(kw.get("volume_estimate", 0))

        avg_volume = round(sum(volumes) / len(volumes)) if volumes else 0
        top_5 = [
            {
                "keyword": kw["keyword"],
                "search_volume": kw.get("volume_estimate", 0),
                "relevance_score": kw.get("relevance_score", 0),
            }
            for kw in serp_results[:5]
        ]

        logger.info(
            "Keyword research complete for niche %d: %d keywords discovered, avg volume %d",
            niche_id, saved_count, avg_volume,
        )

        return {
            "total_keywords_discovered": saved_count,
            "top_keywords": top_5,
            "avg_search_volume": avg_volume,
            "volume_tier_distribution": tier_distribution,
        }
