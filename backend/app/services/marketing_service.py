"""Marketing service — launch playbook generation, channel planning, and budget allocation."""

import logging

from app.llm.base_client import BaseLLMClient

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
        prompt = f"""Create a detailed 12-week Amazon product launch playbook for a product in the "{niche_keyword}" niche.

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

Return a JSON object:
{{
    "playbook_name": "<catchy name for this launch plan>",
    "total_budget": <total budget for 12 weeks>,
    "weeks": [
        {{
            "week": <1-12>,
            "theme": "<weekly focus theme>",
            "priorities": ["<top 3 priorities>"],
            "ppc_actions": ["<specific PPC actions>"],
            "review_actions": ["<review acquisition actions>"],
            "marketing_actions": ["<external marketing actions>"],
            "listing_actions": ["<listing optimization actions>"],
            "kpis": ["<metrics to track this week>"],
            "budget_allocation": {{
                "ppc": <dollar amount>,
                "marketing": <dollar amount>,
                "other": <dollar amount>
            }}
        }}
    ],
    "pre_launch_checklist": [
        "<things to have ready before week 1>"
    ],
    "risk_mitigation": [
        {{
            "risk": "<potential risk>",
            "mitigation": "<how to handle it>",
            "trigger": "<when to activate mitigation>"
        }}
    ],
    "success_metrics": {{
        "week_4_targets": {{
            "reviews": <target>,
            "daily_sales": <target>,
            "organic_rank": <target>
        }},
        "week_8_targets": {{
            "reviews": <target>,
            "daily_sales": <target>,
            "organic_rank": <target>
        }},
        "week_12_targets": {{
            "reviews": <target>,
            "daily_sales": <target>,
            "organic_rank": <target>
        }}
    }}
}}"""

        return await self.llm.generate_json(prompt, max_tokens=8192)

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
        prompt = f"""Recommend the best marketing channels for an Amazon product in the "{niche_keyword}" niche.

Category: {product_category}
Target audience: {target_audience or 'General consumers'}
Monthly marketing budget: ${budget}

Return a JSON object:
{{
    "channels": [
        {{
            "channel": "<channel name>",
            "platform": "<specific platform>",
            "strategy": "<how to use this channel>",
            "budget_pct": <percentage of budget>,
            "budget_amount": <dollar amount>,
            "expected_roi": "<low|medium|high>",
            "difficulty": "<easy|moderate|hard>",
            "time_to_results": "<immediate|1-2 weeks|1-3 months>",
            "tactics": ["<specific tactic>"]
        }}
    ],
    "total_monthly_budget": {budget},
    "priority_order": ["<channels in order of priority>"],
    "channels_to_avoid": [
        {{
            "channel": "<channel>",
            "reason": "<why to avoid>"
        }}
    ],
    "external_traffic_bonus": "<how external traffic helps Amazon ranking>"
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096)

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
        prompt = f"""Create an external traffic strategy for an Amazon product in the "{niche_keyword}" niche.

Product features: {product_features[:5]}
Price: ${selling_price}
Target: {target_daily_external_sessions} daily external sessions to Amazon listing

Return a JSON object:
{{
    "strategies": [
        {{
            "source": "<traffic source>",
            "method": "<specific method>",
            "estimated_daily_sessions": <number>,
            "cost_per_session": <estimated cost>,
            "setup_steps": ["<step-by-step setup>"],
            "content_needed": ["<content to create>"],
            "amazon_attribution_compatible": <true|false>
        }}
    ],
    "social_media_plan": {{
        "platforms": ["<best platforms for this niche>"],
        "content_calendar": [
            {{
                "day": "<day of week>",
                "content_type": "<type>",
                "topic_idea": "<specific idea>"
            }}
        ],
        "hashtag_strategy": ["<relevant hashtags>"]
    }},
    "influencer_strategy": {{
        "influencer_type": "<micro|mid|macro>",
        "budget_per_influencer": <amount>,
        "number_of_influencers": <count>,
        "outreach_template_theme": "<what to say>"
    }},
    "amazon_attribution_tips": [
        "<how to use Amazon Attribution for tracking>"
    ],
    "estimated_total_monthly_cost": <amount>,
    "estimated_monthly_external_sessions": <number>
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096)

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
        prompt = f"""Create a {timeline_months}-month brand building roadmap for an Amazon brand in the "{niche_keyword}" niche.

Brand name: {brand_name or 'TBD'}
Target product count: {product_count_target} products in {timeline_months} months

Return a JSON object:
{{
    "brand_strategy": {{
        "positioning": "<brand positioning statement>",
        "target_audience": "<detailed target customer profile>",
        "value_proposition": "<core value proposition>",
        "brand_voice": "<brand communication style>"
    }},
    "milestones": [
        {{
            "month": <month number>,
            "milestone": "<key milestone>",
            "actions": ["<specific actions>"],
            "investment": <estimated cost>
        }}
    ],
    "product_line_expansion": [
        {{
            "product_number": <1-N>,
            "launch_month": <month>,
            "product_concept": "<what to launch>",
            "reason": "<why this product next>"
        }}
    ],
    "brand_assets_needed": [
        {{
            "asset": "<brand asset>",
            "priority": "<high|medium|low>",
            "estimated_cost": <cost>,
            "when_needed": "<month or phase>"
        }}
    ],
    "total_12_month_investment": <total estimated investment>
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096)

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
