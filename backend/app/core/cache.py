"""Redis-based caching for expensive operations."""

import json
import logging
from functools import wraps
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class CacheService:
    """Simple Redis cache with TTL support."""

    def __init__(self, redis: Redis, prefix: str = "omniscient"):
        self.redis = redis
        self.prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        """Get a cached value."""
        raw = await self.redis.get(self._key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Set a cached value with TTL in seconds."""
        serialized = json.dumps(value, default=str)
        await self.redis.set(self._key(key), serialized, ex=ttl)

    async def delete(self, key: str) -> None:
        """Delete a cached value."""
        await self.redis.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        return bool(await self.redis.exists(self._key(key)))

    async def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        full_pattern = self._key(pattern)
        keys = []
        async for key in self.redis.scan_iter(match=full_pattern):
            keys.append(key)
        if keys:
            return await self.redis.delete(*keys)
        return 0

    async def get_or_set(self, key: str, factory, ttl: int = 3600) -> Any:
        """Get from cache or compute and store."""
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = await factory() if callable(factory) else factory
        await self.set(key, value, ttl=ttl)
        return value
