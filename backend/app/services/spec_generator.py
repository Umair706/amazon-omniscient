"""LLM-powered product specification generator based on market analysis."""

import logging
from app.llm.base_client import BaseLLMClient, EXPERT_SYSTEM_PROMPT

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
        prompt = f"""Based on the following market analysis for the "{niche_keyword}" niche, generate a product specification with conservative financial estimates.

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

FINANCIAL ESTIMATION RULES:
- target_cost must include a 15-20% buffer for quality defects and returns. Real defect rates are 3-8%, not the 1-2% suppliers quote. Returns on Amazon average 5-15% depending on category.
- estimated_fba_fees must account for ALL fee components: referral fee (15%), FBA fulfillment, inbound placement fee ($0.21-0.68/unit depending on size), monthly storage ($0.87-2.40/cu ft), and aged inventory surcharge (if unsold after 181 days).
- estimated_ppc_cost_per_unit should assume 50-70% ACOS for the first 90 days on a zero-review listing. This is the reality for new products.
- moq_recommendation must reflect actual supplier minimums: typically 500-2000 units for standard products, 3000-5000 for custom tooling. First order should be conservative (lower MOQ even at higher per-unit cost) to validate product-market fit before scaling.
- estimated_net_margin_percent should be the WORST-CASE margin (after all fees, returns, PPC), not the best-case.

Generate a detailed product specification as JSON:
{{
    "product_name_suggestion": "<suggested product name>",
    "target_price": <recommended selling price>,
    "target_cost": <maximum acceptable landed cost — including 15-20% buffer>,
    "key_features": [
        {{
            "feature": "<feature name>",
            "description": "<why this matters — reference review data>",
            "addresses_pain_point": "<which pain point this solves or null>",
            "priority": "<must_have|should_have|nice_to_have>",
            "estimated_cogs_impact": "<per-unit cost impact>"
        }}
    ],
    "materials": ["<recommended materials with specific grades where possible>"],
    "dimensions": {{
        "notes": "<size/dimension recommendations — consider FBA size tier implications>"
    }},
    "packaging_requirements": [
        "<packaging spec — include FBA prep requirements>"
    ],
    "quality_standards": [
        "<specific quality benchmarks — reference testing standards where applicable>"
    ],
    "differentiation_strategy": "<how this product wins — must be grounded in review evidence, not aspirational>",
    "listing_optimization": {{
        "title_keywords": ["<high-value keywords for the title>"],
        "bullet_points": [
            "<bullet point that addresses a top buyer objection>"
        ],
        "backend_keywords": ["<additional search terms>"],
        "a_plus_content_themes": ["<themes for A+ content>"]
    }},
    "estimated_margin": {{
        "selling_price": <price>,
        "estimated_landed_cost": <cost including buffer>,
        "estimated_fba_fees": <all FBA fees combined>,
        "estimated_ppc_cost_per_unit": <assuming 50-70% ACOS for first 90 days>,
        "estimated_return_cost_per_unit": <returns * (product cost + FBA return fee)>,
        "estimated_net_margin_percent": <conservative margin after ALL costs>,
        "margin_notes": "<explain key assumptions>"
    }},
    "risk_factors": [
        "<specific risk with probability estimate and financial impact>"
    ],
    "moq_recommendation": <recommended first-order quantity — conservative>,
    "moq_reasoning": "<why this MOQ — balance validation vs per-unit cost>",
    "total_first_order_investment": <MOQ * landed cost + shipping + customs + inspection>,
    "launch_strategy_notes": "<brief notes on launch approach — be realistic about timeline>"
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)

    async def generate_listing_copy(
        self,
        product_spec: dict,
        niche_keyword: str,
        top_keywords: list[str],
    ) -> dict:
        """Generate optimized Amazon listing copy."""
        prompt = f"""Create Amazon listing copy for a product in the "{niche_keyword}" niche. Write copy that converts shoppers into buyers, not copy that impresses copywriters.

PRODUCT SPEC:
{product_spec}

TOP KEYWORDS TO INCLUDE:
{', '.join(top_keywords[:20])}

LISTING COPY RULES:
- The #1 job of listing copy is to overcome buyer objections. Focus on the top 3 objections from review data (quality concerns, durability, value for money).
- Avoid hyperbole: no "best ever," "revolutionary," "game-changing," "premium quality." These trigger skepticism. Use specific claims instead: "1.2mm thick stainless steel" beats "premium quality materials."
- Bullet points should answer: "Why should I buy THIS one instead of the other 20 options?"
- Description should address the specific fears buyers have in this category (based on negative review themes).
- Do not promise what the product can't deliver. Overpromising leads to returns and bad reviews.

