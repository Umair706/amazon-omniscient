"""Omniscient MCP server entry point.

Exposes the research engine as tools an LLM agent can drive: instead of
Omniscient calling an LLM for sub-steps, an agent (Claude Desktop, etc.)
connects here and uses Omniscient as a toolbox — discovering niches, running
analyses, reading scored briefs, and modelling economics — then writes the
strategy itself. The data lives in Omniscient's DB, so the agent queries tools
instead of holding everything in context. See docs/MCP.md.

Run (stdio), with the stack up:

    cd backend
    OMNISCIENT_API_URL=http://localhost:8000 python -m app.mcp_server
"""

from app.mcp import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
