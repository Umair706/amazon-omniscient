# AGENTS.md — setup guide for AI coding agents

This tells an AI agent (Claude Code, etc.) how to get productive in this repo
quickly and correctly. For deep architecture, read `CLAUDE.md`. For using
Omniscient *as tools* over MCP, read `docs/MCP.md`.

## What this is

Omniscient — an Amazon FBA product-research engine. Backend: Python 3.12,
FastAPI (async), SQLAlchemy 2.0 + asyncpg, Alembic, Celery + Redis,
PostgreSQL 16 + TimescaleDB, Playwright. Frontend: Next.js 14 + TypeScript +
Tailwind. LLM is configurable (Qwen/Claude/GPT or a free local model via Ollama).

## Run it

```bash
cp .env.example .env          # defaults run key-free (scraping-only)
docker compose up --build     # backend migrates the DB on start
```

- App: http://localhost:3000 · API: http://localhost:8000 · API docs: /docs
- The backend and frontend are **baked Docker images with no live mount for the
  frontend**: after changing frontend code you must
  `docker compose up -d --build frontend` to see it. The backend mounts its
  source and reloads, so backend edits are live.

## Test, migrate, typecheck

```bash
# Backend tests (run in the container; DB tests need TEST_DATABASE_URL)
docker exec <backend-container> pytest -q
# with the DB-backed tests:
#   -e TEST_DATABASE_URL=postgresql+asyncpg://omniscient:password@<db-host>:5432/omniscient

# Apply migrations by hand
docker compose exec backend alembic upgrade head

# Frontend
cd frontend && npx tsc --noEmit && npm run build
```

## Conventions & gotchas

- **Currency is per-marketplace.** Amazon prices are in the marketplace currency
  (AU = AUD). Always thread `marketplace` into `formatCurrency` and the sales
  model; supplier costs are USD and converted (`app/core/currency.py`).
- **Scoring is configurable.** Thresholds/weights/sales-multiplier live in
  `app/services/scoring_config.py`; a recommendation stores the exact rules it
  used (`scoring_snapshot`). Don't hardcode thresholds.
- **Honesty over guessing.** Assumed/estimated values are flagged as data gaps
  (`app/workers/pipeline_steps/assumptions.py`); never present a guess as a fact.
- **Never commit `frontend/tsconfig.tsbuildinfo`** (tsc rewrites it):
  `git checkout -- frontend/tsconfig.tsbuildinfo` before staging.
- **`internal/` is gitignored** — roadmap/todo/positioning/licensing-operator
  docs and the license-issuing guide live there, out of the public repo.
- Line endings: the repo is LF; Windows checkouts show CRLF warnings — harmless.

## Licensing

Omniscient is proprietary **open-core**. The base research runs free; some
features (export, blueprint, financial_report, multi_marketplace, api,
white_label) require a paid license key set as `LICENSE_KEY`. The gate is
offline (Ed25519-signed keys). A `402` from a premium route/tool means the
feature is locked — surface that to the user; do not try to bypass it. Operators
issue keys per the guide in `internal/ISSUING-LICENSES.md`.

## Use Omniscient as tools (MCP)

An LLM agent can drive Omniscient over MCP (discover niches, run analyses, read
scored briefs, save plans). Start the hosted server and connect:

```bash
docker compose --profile mcp up -d ollama   # optional: free local LLM
docker compose --profile mcp up -d mcp       # MCP over SSE on :8765
```

`.mcp.json` in this repo already points Claude Code at `http://localhost:8765/sse`.
See `docs/MCP.md` for the full tool list and Claude Desktop config.