Generate listing copy as JSON:
{{
    "title": "<Amazon-optimized title, max 200 chars, include top keywords. No hyperbole.>",
    "bullet_points": [
        "<5 bullet points. Each starts with ALL CAPS benefit keyword. Focus on addressing buyer objections, not listing features. Be specific.>"
    ],
    "product_description": "<description that addresses the top 3 buyer fears/objections in this category. Use specific claims, not vague quality promises. 1000+ chars.>",
    "backend_search_terms": "<comma-separated, max 250 bytes>",
    "subject_matter": "<subject matter keywords>",
    "target_audience": "<intended target audience>",
    "objections_addressed": ["<the top buyer objections this copy addresses>"]
}}

Rules:
- Title: Brand + Primary Keyword + Key Feature + Secondary Keywords + Size/Variant
- Bullet points: Specific claims with numbers beat vague quality promises every time.
- Backend: No duplicates from title/bullets, no brand names, no ASINs.
- If the product spec doesn't support a claim, don't make it."""

        return await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)

    async def generate_product_ideas(
        self,
        niche_keyword: str,
        pain_points: list[dict],
        positive_themes: list[dict],
        competitor_data: list[dict],
        price_range: dict,
        product_blueprint: dict | None = None,
    ) -> list[dict]:
        """
        Generate 3-5 differentiated product ideas based on review gaps,
        competitor weaknesses, and market opportunities.
        """
        blueprint_section = ""
        if product_blueprint:
            bp = product_blueprint.get("product_blueprint", {})
            must_haves = bp.get("must_have_improvements", [])
            differentiators = bp.get("differentiators", [])
            if must_haves:
                blueprint_section += "\nMust-have improvements from blueprint:\n"
                for imp in must_haves[:5]:
                    blueprint_section += f"  - {imp.get('improvement', '')}: {imp.get('why', '')}\n"
            if differentiators:
                blueprint_section += "\nDifferentiator opportunities from blueprint:\n"
                for d in differentiators[:5]:
                    blueprint_section += f"  - {d.get('feature', '')}: {d.get('marketing_angle', '')}\n"

        prompt = f"""Based on the competitive analysis below, generate 3-5 product ideas for the "{niche_keyword}" niche. Every idea must pass a basic financial sanity check.

Review Pain Points (what customers hate about existing products):
{self._format_pain_points(pain_points)}

Positive Themes (what customers love — KEEP these):
{self._format_positive_themes(positive_themes)}

Competitor Landscape:
- {len(competitor_data)} products analyzed
- Price range: ${price_range.get('min', 0):.2f}-${price_range.get('max', 0):.2f}
- Average price: ${price_range.get('avg', 0):.2f}

{self._format_competitors(competitor_data[:5])}
{blueprint_section}

PRODUCT IDEA REQUIREMENTS:
- Each idea must pass a quick financial sanity check: target_price must be >2.5x estimated landed cost to leave room for FBA fees (30-35% of price) + PPC (15-25% of price during launch) + margin.
- estimated_difficulty must be realistic: "low" = an existing mold/design already exists on 1688 that just needs minor modifications, "medium" = modifications to existing designs requiring some tooling changes, "high" = custom tooling, new molds, or longer development cycle ($3K-10K+ in tooling costs, 60-90 day lead time).
- Preserve features customers already love. Do not sacrifice proven positive features for differentiation.
- Every idea must be manufacturable by standard Chinese OEM suppliers. No ideas requiring proprietary technology, complex electronics, or regulatory certifications (FDA, UL, etc.) unless the niche inherently requires it.
- Be honest about risk_factors. Include market risks (competitor response, demand uncertainty) and operational risks (quality control, IP concerns).

Return as a JSON array:
[
    {{
        "idea_name": "<descriptive product name — not marketing fluff>",
        "concept": "<2-3 sentence description of the product idea>",
        "target_price": <recommended selling price as number>,
        "estimated_landed_cost": <estimated cost per unit including shipping and duties>,
        "key_differentiators": ["<unique feature 1>", "<unique feature 2>"],
        "pain_points_addressed": ["<pain point 1>", "<pain point 2>"],
        "estimated_difficulty": "<low|medium|high — per the criteria above>",
        "tooling_cost_estimate": "<estimated tooling/mold cost if applicable, e.g., '$0' for existing designs, '$3K-5K' for new molds>",
        "estimated_margin": "<conservative margin range after ALL costs including PPC>",
        "financial_sanity_check": "<brief explanation: does the math work? price vs cost vs fees>",
        "why_it_works": "<grounded in review data, not aspirational>",
        "why_it_might_fail": "<honest assessment of failure scenarios>",
        "risk_factors": ["<specific risk with impact assessment>"],
        "supplier_search_terms": ["<Chinese search term>", "<English search term>"],
        "estimated_first_order_investment": <total capital needed for first order including tooling, inventory, shipping>
    }}
]"""

        result = await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)
        if isinstance(result, list):
            return result
        # Some LLMs wrap arrays in an object — try to extract
        if isinstance(result, dict):
            for key in ("ideas", "product_ideas", "products", "items"):
                if isinstance(result.get(key), list):
                    return result[key]
            # If the dict has a single list value, use that
            list_values = [v for v in result.values() if isinstance(v, list)]
            if len(list_values) == 1:
                return list_values[0]
        return []

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
