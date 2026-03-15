"""LLM-powered niche intelligence: market overview and per-product competitive analysis."""

import logging

from app.llm.base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class NicheIntelligenceService:
    """Generates comprehensive LLM-powered intelligence reports."""

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    async def generate_niche_overview(
        self,
        niche_keyword: str,
        products: list[dict],
        competitor_landscape: dict,
        metrics: dict,
    ) -> dict:
        """
        Generate a comprehensive market intelligence overview.

        Returns dict with market_narrative, market_size_assessment, trend_analysis,
        competitive_dynamics, entry_barriers, opportunity_windows, key_takeaway.
        """
        price_stats = competitor_landscape.get("price_stats", {}) if competitor_landscape else {}
        review_stats = competitor_landscape.get("review_stats", {}) if competitor_landscape else {}

        # Build top products summary
        top_products_text = ""
        for p in products[:5]:
            top_products_text += (
                f"  - {p.get('title', 'N/A')[:80]}: "
                f"${p.get('price', '?')}, "
                f"BSR={p.get('bsr') or p.get('current_bsr', '?')}, "
                f"Reviews={p.get('review_count', '?')}\n"
            )

        avg_price = metrics.get("avg_price", 0)
        avg_bsr = metrics.get("avg_bsr", 0)
        avg_reviews = metrics.get("avg_review_count", 0)
        avg_listing_quality = metrics.get("avg_listing_quality", 50)

        # Count high vulnerability competitors
        competitor_details = competitor_landscape.get("competitor_details", []) if competitor_landscape else []
        high_vuln_count = sum(
            1 for c in competitor_details
            if c.get("vulnerability") in ("high", "critical")
        )

        prompt = f"""You are an Amazon FBA product research analyst. Analyze this niche and write a comprehensive market overview.

Niche: {niche_keyword}
Products analyzed: {len(products)}
Average price: ${avg_price:.2f}
Average BSR: {avg_bsr}
Average reviews: {avg_reviews}
Price range: ${price_stats.get('min', 0):.2f}-${price_stats.get('max', 0):.2f}
Review range: {review_stats.get('min', 0)}-{review_stats.get('max', 0)}

Top products:
{top_products_text}

Average listing quality: {avg_listing_quality}/100
High vulnerability competitors: {high_vuln_count}

Write a market intelligence report as JSON:
{{
    "market_narrative": "<2-3 paragraphs analyzing the competitive landscape, demand signals, and market maturity>",
    "market_size_assessment": "<estimate of market size based on BSR and pricing data>",
    "trend_analysis": "<whether the niche is growing, stable, or declining based on available signals>",
    "competitive_dynamics": "<who dominates, what strategies work, where are the gaps>",
    "entry_barriers": ["<top 3-5 barriers to entry>"],
    "opportunity_windows": ["<top 3-5 specific opportunities for a new entrant>"],
    "key_takeaway": "<one decisive sentence>"
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096)

    async def generate_product_overviews(
        self,
        products: list[dict],
        competitor_details: list[dict],
    ) -> list[dict]:
        """
        Per-product LLM competitive analysis.

        Returns list of per-product assessments with overview, strengths, weaknesses,
        threat_level, what_they_do_well, vulnerability_to_exploit, plus product metadata
        (title, price, rating, image_url).
        """
        if not products:
            return []

        # Build product summaries for the prompt
        products_text = ""
        detail_by_asin = {
            c.get("asin", c.get("product_asin", "")): c
            for c in competitor_details
        } if competitor_details else {}

        # Build a lookup for product metadata to enrich LLM results
        product_meta: dict[str, dict] = {}
        for p in products[:10]:
            asin = p.get("asin", "?")
            product_meta[asin] = {
                "title": p.get("title", ""),
                "price": p.get("price"),
                "rating": p.get("rating"),
                "review_count": p.get("review_count"),
                "image_url": p.get("image_url"),
                "bsr": p.get("bsr") or p.get("current_bsr"),
            }
            detail = detail_by_asin.get(asin, {})
            products_text += (
                f"- ASIN: {asin}\n"
                f"  Title: {p.get('title', 'N/A')[:100]}\n"
                f"  Price: ${p.get('price', '?')}\n"
                f"  Rating: {p.get('rating', '?')}\n"
                f"  Reviews: {p.get('review_count', '?')}\n"
                f"  BSR: {p.get('bsr') or p.get('current_bsr', '?')}\n"
                f"  Listing quality: {detail.get('listing_quality_score', 'N/A')}/100\n"
                f"  Vulnerability: {detail.get('vulnerability', 'N/A')}\n"
                f"  Has A+: {p.get('has_a_plus', 'N/A')}\n"
                f"  Has video: {p.get('has_video', 'N/A')}\n"
                f"  Image count: {p.get('image_count', 'N/A')}\n\n"
            )

        prompt = f"""Analyze each Amazon product as a competitor. For each product, assess its competitive position.

Products:
{products_text}

For each product return a JSON object with:
- asin: the product ASIN
- overview: 2-3 sentence competitive assessment
- strengths: array of 2-3 key strengths
- weaknesses: array of 2-3 key weaknesses
- threat_level: "low", "medium", or "high" (how hard would it be to beat this product)
- what_they_do_well: one specific thing to learn from
- vulnerability_to_exploit: one specific gap a new product could target

Return as a JSON array."""

        result = await self.llm.generate_json(prompt, max_tokens=8192)
        if not isinstance(result, list):
            return []

        # Enrich LLM results with product metadata (images, title, price)
        for item in result:
            asin = item.get("asin", "")
            meta = product_meta.get(asin, {})
            item["title"] = meta.get("title", "")
            item["price"] = meta.get("price")
            item["rating"] = meta.get("rating")
            item["review_count"] = meta.get("review_count")
            item["image_url"] = meta.get("image_url")
            item["bsr"] = meta.get("bsr")

        return result
