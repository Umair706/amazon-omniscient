from unittest.mock import AsyncMock, MagicMock

import pytest

from app.scraping.pacing import ALIBABA_GAP_SECONDS, AMAZON_GAP_SECONDS, SharedPacer, pacer_for
from app.workers import tasks


def test_shared_pacer_uses_site_gaps_and_local_fallback():
    amazon = tasks._shared_pacer(object(), "amazon")
    alibaba = tasks._shared_pacer(object(), "1688")
    assert isinstance(amazon, SharedPacer)
    assert (amazon.min_gap_s, amazon.max_gap_s) == AMAZON_GAP_SECONDS
    assert (alibaba.min_gap_s, alibaba.max_gap_s) == ALIBABA_GAP_SECONDS
    assert amazon.fallback is pacer_for("amazon")


def test_shared_pacer_names_the_known_sites_when_given_an_unknown_one():
    with pytest.raises(ValueError, match=r"Unknown pacing site 'ebay'; expected one of \['1688', 'amazon', 'made-in-china'\]"):
        tasks._shared_pacer(object(), "ebay")


def test_page_cache_is_skipped_on_forced_rerun():
    assert tasks._page_cache_for(object(), force=True) is None
    assert tasks._page_cache_for(object(), force=False) is not None


async def test_redis_for_run_builds_client_with_short_timeouts_and_closes_it(monkeypatch):
    """A hung Redis must not block a worker forever, so the client is built with
    explicit socket timeouts, and it must always be closed on the way out."""
    fake_client = MagicMock()
    fake_client.aclose = AsyncMock()
    from_url = MagicMock(return_value=fake_client)
    monkeypatch.setattr("redis.asyncio.Redis.from_url", from_url)

    async with tasks._redis_for_run() as redis:
        assert redis is fake_client

    _, kwargs = from_url.call_args
    assert kwargs["socket_timeout"] == tasks.REDIS_SOCKET_TIMEOUT_SECONDS
    assert kwargs["socket_connect_timeout"] == tasks.REDIS_SOCKET_TIMEOUT_SECONDS
    fake_client.aclose.assert_awaited_once()
