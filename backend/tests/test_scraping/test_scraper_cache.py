"""scrape_product_page: cache hits skip the browser and are marked; non-ok verdicts aren't cached."""

import fakeredis.aioredis

from app.core.proxy_manager import ProxyManager
from app.scraping.page_cache import PageCache
from app.services.scraper_service import FROM_CACHE_KEY, ScraperService

ASIN = "B0TEST0001"


class _FakePage:
    async def close(self):
        pass


class _StubCache:
    """Minimal PageCache stand-in — no Redis, just a dict."""

    def __init__(self, preload: dict | None = None):
        self._store = preload or {}

    async def get(self, kind, key):
        return self._store.get((kind, key))

    async def set(self, kind, key, value):
        self._store[(kind, key)] = value


def _scraper_with_cache(page_cache) -> ScraperService:
    # WHY session=object(): a cache hit must return before the scraper ever touches
    # the browser session, so a session that would blow up on first use proves it.
    return ScraperService(proxy_manager=ProxyManager(provider="none"), marketplace="US", session=object(), page_cache=page_cache)


async def test_cache_hit_skips_the_browser_and_is_marked_from_cache():
    cache = _StubCache(preload={("product", f"US:{ASIN}"): {"asin": ASIN, "price": 9.99}})
    result = await _scraper_with_cache(cache).scrape_product_page(ASIN)

    assert result == {"asin": ASIN, "price": 9.99, FROM_CACHE_KEY: True}


async def test_cache_miss_falls_through_to_a_live_scrape():
    cache = _StubCache()
    scraper = _scraper_with_cache(cache)
    scraper._load = _fake_load("ok")
    scraper._extract_product_fields = _fake_extract

    result = await scraper.scrape_product_page(ASIN)

    assert result == {"asin": ASIN, "title": "Live Title"}
    assert FROM_CACHE_KEY not in result


async def test_soft_block_is_not_cached():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache = PageCache(redis)
    scraper = _scraper_with_cache(cache)
    scraper._load = _fake_load("soft_block")
    scraper._extract_product_fields = _fake_extract

    result = await scraper.scrape_product_page(ASIN)

    assert result == {"asin": ASIN, "title": "Live Title"}
    assert await cache.get("product", f"US:{ASIN}") is None


async def test_ok_verdict_is_cached():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache = PageCache(redis)
    scraper = _scraper_with_cache(cache)
    scraper._load = _fake_load("ok")
    scraper._extract_product_fields = _fake_extract

    await scraper.scrape_product_page(ASIN)

    assert await cache.get("product", f"US:{ASIN}") == {"asin": ASIN, "title": "Live Title"}


def _fake_load(verdict: str):
    async def fake_load(url, expected_selector, url_kind):
        return _FakePage(), verdict
    return fake_load


async def _fake_extract(page, asin):
    return {"asin": asin, "title": "Live Title"}
