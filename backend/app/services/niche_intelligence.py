"""LLM-powered niche intelligence: market overview and per-product competitive analysis."""

import logging

from app.llm.base_client import BaseLLMClient, EXPERT_SYSTEM_PROMPT

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
                f"  - {(p.get('title') or 'N/A')[:80]}: "
                f"${p.get('price') or '?'}, "
                f"BSR={p.get('bsr') or p.get('current_bsr') or '?'}, "
                f"Reviews={p.get('review_count') or '?'}\n"
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

        prompt = f"""Analyze this Amazon niche and write an honest, data-driven market intelligence assessment. Do not default to "opportunity exists" — if the niche is saturated, say so plainly.

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

ASSESSMENT GUIDELINES:
- If avg reviews > 500 and avg rating > 4.3, this is a mature/saturated market. Say so.
- If the top 3 products have 5K+ reviews each, acknowledge the review moat is likely insurmountable without 6-12+ months and significant capital.
- Include realistic capital requirements: inventory (2x MOQ for safety stock), PPC budget (first 90 days at 50-70% ACOS), Vine costs, professional photography/listing, and working capital buffer.
- Timeline to profitability should be realistic: most new PL products take 4-8 months to reach consistent daily sales, and 6-12 months to recover launch investment.
- entry_barriers should include financial barriers (capital required), not just competitive barriers.
- opportunity_windows should only list genuine, actionable opportunities supported by the data. Empty array is acceptable if none exist.

Write a market intelligence report as JSON:
{{
    "market_narrative": "<2-3 paragraphs. Be direct about market maturity. Include whether this is a market a new entrant can realistically compete in. Cite specific data points.>",
    "market_maturity": "<emerging|growing|mature|saturated|declining>",
    "market_size_assessment": "<estimate based on BSR and pricing data. Include confidence level.>",
    "trend_analysis": "<growing/stable/declining based on available signals. If insufficient data to determine trend, say so.>",
    "competitive_dynamics": "<who dominates, what strategies work. If top players are entrenched, say so.>",
    "entry_barriers": ["<barrier with specific numbers — e.g., 'Review moat: avg competitor has 800+ reviews, requiring 6-12 months to reach competitive level'>"],
    "opportunity_windows": ["<specific, actionable opportunity supported by the data — or empty if none>"],
    "realistic_capital_required": "<estimated total capital needed for launch through break-even, including inventory, PPC, Vine, listing, and buffer>",
    "realistic_timeline_to_profitability": "<months to monthly break-even, accounting for PPC ramp and review building>",
    "key_takeaway": "<one decisive sentence — be blunt about whether this is worth pursuing>"
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)

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
            listing_scores = detail.get("listing_scores", {}) or {}
            vulnerabilities = detail.get("vulnerabilities", []) or []
            vuln_types = [v.get("type", "") for v in vulnerabilities if isinstance(v, dict)]
            products_text += (
                f"- ASIN: {asin}\n"
                f"  Title: {(p.get('title') or 'N/A')[:100]}\n"
                f"  Price: ${p.get('price') or '?'}\n"
                f"  Rating: {p.get('rating') or '?'}\n"
                f"  Reviews: {p.get('review_count') or '?'}\n"
                f"  BSR: {p.get('bsr') or p.get('current_bsr') or '?'}\n"
                f"  Listing quality: {listing_scores.get('overall', 'N/A')}/100\n"
                f"  Vulnerabilities: {', '.join(vuln_types) if vuln_types else 'none'}\n"
                f"  Has A+: {p.get('has_a_plus') or 'N/A'}\n"
                f"  Has video: {p.get('has_video') or 'N/A'}\n"
                f"  Image count: {p.get('image_count') or 'N/A'}\n\n"
            )

        prompt = f"""Assess each Amazon product as a competitor honestly. Do not underestimate entrenched players.

Products:
{products_text}

ASSESSMENT RULES:
- A product with 10K+ reviews and 4.5+ stars is a FORTRESS. Call it what it is — a new entrant cannot realistically displace it. threat_level must be "high".
- A product with 1K+ reviews and 4.0+ stars is ESTABLISHED. Displacing it requires 6-12+ months and significant differentiation. threat_level should be "high" unless listing quality is poor.
- Products with <100 reviews and <4.0 stars are genuinely vulnerable. These are the realistic targets.
- vulnerability_to_exploit must be something that's actually exploitable in practice (poor listing quality, no A+ content, outdated images) — not aspirational ("could offer better quality" without evidence).
- Do NOT suggest that high review count products can be beaten by "just having better listing quality." Reviews are the #1 conversion factor on Amazon.

For each product return a JSON object with:
- asin: the product ASIN
- overview: 2-3 sentence honest competitive assessment. If it's a dominant player, say so.
- strengths: array of 2-3 key strengths
- weaknesses: array of 2-3 key weaknesses (if the product has high reviews and high rating, "none significant" is a valid weakness entry)
- threat_level: "low", "medium", or "high" (be realistic — most established products are "high")
- what_they_do_well: one specific thing to learn from
- vulnerability_to_exploit: one specific, actionable gap — or "none identified" if the product is well-defended
- realistic_displacement_difficulty: "<easy|moderate|hard|near_impossible>"

Return as a JSON array."""

        result = await self.llm.generate_json(prompt, max_tokens=8192, system_message=EXPERT_SYSTEM_PROMPT)
        if isinstance(result, dict):
            # LLM may wrap array in an object
            for key in ("products", "product_overviews", "overviews", "competitors", "items"):
                if isinstance(result.get(key), list):
                    result = result[key]
                    break
            else:
                list_values = [v for v in result.values() if isinstance(v, list)]
                result = list_values[0] if len(list_values) == 1 else []
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
