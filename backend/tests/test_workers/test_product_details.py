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


async def test_first_snapshot_forwards_review_count(monkeypatch):
    tracker_stub = SimpleNamespace(record_product_snapshot=AsyncMock())
    monkeypatch.setattr(product_details, "BSRTracker", lambda db: tracker_stub)
    db = make_fake_session()
    product = SimpleNamespace(id=1, asin="B0A")

    await product_details._record_first_snapshots(db, product, {"review_count": 1543})

    kwargs = tracker_stub.record_product_snapshot.await_args.kwargs
    assert kwargs["review_count"] == 1543


def test_derived_economics_fill_units_revenue_referral_and_quality():
    product = SimpleNamespace(
        estimated_monthly_units=None, estimated_monthly_revenue=None,
        listing_quality_score=None, referral_fee_pct=None, fba_fee=None, product_weight_lbs=None,
    )
    detail = {
        "asin": "B0A", "title": "A well-formed garlic press title that is long enough to score well",
        "price": 25.0, "current_bsr": 500, "bsr_category": "Home & Kitchen",
        "image_count": 7, "bullet_count": 5, "has_a_plus": True, "has_video": True,
        "rating": 4.5, "review_count": 1200,
    }
    product_details._apply_derived_economics(make_fake_session(), product, detail, "US")

    assert product.estimated_monthly_units and product.estimated_monthly_units > 0
    assert product.estimated_monthly_revenue == round(product.estimated_monthly_units * 25.0, 2)
    assert product.referral_fee_pct is not None and product.referral_fee_pct > 0
    assert product.listing_quality_score is not None
    # No dimensions in the detail, so the fulfilment fee stays unknown rather than guessed.
    assert product.fba_fee is None


def test_derived_economics_are_skipped_without_price_or_bsr():
    product = SimpleNamespace(
        estimated_monthly_units=None, estimated_monthly_revenue=None,
        listing_quality_score=None, referral_fee_pct=None, fba_fee=None, product_weight_lbs=None,
    )
    product_details._apply_derived_economics(make_fake_session(), product, {"asin": "B0A", "title": "x"}, "US")
    assert product.estimated_monthly_units is None
    assert product.referral_fee_pct is None
