"""Redis cache for parsed scrape results. WHY: sub-niche flows and forced re-runs re-request the same pages."""

import json
import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

SERP_TTL_SECONDS = 6 * 3600
PRODUCT_TTL_SECONDS = 24 * 3600
_TTL_BY_KIND = {"serp": SERP_TTL_SECONDS, "product": PRODUCT_TTL_SECONDS, "serp_meta": SERP_TTL_SECONDS}


class PageCache:
    def __init__(self, redis: Redis):
        self.redis = redis

    @staticmethod
    def _key(kind: str, key: str) -> str:
        return f"scrape:{kind}:{key}"

    async def get(self, kind: str, key: str) -> dict | list | None:
        """Return the cached value, or None on a miss. Never raises — a down Redis is a miss, not a failure."""
        try:
            raw = await self.redis.get(self._key(kind, key))
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning("Page cache get failed for %s:%s: %s", kind, key, e)
            return None

    async def set(self, kind: str, key: str, value: dict | list) -> None:
        """Write value to the cache. Never raises — the cache is an optimisation, not a failure source."""
        try:
            await self.redis.set(self._key(kind, key), json.dumps(value, default=str), ex=_TTL_BY_KIND[kind])
        except Exception as e:
            logger.warning("Page cache set failed for %s:%s: %s", kind, key, e)
