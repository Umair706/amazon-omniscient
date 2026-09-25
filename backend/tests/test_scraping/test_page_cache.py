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
