"""Omniscient MCP server entry point.

Exposes the research engine as tools an LLM agent can drive: instead of
Omniscient calling an LLM for sub-steps, an agent (Claude Desktop, etc.)
connects here and uses Omniscient as a toolbox — discovering niches, running
analyses, reading scored briefs, modelling economics, and saving plans — then
writes the strategy itself. See docs/MCP.md.

Two transports, chosen by MCP_TRANSPORT:
- stdio (default): a local process an MCP client launches. Run:
    cd backend && OMNISCIENT_API_URL=http://localhost:8000 python -m app.mcp_server
- sse: a hosted HTTP endpoint remote agents connect to. Set MCP_TRANSPORT=sse,
    MCP_PORT (default 8765), and optionally MCP_AUTH_TOKEN to require a
    "Authorization: Bearer <token>" header.
"""

import os

from app.mcp import mcp


def _run_sse() -> None:
    """Serve the MCP over HTTP/SSE, with an optional bearer-token gate."""
    import uvicorn
    from starlette.responses import JSONResponse

    app = mcp.sse_app()

    token = os.environ.get("MCP_AUTH_TOKEN", "")
    if token:
        # Require a bearer token on every request when one is configured.
        from starlette.middleware.base import BaseHTTPMiddleware

        class _BearerAuth(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                if request.headers.get("authorization") != f"Bearer {token}":
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
                return await call_next(request)

        app.add_middleware(_BearerAuth)

    uvicorn.run(
        app,
        host=os.environ.get("MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_PORT", "8765")),
    )


def main() -> None:
    if os.environ.get("MCP_TRANSPORT", "stdio").lower() in ("sse", "http"):
        _run_sse()
    else:
        mcp.run()


if __name__ == "__main__":
    main()
