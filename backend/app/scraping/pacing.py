"""Jittered minimum gap between page loads to the same site, shared by every scraper in the process."""

import asyncio
import random
import time

AMAZON_GAP_SECONDS = (3.0, 7.0)
ALIBABA_GAP_SECONDS = (5.0, 10.0)


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


# NOTE: this registry lives in one worker process. With Celery concurrency=4
# there are four of them, so the combined request rate to one domain can be
# about 4x the gap configured here.
_PACERS = {
    "amazon": Pacer(*AMAZON_GAP_SECONDS),
    "1688": Pacer(*ALIBABA_GAP_SECONDS),
}


def pacer_for(site: str) -> Pacer:
    """'amazon' or '1688'."""
    return _PACERS[site]
