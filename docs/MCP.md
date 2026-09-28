# Omniscient as an MCP server — let an LLM drive the research

Omniscient normally *uses* an LLM for sub-steps. The MCP server flips that: an
LLM agent (Claude Desktop, Cursor, or any MCP client) connects to Omniscient
and uses it as a **toolbox** to research products, then writes the strategy and
business plan itself. The heavy data lives in Omniscient's database, so the
agent queries a tool when it needs a fact instead of holding everything in its
context — which is exactly what an LLM's limited context/memory needs.

## What the agent gets

**Tools**
- `list_niches`, `get_niche` — analysed niches, scores, sub-scores.
- `list_recommendations`, `get_recommendation` — full opportunity briefs
  (financials, suppliers, PPC, blueprint, risk flags, and the exact scoring
  rules used).
- `discover_opportunities(seed, marketplace)` — rank candidate niches from a
  broad idea. Returns a `job_id`.
- `analyze_keyword(keyword, marketplace)` — start a full analysis. Returns a `job_id`.
- `reanalyze_niche(niche_id)` — re-run without re-scraping. Returns a `job_id`.
- `job_status(job_id)` — poll a background job to completion.
- `estimate_monthly_sales(bsr, category, marketplace)` — pure BSR→sales compute.

**Prompt**
- `build_business_plan(idea, marketplace)` — a guided workflow: discover →
  analyze → read the brief → write a sourced, costed plan with a go/no-go.

Long-running work returns a `job_id` the agent polls, so no tool call blocks.

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

## Notes

- The server is a thin client over the REST API plus a couple of pure-compute
  tools, so it stays in sync with the app automatically.
- It's read/observe + dispatch only; it never bypasses the app's own gates.
- Roadmap: expose supplier and landed-cost tools, resources for the scoring
  docs, and an HTTP/SSE transport for hosted/remote agents.
