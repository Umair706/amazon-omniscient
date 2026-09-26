from types import SimpleNamespace
from datetime import datetime, timezone
from decimal import Decimal

from app.schemas.recommendation import RecommendationResponse


def test_recommendation_response_accepts_marketing_channels_array():
    row = SimpleNamespace(
        id=1, niche_id=2, omniscient_score=Decimal("61.5"), confidence_tier="MEDIUM",
        marketing_channels=[{"channel": "Amazon PPC", "budget_pct": 80}],
        generated_at=datetime.now(timezone.utc),
    )
    parsed = RecommendationResponse.model_validate(row)
    assert parsed.marketing_channels[0]["channel"] == "Amazon PPC"
