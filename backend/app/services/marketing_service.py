"""Marketing service — launch playbook generation, channel planning, and budget allocation."""

import logging

from app.llm.base_client import BaseLLMClient, EXPERT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class MarketingService:
    """
    Generates marketing plans and launch playbooks for new Amazon products.

    Capabilities:
    1. Generate launch playbook (week-by-week plan)
    2. Marketing channel recommendations
    3. External traffic strategy
    4. Brand building roadmap
    5. Budget allocation across channels
    """

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    # ------------------------------------------------------------------
    # 1. Generate launch playbook
    # ------------------------------------------------------------------
    async def generate_launch_playbook(
        self,
        niche_keyword: str,
        product_spec: dict,
        ppc_strategy: dict,
        review_strategy: dict,
        financial_summary: dict,
        competitor_landscape: dict | None = None,
    ) -> dict:
        """
        Generate a comprehensive week-by-week launch playbook.

        Integrates PPC, review, and marketing strategies into a
        unified execution plan.
        """
        prompt = f"""Create a realistic 12-week Amazon product launch playbook for a product in the "{niche_keyword}" niche. No hockey-stick projections.

PRODUCT:
- Price: ${product_spec.get('target_price', 0)}
- Key features: {product_spec.get('key_features', [])[:5]}
- Differentiation: {product_spec.get('differentiation_strategy', 'N/A')}

PPC STRATEGY:
- 30-day budget: ${ppc_strategy.get('phases', {}).get('launch', {}).get('monthly_budget', 0)}
- Target ACOS: {ppc_strategy.get('target_acos', 35)}%
- Top keywords: {ppc_strategy.get('top_keywords', [])[:5]}

REVIEW STRATEGY:
- Target reviews: {review_strategy.get('review_threshold', {}).get('threshold', 30)}
- Using Vine: {review_strategy.get('vine_plan', {}).get('recommended', True)}
- Review velocity: {review_strategy.get('review_velocity', {}).get('reviews_per_month', 0)}/month

FINANCIALS:
- Break-even week (base): {financial_summary.get('base', {}).get('break_even_week', 'N/A')}
- Total launch capital: ${financial_summary.get('total_launch_capital', 0)}

LAUNCH REALITY:
- Expect 4-8 weeks to reach consistent daily sales. Week 1-2 will be near-zero organic sales.
- Page 1 ranking for mid-tail keywords takes 3-6 months minimum with consistent PPC and review velocity.
- Do NOT project exponential growth. New Amazon products grow linearly at best, with frequent setbacks (listing suppression, stock-outs, negative reviews).
- Include an explicit "walk away" threshold: at what point should the seller cut losses?
- PPC will be unprofitable for the first 30-60 days. This is expected and should be budgeted for.

Return a JSON object:
{{
    "playbook_name": "<descriptive name — not marketing fluff>",
    "total_budget": <total budget for 12 weeks — be honest about burn>,
    "expected_total_loss_weeks_1_to_4": <how much money the seller will likely lose in the first month>,
    "weeks": [
        {{
            "week": <1-12>,
            "theme": "<weekly focus>",
            "priorities": ["<top 3 priorities>"],
            "ppc_actions": ["<specific PPC actions>"],
            "review_actions": ["<TOS-compliant review actions>"],
            "marketing_actions": ["<external marketing — only if ROI-positive>"],
            "listing_actions": ["<listing optimization>"],
            "kpis": ["<metrics with realistic targets for THIS week>"],
            "budget_allocation": {{
                "ppc": <dollar amount>,
                "marketing": <dollar amount>,
                "other": <dollar amount>
            }},
            "expected_daily_sales": <realistic for this stage>,
            "expected_acos": "<realistic ACOS range for this week>"
        }}
    ],
    "pre_launch_checklist": [
        "<things to have ready before week 1 — include listing quality, inventory, brand registry>"
    ],
    "walk_away_threshold": {{
        "cumulative_loss_limit": <max dollar loss before reconsidering>,
        "weeks_without_improvement": <how many weeks of flat/declining metrics>,
        "min_conversion_rate": <if below this after 30 days with 10+ reviews, reconsider>,
        "action_plan_if_triggered": "<specific steps — liquidate, pivot, or optimize>"
    }},
    "risk_mitigation": [
        {{
            "risk": "<specific risk with probability>",
            "mitigation": "<how to handle it>",
            "trigger": "<when to activate mitigation>",
            "cost_of_mitigation": <estimated cost>
        }}
    ],
    "success_metrics": {{
        "week_4_targets": {{
            "reviews": <target — typically 5-10 with Vine>,
            "daily_sales": <target — typically 2-5 for new listing>,
            "organic_rank": "<realistic — probably not page 1 yet>"
        }},
        "week_8_targets": {{
            "reviews": <target — typically 15-25>,
            "daily_sales": <target — typically 5-10>,
            "organic_rank": "<realistic — maybe page 2-3 for mid-tail>"
        }},
        "week_12_targets": {{
            "reviews": <target — typically 20-40>,
            "daily_sales": <target — typically 8-15>,
            "organic_rank": "<realistic — page 1-2 for long-tail, page 3-5 for main keyword>"
        }}
    }}
}}"""

        return await self.llm.generate_json(prompt, max_tokens=8192, system_message=EXPERT_SYSTEM_PROMPT)

    # ------------------------------------------------------------------
    # 2. Marketing channel recommendations
    # ------------------------------------------------------------------
    async def recommend_channels(
        self,
        niche_keyword: str,
        product_category: str,
        target_audience: str | None = None,
        budget: float = 1000.0,
    ) -> dict:
        """Recommend marketing channels and budget allocation."""
        prompt = f"""Recommend marketing channels for an Amazon product in the "{niche_keyword}" niche. Be honest about what actually works for Amazon sellers.

Category: {product_category}
Target audience: {target_audience or 'General consumers'}
Monthly marketing budget: ${budget}

CHANNEL REALITY FOR AMAZON SELLERS:
- External traffic to Amazon converts at 1-3% typically — much lower than Amazon's native 10-15% conversion rate. Factor this into ROI calculations.
- Influencer ROI is highly uncertain and difficult to attribute. Micro-influencers ($50-200/post) are more cost-effective than macro, but results are unpredictable.
- Social media organic reach takes months to build and has near-zero short-term ROI for product launches. Only recommend if the seller has an existing audience.
- Amazon PPC is almost always the highest-ROI channel for Amazon sellers. External traffic should supplement PPC, not replace it.
- For a ${budget}/month budget, be realistic about what's achievable. ${budget} doesn't go far across multiple channels.

Return a JSON object:
{{
    "channels": [
        {{
            "channel": "<channel name>",
            "platform": "<specific platform>",
            "strategy": "<how to use this channel>",
            "budget_pct": <percentage of budget>,
            "budget_amount": <dollar amount>,
            "expected_roi": "<negative|break_even|low|medium|high — be honest>",
            "confidence_in_roi": "<low|medium|high — how predictable is the return>",
            "difficulty": "<easy|moderate|hard>",
            "time_to_results": "<immediate|1-2 weeks|1-3 months|3-6 months>",
            "tactics": ["<specific tactic>"],
            "realistic_conversion_rate": "<expected conversion rate for this channel to Amazon>"
        }}
    ],
    "total_monthly_budget": {budget},
    "priority_order": ["<channels in order of expected ROI — PPC first unless budget is exhausted>"],
    "channels_to_avoid": [
        {{
            "channel": "<channel>",
            "reason": "<specific reason — not just 'not effective' but why>"
        }}
    ],
    "budget_reality_check": "<is ${budget}/month enough to make a meaningful impact? Be honest.>",
    "external_traffic_bonus": "<Amazon Attribution credit (Brand Referral Bonus ~10%) is the main benefit of external traffic. Explain how this works.>"
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)

    # ------------------------------------------------------------------
    # 3. External traffic strategy
    # ------------------------------------------------------------------
    async def generate_external_traffic_plan(
        self,
        niche_keyword: str,
        product_features: list[str],
        selling_price: float,
        target_daily_external_sessions: int = 50,
    ) -> dict:
        """Generate external traffic strategy to boost Amazon ranking."""
        prompt = f"""Create an external traffic strategy for an Amazon product in the "{niche_keyword}" niche. Be honest about what works and what doesn't.

