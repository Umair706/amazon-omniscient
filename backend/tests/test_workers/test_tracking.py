from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.workers import tasks
from tests.test_workers.fake_session import make_fake_session


def _snapshot(verdict: str) -> dict:
    """What ScraperService.scrape_rank_snapshot returns for one page."""
    return {
        "asin": "B0A", "verdict": verdict, "price": 29.0,
        "current_bsr": 118, "bsr_category": "Home & Kitchen",
        "current_subcategory_bsr": 1, "subcategory_name": "Garlic Presses",
        "stock_level": None, "stock_text": "In stock", "is_in_stock": True,
    }


def _context(snapshots: list[dict]) -> tasks.TrackingContext:
    return tasks.TrackingContext(
        scraper=SimpleNamespace(scrape_rank_snapshot=AsyncMock(side_effect=snapshots)),
        tracker=SimpleNamespace(record_product_snapshot=AsyncMock()),
        velocity_svc=SimpleNamespace(record_stock_snapshot=AsyncMock()),
    )


def _product(asin: str = "B0A") -> SimpleNamespace:
    return SimpleNamespace(id=1, asin=asin, current_bsr=None, current_price=None, last_stock_level=None)


async def test_soft_blocked_page_records_nothing():
    context = _context([_snapshot("soft_block")])
    product = _product()
    await tasks._track_one_product(product, context)
    context.tracker.record_product_snapshot.assert_not_awaited()
    context.velocity_svc.record_stock_snapshot.assert_not_awaited()
    assert product.current_bsr is None


async def test_real_page_records_rank_and_stock():
    context = _context([_snapshot("ok")])
    product = _product()
    await tasks._track_one_product(product, context)
    context.tracker.record_product_snapshot.assert_awaited_once()
    context.velocity_svc.record_stock_snapshot.assert_awaited_once()
    assert product.current_bsr == 118


async def test_one_failing_product_does_not_stop_the_rest():
    db = make_fake_session()
    context = _context([_snapshot("ok"), _snapshot("ok")])
    context.tracker.record_product_snapshot.side_effect = [RuntimeError("duplicate key"), None]
    await tasks._track_products(db, [_product("B0A"), _product("B0B")], context)
    assert db.events == ["savepoint", "rolled_back", "savepoint", "released", "commit"]
