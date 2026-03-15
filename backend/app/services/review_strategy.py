"""Review strategy service — Vine enrollment, review velocity, and launch review plan."""

import logging
import math

from app.llm.base_client import BaseLLMClient

logger = logging.getLogger(__name__)

# Amazon Vine costs (approximate, per unit)
VINE_COST_PER_UNIT = 200.0  # Vine enrollment fee
VINE_MAX_UNITS = 30  # Max Vine units per enrollment


class ReviewStrategyService:
    """
    Plans review acquisition strategy for new product launches.

    Capabilities:
    1. Calculate review threshold needed to compete
    2. Vine enrollment planning and ROI
    3. Review velocity estimation
    4. Timeline to review targets
    5. LLM-powered review strategy
    """

    def __init__(self, llm_client: BaseLLMClient | None = None):
        self.llm = llm_client

    # ------------------------------------------------------------------
    # 1. Calculate review threshold
    # ------------------------------------------------------------------
    def calculate_review_threshold(
        self,
        competitor_reviews: list[int],
        target_percentile: float = 0.3,
    ) -> dict:
        """
        Determine minimum reviews needed to compete.

        Target: reach the review count of the bottom 30th percentile
        of successful competitors (those ranking on page 1).
        """
        if not competitor_reviews:
            return {
                "threshold": 15,
                "strategy": "minimal",
                "reasoning": "No competitor data — default minimum of 15 reviews",
            }

        sorted_reviews = sorted(competitor_reviews)
        idx = max(0, int(len(sorted_reviews) * target_percentile) - 1)
        threshold = sorted_reviews[idx]

        # Apply minimum floor
        threshold = max(15, threshold)

        # Determine strategy tier
        if threshold <= 30:
            strategy = "vine_only"
            reasoning = f"Low bar ({threshold} reviews). Vine enrollment alone should suffice."
        elif threshold <= 100:
            strategy = "vine_plus_organic"
            reasoning = f"Moderate bar ({threshold} reviews). Use Vine + organic velocity."
        elif threshold <= 500:
            strategy = "aggressive"
            reasoning = f"High bar ({threshold} reviews). Need Vine + inserts + follow-ups + time."
        else:
            strategy = "long_game"
            reasoning = f"Very high bar ({threshold} reviews). This is a long-term play (6-12+ months)."

        avg_reviews = round(sum(competitor_reviews) / len(competitor_reviews))
        median_reviews = sorted_reviews[len(sorted_reviews) // 2]

        return {
            "threshold": threshold,
            "strategy": strategy,
            "reasoning": reasoning,
            "competitor_stats": {
                "min_reviews": sorted_reviews[0],
                "max_reviews": sorted_reviews[-1],
                "avg_reviews": avg_reviews,
                "median_reviews": median_reviews,
                "p30_reviews": threshold,
            },
        }

    # ------------------------------------------------------------------
    # 2. Vine enrollment planning
    # ------------------------------------------------------------------
    def plan_vine_enrollment(
        self,
        product_cost: float,
        selling_price: float,
        target_reviews: int = 30,
    ) -> dict:
        """
        Plan Amazon Vine enrollment strategy.

        Vine provides up to 30 free units to Vine Voice reviewers.
        Cost: enrollment fee + product cost + FBA fees for each unit.
        Expected review rate: ~80% of Vine recipients leave reviews.
        """
        vine_units = min(target_reviews, VINE_MAX_UNITS)
        vine_review_rate = 0.80
        expected_vine_reviews = round(vine_units * vine_review_rate)

        # Costs
        product_cost_total = vine_units * product_cost
        enrollment_fee = VINE_COST_PER_UNIT  # One-time fee
        fba_fee_estimate = vine_units * 3.50  # Approximate FBA fee per unit
        total_vine_cost = enrollment_fee + product_cost_total + fba_fee_estimate

        # ROI: value of reviews (each review ~ $50-100 in equivalent ad spend)
        review_value = expected_vine_reviews * 75  # $75 per review equivalent
        vine_roi = ((review_value - total_vine_cost) / total_vine_cost * 100) if total_vine_cost > 0 else 0

        return {
            "vine_units": vine_units,
            "expected_reviews": expected_vine_reviews,
            "vine_review_rate": vine_review_rate,
            "costs": {
                "enrollment_fee": enrollment_fee,
                "product_cost_total": round(product_cost_total, 2),
                "fba_fee_estimate": round(fba_fee_estimate, 2),
                "total_vine_cost": round(total_vine_cost, 2),
            },
            "estimated_review_value": round(review_value, 2),
            "vine_roi_pct": round(vine_roi, 1),
            "recommended": total_vine_cost < selling_price * 100,  # Worth it if < 100 units of revenue
            "timeline_days": 30,  # Vine reviews typically arrive within 30 days
        }

    # ------------------------------------------------------------------
    # 3. Review velocity estimation
    # ------------------------------------------------------------------
    def estimate_review_velocity(
        self,
        monthly_sales: int,
        category: str = "default",
    ) -> dict:
        """
        Estimate organic review velocity based on sales volume.

        Amazon review rate varies by category:
        - Electronics: ~1-2% of buyers leave reviews
        - Home & Kitchen: ~2-3%
        - Beauty: ~3-5%
        - Average: ~2%
        """
        review_rates = {
            "electronics": 0.015,
            "home": 0.025,
            "kitchen": 0.025,
            "beauty": 0.04,
            "health": 0.03,
            "sports": 0.02,
            "toys": 0.03,
            "pet": 0.035,
            "baby": 0.03,
            "default": 0.02,
        }

        rate = review_rates.get(category.lower().split("&")[0].strip(), review_rates["default"])

        monthly_reviews = monthly_sales * rate
        weekly_reviews = monthly_reviews / 4.33
        daily_reviews = monthly_reviews / 30

        return {
            "monthly_sales": monthly_sales,
            "review_rate": rate,
            "reviews_per_month": round(monthly_reviews, 1),
            "reviews_per_week": round(weekly_reviews, 1),
            "reviews_per_day": round(daily_reviews, 2),
            "reviews_per_year": round(monthly_reviews * 12),
            "category": category,
        }

    # ------------------------------------------------------------------
    # 4. Timeline to review targets
    # ------------------------------------------------------------------
    def calculate_review_timeline(
        self,
        target_reviews: int,
        monthly_sales: int,
        category: str = "default",
        use_vine: bool = True,
        vine_units: int = 30,
    ) -> dict:
        """
        Calculate weeks to reach review targets with different strategies.
        """
        velocity = self.estimate_review_velocity(monthly_sales, category)
        monthly_organic = velocity["reviews_per_month"]

        # Strategy 1: Organic only
        if monthly_organic > 0:
            months_organic = target_reviews / monthly_organic
            weeks_organic = months_organic * 4.33
        else:
            weeks_organic = float("inf")

        # Strategy 2: Vine + Organic
        vine_reviews = round(vine_units * 0.80) if use_vine else 0
        remaining_after_vine = max(0, target_reviews - vine_reviews)

        if monthly_organic > 0:
            months_vine_organic = remaining_after_vine / monthly_organic
            weeks_vine_organic = months_vine_organic * 4.33 + 4  # +4 weeks for Vine delivery
        else:
            weeks_vine_organic = 4 if vine_reviews >= target_reviews else float("inf")

        # Strategy 3: Vine + Request a Review button (adds ~10-20% more reviews)
        enhanced_monthly = monthly_organic * 1.15  # 15% boost from follow-ups
        remaining_enhanced = max(0, target_reviews - vine_reviews)

        if enhanced_monthly > 0:
            months_enhanced = remaining_enhanced / enhanced_monthly
            weeks_enhanced = months_enhanced * 4.33 + 4
        else:
            weeks_enhanced = 4 if vine_reviews >= target_reviews else float("inf")

        return {
            "target_reviews": target_reviews,
            "organic_review_velocity": round(monthly_organic, 1),
            "strategies": {
                "organic_only": {
                    "weeks_to_target": round(weeks_organic, 1) if weeks_organic != float("inf") else None,
                    "description": "Rely purely on organic review velocity",
                },
                "vine_plus_organic": {
                    "weeks_to_target": round(weeks_vine_organic, 1) if weeks_vine_organic != float("inf") else None,
                    "vine_reviews": vine_reviews,
                    "remaining_organic": remaining_after_vine,
                    "description": f"Vine ({vine_reviews} reviews) + organic velocity",
                },
                "vine_plus_enhanced": {
                    "weeks_to_target": round(weeks_enhanced, 1) if weeks_enhanced != float("inf") else None,
                    "vine_reviews": vine_reviews,
                    "remaining_enhanced": remaining_enhanced,
                    "description": "Vine + Request a Review + product inserts",
                },
            },
            "recommended_strategy": (
                "vine_plus_enhanced" if target_reviews > 30
                else "vine_plus_organic" if target_reviews > 10
                else "organic_only"
            ),
        }

    # ------------------------------------------------------------------
    # 5. Full review strategy report
    # ------------------------------------------------------------------
    async def generate_review_strategy(
        self,
        niche_keyword: str,
        competitor_reviews: list[int],
        monthly_sales_estimate: int,
        product_cost: float,
        selling_price: float,
        category: str = "default",
    ) -> dict:
        """Generate a comprehensive review strategy combining all analyses."""
        # Calculate all components
        threshold = self.calculate_review_threshold(competitor_reviews)
        vine_plan = self.plan_vine_enrollment(
            product_cost, selling_price, min(threshold["threshold"], 30)
        )
        velocity = self.estimate_review_velocity(monthly_sales_estimate, category)
        timeline = self.calculate_review_timeline(
            threshold["threshold"], monthly_sales_estimate, category
        )

        result = {
            "review_threshold": threshold,
            "vine_plan": vine_plan,
            "review_velocity": velocity,
            "timeline": timeline,
        }

        # Add LLM strategy if available
        if self.llm:
            try:
                llm_strategy = await self._generate_llm_strategy(
                    niche_keyword, threshold, vine_plan, velocity, timeline
                )
                result["llm_strategy"] = llm_strategy
            except Exception as e:
                logger.warning("LLM review strategy generation failed: %s", e)
                result["llm_strategy"] = None

        return result

    async def _generate_llm_strategy(
        self,
        niche_keyword: str,
        threshold: dict,
        vine_plan: dict,
        velocity: dict,
        timeline: dict,
    ) -> dict:
        """Generate LLM-powered review strategy recommendations."""
        prompt = f"""Create a review acquisition strategy for a new Amazon product launch in the "{niche_keyword}" niche.

DATA:
- Target reviews needed: {threshold['threshold']}
- Strategy tier: {threshold['strategy']}
- Vine plan: {vine_plan['vine_units']} units, expected {vine_plan['expected_reviews']} reviews
- Organic velocity: {velocity['reviews_per_month']} reviews/month
- Fastest timeline: {timeline['strategies']['vine_plus_enhanced']['weeks_to_target']} weeks

Return a JSON object:
{{
    "week_by_week_plan": [
        {{
            "week": "<week range>",
            "target_review_count": <cumulative target>,
            "actions": ["<specific action>"],
            "expected_new_reviews": <count>
        }}
    ],
    "product_insert_strategy": {{
        "recommended": <true|false>,
        "message_theme": "<what the insert should communicate>",
        "compliance_notes": ["<Amazon TOS compliance reminders>"]
    }},
    "early_reviewer_tactics": [
        "<legitimate tactic to encourage reviews>"
    ],
    "review_quality_tips": [
        "<how to get higher quality/more detailed reviews>"
    ],
    "negative_review_mitigation": [
        "<how to handle/prevent negative reviews>"
    ],
    "total_estimated_cost": <total cost of review strategy>,
    "risk_assessment": "<low|medium|high risk of review strategy failing>"
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096)
