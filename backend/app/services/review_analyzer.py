"""LLM-powered review analysis: sentiment scoring, pain point clustering, opportunity detection."""

import logging
from app.llm.base_client import BaseLLMClient
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

        prompt = f"""Analyze these Amazon product reviews for "{product_title}" in the "{category}" category.

REVIEWS:
{reviews_text}

Return a JSON object with EXACTLY this structure:
{{
    "sentiment_score": <0-100, where 100 is perfectly positive>,
    "pain_points": [
        {{
            "theme": "<pain point theme>",
            "frequency": <number of reviews mentioning this>,
            "severity": "<low|medium|high|critical>",
            "sample_quotes": ["<direct quote 1>", "<direct quote 2>"]
        }}
    ],
    "positive_themes": [
        {{
            "theme": "<positive theme>",
            "frequency": <number of reviews mentioning this>,
            "sample_quotes": ["<direct quote 1>", "<direct quote 2>"]
        }}
    ],
    "improvement_opportunities": [
        "<specific product improvement suggestion based on negative feedback>"
    ],
    "review_quality_score": <0-100, based on detail, verified purchase %, helpfulness>,
    "fake_review_risk": <0-100, based on generic language, timing patterns, suspicious patterns>,
    "common_use_cases": ["<how customers actually use this product>"],
    "competitor_mentions": ["<any competitor products mentioned in reviews>"]
}}

Focus on actionable insights. Group similar complaints into themes. Be specific about improvement opportunities."""

        result = await self.llm.generate_json(prompt, max_tokens=4096)
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

        return await self.llm.generate_json(prompt, max_tokens=4096)

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

        prompt = f"""Analyze reviews across multiple competing products in the "{niche_keyword}" niche on Amazon.

{combined}

Return a JSON object:
{{
    "market_pain_points": [
        {{
            "theme": "<pain point common across competitors>",
            "affected_products": <number of products with this issue>,
            "severity": "<low|medium|high|critical>",
            "opportunity_score": <0-100, how exploitable is this gap>
        }}
    ],
    "unmet_needs": [
        "<customer need that NO competitor is satisfying well>"
    ],
    "winning_features": [
        "<features that get consistently praised across products>"
    ],
    "differentiation_opportunities": [
        "<specific ways a new product could stand out>"
    ],
    "price_sentiment": "<how customers feel about pricing in this niche>",
    "quality_expectations": "<what quality level customers expect>"
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096)
