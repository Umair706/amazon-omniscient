from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from app.workers import tasks


def _install_fake_session(monkeypatch, execute_result) -> MagicMock:
    """Make the worker's session factory hand out one fake session."""
    db = MagicMock()
    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock()

    @asynccontextmanager
    async def session():
        yield db

    monkeypatch.setattr(tasks, "_get_session_factory", lambda: session)
    return db


async def test_daily_refresh_queues_every_completed_niche_with_its_keyword(monkeypatch):
    result = MagicMock()
    result.all.return_value = [(4, "garlic press")]
    _install_fake_session(monkeypatch, result)
    queued = MagicMock()
    monkeypatch.setattr(tasks.refresh_competitor_data, "delay", queued)

    await tasks._refresh_all_competitors_async()

    queued.assert_called_once_with(4, "garlic press")


async def test_competitor_refresh_saves_the_new_landscape(monkeypatch):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = _install_fake_session(monkeypatch, result)
    monkeypatch.setattr(tasks, "_get_llm_client", lambda: None)
    service = MagicMock()
    service.analyze_landscape = AsyncMock(return_value={"competitor_details": []})
    service.persist_landscape = AsyncMock(return_value=0)
    monkeypatch.setattr("app.services.competitor_service.CompetitorService", lambda db, llm: service)

    await tasks._refresh_competitor_async(4, "garlic press")

    service.persist_landscape.assert_awaited_once_with(4, {"competitor_details": []})
    db.commit.assert_awaited_once()
