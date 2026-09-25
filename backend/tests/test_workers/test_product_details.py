from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.workers.pipeline_steps import product_details
from app.workers.pipeline_steps.product_details import apply_detail_to_product, scrape_product_details
from tests.test_workers.fake_session import make_fake_session


def _lookup_result(product) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = product
    return result


async def test_one_product_failing_to_save_does_not_stop_the_rest():
    db = make_fake_session()
    db.execute = AsyncMock(side_effect=[RuntimeError("value too long"), _lookup_result(None)])
    scraper = SimpleNamespace(scrape_product_page=AsyncMock(side_effect=[{"asin": "B0A"}, {"asin": "B0B"}]))

    detailed = await scrape_product_details(db, [{"asin": "B0A"}, {"asin": "B0B"}], scraper)

    assert [d["asin"] for d in detailed] == ["B0A", "B0B"]
    assert db.events == ["savepoint", "rolled_back", "savepoint", "released", "commit"]


async def test_a_failed_scrape_is_skipped():
    db = make_fake_session()
    scraper = SimpleNamespace(scrape_product_page=AsyncMock(side_effect=RuntimeError("timeout")))
    assert await scrape_product_details(db, [{"asin": "B0A"}], scraper) == []
    assert db.events == ["commit"]


def test_apply_detail_copies_found_values_and_keeps_stored_ones():
    product = SimpleNamespace(title="Old title", brand="OXO", current_price=None)
    apply_detail_to_product(product, {
        "title": "New title", "brand": "", "price": 29.0,
        "date_first_available": "12 March 2021", "last_scraped_at": "not a date",
    })
    assert product.title == "New title"
    assert product.brand == "OXO"
    assert product.current_price == 29.0
    assert product.date_first_available == date(2021, 3, 12)
    assert not hasattr(product, "last_scraped_at")


def test_every_mapped_attribute_exists_on_the_product_model():
    from app.models.product import Product

    for _, attribute in product_details._DETAIL_TO_PRODUCT_FIELDS:
        assert hasattr(Product, attribute), attribute
