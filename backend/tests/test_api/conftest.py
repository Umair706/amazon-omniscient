"""HTTP-level tests against the real FastAPI app and a real (rolled back) database.

The database fixtures skip themselves unless TEST_DATABASE_URL points at a
TimescaleDB migrated to head. The skip lives in the fixtures, not in a
directory-wide mark, so the plain unit tests in this folder still run.
"""

import os
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.dependencies import get_db
from app.main import create_app
from app.models.competitor import Competitor
from app.models.financial_projection import FinancialProjection
from app.models.keyword import NicheKeyword
from app.models.niche import Niche
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.review import ReviewPainPoint
from app.models.supplier import Supplier

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

# NOTE: every seeded ASIN starts with this, so a row that ever leaks out of
# the rolled-back transaction is easy to spot and delete by hand.
# ProductResponse rejects any ASIN that is not exactly 10 characters, so
# the prefix plus a two-digit suffix makes a valid-looking ASIN.
SEED_ASIN_PREFIX = "BTESTAPI"
SEED_KEYWORD = "btestapi http harness niche"
SEED_RECOMMENDATION_SCORE = Decimal("72.50")
SEED_CONFIDENCE_TIER = "MEDIUM"


@pytest.fixture
async def db_session():
    """One session inside one outer transaction that is always rolled back."""
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set; needs a real TimescaleDB")
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        # WHY create_savepoint: some routes call db.commit(). In this mode a
        # commit only releases a savepoint, so the outer transaction survives
        # and the rollback below still wipes everything the test wrote.
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def client(db_session):
    """An HTTP client that talks to the real app, using the test session for every request."""
    # WHY no lifespan: it would open Redis and a second engine.
    # The routes under test only need get_db, which we replace here.
    app = create_app()

    async def _yield_test_session():
        yield db_session

    app.dependency_overrides[get_db] = _yield_test_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


@pytest.fixture
async def seeded_niche(db_session):
    """Inserts one niche with one row in every sub-resource table. Returns the Niche."""
    niche = Niche(name=SEED_KEYWORD, primary_keyword=SEED_KEYWORD)
    db_session.add(niche)
    await db_session.flush()

    products = _build_products(niche.id)
    db_session.add_all(products)
    await db_session.flush()

    db_session.add_all(_build_niche_children(niche.id, products[0].id))
    await db_session.flush()
    return niche


def _build_products(niche_id: int) -> list[Product]:
    """Two products, so list routes have more than one row to order."""
    return [
        Product(asin=f"{SEED_ASIN_PREFIX}01", niche_id=niche_id, title="Harness product one"),
        Product(asin=f"{SEED_ASIN_PREFIX}02", niche_id=niche_id, title="Harness product two"),
    ]


def _build_niche_children(niche_id: int, product_id: int) -> list:
    """One row for each table that the niche sub-resource routes read."""
    return [
        Competitor(niche_id=niche_id, product_id=product_id),
        Supplier(niche_id=niche_id, supplier_name="Harness supplier"),
        FinancialProjection(niche_id=niche_id, scenario="base", week_number=1),
        NicheKeyword(niche_id=niche_id, keyword=SEED_KEYWORD),
        ReviewPainPoint(niche_id=niche_id, cluster_name="Harness pain point"),
        Recommendation(
            niche_id=niche_id,
            omniscient_score=SEED_RECOMMENDATION_SCORE,
            confidence_tier=SEED_CONFIDENCE_TIER,
        ),
    ]
