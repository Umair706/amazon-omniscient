import fakeredis.aioredis

from app.scraping.page_cache import PRODUCT_TTL_SECONDS, PageCache


async def test_set_then_get_roundtrip_and_ttl():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache = PageCache(redis)
    await cache.set("product", "US:B0A", {"asin": "B0A", "price": 9.99})
    assert await cache.get("product", "US:B0A") == {"asin": "B0A", "price": 9.99}
    assert 0 < await redis.ttl("scrape:product:US:B0A") <= PRODUCT_TTL_SECONDS


async def test_miss_returns_none():
    cache = PageCache(fakeredis.aioredis.FakeRedis(decode_responses=True))
    assert await cache.get("serp", "US:nothing") is None


class _RaisingRedis:
    """Stands in for a Redis client that is down. No fakeredis needed for this."""

    async def get(self, key):
        raise ConnectionError("redis unavailable")

    async def set(self, key, value, ex=None):
        raise ConnectionError("redis unavailable")


async def test_get_and_set_swallow_a_dead_redis():
    """The cache is an optimisation, never a failure source — a down Redis must not raise."""
    cache = PageCache(_RaisingRedis())
    assert await cache.get("product", "US:B0A") is None
    await cache.set("product", "US:B0A", {"asin": "B0A"})  # must not raise
