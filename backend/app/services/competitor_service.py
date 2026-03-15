"""Competitor analysis service — listing quality, vulnerability detection, competitive landscape."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bsr_regression import bsr_estimator
from app.llm.base_client import BaseLLMClient
from app.models.competitor import Competitor
from app.models.product import Product

logger = logging.getLogger(__name__)


class CompetitorService:
    """
    Analyzes competitors within a niche:
    1. Score listing quality (title, images, bullets, A+, video, backend KW)
    2. Detect vulnerabilities (weak listings, few reviews, poor ratings, etc.)
    3. Compute competitive landscape metrics
    4. Generate LLM-powered competitive analysis
    """

    def __init__(self, db: AsyncSession, llm_client: BaseLLMClient | None = None):
        self.db = db
        self.llm = llm_client

    # ------------------------------------------------------------------
    # 1. Score listing quality
    # ------------------------------------------------------------------
    def score_listing(self, product_data: dict) -> dict:
        """
        Score a product listing's quality across 7 dimensions.
        Each sub-score is 0-100. Weighted average produces overall score.

        product_data should contain keys from the scraper output:
            title, bullet_count, image_count, has_video,
            has_a_plus, has_brand_story, rating, review_count
        """
        scores = {}

        # Title quality (0-100) — length, keyword stuffing, readability
        title = product_data.get("title", "") or ""
        title_len = len(title)
        if 80 <= title_len <= 200:
            scores["title"] = 90
        elif 50 <= title_len < 80:
            scores["title"] = 70
        elif 200 < title_len <= 250:
            scores["title"] = 60
        elif title_len > 250:
            scores["title"] = 30  # Likely keyword stuffed
        else:
            scores["title"] = 40  # Too short

        # Image quality (0-100)
        image_count = product_data.get("image_count") or 0
        if image_count >= 7:
            scores["images"] = 100
        elif image_count >= 5:
            scores["images"] = 80
        elif image_count >= 3:
            scores["images"] = 60
        elif image_count >= 1:
            scores["images"] = 40
        else:
            scores["images"] = 0

        # Bullet points (0-100)
        bullet_count = product_data.get("bullet_count") or 0
        if bullet_count >= 5:
            scores["bullets"] = 100
        elif bullet_count >= 4:
            scores["bullets"] = 80
        elif bullet_count >= 3:
            scores["bullets"] = 60
        elif bullet_count >= 1:
            scores["bullets"] = 40
        else:
            scores["bullets"] = 0

        # A+ content (0-100)
        has_a_plus = product_data.get("has_a_plus", False)
        has_brand_story = product_data.get("has_brand_story", False)
        if has_a_plus and has_brand_story:
            scores["a_plus"] = 100
        elif has_a_plus:
            scores["a_plus"] = 75
        elif has_brand_story:
            scores["a_plus"] = 40
        else:
            scores["a_plus"] = 0

        # Video (0-100)
        has_video = product_data.get("has_video", False)
        scores["video"] = 100 if has_video else 0

        # Backend keywords (estimated — can only fully assess with SP-API)
        # Use title keyword density as proxy
        title_words = len(title.split()) if title else 0
        if title_words >= 15:
            scores["backend_kw"] = 70  # Assume decent if title is keyword-rich
        elif title_words >= 10:
            scores["backend_kw"] = 50
        else:
            scores["backend_kw"] = 30

        # Review strength (not listing quality per se, but impacts competitiveness)
        review_count = product_data.get("review_count") or 0
        rating = product_data.get("rating") or 0
        if review_count >= 1000 and rating >= 4.5:
            scores["reviews"] = 100
        elif review_count >= 500 and rating >= 4.0:
            scores["reviews"] = 80
        elif review_count >= 100 and rating >= 4.0:
            scores["reviews"] = 60
        elif review_count >= 50:
            scores["reviews"] = 40
        elif review_count >= 10:
            scores["reviews"] = 20
        else:
            scores["reviews"] = 0

        # Weighted overall
        weights = {
            "title": 0.15,
            "images": 0.20,
            "bullets": 0.15,
            "a_plus": 0.15,
            "video": 0.10,
            "backend_kw": 0.10,
            "reviews": 0.15,
        }
        overall = sum(scores[k] * weights[k] for k in weights)

        return {
            "overall_score": round(overall, 1),
            "title_score": scores["title"],
            "image_score": scores["images"],
            "bullet_score": scores["bullets"],
            "a_plus_score": scores["a_plus"],
            "video_score": scores["video"],
            "backend_kw_score": scores["backend_kw"],
            "review_score": scores["reviews"],
        }

    # ------------------------------------------------------------------
    # 2. Detect vulnerabilities
    # ------------------------------------------------------------------
    def detect_vulnerabilities(self, product_data: dict, listing_scores: dict) -> dict:
        """
        Identify exploitable weaknesses in a competitor's listing.

        Returns vulnerability level (low/medium/high) and specific types.
        """
        vulnerabilities = []
        severity_scores = []

        # Low review count
        review_count = product_data.get("review_count") or 0
        if review_count < 50:
            vulnerabilities.append("few_reviews")
            severity_scores.append(3)
        elif review_count < 200:
            vulnerabilities.append("moderate_reviews")
            severity_scores.append(1)

        # Poor rating
        rating = product_data.get("rating") or 0
        if rating < 3.5:
            vulnerabilities.append("poor_rating")
            severity_scores.append(3)
        elif rating < 4.0:
            vulnerabilities.append("below_avg_rating")
            severity_scores.append(2)

        # Weak listing
        overall_score = listing_scores.get("overall_score", 0)
        if overall_score < 40:
            vulnerabilities.append("weak_listing")
            severity_scores.append(3)
        elif overall_score < 60:
            vulnerabilities.append("average_listing")
            severity_scores.append(1)

        # No A+ content
        if listing_scores.get("a_plus_score", 0) == 0:
            vulnerabilities.append("no_a_plus")
            severity_scores.append(2)

        # No video
        if listing_scores.get("video_score", 0) == 0:
            vulnerabilities.append("no_video")
            severity_scores.append(1)

        # Few images
        if listing_scores.get("image_score", 0) < 60:
            vulnerabilities.append("few_images")
            severity_scores.append(2)

        # Short bullets
        if listing_scores.get("bullet_score", 0) < 60:
            vulnerabilities.append("weak_bullets")
            severity_scores.append(1)

        # No subscribe & save
        if not product_data.get("subscribe_save", False):
            vulnerabilities.append("no_subscribe_save")
            severity_scores.append(1)

        # Determine overall vulnerability level
        total_severity = sum(severity_scores)
        if total_severity >= 8:
            level = "high"
        elif total_severity >= 4:
            level = "medium"
        elif total_severity >= 1:
            level = "low"
        else:
            level = "none"

        return {
            "vulnerability_level": level,
            "vulnerability_types": vulnerabilities,
            "severity_score": total_severity,
            "exploitable_gaps": [
                v for v in vulnerabilities
                if v in ("few_reviews", "poor_rating", "weak_listing", "no_a_plus", "no_video")
            ],
        }

    # ------------------------------------------------------------------
    # 3. Analyze full competitive landscape
    # ------------------------------------------------------------------
    async def analyze_landscape(
        self,
        niche_id: int,
        products: list[dict],
        category: str,
    ) -> dict:
        """
        Analyze the full competitive landscape for a niche.

        products: list of dicts with scraper data for each competitor product

        Returns aggregated metrics: avg listing quality, market gaps,
        entry difficulty score, etc.
        """
        if not products:
            return self._empty_landscape()

        all_scores = []
        all_vulnerabilities = []
        all_prices = []
        all_reviews = []
        all_ratings = []
        all_bsrs = []

        for p in products:
            scores = self.score_listing(p)
            vulns = self.detect_vulnerabilities(p, scores)

            all_scores.append(scores)
            all_vulnerabilities.append(vulns)

            if p.get("price"):
                all_prices.append(float(p["price"]))
            if p.get("review_count"):
                all_reviews.append(p["review_count"])
            if p.get("rating"):
                all_ratings.append(float(p["rating"]))
            if p.get("current_bsr"):
                all_bsrs.append(p["current_bsr"])

        # Aggregate listing quality
        avg_listing_quality = (
            sum(s["overall_score"] for s in all_scores) / len(all_scores)
        )

        # Count high-vulnerability competitors
        high_vuln_count = sum(
            1 for v in all_vulnerabilities if v["vulnerability_level"] == "high"
        )
        medium_vuln_count = sum(
            1 for v in all_vulnerabilities if v["vulnerability_level"] == "medium"
        )

        # Price analysis
        price_stats = {}
        if all_prices:
            price_stats = {
                "min": round(min(all_prices), 2),
                "max": round(max(all_prices), 2),
                "avg": round(sum(all_prices) / len(all_prices), 2),
                "median": round(sorted(all_prices)[len(all_prices) // 2], 2),
            }

        # Review analysis
        review_stats = {}
        if all_reviews:
            review_stats = {
                "min": min(all_reviews),
                "max": max(all_reviews),
                "avg": round(sum(all_reviews) / len(all_reviews)),
                "median": sorted(all_reviews)[len(all_reviews) // 2],
            }

        # Rating analysis
        rating_stats = {}
        if all_ratings:
            rating_stats = {
                "min": round(min(all_ratings), 1),
                "max": round(max(all_ratings), 1),
                "avg": round(sum(all_ratings) / len(all_ratings), 2),
            }

        # Entry difficulty score (0-100, higher = harder to enter)
        difficulty = self._calculate_entry_difficulty(
            avg_listing_quality, review_stats, rating_stats, len(products),
        )

        # Market opportunity: gaps where we can win
        opportunity_areas = self._identify_opportunities(
            all_scores, all_vulnerabilities, price_stats,
        )

        return {
            "total_competitors": len(products),
            "avg_listing_quality": round(avg_listing_quality, 1),
            "high_vulnerability_count": high_vuln_count,
            "medium_vulnerability_count": medium_vuln_count,
            "price_stats": price_stats,
            "review_stats": review_stats,
            "rating_stats": rating_stats,
            "entry_difficulty_score": difficulty,
            "opportunity_areas": opportunity_areas,
            "competitor_details": [
                {
                    "asin": p.get("asin"),
                    "title": (p.get("title") or "")[:80],
                    "listing_scores": s,
                    "vulnerabilities": v,
                }
                for p, s, v in zip(products, all_scores, all_vulnerabilities)
            ],
        }

    # ------------------------------------------------------------------
    # 4. Save competitor analysis to DB
    # ------------------------------------------------------------------
    async def save_competitor(
        self,
        niche_id: int,
        product_id: int,
        organic_rank: int,
        listing_scores: dict,
        vulnerability_info: dict,
        price_trend: dict | None = None,
        review_velocity: float | None = None,
        sentiment_score: float | None = None,
    ) -> Competitor:
        """Persist competitor analysis to the database."""
        now = datetime.now(timezone.utc)

        # Check for existing
        stmt = select(Competitor).where(
            Competitor.niche_id == niche_id,
            Competitor.product_id == product_id,
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()

        if existing:
            comp = existing
        else:
            comp = Competitor(niche_id=niche_id, product_id=product_id)
            self.db.add(comp)

        comp.organic_rank = organic_rank
        comp.listing_quality_score = Decimal(str(listing_scores.get("overall_score", 0)))
        comp.title_score = Decimal(str(listing_scores.get("title_score", 0)))
        comp.image_score = Decimal(str(listing_scores.get("image_score", 0)))
        comp.bullet_score = Decimal(str(listing_scores.get("bullet_score", 0)))
        comp.a_plus_score = Decimal(str(listing_scores.get("a_plus_score", 0)))
        comp.video_score = Decimal(str(listing_scores.get("video_score", 0)))
        comp.backend_kw_score = Decimal(str(listing_scores.get("backend_kw_score", 0)))

        comp.vulnerability = vulnerability_info.get("vulnerability_level")
        comp.vulnerability_type = ",".join(
            vulnerability_info.get("vulnerability_types", [])[:3]
        )

        if price_trend:
            comp.price_90d_min = Decimal(str(price_trend.get("min_price", 0))) if price_trend.get("min_price") else None
            comp.price_90d_max = Decimal(str(price_trend.get("max_price", 0))) if price_trend.get("max_price") else None
            comp.price_90d_avg = Decimal(str(price_trend.get("avg_price", 0))) if price_trend.get("avg_price") else None

        if review_velocity is not None:
            comp.review_velocity = Decimal(str(review_velocity))
        if sentiment_score is not None:
            comp.sentiment_score = Decimal(str(sentiment_score))

        comp.last_analyzed_at = now
        await self.db.flush()
        return comp

    # ------------------------------------------------------------------
    # 5. LLM-powered competitive insight
    # ------------------------------------------------------------------
    async def generate_competitive_insight(
        self,
        niche_keyword: str,
        landscape: dict,
    ) -> dict:
        """Use LLM to generate strategic competitive insights."""
        if not self.llm:
            return {"error": "LLM client required"}

        # Summarize competitor data for prompt
        competitor_summaries = []
        for c in landscape.get("competitor_details", [])[:15]:
            competitor_summaries.append(
                f"- {c.get('asin')}: Listing={c.get('listing_scores', {}).get('overall_score', 0)}, "
                f"Vuln={c.get('vulnerabilities', {}).get('vulnerability_level', '?')}"
            )

        prompt = f"""Analyze this competitive landscape for the Amazon niche "{niche_keyword}":

