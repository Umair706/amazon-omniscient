"""FastAPI dependency injection functions."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings

if TYPE_CHECKING:
    from app.llm.factory import BaseLLMClient


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session from the application state.

    The session is automatically closed when the request finishes.
    """
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_redis(request: Request) -> Redis:
    """Return a Redis client backed by the shared connection pool."""
    return Redis(connection_pool=request.app.state.redis_pool)


async def get_llm_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> "BaseLLMClient":
    """Build and return an LLM client based on the configured provider.

    The concrete ``BaseLLMClient`` implementation is resolved by
    ``app.llm.factory`` (created separately).
    """
    from app.llm.factory import create_llm_client  # noqa: WPS433 – deferred import

    return create_llm_client(settings)
