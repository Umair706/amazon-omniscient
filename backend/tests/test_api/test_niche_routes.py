"""Niche and recommendation routes, called over HTTP against a real database.

Skipped unless TEST_DATABASE_URL is set. Every test runs inside a transaction
that is rolled back, so nothing written here is left behind.
"""

import os

import pytest
from sqlalchemy import event, func, select

from app.models.competitor import Competitor

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set; needs a real TimescaleDB"
)

UNKNOWN_NICHE_ID = 999_999_999
NICHE_SUB_RESOURCES = ["", "/products", "/competitors", "/keywords", "/reviews", "/financials", "/suppliers"]


async def test_list_niches_returns_envelope(client, seeded_niche):
    response = await client.get("/api/v1/niches/", params={"per_page": 5})
    assert response.status_code == 200
    body = response.json()
    assert {"items", "total", "page", "per_page", "total_pages"} <= body.keys()
    assert any(item["id"] == seeded_niche.id for item in body["items"])


@pytest.mark.parametrize("suffix", NICHE_SUB_RESOURCES)
async def test_niche_sub_resources_respond(client, seeded_niche, suffix):
    response = await client.get(f"/api/v1/niches/{seeded_niche.id}{suffix}")
    assert response.status_code == 200, response.text


async def test_recommendations_list(client, seeded_niche):
    response = await client.get("/api/v1/recommendations/")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_unknown_niche_is_404(client):
    assert (await client.get(f"/api/v1/niches/{UNKNOWN_NICHE_ID}")).status_code == 404


async def test_get_niche_runs_one_query(client, seeded_niche, db_session):
    """GET /niches/{id} must not fan out into one SELECT per relationship.

    Before Task F2, every Niche relationship was lazy="selectin", so loading
    one niche triggered ~10 extra SELECTs (one per relationship) whether or
    not the response used them. NicheResponse only reads scalar columns, so
    the route should issue exactly one SELECT.
    """
    statements: list[str] = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    # NOTE: db_session.bind is an AsyncConnection; the sync engine underneath
    # it is what actually fires "before_cursor_execute".
    sync_engine = db_session.bind.sync_connection.engine
    event.listen(sync_engine, "before_cursor_execute", record_statement)
    try:
        assert (await client.get(f"/api/v1/niches/{seeded_niche.id}")).status_code == 200
    finally:
        event.remove(sync_engine, "before_cursor_execute", record_statement)

    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1, selects


async def test_delete_niche_cascades_in_the_database(client, seeded_niche, db_session):
    """Deleting a niche must not need to load its children just to null their FKs.

    passive_deletes=True on the ORM relationships relies on the database's
    own ON DELETE CASCADE / SET NULL to clean up children, instead of
    SQLAlchemy loading each collection to update it in Python.
    """
    assert (await client.delete(f"/api/v1/niches/{seeded_niche.id}")).status_code == 204
    assert (await client.get(f"/api/v1/niches/{seeded_niche.id}")).status_code == 404

    remaining = (await db_session.execute(
        select(func.count()).select_from(Competitor).where(Competitor.niche_id == seeded_niche.id)
    )).scalar_one()
    assert remaining == 0
