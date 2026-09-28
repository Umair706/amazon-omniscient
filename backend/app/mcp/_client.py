"""Thin HTTP helpers the MCP tools use to call Omniscient's REST API."""

from __future__ import annotations

import os

import httpx

API_BASE = os.environ.get("OMNISCIENT_API_URL", "http://localhost:8000").rstrip("/")
API = f"{API_BASE}/api/v1"
_TIMEOUT = httpx.Timeout(30.0)


async def get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{API}{path}", params=params)
        r.raise_for_status()
        return r.json()


async def post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{API}{path}", json=body)
        r.raise_for_status()
        return r.json()
