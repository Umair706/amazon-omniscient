# Project Omniscient -- Setup Guide

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Docker & Docker Compose | 24+ | `docker --version` |
| Python | 3.12+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| npm | 10+ | `npm --version` |
| Git | any | `git --version` |

---

## Option A: Docker Compose (Recommended)

This starts everything -- Postgres, Redis, backend, frontend, Celery worker, and Celery beat -- in one command.

### 1. Create your .env file

```bash
cd omniscient
cp .env.example .env
```

Open `.env` and fill in the required values:

```bash
# REQUIRED -- at least one LLM provider key
DASHSCOPE_API_KEY=sk-xxxx         # if using Qwen (default)
# OR
ANTHROPIC_API_KEY=sk-ant-xxxx     # if using Claude
# OR
OPENAI_API_KEY=sk-xxxx            # if using GPT

# OPTIONAL but recommended -- Amazon APIs
SP_API_CLIENT_ID=amzn1.application-oa2-client.xxxx
SP_API_CLIENT_SECRET=xxxx
SP_API_REFRESH_TOKEN=xxxx

# OPTIONAL -- rotating proxies (needed for scraping at scale)
PROXY_HOST=brd.superproxy.io
PROXY_PORT=22225
PROXY_USERNAME=xxxx
PROXY_PASSWORD=xxxx
```

Everything else has sensible defaults for local development.

### 2. Build and start

```bash
docker compose up --build
```

This will:
- Start **TimescaleDB** (PostgreSQL 16) on port `5432`
- Start **Redis 7** on port `6379`
- Build and start the **FastAPI backend** on port `8000`
- Build and start the **Next.js frontend** on port `3000`
- Start a **Celery worker** (4 concurrent threads)
- Start **Celery beat** (scheduled tasks)

### 3. Run the database migration

In a separate terminal:

```bash
docker compose exec backend alembic upgrade head
```

This creates all tables and TimescaleDB hypertables.

### 4. Install Playwright browsers (for scraping)

```bash
docker compose exec backend python -m playwright install chromium --with-deps
```

### 5. Verify

- Backend health: http://localhost:8000/health -- should return `{"status": "ok"}`
- Frontend: http://localhost:3000 -- should show the dashboard
- API docs: http://localhost:8000/docs -- Swagger UI

### Stop / restart

```bash
docker compose down          # stop all containers
docker compose up -d         # restart in background
docker compose logs -f backend  # tail backend logs
```

### Reset database

```bash
docker compose down -v       # removes volumes (all data!)
docker compose up --build
docker compose exec backend alembic upgrade head
```

---

## Option B: Local Development (No Docker for app code)

Use Docker only for Postgres and Redis; run backend and frontend directly for faster iteration.

### 1. Start infrastructure

```bash
cd omniscient
docker compose up db redis -d
```

Wait until both are healthy:

```bash
docker compose ps   # should show "healthy" for db and redis
```

### 2. Set up the backend

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium

# Create .env in the project root (omniscient/.env) if not done already
cp ../.env.example ../.env
# Edit ../.env with your API keys
```

### 3. Run database migration

```bash
cd backend
alembic upgrade head
```

Verify with:

```bash
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    e = create_async_engine('postgresql+asyncpg://omniscient:password@localhost:5432/omniscient')
    async with e.begin() as conn:
        r = await conn.execute(text('SELECT count(*) FROM information_schema.tables WHERE table_schema = \'public\''))
        print(f'Tables created: {r.scalar()}')
    await e.dispose()

asyncio.run(check())
"
```

Should print `Tables created: 14` (or more after migration 002).

### 4. Start the backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 5. Start Celery (optional, needed for background analysis)

In separate terminals:

```bash
# Terminal 2: Worker
cd backend
celery -A app.workers.celery_app worker --loglevel=info

# Terminal 3: Beat scheduler
cd backend
celery -A app.workers.celery_app beat --loglevel=info
```

### 6. Set up the frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend starts on http://localhost:3000 and proxies API calls to http://localhost:8000 via the `rewrites` in `next.config.js`.

---

## Environment Variables Reference

### Required for core functionality

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://omniscient:password@localhost:5432/omniscient` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `LLM_PROVIDER` | `qwen`, `anthropic`, or `openai` | `qwen` |
| `LLM_MODEL` | Model name for the chosen provider | `qwen-max-latest` |

### LLM provider keys (configure at least one)

