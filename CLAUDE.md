# CLAUDE.md — Project Context for Claude Code

## What is this project?

Omniscient is an Amazon Product Research Engine. It identifies profitable FBA product opportunities by analyzing demand, competition, suppliers, ad costs, review barriers, and sales velocity. It outputs a scored recommendation (0-100 Omniscient Score) with a 52-week financial projection across bull/base/bear scenarios.

## Tech stack

- **Backend:** Python 3.12, FastAPI (async), SQLAlchemy 2.0 (async ORM), Alembic migrations, Celery + Redis for background tasks
- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts for charts
- **Database:** PostgreSQL 16 with TimescaleDB extension (hypertables for BSR and price time-series)
- **LLM:** Configurable provider system — Qwen (default via DashScope), Anthropic Claude, OpenAI GPT. All implement `BaseLLMClient` abstract class.
- **Scraping:** Playwright headless Chromium with rotating residential proxies

## Project layout

```
omniscient/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app factory, lifespan, middleware
│   │   ├── config.py          # Pydantic Settings from env vars
│   │   ├── dependencies.py    # DI: get_db, get_redis, get_llm_client
│   │   ├── api/               # FastAPI route handlers
│   │   ├── models/            # SQLAlchemy 2.0 ORM models (14 tables)
│   │   ├── schemas/           # Pydantic v2 request/response schemas
│   │   ├── services/          # Business logic layer
│   │   ├── core/              # Utilities (BSR regression, proxy, cache, encryption)
│   │   ├── llm/               # LLM provider abstraction + implementations
│   │   └── workers/           # Celery app, tasks, beat schedule
│   ├── migrations/            # Alembic migration versions
│   ├── tests/                 # pytest suite
│   └── pyproject.toml         # Python deps
├── frontend/
│   └── src/
│       ├── app/               # Next.js App Router pages
│       ├── components/        # UI components + charts
│       ├── lib/               # API client (axios), utilities
│       └── types/             # TypeScript type definitions
├── docker-compose.yml
└── .env.example
```

## Key architectural decisions

- **Async everywhere:** FastAPI + SQLAlchemy async sessions + asyncpg. Celery workers run in sync context but use `_run_async()` helper to call async service methods.
- **BSR regression:** `app/core/bsr_regression.py` converts BSR to estimated sales using `sales = A * BSR^(-B)` with category-specific coefficients. Handles both main-category and sub-category BSR (10x scaling factor).
- **TimescaleDB hypertables:** `bsr_history` and `price_history` use composite PKs `(time, product_id)` with `implicit_returning=False` for TimescaleDB compatibility.
- **LLM abstraction:** All LLM calls go through `BaseLLMClient.generate_json()` which handles JSON extraction, code fence stripping, and retries.
- **Scoring:** `ScoringService` computes 9 weighted sub-scores (0-100 each) and applies 9 hard disqualification filters. Any filter failure = FAIL tier.

## How to run

```bash
# Full stack via Docker
docker compose up --build
docker compose exec backend alembic upgrade head

# Or locally
cd backend && pip install -e ".[dev]" && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

## Database

- 14 tables, 2 hypertables (bsr_history, price_history)
- Migrations in `backend/migrations/versions/`
- Migration 001: initial schema with all tables + TimescaleDB hypertables
- Migration 002: BSR sub-category columns + review velocity gap support

## Testing

```bash
cd backend
pytest                    # all tests
pytest -v -k scoring      # just scoring tests
pytest --cov=app          # with coverage
```

71 tests across 4 modules: scoring_service, sales_forecast, supplier_service, recommendation_engine.

## Common patterns

- **Service constructors** accept `AsyncSession` and optionally `BaseLLMClient`
- **API routes** use `Depends(get_db)` for database sessions
- **Pydantic schemas** use `model_config = ConfigDict(from_attributes=True)` for ORM conversion
- **Frontend pages** are `"use client"` components that fetch from `/api/v1/*` via the axios instance in `src/lib/api.ts`
- **Frontend routing** uses Next.js App Router: `app/niches/[nicheId]/page.tsx`, `app/recommendations/[id]/page.tsx`

## Important files to know

| File | Purpose |
|------|---------|
| `backend/app/services/scoring_service.py` | Omniscient Score calculation (9 sub-scores + 9 filters) |
| `backend/app/services/recommendation_engine.py` | Master orchestrator that coordinates all services |
| `backend/app/services/sales_forecast.py` | 52-week bull/base/bear projections |
| `backend/app/services/competitor_service.py` | Listing quality scoring + vulnerability detection |
| `backend/app/services/supplier_service.py` | Landed cost calculator + margin analysis |
| `backend/app/core/bsr_regression.py` | BSR-to-sales conversion model |
| `backend/app/workers/tasks.py` | Celery task definitions (full analysis pipeline) |
| `backend/app/llm/base_client.py` | LLM provider abstract interface |
| `frontend/src/app/page.tsx` | Dashboard |
| `frontend/src/app/recommendations/[id]/page.tsx` | Opportunity brief (5 tabs) |

## Environment variables

All config is in `backend/app/config.py`. Key vars:
- `DATABASE_URL` — Postgres connection string
- `REDIS_URL` — Redis connection string
- `LLM_PROVIDER` — `qwen` | `anthropic` | `openai`
- `DASHSCOPE_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` — LLM auth
- `SP_API_*` — Amazon Selling Partner API credentials
- `PROXY_*` — Rotating proxy configuration
- `CELERY_BROKER_URL` — Celery Redis broker

## License

Proprietary. All rights reserved. Source is public for reference only.
