# backend/tests/test_services/test_competitor_persist.py
from unittest.mock import AsyncMock, MagicMock

from app.models.competitor import Competitor
from app.services.competitor_service import CompetitorService


def _result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


async def test_persist_landscape_saves_one_row_per_known_product(mock_db):
    # First execute = product lookup (found, id 42); second = existing competitor (none)
    mock_db.execute = AsyncMock(side_effect=[_result(42), _result(None)])
    svc = CompetitorService(mock_db)
    landscape = {
        "competitor_details": [{
            "asin": "B0A",
            "search_position": 7,
            "listing_scores": {"overall_score": 61.5, "title_score": 70, "image_score": 60, "bullet_score": 80,
                               "a_plus_score": 0, "video_score": 0, "backend_kw_score": 50, "review_score": 40},
            "vulnerabilities": {"vulnerability_level": "medium", "vulnerability_types": ["no_a_plus", "no_video"]},
        }]
    }
    saved = await svc.persist_landscape(niche_id=1, landscape=landscape)
    assert saved == 1
    comp = mock_db.add.call_args.args[0]
    assert isinstance(comp, Competitor)
    assert comp.organic_rank == 7
    assert float(comp.listing_quality_score) == 61.5
    assert comp.vulnerability == "medium"
    assert comp.vulnerability_type == "no_a_plus,no_video"


async def test_persist_landscape_skips_unknown_asin(mock_db):
    mock_db.execute = AsyncMock(side_effect=[_result(None)])
    svc = CompetitorService(mock_db)
    saved = await svc.persist_landscape(1, {"competitor_details": [{"asin": "NOPE", "listing_scores": {}, "vulnerabilities": {}}]})
    assert saved == 0
    mock_db.add.assert_not_called()
