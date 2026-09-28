"""GlobalExceptionMiddleware turns server-side failures into logged 500s, never silent 400s."""

import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.middleware import GlobalExceptionMiddleware


class Asin(BaseModel):
    asin: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if len(self.asin) != 10:
            raise ValueError(f"ASIN must be 10 characters, got {self.asin!r}")


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(GlobalExceptionMiddleware)

    @app.get("/bad-row")
    async def bad_row():
        return Asin(asin="SHORT")

    @app.get("/forbidden")
    async def forbidden():
        raise PermissionError("no")

    return app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as http:
        yield http


async def test_value_error_from_bad_data_is_a_logged_500(client, caplog):
    with caplog.at_level(logging.ERROR, logger="app.core.middleware"):
        response = await client.get("/bad-row")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "ASIN must be 10 characters" in caplog.text


async def test_permission_error_is_a_logged_403(client, caplog):
    with caplog.at_level(logging.WARNING, logger="app.core.middleware"):
        response = await client.get("/forbidden")
    assert response.status_code == 403
    assert "/forbidden" in caplog.text
