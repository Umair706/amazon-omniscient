"""Niche and recommendation routes, called over HTTP against a real database.

Skipped unless TEST_DATABASE_URL is set. Every test runs inside a transaction
that is rolled back, so nothing written here is left behind.
"""

import os

import pytest

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
