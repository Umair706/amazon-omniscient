"""Product Blueprint Service — deep LLM analysis of competitor reviews to produce
an actionable product improvement blueprint.

Takes reviews across all competitors in a niche and produces:
1. Categorized complaint analysis (design, quality, features, packaging, value)
2. Competitor weakness matrix (which competitors have which problems)
3. Improvement priority scoring (frequency × severity × feasibility × gap)
4. Actionable product blueprint (specific changes, supplier talking points, cost impact)
"""

import logging
from app.llm.base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class ProductBlueprintService:
    """Generates a structured product improvement blueprint from competitor reviews."""

    COMPLAINT_CATEGORIES = [
        "design_flaws",
        "quality_durability",
        "missing_features",
        "sizing_fit",
        "packaging",
        "value_perception",
        "usability",
    ]

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    async def generate_blueprint(
        self,
        niche_keyword: str,
        competitor_reviews: dict[str, list[dict]],
        competitor_metadata: list[dict],
        price_range: dict | None = None,
    ) -> dict:
        """
        Generate a full product blueprint from competitor reviews.

        Args:
            niche_keyword: The niche being analyzed (e.g. "garlic press")
            competitor_reviews: {asin: [review dicts]} for each competitor
            competitor_metadata: [{asin, title, price, rating, review_count, bsr}]
            price_range: {min, avg, max} price stats

        Returns:
            Full blueprint dict with complaints, weakness matrix, priorities,
            and actionable improvements.
        """
        if not competitor_reviews:
            return self._empty_blueprint()

        # Step 1: Extract and categorize complaints across all competitors
        complaint_analysis = await self._analyze_complaints(
            niche_keyword, competitor_reviews, competitor_metadata,
        )

        # Step 2: Build the improvement blueprint with priorities
        blueprint = await self._build_blueprint(
            niche_keyword, complaint_analysis, competitor_metadata, price_range,
        )

        return blueprint

    async def _analyze_complaints(
        self,
        niche_keyword: str,
        competitor_reviews: dict[str, list[dict]],
        competitor_metadata: list[dict],
    ) -> dict:
        """Extract and categorize complaints across all competitors."""
        # Build a compact review summary per competitor
        competitor_sections = []
        for meta in competitor_metadata[:15]:
            asin = meta.get("asin", "")
            reviews = competitor_reviews.get(asin, [])
            if not reviews:
                continue

            # Focus on negative/mixed reviews (1-3 stars) for complaints,
            # but include positive for context
            negative = [r for r in reviews if (r.get("rating") or 5) <= 3]
            positive = [r for r in reviews if (r.get("rating") or 0) >= 4]

            section = (
                f"COMPETITOR: {asin} — \"{meta.get('title', '')[:80]}\"\n"
                f"Price: ${meta.get('price', '?')} | Rating: {meta.get('rating', '?')}/5 | "
                f"Reviews: {meta.get('review_count', '?')} | BSR: {meta.get('bsr', '?')}\n"
            )

            if negative:
                section += f"\nNEGATIVE REVIEWS ({len(negative)} of {len(reviews)} sampled):\n"
                for r in negative[:15]:
                    section += (
                        f"  [{r.get('rating', '?')}★] {r.get('title', '')}\n"
                        f"  {(r.get('body', '') or '')[:300]}\n\n"
                    )

            if positive:
                section += f"\nPOSITIVE REVIEWS (sample of {len(positive)}):\n"
                for r in positive[:5]:
                    section += (
                        f"  [{r.get('rating', '?')}★] {r.get('title', '')}\n"
                        f"  {(r.get('body', '') or '')[:200]}\n\n"
                    )

            competitor_sections.append(section)

        reviews_text = "\n===\n\n".join(competitor_sections)

        prompt = f"""Analyze customer reviews across multiple competing products in the "{niche_keyword}" niche on Amazon. Extract and categorize every complaint and identify what customers wish was better.

COMPETITOR REVIEWS:
{reviews_text}

Return a JSON object with this EXACT structure:
{{
    "complaint_categories": [
        {{
            "category": "<one of: design_flaws, quality_durability, missing_features, sizing_fit, packaging, value_perception, usability>",
            "complaints": [
                {{
                    "complaint": "<specific complaint in clear language>",
                    "frequency": "<how many reviews across all competitors mention this>",
                    "severity": "<low|medium|high|critical>",
                    "affected_asins": ["<ASINs where this complaint appears>"],
                    "sample_quotes": ["<1-2 direct quotes from reviews>"],
                    "customer_impact": "<how this affects the customer experience>"
                }}
            ]
        }}
    ],
    "positive_features_to_keep": [
        {{
            "feature": "<feature customers consistently praise>",
            "frequency": "<how often mentioned>",
            "asins_excelling": ["<ASINs that do this well>"],
            "customer_quote": "<representative positive quote>"
        }}
    ],
    "unmet_needs": [
        {{
            "need": "<something customers want but no competitor offers>",
            "evidence": "<quotes or patterns supporting this>",
            "potential_value": "<low|medium|high>"
        }}
    ]
}}

Rules:
- Be specific. "Poor quality" is too vague — say "Handle breaks after 2-3 months of regular use".
- Group truly similar complaints together but keep distinct issues separate.
- Only include complaints with real evidence from the reviews.
- Include ALL categories even if some have no complaints (empty complaints array).
- Focus on product-level issues, not shipping/seller issues."""

        return await self.llm.generate_json(prompt, max_tokens=8192)

    async def _build_blueprint(
        self,
        niche_keyword: str,
        complaint_analysis: dict,
        competitor_metadata: list[dict],
        price_range: dict | None,
    ) -> dict:
        """Build the actionable product blueprint from complaint analysis."""
        price_context = ""
        if price_range:
            price_context = (
                f"\nPRICE RANGE: ${price_range.get('min', 0):.2f} - "
                f"${price_range.get('max', 0):.2f} "
                f"(avg ${price_range.get('avg', 0):.2f})"
            )

        competitor_summary = "\n".join(
            f"- {m.get('asin')}: \"{m.get('title', '')[:60]}\" — "
            f"${m.get('price', '?')}, {m.get('rating', '?')}★, "
            f"{m.get('review_count', '?')} reviews"
            for m in competitor_metadata[:15]
        )

        prompt = f"""You are a product development strategist for Amazon private label products. Based on this complaint analysis for the "{niche_keyword}" niche, create an actionable product improvement blueprint.

COMPLAINT ANALYSIS:
{complaint_analysis}

COMPETITORS:
{competitor_summary}
{price_context}

Return a JSON object with this EXACT structure:
{{
    "weakness_matrix": [
        {{
            "complaint": "<the complaint>",
            "category": "<complaint category>",
            "competitors_affected": <number of competitors with this issue>,
            "total_competitors": <total competitors analyzed>,
            "pct_affected": <percentage of competitors affected>,
            "avg_rating_of_affected": <average rating of products with this issue>,
            "severity": "<low|medium|high|critical>"
        }}
    ],
    "improvement_priorities": [
        {{
            "rank": <1-N, highest priority first>,
            "improvement": "<specific improvement to make>",
            "addresses_complaint": "<which complaint this fixes>",
            "category": "<complaint category>",
            "priority_score": <0-100, based on frequency × severity × feasibility × competitive gap>,
            "frequency_score": <0-100>,
            "severity_score": <0-100>,
            "feasibility_score": <0-100, how easy to implement in manufacturing>,
            "competitive_gap_score": <0-100, how many competitors fail at this>,
            "estimated_cost_impact": "<minimal|low|moderate|significant>",
            "expected_review_uplift": "<how this should improve review scores>"
        }}
    ],
    "product_blueprint": {{
        "strategy_summary": "<2-3 sentence product strategy>",
        "target_price_point": <recommended price>,
        "target_rating": <realistic target rating, e.g. 4.5>,
        "must_have_improvements": [
            {{
                "improvement": "<what to change>",
                "why": "<why this matters — reference complaint data>",
                "supplier_talking_point": "<what to tell your manufacturer>",
                "cost_impact": "<minimal|low|moderate|significant>",
                "competitors_failing": <how many competitors don't do this>
            }}
        ],
        "differentiators": [
            {{
                "feature": "<unique feature no competitor has>",
                "source": "<unmet need or innovation>",
                "marketing_angle": "<how to promote this in your listing>",
                "cost_impact": "<minimal|low|moderate|significant>"
            }}
        ],
        "features_to_match": [
            {{
                "feature": "<feature that top competitors do well>",
                "why": "<customers expect this as baseline>",
                "benchmark_asin": "<ASIN that does this best>"
            }}
        ],
        "features_to_avoid": [
            {{
                "feature": "<feature that seems good but causes problems>",
                "why": "<evidence from reviews>"
            }}
        ],
        "packaging_recommendations": [
            "<specific packaging improvements based on complaints>"
        ],
        "quality_benchmarks": [
            {{
                "benchmark": "<specific quality standard to meet>",
                "reason": "<complaint this prevents>",
                "test_method": "<how to verify with supplier>"
            }}
        ]
    }},
    "listing_angles": [
        {{
            "angle": "<marketing angle for the listing>",
            "addresses": "<which competitor weakness this exploits>",
            "suggested_bullet": "<example bullet point copy>"
        }}
    ],
    "risk_warnings": [
        {{
            "risk": "<potential risk with this product approach>",
            "mitigation": "<how to mitigate>"
        }}
    ]
}}

Rules:
- Rank improvement_priorities by priority_score descending (most impactful first).
- Be specific and actionable — "use thicker stainless steel" not "improve quality".
- supplier_talking_points should be things you can actually say to a Chinese manufacturer.
- Every recommendation must trace back to actual review data.
- Keep must_have_improvements to 5-8 items max (the critical ones).
- Keep differentiators to 3-5 items max (things that truly stand out).
- listing_angles should be compelling A+ content / bullet point ideas."""

        return await self.llm.generate_json(prompt, max_tokens=8192)

    @staticmethod
    def _empty_blueprint() -> dict:
        return {
            "complaint_categories": [],
            "positive_features_to_keep": [],
            "unmet_needs": [],
            "weakness_matrix": [],
            "improvement_priorities": [],
            "product_blueprint": {
                "strategy_summary": "Insufficient review data for analysis.",
                "target_price_point": 0,
                "target_rating": 0,
                "must_have_improvements": [],
                "differentiators": [],
                "features_to_match": [],
                "features_to_avoid": [],
                "packaging_recommendations": [],
                "quality_benchmarks": [],
            },
            "listing_angles": [],
            "risk_warnings": [],
        }
