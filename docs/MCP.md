# Omniscient as an MCP server — let an LLM drive the research

Omniscient normally *uses* an LLM for sub-steps. The MCP server flips that: an
LLM agent (Claude Desktop, Cursor, or any MCP client) connects to Omniscient
and uses it as a **toolbox** to research products, then writes the strategy and
business plan itself. The heavy data lives in Omniscient's database, so the
agent queries a tool when it needs a fact instead of holding everything in its
context — which is exactly what an LLM's limited context/memory needs.

## What the agent gets

**Read tools** — `list_niches`, `get_niche`, `get_niche_products`,
`get_niche_competitors`, `get_niche_suppliers`, `get_niche_financials`,
`get_product`, `list_recommendations`, `get_recommendation` (the full brief:
financials, suppliers, PPC, blueprint, risk flags, and the exact scoring rules).

**Action tools** (return a `job_id`; poll `job_status`) — `discover_opportunities`,
`analyze_keyword`, `reanalyze_niche`, `job_status`. Long work never blocks a call.

**Compute tools** (pure, no running API needed) — `estimate_monthly_sales`,
`landed_cost_and_margin` (converts a USD factory cost to a marketplace-currency
landed cost and computes pre/post-PPC margin).

**Workflow prompts** — `build_business_plan`, `validate_product_idea`,
`sourcing_plan`, `launch_plan`: guided playbooks that steer the agent to use the
tools and respect FAIL verdicts and data gaps.

**Resource** — `omniscient://scoring-guide`: how to read the score, tiers,
weights, hard filters, and data gaps (generated from the live config).

## Run it

1. Start the stack so the REST API is up: `docker compose up -d`.
2. Install the backend deps where you'll run the server (they include `mcp`):
   `cd backend && pip install -e .`
3. Start the MCP server (stdio):

   ```bash
   OMNISCIENT_API_URL=http://localhost:8000 python -m app.mcp_server
   ```

## Connect Claude Desktop

Add this to your Claude Desktop MCP config (`claude_desktop_config.json`),
adjusting the path to your checkout:

```json
{
  "mcpServers": {
    "omniscient": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/amazon-omniscient/backend",
      "env": { "OMNISCIENT_API_URL": "http://localhost:8000" }
    }
  }
}
```

Restart Claude Desktop, then ask it to "find a product I can sell in AU and
build a business plan" — it will call `discover_opportunities`, `analyze_keyword`,
`get_recommendation`, and write the plan from the real data.

## Hosted / remote agents (HTTP/SSE)

To let a remote agent connect (not a local stdio process), run the MCP over
HTTP/SSE. It's an opt-in compose service:

```bash
# optional: require a token
echo "MCP_AUTH_TOKEN=your-long-random-token" >> .env
docker compose --profile mcp up -d mcp
```

The agent connects to `http://<host>:8765/sse`. When `MCP_AUTH_TOKEN` is set,
every request must carry `Authorization: Bearer <token>`. Run it behind TLS
(a reverse proxy) before exposing it publicly. You can also start it directly:

```bash
cd backend
MCP_TRANSPORT=sse MCP_PORT=8765 OMNISCIENT_API_URL=http://localhost:8000 python -m app.mcp_server
```

## Notes

- The server is a thin client over the REST API plus a couple of pure-compute
  tools, so it stays in sync with the app automatically.
- It's read + dispatch + write-back (saved plans/notes/watchlists); it never
  bypasses the app's own gates.
- The bearer token is a coarse gate; per-customer auth tied to the license is a
  natural next step for a paid hosted offering.