MARKET OVERVIEW:
- Total competitors: {landscape.get('total_competitors', 0)}
- Avg listing quality: {landscape.get('avg_listing_quality', 0)}/100
- High vulnerability competitors: {landscape.get('high_vulnerability_count', 0)}
- Entry difficulty: {landscape.get('entry_difficulty_score', 0)}/100
- Price range: ${landscape.get('price_stats', {}).get('min', 0)} - ${landscape.get('price_stats', {}).get('max', 0)} (avg ${landscape.get('price_stats', {}).get('avg', 0)})
- Avg reviews: {landscape.get('review_stats', {}).get('avg', 0)}

COMPETITORS:
{chr(10).join(competitor_summaries)}

OPPORTUNITY AREAS:
{landscape.get('opportunity_areas', [])}

Return a JSON object:
{{
    "market_assessment": "<1-2 sentence market summary>",
    "entry_recommendation": "<enter|cautious|avoid>",
    "entry_reason": "<why enter or avoid>",
    "competitive_strategy": "<recommended competitive positioning>",
    "price_recommendation": {{
        "target_price": <recommended price>,
        "reasoning": "<why this price>"
    }},
    "key_differentiators": [
        "<how to differentiate from competitors>"
    ],
    "weakest_competitors": [
        "<ASINs of most beatable competitors and why>"
    ],
    "biggest_threats": [
        "<ASINs of strongest competitors and why>"
    ],
    "estimated_months_to_page_1": <realistic estimate>,
    "minimum_reviews_needed": <reviews needed to compete>,
    "recommended_launch_budget": <estimated launch budget USD>
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096)

    # ------------------------------------------------------------------
    # 6. Review Velocity Gap analysis
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_review_velocity_gap(
        estimated_monthly_sales: int,
        review_velocity_per_month: float,
    ) -> dict:
        """
        Compare sales volume to review growth to detect opportunity gaps.

        A product selling many units but gaining few reviews signals a
        "lazy" seller or poor follow-up — a goldmine for a new entrant
        who invests in review strategy (Vine, Request-a-Review, inserts).

        Conversely, review velocity that's disproportionately high relative
        to sales suggests grey-hat tactics or heavy Vine usage — a trap.

        Returns:
            gap_ratio: reviews_per_100_sales (lower = bigger opportunity)
            gap_type: "goldmine" | "normal" | "trap"
            opportunity_score: 0-100 (higher = more attractive gap)
        """
        if estimated_monthly_sales <= 0:
            return {
                "gap_ratio": 0,
                "gap_type": "unknown",
                "opportunity_score": 0,
            }

        # Reviews per 100 units sold per month
        gap_ratio = (review_velocity_per_month / estimated_monthly_sales) * 100

        # Typical Amazon organic review rate is ~1-3% of sales
        # < 0.5% = severe under-review = goldmine
        # 0.5-5% = normal range
        # > 5% = suspiciously high = trap
        if gap_ratio < 0.5:
            gap_type = "goldmine"
            opportunity_score = min(100, round(90 - gap_ratio * 100))
        elif gap_ratio <= 5.0:
            gap_type = "normal"
            opportunity_score = round(50 - abs(gap_ratio - 2.0) * 10)
        else:
            gap_type = "trap"
            opportunity_score = max(0, round(20 - (gap_ratio - 5.0) * 5))

        return {
            "gap_ratio": round(gap_ratio, 2),
            "gap_type": gap_type,
            "opportunity_score": max(0, min(100, opportunity_score)),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_entry_difficulty(
        avg_listing_quality: float,
        review_stats: dict,
        rating_stats: dict,
        competitor_count: int,
    ) -> int:
        """Calculate how difficult it is to enter this niche (0-100)."""
        difficulty = 0

        # Listing quality barrier
        if avg_listing_quality >= 80:
            difficulty += 25
        elif avg_listing_quality >= 60:
            difficulty += 15
        else:
            difficulty += 5

        # Review barrier
        avg_reviews = review_stats.get("avg", 0)
        if avg_reviews >= 1000:
            difficulty += 30
        elif avg_reviews >= 500:
            difficulty += 22
        elif avg_reviews >= 200:
            difficulty += 15
        elif avg_reviews >= 50:
            difficulty += 8
        else:
            difficulty += 3

        # Rating barrier
        avg_rating = rating_stats.get("avg", 0)
        if avg_rating >= 4.5:
            difficulty += 20
        elif avg_rating >= 4.0:
            difficulty += 12
        else:
            difficulty += 5

        # Competition density
        if competitor_count >= 50:
            difficulty += 25
        elif competitor_count >= 30:
            difficulty += 18
        elif competitor_count >= 15:
            difficulty += 10
        else:
            difficulty += 5

        return min(100, difficulty)

    @staticmethod
    def _identify_opportunities(
        all_scores: list[dict],
        all_vulnerabilities: list[dict],
        price_stats: dict,
    ) -> list[str]:
        """Identify specific market entry opportunities."""
        opportunities = []

        # Check listing quality gaps
        avg_a_plus = sum(s.get("a_plus_score", 0) for s in all_scores) / max(len(all_scores), 1)
        if avg_a_plus < 50:
            opportunities.append("Most competitors lack A+ content — strong A+ can differentiate")

        avg_video = sum(s.get("video_score", 0) for s in all_scores) / max(len(all_scores), 1)
        if avg_video < 40:
            opportunities.append("Few competitors use video — product video can boost conversion")

        avg_images = sum(s.get("image_score", 0) for s in all_scores) / max(len(all_scores), 1)
        if avg_images < 70:
            opportunities.append("Image quality is generally low — professional photography opportunity")

        # Check vulnerability concentration
        high_vuln_pct = (
            sum(1 for v in all_vulnerabilities if v["vulnerability_level"] == "high")
            / max(len(all_vulnerabilities), 1)
            * 100
        )
        if high_vuln_pct >= 30:
            opportunities.append(f"{high_vuln_pct:.0f}% of competitors are highly vulnerable")

        # Price gap
        if price_stats:
            price_range = price_stats.get("max", 0) - price_stats.get("min", 0)
            avg_price = price_stats.get("avg", 0)
            if avg_price > 0 and price_range / avg_price > 0.5:
                opportunities.append("Wide price range — room for strategic pricing")

        return opportunities

    @staticmethod
    def _empty_landscape() -> dict:
        return {
            "total_competitors": 0,
            "avg_listing_quality": 0,
            "high_vulnerability_count": 0,
            "medium_vulnerability_count": 0,
            "price_stats": {},
            "review_stats": {},
            "rating_stats": {},
            "entry_difficulty_score": 0,
            "opportunity_areas": [],
            "competitor_details": [],
        }