| Variable | When needed |
|----------|-------------|
| `DASHSCOPE_API_KEY` | When `LLM_PROVIDER=qwen` |
| `ANTHROPIC_API_KEY` | When `LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | When `LLM_PROVIDER=openai` |
| `OPENAI_BASE_URL` | For OpenAI-compatible APIs (e.g., local models) |

### Amazon APIs (optional for initial setup)

| Variable | Description |
|----------|-------------|
| `SP_API_CLIENT_ID` | SP-API OAuth client ID |
| `SP_API_CLIENT_SECRET` | SP-API OAuth client secret |
| `SP_API_REFRESH_TOKEN` | SP-API refresh token |
| `SP_API_MARKETPLACE_ID` | Marketplace (default: `ATVPDKIKX0DER` = US) |
| `AMAZON_ADS_CLIENT_ID` | Advertising API client ID |
| `AMAZON_ADS_CLIENT_SECRET` | Advertising API client secret |
| `AMAZON_ADS_REFRESH_TOKEN` | Advertising API refresh token |

> **Note:** Apply for a **Private Developer** profile when registering with
> Amazon SP-API. A "Public/Third-party" profile requires a SOC2 security audit.

### Proxy (required for scraping at scale)

| Variable | Description |
|----------|-------------|
| `PROXY_PROVIDER` | `brightdata` or `smartproxy` |
| `PROXY_HOST` | Proxy hostname |
| `PROXY_PORT` | Proxy port |
| `PROXY_USERNAME` | Proxy auth username |
| `PROXY_PASSWORD` | Proxy auth password |

### Celery

| Variable | Default |
|----------|---------|
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` |

---

## Running Tests

```bash
cd backend
source .venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run a specific test module
pytest tests/test_scoring_service.py -v
```

---

## Running the First Analysis

Once the app is running:

1. Open http://localhost:3000
2. On the dashboard, enter a keyword in the "Analyze New Niche" form (e.g., `garlic press`)
3. Click **Analyze** -- this triggers a background Celery task
4. The analysis pipeline will:
   - Scrape Amazon search results for the keyword
   - Scrape product detail pages for the top results
   - Run competitor analysis and listing quality scoring
   - Analyze reviews via the LLM
   - Query supplier data
   - Generate financial projections (52 weeks, 3 scenarios)
   - Compute the Omniscient Score (0-100)
   - Generate a full product recommendation
5. Once complete, the niche appears in the **Niche Explorer** and a recommendation appears in **Recommendations**

> **Without Amazon API keys:** The scraper still works via Playwright (headless browser),
> but you need a proxy configured to avoid Amazon's bot detection. Without a proxy,
> scraping will likely fail after a few requests.

> **Without a proxy:** You can still explore the app by manually inserting test data
> into the database, or by configuring the SP-API keys which don't require a proxy.

---

## Project Structure Quick Reference

```
omniscient/
├── docker-compose.yml        # All services
├── .env.example              # Template for environment variables
├── .env                      # Your local config (git-ignored)
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml        # Python dependencies
│   ├── alembic.ini           # Alembic config
│   ├── migrations/           # Database migrations
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       └── 002_bsr_subcategory_and_review_velocity_gap.py
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── config.py         # Environment variable config
│   │   ├── dependencies.py   # Dependency injection
│   │   ├── api/              # Route handlers
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic
│   │   ├── core/             # Utilities (proxy, encryption, BSR regression)
│   │   ├── llm/              # LLM provider abstraction
│   │   └── workers/          # Celery tasks
│   └── tests/
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/              # Next.js App Router pages
│       │   ├── page.tsx              # Dashboard
│       │   ├── niches/               # Niche explorer + detail
│       │   ├── recommendations/      # Opportunity briefs
│       │   └── settings/             # API credentials config
│       ├── components/       # UI components
│       │   ├── ui/                   # Base components (button, card, etc.)
│       │   └── charts/               # Recharts visualizations
│       ├── lib/              # API client, utilities
│       └── types/            # TypeScript type definitions
```

---

## Troubleshooting

### "connection refused" on port 5432 or 6379
Postgres or Redis isn't running. Check `docker compose ps` and ensure both show "healthy".

### Alembic "target database is not up to date"
Run `alembic upgrade head` to apply pending migrations.

### "Cannot find module 'react'" in the frontend
Run `npm install` in the `frontend/` directory. These errors are expected before installing node_modules.

### Scraping fails with timeout or CAPTCHA
Amazon is blocking requests. You need a rotating residential proxy configured via `PROXY_*` env vars.

### "No module named 'app'" when running Celery
Make sure you're running Celery from the `backend/` directory, not the project root.

### LLM calls fail with authentication error
Check that you've set the correct API key for your chosen `LLM_PROVIDER`:
- `qwen` needs `DASHSCOPE_API_KEY`
- `anthropic` needs `ANTHROPIC_API_KEY`
- `openai` needs `OPENAI_API_KEY`

### TimescaleDB extension not found
The `docker-compose.yml` uses `timescale/timescaledb:latest-pg16`. If you're running Postgres locally without Docker, you need to install the TimescaleDB extension separately: https://docs.timescale.com/install/latest/
