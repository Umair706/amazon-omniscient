"""A stand-in AsyncSession that records savepoints, rollbacks and commits."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock


def make_fake_session() -> MagicMock:
    """Session whose begin_nested() logs "savepoint" / "rolled_back" / "released" to db.events."""
    db = MagicMock()
    db.events = []
    db.commit = AsyncMock(side_effect=lambda: db.events.append("commit"))

    @asynccontextmanager
    async def begin_nested():
        db.events.append("savepoint")
        try:
            yield
        except Exception:
            db.events.append("rolled_back")
            raise
        db.events.append("released")

    db.begin_nested = begin_nested
    return db
