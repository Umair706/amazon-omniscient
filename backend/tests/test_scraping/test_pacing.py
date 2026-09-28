import time

from app.scraping.pacing import Pacer, SharedPacer


async def test_second_request_waits_at_least_min_gap():
    pacer = Pacer(min_gap_s=0.2, max_gap_s=0.2)
    await pacer.wait_turn("example.com")
    start = time.monotonic()
    await pacer.wait_turn("example.com")
    assert time.monotonic() - start >= 0.19


async def test_different_domains_do_not_block_each_other():
    pacer = Pacer(min_gap_s=0.5, max_gap_s=0.5)
    await pacer.wait_turn("a.com")
    start = time.monotonic()
    await pacer.wait_turn("b.com")
    assert time.monotonic() - start < 0.1


class FakeRedis:
    """Just enough of redis.asyncio for SharedPacer: SET NX PX and PTTL."""

    def __init__(self):
        self.expires_at: dict[str, float] = {}

    async def set(self, key, value, nx=False, px=None):
        now = time.monotonic()
        if nx and self.expires_at.get(key, 0) > now:
            return None
        self.expires_at[key] = now + px / 1000
        return True

    async def pttl(self, key):
        remaining = self.expires_at.get(key, 0) - time.monotonic()
        return int(remaining * 1000) if remaining > 0 else -2


class BrokenRedis:
    async def set(self, *a, **k):
        raise ConnectionError("redis down")

    async def pttl(self, *a, **k):
        raise ConnectionError("redis down")


async def test_two_shared_pacers_take_turns():
    redis = FakeRedis()
    a = SharedPacer(redis, 0.2, 0.2, fallback=Pacer(0, 0))
    b = SharedPacer(redis, 0.2, 0.2, fallback=Pacer(0, 0))
    await a.wait_turn("amazon.com")
    start = time.monotonic()
    await b.wait_turn("amazon.com")
    assert time.monotonic() - start >= 0.19


async def test_redis_failure_falls_back_to_local_pacing():
    pacer = SharedPacer(BrokenRedis(), 0.2, 0.2, fallback=Pacer(0.2, 0.2))
    await pacer.wait_turn("amazon.com")
    start = time.monotonic()
    await pacer.wait_turn("amazon.com")
    assert time.monotonic() - start >= 0.19
    assert pacer.using_fallback is True
