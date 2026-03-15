"""Shared test fixtures."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    """Mock async database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def mock_llm():
    """Mock LLM client."""
    llm = AsyncMock()
    llm.generate_json = AsyncMock(return_value={
        "verdict": "BUY",
        "one_liner": "Test summary",
        "key_strengths": ["strength1"],
        "key_risks": ["risk1"],
        "action_items": [],
        "confidence_notes": "test",
        "comparable_opportunities": "test",
    })
    llm.generate_text = AsyncMock(return_value="Test response")
    return llm


@pytest.fixture
def sample_metrics():
    """Sample metrics dict for scoring tests."""
    return {
        "search_volume": 5000,
        "avg_bsr": 3000,
        "estimated_monthly_sales": 500,
        "avg_price": 29.99,
        "monthly_revenue_per_seller": 5000,
        "pre_ppc_margin_pct": 40,
        "post_ppc_margin_pct": 20,
        "avg_listing_quality": 55,
        "median_competitor_reviews": 200,
        "strong_seller_count": 2,
        "bsr_velocity_pct": -10,
        "search_volume_trend": "stable",
        "is_seasonal": False,
        "review_threshold": 50,
        "weeks_to_review_threshold": 20,
        "supplier_count": 8,
        "best_supplier_score": 80,
        "min_moq": 200,
        "avg_cpc": 1.20,
        "break_even_acos": 35,
        "relevant_keyword_count": 25,
        "total_launch_capital": 5000,
        "break_even_week_base": 14,
        "amazon_seller_pct": 10,
        "is_restricted_category": False,
        "ip_risk_detected": False,
    }
