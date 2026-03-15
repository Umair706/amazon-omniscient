"""PPC (Pay-Per-Click) advertising service — bid optimization, ACOS projections, budget planning."""

import logging
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LLMError
from app.llm.base_client import BaseLLMClient
from app.models.keyword import NicheKeyword, PPCKeyword

logger = logging.getLogger(__name__)


class PPCService:
    """
    Amazon PPC advertising intelligence:
    1. Estimate CPC/ACOS from keyword data
    2. Build keyword portfolios (exact, phrase, broad)
    3. Budget planning (30-day, 90-day)
    4. Break-even ACOS calculation
    5. LLM-powered PPC strategy generation
    """

    def __init__(self, db: AsyncSession, llm_client: BaseLLMClient | None = None):
        self.db = db
        self.llm = llm_client

    # ------------------------------------------------------------------
    # 1. Calculate break-even ACOS
    # ------------------------------------------------------------------
    def calculate_break_even_acos(
        self,
        selling_price: float,
        landed_cost: float,
        fba_fees: float,
        referral_fee_pct: float = 0.15,
    ) -> dict:
        """
        Calculate the break-even ACOS (Advertising Cost of Sales).

        Break-even ACOS = (Selling Price - All Costs) / Selling Price * 100

        Above this ACOS, you lose money on every ad-driven sale.
        """
        referral_fee = selling_price * referral_fee_pct
        total_costs = landed_cost + fba_fees + referral_fee
        profit_before_ads = selling_price - total_costs

        break_even_acos = (profit_before_ads / selling_price * 100) if selling_price > 0 else 0
        target_acos = break_even_acos * 0.7  # Target 70% of break-even for profit

        return {
            "selling_price": round(selling_price, 2),
            "total_costs": round(total_costs, 2),
            "profit_before_ads": round(profit_before_ads, 2),
            "break_even_acos": round(max(0, break_even_acos), 1),
            "target_acos": round(max(0, target_acos), 1),
            "is_viable": break_even_acos > 15,  # Minimum viable ACOS margin
        }

    # ------------------------------------------------------------------
    # 2. Build keyword portfolio
    # ------------------------------------------------------------------
    async def build_keyword_portfolio(
        self,
        niche_id: int,
        max_keywords: int = 100,
    ) -> dict:
        """
        Build a PPC keyword portfolio from niche keyword data.
        Classifies keywords into campaigns: exact, phrase, broad.
        """
        # Get niche keywords sorted by relevance and search volume
        stmt = (
            select(NicheKeyword)
            .where(NicheKeyword.niche_id == niche_id)
            .order_by(
                NicheKeyword.relevance_score.desc().nulls_last(),
                NicheKeyword.search_volume.desc().nulls_last(),
            )
            .limit(max_keywords)
        )
        result = await self.db.execute(stmt)
        keywords = result.scalars().all()

        if not keywords:
            return self._empty_portfolio()

        # Classify keywords
        exact_match = []
        phrase_match = []
        broad_match = []
        negative_candidates = []

        for kw in keywords:
            sv = kw.search_volume or 0
            relevance = float(kw.relevance_score or 0)
            cpc = float(kw.avg_cpc or 0)
            competition = kw.competition_level or "medium"

            keyword_data = {
                "keyword": kw.keyword,
                "search_volume": sv,
                "avg_cpc": cpc,
                "competition": competition,
                "relevance_score": relevance,
            }

            # High relevance + decent volume → exact match
            if relevance >= 70 and sv >= 500:
                exact_match.append(keyword_data)
            # Medium relevance or lower volume → phrase match
            elif relevance >= 40 and sv >= 100:
                phrase_match.append(keyword_data)
            # Everything else → broad match (discovery)
            elif relevance >= 20:
                broad_match.append(keyword_data)
            # Very low relevance → potential negative
            else:
                negative_candidates.append(keyword_data)

        # Calculate estimated metrics
        total_daily_spend = sum(
            k["avg_cpc"] * min(k["search_volume"] / 30 * 0.03, 50)  # Est. 3% CTR, cap at 50 clicks
            for k in exact_match + phrase_match
        )

        return {
            "exact_match": exact_match,
            "phrase_match": phrase_match,
            "broad_match": broad_match,
            "negative_candidates": negative_candidates,
            "total_keywords": len(exact_match) + len(phrase_match) + len(broad_match),
            "estimated_daily_spend": round(total_daily_spend, 2),
            "estimated_monthly_spend": round(total_daily_spend * 30, 2),
        }

    # ------------------------------------------------------------------
    # 3. Budget planning
    # ------------------------------------------------------------------
    def plan_budget(
        self,
        keyword_portfolio: dict,
        target_acos: float,
        selling_price: float,
        conversion_rate: float = 0.10,
        daily_budget_cap: float = 50.0,
    ) -> dict:
        """
        Plan PPC budgets for launch (aggressive) and steady-state (optimized).

        Launch phase: 30 days aggressive spending to gain rank
        Growth phase: 31-90 days moderate spending
        Steady state: 91+ days optimized for profit
        """
        avg_cpc = 0
        total_keywords = keyword_portfolio.get("total_keywords", 0)

        all_keywords = (
            keyword_portfolio.get("exact_match", [])
            + keyword_portfolio.get("phrase_match", [])
            + keyword_portfolio.get("broad_match", [])
        )

        if all_keywords:
            avg_cpc = sum(k.get("avg_cpc", 0) for k in all_keywords) / len(all_keywords)

        # Launch phase (days 1-30): aggressive, 1.5x normal spend
        launch_daily = min(daily_budget_cap * 1.5, daily_budget_cap * 2)
        launch_clicks_per_day = launch_daily / max(avg_cpc, 0.5)
        launch_orders_per_day = launch_clicks_per_day * conversion_rate
        launch_revenue_per_day = launch_orders_per_day * selling_price
        launch_acos = (launch_daily / max(launch_revenue_per_day, 0.01)) * 100

        # Growth phase (days 31-90): moderate
        growth_daily = daily_budget_cap
        growth_clicks = growth_daily / max(avg_cpc, 0.5)
        growth_orders = growth_clicks * min(conversion_rate * 1.2, 0.20)  # Improved CVR
        growth_revenue = growth_orders * selling_price
        growth_acos = (growth_daily / max(growth_revenue, 0.01)) * 100

        # Steady state (91+): optimized
        steady_daily = daily_budget_cap * 0.6
        steady_clicks = steady_daily / max(avg_cpc * 0.85, 0.5)  # Lower CPC with optimization
        steady_orders = steady_clicks * min(conversion_rate * 1.5, 0.25)  # Better CVR
        steady_revenue = steady_orders * selling_price
        steady_acos = (steady_daily / max(steady_revenue, 0.01)) * 100

        return {
            "avg_cpc": round(avg_cpc, 2),
            "total_keywords": total_keywords,
            "target_acos": target_acos,
            "phases": {
                "launch": {
                    "days": "1-30",
                    "daily_budget": round(launch_daily, 2),
                    "monthly_budget": round(launch_daily * 30, 2),
                    "estimated_daily_clicks": round(launch_clicks_per_day),
                    "estimated_daily_orders": round(launch_orders_per_day, 1),
                    "estimated_acos": round(launch_acos, 1),
                    "strategy": "Aggressive: bid high on exact match, run auto campaigns for discovery",
                },
                "growth": {
                    "days": "31-90",
                    "daily_budget": round(growth_daily, 2),
                    "monthly_budget": round(growth_daily * 30, 2),
                    "estimated_daily_clicks": round(growth_clicks),
                    "estimated_daily_orders": round(growth_orders, 1),
                    "estimated_acos": round(growth_acos, 1),
                    "strategy": "Moderate: optimize bids, negate poor performers, scale winners",
                },
                "steady_state": {
                    "days": "91+",
                    "daily_budget": round(steady_daily, 2),
                    "monthly_budget": round(steady_daily * 30, 2),
                    "estimated_daily_clicks": round(steady_clicks),
                    "estimated_daily_orders": round(steady_orders, 1),
                    "estimated_acos": round(steady_acos, 1),
                    "strategy": "Optimized: focus on profitable keywords, lower bids, increase organic",
                },
            },
            "total_90_day_budget": round(launch_daily * 30 + growth_daily * 60, 2),
            "total_180_day_budget": round(
                launch_daily * 30 + growth_daily * 60 + steady_daily * 90, 2
            ),
        }

    # ------------------------------------------------------------------
    # 4. Save PPC keywords to DB
    # ------------------------------------------------------------------
    async def save_ppc_keywords(
        self,
        niche_id: int,
        keyword_portfolio: dict,
    ) -> int:
        """Save the keyword portfolio as PPCKeyword records."""
        count = 0
        now = datetime.now(timezone.utc)

        for match_type, keywords in [
            ("exact", keyword_portfolio.get("exact_match", [])),
            ("phrase", keyword_portfolio.get("phrase_match", [])),
            ("broad", keyword_portfolio.get("broad_match", [])),
        ]:
            for kw_data in keywords:
                # Check for existing
                stmt = select(PPCKeyword).where(
                    PPCKeyword.niche_id == niche_id,
                    PPCKeyword.keyword == kw_data["keyword"],
                    PPCKeyword.match_type == match_type,
                )
                existing = (await self.db.execute(stmt)).scalar_one_or_none()

                if existing:
                    existing.suggested_bid = Decimal(str(kw_data.get("avg_cpc", 0)))
                    existing.estimated_cpc = Decimal(str(kw_data.get("avg_cpc", 0)))
                    existing.last_updated_at = now
                else:
                    ppc_kw = PPCKeyword(
                        niche_id=niche_id,
                        keyword=kw_data["keyword"],
                        match_type=match_type,
                        suggested_bid=Decimal(str(kw_data.get("avg_cpc", 0))),
                        estimated_cpc=Decimal(str(kw_data.get("avg_cpc", 0))),
                        last_updated_at=now,
                    )
                    self.db.add(ppc_kw)
                    count += 1

        await self.db.flush()
        return count

    # ------------------------------------------------------------------
    # 5. LLM PPC strategy generation
    # ------------------------------------------------------------------
    async def generate_ppc_strategy(
        self,
        niche_keyword: str,
        keyword_portfolio: dict,
        budget_plan: dict,
        break_even_acos: dict,
        competitor_landscape: dict | None = None,
    ) -> dict:
        """Generate a comprehensive PPC strategy using LLM."""
        if not self.llm:
            return {"error": "LLM client required"}

        prompt = f"""Create a detailed Amazon PPC launch strategy for the "{niche_keyword}" niche.

KEYWORD PORTFOLIO:
- Exact match keywords: {len(keyword_portfolio.get('exact_match', []))}
- Phrase match keywords: {len(keyword_portfolio.get('phrase_match', []))}
- Broad match keywords: {len(keyword_portfolio.get('broad_match', []))}
- Top exact keywords: {[k['keyword'] for k in keyword_portfolio.get('exact_match', [])[:10]]}

BUDGET PLAN:
- Launch phase (30 days): ${budget_plan.get('phases', {}).get('launch', {}).get('monthly_budget', 0)}/month
- Growth phase (60 days): ${budget_plan.get('phases', {}).get('growth', {}).get('monthly_budget', 0)}/month
- Avg CPC: ${budget_plan.get('avg_cpc', 0)}

ACOS TARGETS:
- Break-even ACOS: {break_even_acos.get('break_even_acos', 0)}%
- Target ACOS: {break_even_acos.get('target_acos', 0)}%

Return a JSON object:
{{
    "campaign_structure": [
        {{
            "campaign_name": "<descriptive name>",
            "campaign_type": "<auto|manual_exact|manual_phrase|manual_broad|product_targeting>",
            "match_types": ["<exact|phrase|broad>"],
            "budget_daily": <daily budget>,
            "bid_strategy": "<description>",
            "keywords_count": <number>,
            "purpose": "<why this campaign>"
        }}
    ],
    "bid_strategy": {{
        "initial_bid_multiplier": <multiplier vs suggested bid>,
        "top_of_search_boost_pct": <percentage boost for top of search>,
        "product_page_boost_pct": <percentage boost for product pages>,
        "bid_adjustment_frequency": "<how often to adjust>"
    }},
    "negative_keywords": [
        "<keywords to add as negatives from day 1>"
    ],
    "optimization_schedule": [
        {{
            "week": "<week range>",
            "actions": ["<specific optimization action>"]
        }}
    ],
    "key_metrics_to_track": [
        "<metric and target>"
    ],
    "common_mistakes_to_avoid": [
        "<mistake>"
    ]
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096)

    @staticmethod
    def _empty_portfolio() -> dict:
        return {
            "exact_match": [],
            "phrase_match": [],
            "broad_match": [],
            "negative_candidates": [],
            "total_keywords": 0,
            "estimated_daily_spend": 0,
            "estimated_monthly_spend": 0,
        }
