"""Product Blueprint Service — deep LLM analysis of competitor reviews to produce
an actionable product improvement blueprint.

Takes reviews across all competitors in a niche and produces:
1. Categorized complaint analysis (design, quality, features, packaging, value)
2. Competitor weakness matrix (which competitors have which problems)
3. Improvement priority scoring (frequency × severity × feasibility × gap)
4. Actionable product blueprint (specific changes, supplier talking points, cost impact)
"""

import logging
from app.llm.base_client import BaseLLMClient, EXPERT_SYSTEM_PROMPT

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

        prompt = f"""Analyze customer reviews across multiple competing products in the "{niche_keyword}" niche on Amazon. Extract complaints that are actually actionable for a product developer.

COMPETITOR REVIEWS:
{reviews_text}

CRITICAL ANALYSIS RULES:
- SEPARATE product-level issues from user-error issues. A customer who can't figure out how to use a product is different from a product that's poorly designed. Classify each complaint.
- FLAG complaints that stem from unrealistic customer expectations rather than real product defects (e.g., expecting a $15 product to match $50 quality, complaining about product doing exactly what it's designed to do).
- FOCUS on complaints that are actually fixable at reasonable manufacturing cost. "The product exists" is not a fixable complaint.
- Do NOT include shipping/seller/Amazon issues (late delivery, wrong item sent, etc.).
- For severity: "critical" = primary function fails, "high" = significantly impairs core use, "medium" = degrades experience but product still works, "low" = cosmetic/preference.

Return a JSON object with this EXACT structure:
{{
    "complaint_categories": [
        {{
            "category": "<one of: design_flaws, quality_durability, missing_features, sizing_fit, packaging, value_perception, usability>",
            "complaints": [
                {{
                    "complaint": "<specific complaint — 'Handle breaks after 2-3 months of regular use' not 'poor quality'>",
                    "frequency": "<how many reviews across all competitors mention this>",
                    "severity": "<low|medium|high|critical>",
                    "affected_asins": ["<ASINs where this complaint appears>"],
                    "sample_quotes": ["<1-2 direct quotes from reviews>"],
                    "customer_impact": "<how this affects the customer experience>",
                    "is_product_defect": <true|false — false if user error or unrealistic expectation>,
                    "fixable_in_manufacturing": <true|false>,
                    "estimated_fix_complexity": "<simple|moderate|complex|requires_custom_tooling>"
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
            "need": "<something customers want but no competitor offers — must have direct review evidence>",
            "evidence": "<actual quotes or patterns supporting this>",
            "potential_value": "<low|medium|high>",
            "feasibility": "<easy|moderate|hard — can this realistically be manufactured?>"
        }}
    ],
    "unrealistic_expectations": [
        "<complaints that reflect customer misunderstanding rather than product issues>"
    ]
}}

Include ALL categories even if some have no complaints (empty complaints array)."""

        return await self.llm.generate_json(prompt, max_tokens=8192, system_message=EXPERT_SYSTEM_PROMPT)

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

        prompt = f"""Based on this complaint analysis for the "{niche_keyword}" niche, create a product improvement blueprint grounded in manufacturing reality and honest cost assessment.

COMPLAINT ANALYSIS:
{complaint_analysis}

COMPETITORS:
{competitor_summary}
{price_context}

CRITICAL RULES FOR THIS BLUEPRINT:
- Every improvement MUST include realistic COGS impact. Be specific: "adds $0.30-0.50/unit" not just "moderate."
- Do NOT suggest improvements requiring custom tooling >$5K or adding >15% to unit cost unless explicitly flagged as high-investment.
- Include manufacturing feasibility: can a standard Alibaba/1688 supplier do this, or does it require specialized capability?
- supplier_talking_points must reflect how Chinese OEM negotiations actually work. Reference specific manufacturing processes (injection molding, die casting, CNC, etc.) where relevant. Use realistic language — Chinese suppliers respond to specific material grades, thickness specs, and testing standards, not vague quality requests.
- MOQ implications: if an improvement requires a new mold or tooling, note the typical MOQ impact (usually 500-2000 units minimum).
- target_rating should be conservative. A new product with zero reviews is unlikely to maintain 4.5+ unless it genuinely solves the top complaints. 4.0-4.3 is realistic for a well-executed first production run.

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
            "improvement": "<specific improvement — 'use 304 stainless steel 1.2mm thickness' not 'improve quality'>",
            "addresses_complaint": "<which complaint this fixes>",
            "category": "<complaint category>",
            "priority_score": <0-100, based on frequency * severity * feasibility * competitive gap>,
            "frequency_score": <0-100>,
            "severity_score": <0-100>,
            "feasibility_score": <0-100, how easy for a standard supplier to implement>,
            "competitive_gap_score": <0-100>,
            "estimated_cost_impact_usd": "<estimated per-unit cost increase, e.g. '+$0.30-0.50'>",
            "requires_custom_tooling": <true|false>,
            "expected_review_uplift": "<conservative estimate of rating improvement>"
        }}
    ],
    "product_blueprint": {{
        "strategy_summary": "<2-3 sentence product strategy. Include total estimated COGS impact of all improvements.>",
        "target_price_point": <recommended price — must leave 30%+ gross margin after all FBA fees>,
        "target_rating": <realistic target, typically 4.0-4.3 for first production run>,
        "estimated_total_cogs_increase": "<total per-unit cost increase from all improvements>",
        "must_have_improvements": [
            {{
                "improvement": "<what to change — specific materials, dimensions, or processes>",
                "why": "<reference complaint data>",
                "supplier_talking_point": "<specific request in manufacturing terms — e.g., 'We need 304 stainless steel, 1.2mm minimum wall thickness, with electropolishing finish. Please quote for 1000-unit and 3000-unit MOQ.'>",
                "estimated_cost_per_unit": "<e.g., '+$0.40'>",
                "competitors_failing": <how many competitors don't do this>,
                "manufacturing_feasibility": "<standard capability|specialized supplier|custom tooling required>"
            }}
        ],
        "differentiators": [
            {{
                "feature": "<unique feature — must be manufacturable>",
                "source": "<unmet need from review evidence>",
                "marketing_angle": "<how to promote in listing>",
                "estimated_cost_per_unit": "<cost impact>",
                "manufacturing_feasibility": "<standard|specialized|custom tooling>"
            }}
        ],
        "features_to_match": [
            {{
                "feature": "<table stakes feature top competitors do well>",
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
            "<specific packaging improvements — include cost impact>"
        ],
        "quality_benchmarks": [
            {{
                "benchmark": "<specific quality standard — e.g., 'Must pass 500-cycle hinge test without loosening'>",
                "reason": "<complaint this prevents>",
                "test_method": "<how to verify — e.g., 'Request SGS testing report for XX standard'>"
            }}
        ]
    }},
    "listing_angles": [
        {{
            "angle": "<marketing angle that directly addresses a top competitor weakness>",
            "addresses": "<which competitor weakness this exploits>",
            "suggested_bullet": "<bullet point copy that converts — address buyer objections, not features>"
        }}
    ],
    "risk_warnings": [
        {{
            "risk": "<potential risk — include probability estimate>",
            "mitigation": "<specific mitigation step>",
            "cost_of_mitigation": "<estimated cost>"
        }}
    ]
}}

Keep must_have_improvements to 5-8 items max. Keep differentiators to 3-5 max. Every recommendation must trace to actual review data."""

        return await self.llm.generate_json(prompt, max_tokens=8192, system_message=EXPERT_SYSTEM_PROMPT)

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
