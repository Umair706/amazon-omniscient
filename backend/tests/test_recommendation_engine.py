"""Tests for the RecommendationEngine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from app.services.recommendation_engine import RecommendationEngine


@pytest.fixture
def engine(mock_db, mock_llm):
    return RecommendationEngine(mock_db, mock_llm)


@pytest.fixture
def engine_no_llm(mock_db):
    return RecommendationEngine(mock_db)


class TestGenerateRecommendation:
    @pytest.mark.asyncio
    async def test_returns_required_fields(self, engine, sample_metrics):
        # Mock the DB operations
        engine.db.flush = AsyncMock()

        # Mock _save_recommendation to return a mock rec with id
        mock_rec = MagicMock()
        mock_rec.id = 1
        engine._save_recommendation = AsyncMock(return_value=mock_rec)
        engine._update_niche_scores = AsyncMock()

        result = await engine.generate_recommendation(
            niche_id=1, metrics=sample_metrics,
        )
        assert "omniscient_score" in result
        assert "confidence_tier" in result
        assert "sub_scores" in result
        assert "recommendation_id" in result

    @pytest.mark.asyncio
    async def test_includes_financial_data(self, engine, sample_metrics):
        mock_rec = MagicMock()
        mock_rec.id = 1
        engine._save_recommendation = AsyncMock(return_value=mock_rec)
        engine._update_niche_scores = AsyncMock()

        financial_summary = {
            "base": {"break_even_week": 14, "roi_pct": 45.2, "steady_state_margin_pct": 22.5},
            "bull": {"break_even_week": 10},
            "bear": {"break_even_week": 22},
        }

        result = await engine.generate_recommendation(
            niche_id=1, metrics=sample_metrics,
            financial_summary=financial_summary,
        )
        assert "financials" in result
        assert result["financials"]["break_even_week_base"] == 14

    @pytest.mark.asyncio
    async def test_no_llm_skips_summary(self, engine_no_llm, sample_metrics):
        mock_rec = MagicMock()
        mock_rec.id = 1
        engine_no_llm._save_recommendation = AsyncMock(return_value=mock_rec)
        engine_no_llm._update_niche_scores = AsyncMock()

        result = await engine_no_llm.generate_recommendation(
            niche_id=1, metrics=sample_metrics,
        )
        assert "executive_summary" not in result

    @pytest.mark.asyncio
    async def test_fail_tier_skips_llm_summary(self, engine, sample_metrics):
        """When hard filters fail (FAIL tier), no LLM summary is generated."""
        mock_rec = MagicMock()
        mock_rec.id = 1
        engine._save_recommendation = AsyncMock(return_value=mock_rec)
        engine._update_niche_scores = AsyncMock()

        # Force a hard filter failure
        sample_metrics["avg_price"] = 10
        result = await engine.generate_recommendation(
            niche_id=1, metrics=sample_metrics,
        )
        assert result["confidence_tier"] == "FAIL"
        assert "executive_summary" not in result

    @pytest.mark.asyncio
    async def test_llm_failure_gracefully_handled(self, engine, sample_metrics):
        """LLM errors should be caught and not crash the recommendation."""
        mock_rec = MagicMock()
        mock_rec.id = 1
        engine._save_recommendation = AsyncMock(return_value=mock_rec)
        engine._update_niche_scores = AsyncMock()
        engine.llm.generate_json = AsyncMock(side_effect=Exception("LLM error"))

        result = await engine.generate_recommendation(
            niche_id=1, metrics=sample_metrics,
        )
        # Should still return a result, with executive_summary set to None
        assert "omniscient_score" in result
        assert result.get("executive_summary") is None

    @pytest.mark.asyncio
    async def test_includes_product_spec(self, engine, sample_metrics):
        mock_rec = MagicMock()
        mock_rec.id = 1
        engine._save_recommendation = AsyncMock(return_value=mock_rec)
        engine._update_niche_scores = AsyncMock()

        product_spec = {
            "differentiation_strategy": "Premium material with ergonomic design",
            "key_features_list": ["Feature A", "Feature B"],
        }

        result = await engine.generate_recommendation(
            niche_id=1, metrics=sample_metrics,
            product_spec=product_spec,
        )
        assert "product_spec" in result

    @pytest.mark.asyncio
    async def test_save_recommendation_called(self, engine, sample_metrics):
        mock_rec = MagicMock()
        mock_rec.id = 42
        engine._save_recommendation = AsyncMock(return_value=mock_rec)
        engine._update_niche_scores = AsyncMock()

        result = await engine.generate_recommendation(
            niche_id=1, metrics=sample_metrics,
        )
        engine._save_recommendation.assert_awaited_once()
        assert result["recommendation_id"] == 42

    @pytest.mark.asyncio
    async def test_update_niche_scores_called(self, engine, sample_metrics):
        mock_rec = MagicMock()
        mock_rec.id = 1
        engine._save_recommendation = AsyncMock(return_value=mock_rec)
        engine._update_niche_scores = AsyncMock()

        await engine.generate_recommendation(
            niche_id=1, metrics=sample_metrics,
        )
        engine._update_niche_scores.assert_awaited_once()


class TestFormatSubScores:
    def test_formats_correctly(self):
        sub_scores = {"demand": 75, "competition": 80}
        result = RecommendationEngine._format_sub_scores(sub_scores)
        assert "Demand: 75/100" in result
        assert "Competition: 80/100" in result

    def test_formats_compound_names(self):
        sub_scores = {"review_feasibility": 60, "ppc_viability": 45}
        result = RecommendationEngine._format_sub_scores(sub_scores)
        assert "Review Feasibility: 60/100" in result
        assert "Ppc Viability: 45/100" in result

    def test_empty_sub_scores(self):
        result = RecommendationEngine._format_sub_scores({})
        assert result == ""


class TestScorerIntegration:
    def test_engine_uses_scoring_service(self, engine, sample_metrics):
        """Verify the engine delegates scoring to ScoringService."""
        from app.services.scoring_service import ScoringService

        assert isinstance(engine.scorer, ScoringService)

    @pytest.mark.asyncio
    async def test_score_result_propagated(self, engine, sample_metrics):
        """Score result values should appear in the recommendation output."""
        mock_rec = MagicMock()
        mock_rec.id = 1
        engine._save_recommendation = AsyncMock(return_value=mock_rec)
        engine._update_niche_scores = AsyncMock()

        result = await engine.generate_recommendation(
            niche_id=1, metrics=sample_metrics,
        )

        # Verify the score result values match what ScoringService produces
        direct_score = engine.scorer.compute_score(sample_metrics)
        assert result["omniscient_score"] == direct_score["omniscient_score"]
        assert result["confidence_tier"] == direct_score["confidence_tier"]
        assert result["sub_scores"] == direct_score["sub_scores"]
        assert result["pass_all_filters"] == direct_score["pass_all_filters"]
