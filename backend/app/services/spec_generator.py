"""LLM-powered product specification generator based on market analysis."""

import logging
from app.llm.base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class SpecGenerator:
    """Generates optimized product specifications using LLM analysis of market data."""

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    async def generate_product_spec(
        self,
        niche_keyword: str,
        pain_points: list[dict],
        positive_themes: list[dict],
        competitor_data: list[dict],
        price_range: dict,
        target_bsr: int | None = None,
    ) -> dict:
        """
        Generate an optimized product specification based on market analysis.

        Returns a spec that addresses market gaps and maximizes competitiveness.
        """
        prompt = f"""You are an Amazon product development expert. Based on the following market analysis for the "{niche_keyword}" niche, generate an optimized product specification.

MARKET PAIN POINTS (from customer reviews):
{self._format_pain_points(pain_points)}

POSITIVE THEMES (what customers love):
{self._format_positive_themes(positive_themes)}

COMPETITOR LANDSCAPE:
{self._format_competitors(competitor_data)}

PRICE RANGE:
- Low: ${price_range.get('min', 0):.2f}
- Average: ${price_range.get('avg', 0):.2f}
- High: ${price_range.get('max', 0):.2f}

TARGET BSR: {target_bsr or 'Not specified'}

Generate a detailed product specification as JSON:
{{
    "product_name_suggestion": "<suggested product name>",
    "target_price": <recommended selling price>,
    "target_cost": <maximum acceptable landed cost>,
    "key_features": [
        {{
            "feature": "<feature name>",
            "description": "<why this matters>",
            "addresses_pain_point": "<which pain point this solves or null>",
            "priority": "<must_have|should_have|nice_to_have>"
        }}
    ],
    "materials": ["<recommended materials>"],
    "dimensions": {{
        "notes": "<size/dimension recommendations>"
    }},
    "packaging_requirements": [
        "<packaging spec recommendations>"
    ],
    "quality_standards": [
        "<quality benchmarks to meet or exceed>"
    ],
    "differentiation_strategy": "<how this product wins vs competitors>",
    "listing_optimization": {{
        "title_keywords": ["<high-value keywords for the title>"],
        "bullet_points": [
            "<optimized bullet point addressing key benefit/feature>"
        ],
        "backend_keywords": ["<additional search terms>"],
        "a_plus_content_themes": ["<themes for A+ content>"]
    }},
    "estimated_margin": {{
        "selling_price": <price>,
        "estimated_landed_cost": <cost>,
        "estimated_fba_fees": <fees>,
        "estimated_ppc_cost_per_unit": <ppc cost>,
        "estimated_net_margin_percent": <margin %>
    }},
    "risk_factors": [
        "<potential risks with this product>"
    ],
    "moq_recommendation": <recommended minimum order quantity>,
    "launch_strategy_notes": "<brief notes on launch approach>"
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096)

    async def generate_listing_copy(
        self,
        product_spec: dict,
        niche_keyword: str,
        top_keywords: list[str],
    ) -> dict:
        """Generate optimized Amazon listing copy."""
        prompt = f"""Create an optimized Amazon product listing for a product in the "{niche_keyword}" niche.

PRODUCT SPEC:
{product_spec}

TOP KEYWORDS TO INCLUDE:
{', '.join(top_keywords[:20])}

Generate listing copy as JSON:
{{
    "title": "<Amazon-optimized title, max 200 chars, include top keywords>",
    "bullet_points": [
        "<5 compelling bullet points, each starting with CAPS benefit keyword>"
    ],
    "product_description": "<engaging product description, 1000+ chars>",
    "backend_search_terms": "<comma-separated, max 250 bytes>",
    "subject_matter": "<subject matter keywords>",
    "target_audience": "<intended target audience>"
}}

Rules:
- Title: Brand + Primary Keyword + Key Feature + Secondary Keywords + Size/Variant
- Bullet points: Start with ALL CAPS benefit, then explain. Include keywords naturally.
- Description: Tell a story, address pain points, include social proof language.
- Backend: No duplicates from title/bullets, no brand names, no ASINs."""

        return await self.llm.generate_json(prompt, max_tokens=4096)

    @staticmethod
    def _format_pain_points(pain_points: list[dict]) -> str:
        if not pain_points:
            return "No pain points identified"
        lines = []
        for pp in pain_points:
            lines.append(
                f"- {pp.get('theme', 'Unknown')}: "
                f"Severity={pp.get('severity', '?')}, "
                f"Frequency={pp.get('frequency', '?')} mentions"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_positive_themes(themes: list[dict]) -> str:
        if not themes:
            return "No positive themes identified"
        lines = []
        for t in themes:
            lines.append(
                f"- {t.get('theme', 'Unknown')}: "
                f"Frequency={t.get('frequency', '?')} mentions"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_competitors(competitors: list[dict]) -> str:
        if not competitors:
            return "No competitor data available"
        lines = []
        for c in competitors:
            lines.append(
                f"- ASIN {c.get('asin', '?')}: "
                f"Price=${c.get('price', '?')}, "
                f"Rating={c.get('rating', '?')}, "
                f"Reviews={c.get('review_count', '?')}, "
                f"BSR={c.get('bsr', '?')}"
            )
        return "\n".join(lines)
