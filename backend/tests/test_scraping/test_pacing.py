import time

from app.scraping.pacing import Pacer


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
