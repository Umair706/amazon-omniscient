"""Runs record_product_snapshot against a real TimescaleDB.

Mock sessions cannot catch primary-key collisions, which is how the
main-rank/sub-rank bug slipped through. Skipped unless TEST_DATABASE_URL
points at a database migrated to head. Everything is rolled back.
"""

import os

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.bsr_history import BSRHistory
from app.models.niche import Niche
from app.models.price_history import PriceHistory
from app.models.product import Product
from app.services.bsr_tracker import BSRTracker

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set; needs a real TimescaleDB"
)


async def _add_product(session: AsyncSession) -> Product:
    niche = Niche(name="db test niche", primary_keyword="db test niche")
    session.add(niche)
    await session.flush()
    product = Product(asin="BTESTPK015", niche_id=niche.id, title="PK test product")
    session.add(product)
    await session.flush()
    return product


async def _count_rows(session: AsyncSession, model, product_id: int) -> int:
    query = select(func.count()).select_from(model).where(model.product_id == product_id)
    return (await session.execute(query)).scalar_one()


async def test_main_and_sub_rank_recorded_at_same_moment():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection)
        try:
            product = await _add_product(session)
            result = await BSRTracker(session).record_product_snapshot(
                product_id=product.id, asin=product.asin,
                bsr=118, subcategory_bsr=1, price=29.0,
            )
            assert result == {"bsr_recorded": True, "subcategory_bsr_recorded": True, "price_recorded": True}
            assert await _count_rows(session, BSRHistory, product.id) == 2
            assert await _count_rows(session, PriceHistory, product.id) == 1
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()