Product features: {product_features[:5]}
Price: ${selling_price}
Target: {target_daily_external_sessions} daily external sessions to Amazon listing

EXTERNAL TRAFFIC REALITY:
- Most external traffic strategies LOSE MONEY for Amazon sellers when you account for the low conversion rate (1-3% vs Amazon's native 10-15%).
- The main benefit of external traffic is the Amazon Brand Referral Bonus (~10% referral fee credit) and the ranking signal — not direct profitability.
- Only recommend channels with measurable ROI via Amazon Attribution. If ROI can't be tracked, flag it as high-risk spend.
- Social media organic reach takes 3-6 months to build. It is NOT a launch strategy.
- Influencer marketing is unpredictable. Most influencer campaigns for Amazon products break even at best. Budget for testing, not scaling.
- {target_daily_external_sessions} daily sessions is ambitious. Be honest about achievable numbers for the budget.

Return a JSON object:
{{
    "strategies": [
        {{
            "source": "<traffic source>",
            "method": "<specific method>",
            "estimated_daily_sessions": <realistic number>,
            "cost_per_session": <estimated cost>,
            "expected_conversion_rate": <realistic % — typically 1-3% for external traffic>,
            "expected_cost_per_sale": <cost per session / conversion rate>,
            "profitable": <true|false — does cost per sale leave margin after product costs?>,
            "setup_steps": ["<step-by-step setup>"],
            "content_needed": ["<content to create>"],
            "amazon_attribution_compatible": <true|false>,
            "time_intensive": <true|false — flag channels requiring significant ongoing time>
        }}
    ],
    "social_media_plan": {{
        "platforms": ["<best platforms for this niche>"],
        "honest_assessment": "<is social media worth it for this product at this stage? Often the answer is no for launch.>",
        "content_calendar": [
            {{
                "day": "<day of week>",
                "content_type": "<type>",
                "topic_idea": "<specific idea>"
            }}
        ],
        "hashtag_strategy": ["<relevant hashtags>"],
        "months_to_meaningful_traffic": <realistic estimate — typically 3-6>
    }},
    "influencer_strategy": {{
        "influencer_type": "<micro|mid|macro — micro recommended for Amazon products>",
        "budget_per_influencer": <amount>,
        "number_of_influencers": <count>,
        "outreach_template_theme": "<what to say>",
        "expected_roi": "<honest assessment — most campaigns break even at best>",
        "recommendation": "<is influencer marketing worth it at this budget level?>"
    }},
    "amazon_attribution_tips": [
        "<how to use Amazon Attribution for tracking — this is essential for all external traffic>"
    ],
    "estimated_total_monthly_cost": <amount>,
    "estimated_monthly_external_sessions": <realistic number>,
    "estimated_monthly_sales_from_external": <sessions * conversion rate>,
    "honest_recommendation": "<should the seller focus on PPC instead? For most new sellers, the answer is yes.>"
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)

    # ------------------------------------------------------------------
    # 4. Brand building roadmap
    # ------------------------------------------------------------------
    async def generate_brand_roadmap(
        self,
        niche_keyword: str,
        brand_name: str | None = None,
        product_count_target: int = 3,
        timeline_months: int = 12,
    ) -> dict:
        """Generate a brand building roadmap for Amazon."""
        prompt = f"""Create a {timeline_months}-month brand building roadmap for an Amazon brand in the "{niche_keyword}" niche. Be realistic about timelines and investment.

Brand name: {brand_name or 'TBD'}
Target product count: {product_count_target} products in {timeline_months} months

BRAND BUILDING REALITY:
- Most Amazon brands are single-product for 12-18 months. Do NOT plan a multi-product line unless the financials of product #1 are proven (consistent profitability for 3+ months).
- Product #2 should only launch after product #1 has: 50+ reviews, 4.0+ rating, positive monthly profit, and stable supply chain.
- Brand building on Amazon is primarily about product quality and reviews, not traditional branding (logos, social media, etc.). A $500 logo doesn't sell units.
- If the target of {product_count_target} products in {timeline_months} months is unrealistic given typical development timelines (3-6 months per product from sourcing to live), say so.

Return a JSON object:
{{
    "brand_strategy": {{
        "positioning": "<brand positioning — keep it simple, differentiation matters more than storytelling>",
        "target_audience": "<target customer based on review data>",
        "value_proposition": "<core value proposition>",
        "brand_voice": "<brand communication style>"
    }},
    "reality_check": {{
        "is_multi_product_realistic": <true|false — be honest>,
        "recommended_product_count": <realistic number for {timeline_months} months>,
        "reasoning": "<why this is the realistic target>"
    }},
    "milestones": [
        {{
            "month": <month number>,
            "milestone": "<key milestone>",
            "actions": ["<specific actions>"],
            "investment": <estimated cost>,
            "prerequisite": "<what must be true before this milestone makes sense>"
        }}
    ],
    "product_line_expansion": [
        {{
            "product_number": <1-N>,
            "launch_month": <month — earliest realistic>,
            "product_concept": "<what to launch>",
            "reason": "<why this product next>",
            "prerequisite": "<product #1 metrics that must be achieved first>",
            "estimated_development_cost": <sourcing + samples + tooling + first order>
        }}
    ],
    "brand_assets_needed": [
        {{
            "asset": "<brand asset>",
            "priority": "<high|medium|low>",
            "estimated_cost": <cost>,
            "when_needed": "<month or phase>",
            "roi_justification": "<why this asset is worth the cost>"
        }}
    ],
    "total_12_month_investment": <total realistic investment>,
    "investment_breakdown": {{
        "inventory": <total inventory investment>,
        "ppc": <total PPC spend>,
        "branding_assets": <logos, photography, A+ content>,
        "marketing": <external marketing>,
        "other": <samples, inspections, etc.>
    }}
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)

    # ------------------------------------------------------------------
    # 5. Combine into full marketing report
    # ------------------------------------------------------------------
    async def generate_full_marketing_plan(
        self,
        niche_keyword: str,
        product_spec: dict,
        ppc_strategy: dict,
        review_strategy: dict,
        financial_summary: dict,
        budget: float = 1000.0,
    ) -> dict:
        """Generate a complete marketing plan combining all components."""
        result = {}

        # Launch playbook
        try:
            result["launch_playbook"] = await self.generate_launch_playbook(
                niche_keyword, product_spec, ppc_strategy,
                review_strategy, financial_summary,
            )
        except Exception as e:
            logger.warning("Launch playbook generation failed: %s", e)
            result["launch_playbook"] = None

        # Channel recommendations
        try:
            result["channels"] = await self.recommend_channels(
                niche_keyword,
                product_spec.get("category", "General"),
                budget=budget,
            )
        except Exception as e:
            logger.warning("Channel recommendation failed: %s", e)
            result["channels"] = None

        # External traffic
        try:
            result["external_traffic"] = await self.generate_external_traffic_plan(
                niche_keyword,
                [f.get("feature", "") for f in product_spec.get("key_features", [])[:5]],
                product_spec.get("target_price", 0),
            )
        except Exception as e:
            logger.warning("External traffic plan failed: %s", e)
            result["external_traffic"] = None

        return result
