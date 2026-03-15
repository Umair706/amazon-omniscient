"""Master recommendation engine — orchestrates all services to produce the final Omniscient recommendation."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base_client import BaseLLMClient
from app.models.niche import Niche
from app.models.recommendation import Recommendation
from app.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Master orchestrator that pulls together all analysis into a final
    GO/NO-GO recommendation with the Omniscient Score.

    Workflow:
    1. Collect all sub-service outputs (competitive, supplier, PPC, etc.)
    2. Run scoring (9 sub-scores + 8 hard filters)
    3. Generate LLM executive summary
    4. Save recommendation to DB
    """

    def __init__(self, db: AsyncSession, llm_client: BaseLLMClient | None = None):
        self.db = db
        self.llm = llm_client
        self.scorer = ScoringService()

    # ------------------------------------------------------------------
    # 1. Generate recommendation from pre-computed metrics
    # ------------------------------------------------------------------
    async def generate_recommendation(
        self,
        niche_id: int,
        metrics: dict,
        product_spec: dict | None = None,
        ppc_strategy: dict | None = None,
        review_strategy: dict | None = None,
        financial_summary: dict | None = None,
        marketing_plan: dict | None = None,
        supplier_data: dict | None = None,
    ) -> dict:
        """
        Generate the final recommendation for a niche.

        metrics: dict with all scoring inputs (see ScoringService.compute_score)
        """
        # Step 1: Compute Omniscient Score
        score_result = self.scorer.compute_score(metrics)

        # Step 2: Build recommendation data
        recommendation_data = {
            "niche_id": niche_id,
            "omniscient_score": score_result["omniscient_score"],
            "confidence_tier": score_result["confidence_tier"],
            "sub_scores": score_result["sub_scores"],
            "hard_filters": score_result["hard_filters"],
            "pass_all_filters": score_result["pass_all_filters"],
            "fail_reasons": score_result["fail_reasons"],
        }

        # Step 3: Add strategy data
        if product_spec:
            recommendation_data["product_spec"] = product_spec

        if financial_summary:
            base = financial_summary.get("base", {})
            bull = financial_summary.get("bull", {})
            bear = financial_summary.get("bear", {})
            recommendation_data["financials"] = {
                "break_even_week_bull": bull.get("break_even_week"),
                "break_even_week_base": base.get("break_even_week"),
                "break_even_week_bear": bear.get("break_even_week"),
                "total_launch_capital": metrics.get("total_launch_capital"),
                "roi_pct": base.get("roi_pct"),
                "steady_state_margin_pct": base.get("steady_state_margin_pct"),
            }

        if ppc_strategy:
            recommendation_data["ppc_strategy"] = ppc_strategy

        if review_strategy:
            recommendation_data["review_strategy"] = review_strategy

        if marketing_plan:
            recommendation_data["marketing_plan"] = marketing_plan

        # Step 4: Generate LLM executive summary
        if self.llm and score_result["confidence_tier"] != "FAIL":
            try:
                summary = await self._generate_executive_summary(
                    metrics, score_result, product_spec, financial_summary,
                )
                recommendation_data["executive_summary"] = summary
            except Exception as e:
                logger.warning("Executive summary generation failed: %s", e)
                recommendation_data["executive_summary"] = None

        # Step 5: Save to DB
        rec = await self._save_recommendation(niche_id, recommendation_data, metrics)
        recommendation_data["recommendation_id"] = rec.id

        # Step 6: Update niche with scores
        await self._update_niche_scores(niche_id, score_result, metrics)

        return recommendation_data

    # ------------------------------------------------------------------
    # 2. LLM executive summary
    # ------------------------------------------------------------------
    async def _generate_executive_summary(
        self,
        metrics: dict,
        score_result: dict,
        product_spec: dict | None,
        financial_summary: dict | None,
    ) -> dict:
        """Generate an LLM executive summary of the recommendation."""
        prompt = f"""Generate an executive summary for this Amazon product opportunity analysis.

OMNISCIENT SCORE: {score_result['omniscient_score']}/100 ({score_result['confidence_tier']})

SUB-SCORES:
{self._format_sub_scores(score_result['sub_scores'])}

KEY METRICS:
- Avg BSR: {metrics.get('avg_bsr', 'N/A')}
- Avg Price: ${metrics.get('avg_price', 0)}
- Monthly Sales: {metrics.get('estimated_monthly_sales', 0)}
- Pre-PPC Margin: {metrics.get('pre_ppc_margin_pct', 0)}%
- Median Competitor Reviews: {metrics.get('median_competitor_reviews', 0)}
- Search Volume: {metrics.get('search_volume', 0)}

HARD FILTERS:
- Passed all: {score_result['pass_all_filters']}
- Failed: {score_result['fail_reasons'] or 'None'}

FINANCIALS:
- Break-even week (base): {financial_summary.get('base', {}).get('break_even_week', 'N/A') if financial_summary else 'N/A'}
- Launch capital: ${metrics.get('total_launch_capital', 'N/A')}

Return a JSON object:
{{
    "verdict": "<STRONG BUY|BUY|HOLD|AVOID|STRONG AVOID>",
    "one_liner": "<one sentence summary>",
    "key_strengths": ["<top 3 strengths>"],
    "key_risks": ["<top 3 risks>"],
    "action_items": [
        {{
            "priority": <1-5>,
            "action": "<specific next step>",
            "timeline": "<when to do it>"
        }}
    ],
    "confidence_notes": "<what could change this assessment>",
    "comparable_opportunities": "<how this compares to typical Amazon opportunities>"
}}"""

        return await self.llm.generate_json(prompt, max_tokens=4096)

    # ------------------------------------------------------------------
    # 3. Save recommendation to DB
    # ------------------------------------------------------------------
    async def _save_recommendation(
        self,
        niche_id: int,
        data: dict,
        metrics: dict,
    ) -> Recommendation:
        """Persist recommendation to the database."""
        now = datetime.now(timezone.utc)

        rec = Recommendation(
            niche_id=niche_id,
            omniscient_score=Decimal(str(data["omniscient_score"])),
            confidence_tier=data["confidence_tier"],
            # Product strategy
            product_description=data.get("product_spec", {}).get("differentiation_strategy"),
            differentiation_features=data.get("product_spec", {}).get("key_features_list"),
            # Unit economics
            best_landed_cost=Decimal(str(metrics.get("landed_cost", 0))) if metrics.get("landed_cost") else None,
            recommended_sale_price=Decimal(str(metrics.get("avg_price", 0))) if metrics.get("avg_price") else None,
            estimated_net_margin_pct=Decimal(str(metrics.get("post_ppc_margin_pct", 0))) if metrics.get("post_ppc_margin_pct") else None,
            # Break-even
            break_even_week_bull=data.get("financials", {}).get("break_even_week_bull"),
            break_even_week_base=data.get("financials", {}).get("break_even_week_base"),
            break_even_week_bear=data.get("financials", {}).get("break_even_week_bear"),
            # Launch capital
            total_launch_capital=Decimal(str(metrics.get("total_launch_capital", 0))) if metrics.get("total_launch_capital") else None,
            # Reviews
            review_threshold=metrics.get("review_threshold"),
            weeks_to_review_threshold=metrics.get("weeks_to_review_threshold"),
            vine_recommended=data.get("review_strategy", {}).get("vine_plan", {}).get("recommended"),
            vine_cost=Decimal(str(data.get("review_strategy", {}).get("vine_plan", {}).get("costs", {}).get("total_vine_cost", 0))) if data.get("review_strategy") else None,
            # PPC
            ppc_budget_30d=Decimal(str(data.get("ppc_strategy", {}).get("phases", {}).get("launch", {}).get("monthly_budget", 0))) if data.get("ppc_strategy") else None,
            ppc_budget_90d=Decimal(str(metrics.get("ppc_budget_90d", 0))) if metrics.get("ppc_budget_90d") else None,
            break_even_acos=Decimal(str(metrics.get("break_even_acos", 0))) if metrics.get("break_even_acos") else None,
            estimated_acos=Decimal(str(metrics.get("estimated_acos", 0))) if metrics.get("estimated_acos") else None,
            # JSONB payloads
            marketing_channels=data.get("marketing_plan", {}).get("channels"),
            risk_flags={"fail_reasons": data.get("fail_reasons", []), "hard_filters": data.get("hard_filters", [])},
            launch_playbook=data.get("marketing_plan", {}).get("launch_playbook"),
            ppc_strategy=data.get("ppc_strategy"),
            generated_at=now,
        )
        self.db.add(rec)
        await self.db.flush()
        logger.info(
            "Saved recommendation for niche %d: score=%s tier=%s",
            niche_id, data["omniscient_score"], data["confidence_tier"],
        )
        return rec

    # ------------------------------------------------------------------
    # 4. Update niche with computed scores
    # ------------------------------------------------------------------
    async def _update_niche_scores(
        self,
        niche_id: int,
        score_result: dict,
        metrics: dict,
    ) -> None:
        """Update the niche record with computed scores."""
        stmt = select(Niche).where(Niche.id == niche_id)
        niche = (await self.db.execute(stmt)).scalar_one_or_none()
        if not niche:
            return

        niche.opportunity_score = Decimal(str(score_result["omniscient_score"]))
        niche.confidence_tier = score_result["confidence_tier"]
        niche.hard_filter_passed = score_result["pass_all_filters"]
        niche.hard_filter_fail_reasons = score_result.get("fail_reasons", [])

        sub = score_result["sub_scores"]
        niche.demand_score = Decimal(str(sub.get("demand", 0)))
        niche.competition_score = Decimal(str(sub.get("competition", 0)))
        niche.revenue_score = Decimal(str(sub.get("revenue", 0)))
        niche.margin_score = Decimal(str(sub.get("margin", 0)))
        niche.trend_score = Decimal(str(sub.get("trend", 0)))
        niche.review_feasibility_score = Decimal(str(sub.get("review_feasibility", 0)))
        niche.supplier_score = Decimal(str(sub.get("supplier", 0)))
        niche.ppc_viability_score = Decimal(str(sub.get("ppc_viability", 0)))
        niche.launch_feasibility_score = Decimal(str(sub.get("launch_feasibility", 0)))

        # Update market metrics
        niche.avg_bsr = metrics.get("avg_bsr")
        niche.avg_price = Decimal(str(metrics.get("avg_price", 0))) if metrics.get("avg_price") else None
        niche.avg_rating = Decimal(str(metrics.get("avg_rating", 0))) if metrics.get("avg_rating") else None
        niche.avg_review_count = metrics.get("avg_review_count")
        niche.total_monthly_revenue = Decimal(str(metrics.get("total_monthly_revenue", 0))) if metrics.get("total_monthly_revenue") else None
        niche.estimated_monthly_sales = metrics.get("estimated_monthly_sales")
        niche.top_keyword_search_volume = metrics.get("search_volume")
        niche.is_seasonal = metrics.get("is_seasonal", False)

        niche.status = "completed"
        niche.analyzed_at = datetime.now(timezone.utc)

        await self.db.flush()

    @staticmethod
    def _format_sub_scores(sub_scores: dict) -> str:
        """Format sub-scores for LLM prompt."""
        lines = []
        for name, score in sub_scores.items():
            lines.append(f"- {name.replace('_', ' ').title()}: {score}/100")
        return "\n".join(lines)
