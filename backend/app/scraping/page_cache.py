"""Redis cache for parsed scrape results. WHY: sub-niche flows and forced re-runs re-request the same pages."""

import json

from redis.asyncio import Redis

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
        raw = await self.redis.get(self._key(kind, key))
        return json.loads(raw) if raw else None

    async def set(self, kind: str, key: str, value: dict | list) -> None:
        await self.redis.set(self._key(kind, key), json.dumps(value, default=str), ex=_TTL_BY_KIND[kind])
