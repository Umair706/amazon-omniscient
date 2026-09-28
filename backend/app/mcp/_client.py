"""HTTP helpers the MCP tools use to call Omniscient's REST API.

Both success and failure are returned as plain data the LLM can read: on success
the endpoint's JSON, on failure a structured {"error", "detail", "hint"} object.
Tools never raise a raw HTTP/connection exception at the agent — a failed call
comes back as data with an actionable hint, so the model can adjust rather than
see an opaque stack trace.
"""

from __future__ import annotations

import os

import httpx

API_BASE = os.environ.get("OMNISCIENT_API_URL", "http://localhost:8000").rstrip("/")
API = f"{API_BASE}/api/v1"
_TIMEOUT = httpx.Timeout(30.0)

# Actionable, LLM-facing hints per HTTP status.
_HINTS = {
    400: "The request was rejected. Check the inputs.",
    402: "This is a paid feature; it needs a license key. Tell the user rather than retrying.",
    404: "Not found. Verify the id with list_niches or list_recommendations first.",
    409: "Conflict — e.g. reanalyze_niche needs a niche that already has scraped products; analyze it first.",
    422: "Invalid input. Fix the arguments named in `detail` and try again.",
    429: "Rate limited. Wait a few seconds, then retry.",
}


def _error_from_response(r: httpx.Response) -> dict:
    detail: object = None
    try:
        body = r.json()
        detail = body.get("detail", body) if isinstance(body, dict) else body
    except Exception:
        detail = r.text[:300]
    return {
        "error": f"http_{r.status_code}",
        "detail": detail,
        "hint": _HINTS.get(r.status_code, "The request failed. Check inputs; if it persists, tell the user."),
    }


async def _request(method: str, path: str, **kwargs) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.request(method, f"{API}{path}", **kwargs)
    except httpx.RequestError as e:
        return {
            "error": "cannot_reach_omniscient",
            "detail": f"{type(e).__name__}: {e}",
            "hint": (
                f"Could not reach Omniscient at {API_BASE}. Make sure the stack is running "
                "(docker compose up) and OMNISCIENT_API_URL points at it."
            ),
        }
    if r.is_success:
        return r.json()
    return _error_from_response(r)


async def get(path: str, params: dict | None = None) -> dict:
    return await _request("GET", path, params=params)


async def post(path: str, body: dict) -> dict:
    return await _request("POST", path, json=body)
