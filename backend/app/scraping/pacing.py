"""Jittered minimum gap between page loads to the same site, shared by every scraper in the process."""

import asyncio
import logging
import random
import time

logger = logging.getLogger(__name__)

AMAZON_GAP_SECONDS = (3.0, 7.0)
ALIBABA_GAP_SECONDS = (5.0, 10.0)
MADE_IN_CHINA_GAP_SECONDS = (4.0, 9.0)


class Pacer:
    def __init__(self, min_gap_s: float, max_gap_s: float):
        self.min_gap_s = min_gap_s
        self.max_gap_s = max_gap_s
        self._last_request: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait_turn(self, domain: str) -> None:
        """Sleep until at least a random gap has passed since the last request to this domain."""
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            gap = random.uniform(self.min_gap_s, self.max_gap_s)
            elapsed = time.monotonic() - self._last_request.get(domain, 0.0)
            if elapsed < gap:
                await asyncio.sleep(gap - elapsed)
            self._last_request[domain] = time.monotonic()


# Local fallback pacers; the pipeline injects a SharedPacer (Redis) so all worker processes share the gap.
_PACERS = {
    "amazon": Pacer(*AMAZON_GAP_SECONDS),
    "1688": Pacer(*ALIBABA_GAP_SECONDS),
    "made-in-china": Pacer(*MADE_IN_CHINA_GAP_SECONDS),
}


def pacer_for(site: str) -> Pacer:
    """'amazon', '1688' or 'made-in-china'."""
    return _PACERS[site]


# Poll granularity while another process holds the slot. Short enough to feel
# immediate, long enough not to hammer Redis.
_RETRY_SLEEP_SECONDS = 0.05

MS_PER_SECOND = 1000


class SharedPacer:
    """Pacer whose 'last request' lives in Redis, so every worker process shares one gap.

    WHY: with Celery concurrency=4 the in-process Pacer let four workers hit a domain at
    once. The slot is a SET NX key that expires after one random gap; whoever sets it goes.
    """

    def __init__(self, redis, min_gap_s: float, max_gap_s: float, *, fallback: Pacer):
        self.redis = redis
        self.min_gap_s = min_gap_s
        self.max_gap_s = max_gap_s
        self.fallback = fallback
        self.using_fallback = False

    async def wait_turn(self, domain: str) -> None:
        """Block until this process may make the next request to domain."""
        if self.using_fallback:
            await self.fallback.wait_turn(domain)
            return
        try:
            await self._claim_slot(domain)
        except Exception as e:
            logger.warning("Shared pacing unavailable (%s); pacing %s locally for the rest of this run", e, domain)
            self.using_fallback = True
            await self.fallback.wait_turn(domain)

    async def _claim_slot(self, domain: str) -> None:
        key = f"pace:{domain}"
        while True:
            gap_ms = int(random.uniform(self.min_gap_s, self.max_gap_s) * MS_PER_SECOND)
            if await self.redis.set(key, "1", nx=True, px=gap_ms):
                return
            # NOTE: PTTL returns -2 when the key vanished and -1 when it has no
            # expiry; both mean "try again shortly".
            remaining_ms = await self.redis.pttl(key)
            if remaining_ms <= 0:
                await asyncio.sleep(_RETRY_SLEEP_SECONDS)
            else:
                await asyncio.sleep(remaining_ms / MS_PER_SECOND)
