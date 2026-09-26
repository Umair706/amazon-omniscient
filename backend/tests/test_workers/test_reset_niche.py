"""Tests for reset_niche_analysis_data."""

from unittest.mock import AsyncMock

import pytest

from app.workers.pipeline_steps.reset import RESET_TABLES, reset_niche_analysis_data


@pytest.mark.asyncio
async def test_reset_deletes_one_statement_per_table(mock_db):
    """Verify reset_niche_analysis_data executes one delete per table and flushes."""
    mock_db.execute = AsyncMock()
    await reset_niche_analysis_data(mock_db, niche_id=7)
    assert mock_db.execute.await_count == len(RESET_TABLES)
    mock_db.flush.assert_awaited_once()
