"""LLM-powered review analysis: sentiment scoring, pain point clustering, opportunity detection."""

import logging
from app.llm.base_client import BaseLLMClient, EXPERT_SYSTEM_PROMPT
from app.core.exceptions import LLMError

logger = logging.getLogger(__name__)


class ReviewAnalyzer:
    """Analyzes product reviews using LLM to extract actionable insights."""

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    async def analyze_reviews(self, reviews: list[dict], product_title: str, category: str) -> dict:
        """
        Analyze a batch of reviews and return:
        - sentiment_score (0-100)
        - pain_points: list of {theme, frequency, severity, sample_quotes}
        - positive_themes: list of {theme, frequency, sample_quotes}
        - improvement_opportunities: list of strings
        - review_quality_score (0-100) - how authentic/useful the reviews are
        - fake_review_risk (0-100)
        """
        if not reviews:
            return self._empty_analysis()

        # Batch reviews into chunks of 50 for context window management
        chunk_size = 50
        all_analyses = []

        for i in range(0, len(reviews), chunk_size):
            chunk = reviews[i:i + chunk_size]
            analysis = await self._analyze_chunk(chunk, product_title, category)
            all_analyses.append(analysis)

        # If multiple chunks, merge them
        if len(all_analyses) == 1:
            return all_analyses[0]

        return await self._merge_analyses(all_analyses, product_title)

    async def _analyze_chunk(self, reviews: list[dict], product_title: str, category: str) -> dict:
        """Analyze a chunk of reviews."""
        reviews_text = self._format_reviews_for_prompt(reviews)

        prompt = f"""Analyze these Amazon product reviews for "{product_title}" in the "{category}" category with a skeptical, evidence-based lens.

REVIEWS:
{reviews_text}

ANALYSIS REQUIREMENTS:
- Flag likely fake or incentivized reviews: look for generic 5-star language ("great product," "love it," "works as described" with no specifics), suspiciously similar phrasing, unverified purchases with high ratings, and reviews that read like marketing copy.
- Weight verified purchases significantly higher than unverified.
- Treat 5-star reviews with generic language as low-signal. They tell you almost nothing.
- For pain points, only include issues with concrete evidence (specific quotes). Vague complaints should be noted but scored lower.
- Severity ratings must reflect actual product impact: "critical" = product fails its primary function, "high" = significantly impairs usage, "medium" = annoying but workable, "low" = cosmetic or preference-based.

Return a JSON object with EXACTLY this structure:
{{
    "sentiment_score": <0-100, where 100 is perfectly positive. Discount score if fake_review_risk is high>,
    "pain_points": [
        {{
            "theme": "<specific pain point — not vague like 'poor quality' but concrete like 'handle breaks after 2-3 months'>",
            "frequency": <number of reviews mentioning this>,
            "severity": "<low|medium|high|critical>",
            "sample_quotes": ["<direct quote 1>", "<direct quote 2>"],
            "verified_purchase_pct": <what % of reviews mentioning this are verified purchases>
        }}
    ],
    "positive_themes": [
        {{
            "theme": "<positive theme>",
            "frequency": <number of reviews mentioning this>,
            "sample_quotes": ["<direct quote 1>", "<direct quote 2>"],
            "credibility": "<high|medium|low — based on specificity and verified purchase status>"
        }}
    ],
    "improvement_opportunities": [
        "<specific product improvement suggestion based on negative feedback — only include if fixable at reasonable manufacturing cost>"
    ],
    "review_quality_score": <0-100, based on detail level, verified purchase %, helpfulness votes. Generic reviews = low quality>,
    "fake_review_risk": <0-100, based on generic language, unverified purchase clusters, timing patterns, review-to-rating mismatch>,
    "common_use_cases": ["<how customers actually use this product — from review evidence only>"],
    "competitor_mentions": ["<any competitor products mentioned in reviews>"],
    "sample_size_warning": "<if fewer than 20 reviews, note that conclusions are unreliable. null if sample is adequate>"
}}

Do NOT infer pain points or opportunities that aren't directly supported by review text. If the review sample is small, say so."""

        result = await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)
        return result

    async def _merge_analyses(self, analyses: list[dict], product_title: str) -> dict:
        """Merge multiple chunk analyses into one."""
        prompt = f"""Merge these review analyses for "{product_title}" into a single consolidated analysis.

ANALYSES TO MERGE:
{analyses}

Return a single JSON object with the same structure, combining:
- Weighted average for sentiment_score, review_quality_score, fake_review_risk
- Merged and deduplicated pain_points (combine frequencies for same themes)
- Merged and deduplicated positive_themes
- Combined improvement_opportunities (deduplicated)
- Combined common_use_cases
- Combined competitor_mentions

Use the same JSON structure as the inputs."""

        return await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)

    @staticmethod
    def _format_reviews_for_prompt(reviews: list[dict]) -> str:
        """Format reviews into a text block for the LLM prompt."""
        lines = []
        for i, r in enumerate(reviews, 1):
            rating = r.get("rating", "?")
            title = r.get("title", "No title")
            body = r.get("body", "No body")
            verified = "Verified" if r.get("verified_purchase") else "Unverified"
            helpful = r.get("helpful_votes", 0)
            lines.append(
                f"[Review {i}] Rating: {rating}/5 | {verified} | {helpful} helpful votes\n"
                f"Title: {title}\n"
                f"Body: {body}\n"
            )
        return "\n---\n".join(lines)

    @staticmethod
    def _empty_analysis() -> dict:
        return {
            "sentiment_score": 0,
            "pain_points": [],
            "positive_themes": [],
            "improvement_opportunities": [],
            "review_quality_score": 0,
            "fake_review_risk": 0,
            "common_use_cases": [],
            "competitor_mentions": [],
        }

    async def generate_review_intelligence(
        self,
        all_reviews: list[dict],
        product_reviews: dict[str, list[dict]],
        niche_keyword: str,
        product_titles: dict[str, str],
    ) -> dict:
        """
        Cross-product review intelligence synthesis.

        Analyzes all reviews across all products to find patterns, personas,
        purchase drivers/barriers, and market gaps.
        """
        total_reviews = len(all_reviews)
        if total_reviews == 0:
            return {
                "total_reviews_analyzed": 0,
                "overall_sentiment": "neutral",
                "sentiment_score": 50,
                "key_insights": [],
                "customer_personas": [],
                "purchase_drivers": [],
                "purchase_barriers": [],
                "trending_complaints": [],
                "market_gaps": [],
                "best_reviewed_features": [],
                "worst_reviewed_features": [],
            }

        # Build a summary of reviews per product for the prompt
        # Include more reviews per product (up to 20) for richer market gap analysis
        product_summaries = []
        for asin, reviews in list(product_reviews.items())[:10]:
            title = product_titles.get(asin, asin)
            if not reviews:
                continue
            avg_rating = sum(r.get("rating", 3) for r in reviews) / len(reviews)
            # Include more reviews and prioritize low-rating reviews for gap analysis
            low_rated = [r for r in reviews if r.get("rating", 5) <= 3]
            high_rated = [r for r in reviews if r.get("rating", 5) >= 4]
            # Mix: up to 12 low-rated (rich in gaps) + up to 8 high-rated
            sample = low_rated[:12] + high_rated[:8]
            sample_reviews = self._format_reviews_for_prompt(sample)
            product_summaries.append(
                f"Product: {title} (ASIN: {asin})\n"
                f"Reviews: {len(reviews)}, Avg rating: {avg_rating:.1f}\n"
                f"Low-rated reviews ({len(low_rated)} total): shows complaints & unmet needs\n"
                f"Sample reviews:\n{sample_reviews}"
            )

        combined_text = "\n\n===\n\n".join(product_summaries)

        prompt = f"""Analyze reviews across multiple competing products in the "{niche_keyword}" niche on Amazon. Synthesize an evidence-based review intelligence report.

Total reviews analyzed: {total_reviews}
Products covered: {len(product_reviews)}

{combined_text}

CRITICAL RULES:
- Every insight MUST trace to actual review text. No inferences, no assumptions.
- market_gaps must come from actual customer language — direct quotes or near-quotes. Do NOT fabricate gaps from what you think customers might want.
- If the sample size is too small for reliable conclusions (< 50 total reviews or < 3 products), flag this prominently and reduce confidence in all findings.
- customer_personas must be grounded in evidence from the reviews. Do not invent personas based on category assumptions.
- For purchase_barriers, distinguish between product-level issues (fixable) and category-level issues (structural — e.g., "all garlic presses are hard to clean").

Look for market gaps ONLY in:
- Features customers explicitly wish existed ("I wish this had...")
- Use cases where current products fail (with specific quotes)
- Complaints that appear across 3+ products with no solution
- Direct customer suggestions and comparisons

Return a JSON object:
{{
    "total_reviews_analyzed": {total_reviews},
    "overall_sentiment": "<positive|mixed|negative>",
    "sentiment_score": <0-100>,
    "data_confidence": "<high|medium|low — based on sample size and review quality>",
    "key_insights": [
        {{
            "insight": "<specific insight with direct evidence from review text>",
            "category": "<quality|feature|price|shipping|packaging>",
            "impact": "<high|medium|low>",
            "products_affected": <number>,
            "evidence": "<quote or paraphrase from actual reviews>",
            "actionable_recommendation": "<specific recommendation — only if feasible>"
        }}
    ],
    "customer_personas": [
        {{
            "persona": "<persona name>",
            "percentage": <estimated % of buyers — mark as approximate>,
            "needs": ["<need 1>", "<need 2>"],
            "price_sensitivity": "<low|medium|high>",
            "brand_loyalty": "<low|medium|high>",
            "evidence": "<what review patterns support this persona>"
        }}
    ],
    "purchase_drivers": ["<why people buy — cite specific review themes with quotes>"],
    "purchase_barriers": ["<why people don't buy or return — cite specific complaints. Flag if structural vs fixable>"],
    "trending_complaints": ["<issues mentioned across 3+ products — include product count>"],
    "market_gaps": ["<specific unmet need with the actual customer language that reveals it. If no genuine gaps found, return empty array — do NOT fabricate>"],
    "best_reviewed_features": [
        {{"feature": "<feature>", "avg_rating_when_mentioned": <rating>}}
    ],
    "worst_reviewed_features": [
        {{"feature": "<feature>", "avg_rating_when_mentioned": <rating>}}
    ]
}}

If there isn't enough data to support a finding, omit it rather than guessing."""

        return await self.llm.generate_json(prompt, max_tokens=8192, system_message=EXPERT_SYSTEM_PROMPT)

    async def analyze_competitive_reviews(
        self,
        competitor_reviews: dict[str, list[dict]],
        niche_keyword: str,
    ) -> dict:
        """
        Analyze reviews across multiple competitors in a niche.

        competitor_reviews: {asin: [reviews]}

        Returns gaps and opportunities across the competitive landscape.
        """
        summaries = []
        for asin, reviews in competitor_reviews.items():
            if reviews:
                summary = f"ASIN {asin}: {len(reviews)} reviews"
                # Include a sample of reviews
                sample = reviews[:20]
                text = self._format_reviews_for_prompt(sample)
                summaries.append(f"{summary}\n{text}")

        combined = "\n\n===\n\n".join(summaries)

        prompt = f"""Analyze reviews across multiple competing products in the "{niche_keyword}" niche on Amazon. Apply skeptical, evidence-based analysis.

{combined}

SCORING RULES FOR opportunity_score:
- High (70-100): Gap is confirmed across 3+ products with significant review volume (50+ reviews each), and the issue is fixable at reasonable manufacturing cost.
- Medium (40-69): Gap appears in 2+ products but either sample size is limited OR the fix is non-trivial.
- Low (0-39): Gap mentioned in only 1 product, or the issue is structural to the category (e.g., "all plastic products feel cheap"), or fixing it would require unreasonable cost.
- Do NOT give high opportunity scores based on a handful of reviews. Statistical significance matters.

Return a JSON object:
{{
    "market_pain_points": [
        {{
            "theme": "<specific pain point common across competitors — concrete, not vague>",
            "affected_products": <number of products with this issue>,
            "total_reviews_mentioning": <approximate count across all products>,
            "severity": "<low|medium|high|critical>",
            "opportunity_score": <0-100, scored per the rules above>,
            "fixable_at_reasonable_cost": <true|false>,
            "fix_complexity": "<simple|moderate|complex>"
        }}
    ],
    "unmet_needs": [
        "<customer need that NO competitor satisfies — must cite actual review language. If none found, return empty array>"
    ],
    "winning_features": [
        "<features consistently praised — these are table stakes, not differentiators>"
    ],
    "differentiation_opportunities": [
        "<specific ways to stand out — each must be achievable in manufacturing and cite the review evidence>"
    ],
    "price_sentiment": "<how customers feel about pricing — are they price-sensitive or quality-first? Cite evidence>",
    "quality_expectations": "<specific quality bar customers expect — materials, durability, finish level>",
    "sample_size_assessment": "<is the review data sufficient for reliable conclusions? How many total reviews across how many products?>"
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)
