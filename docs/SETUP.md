# Setup — bring your own keys

Omniscient is designed so that **you never pay Omniscient for data**. You plug in your own credentials and
the tool uses them. This keeps the project free to run for you, keeps the data legal and accurate, and
means the maintainer never carries a per-user data bill. Pick the tier that matches what you have.

The single most important fact: **the people this tool is built for — Amazon FBA sellers — already own the
credentials that make it accurate and legal.** If you sell on Amazon you already have an SP-API account and
an Ads account. Use them. They are free to you, location-independent, and never get blocked.

## The three tiers

| Tier | You provide | What you get | Cost to you |
|---|---|---|---|
| 0 — Scraping only | nothing | Approximate data for the marketplace your IP is in; reviews and Made-in-China supplier prices | free |
| 1 — Recommended | SP-API creds + local LLM | Real catalog, rank, pricing and FBA fees for your account; free AI analysis | free (you already have the keys) |
| 2 — Full | Tier 1 + a proxy | Reliable multi-marketplace scraping for the data SP-API doesn't cover | proxy cost only |

### What SP-API does and does not cover

SP-API is ground truth for the numbers it returns, but it is not the whole picture. Be clear on the split
so you know why Tier 2 still exists:

- **SP-API gives you:** catalog items, sales rank / BSR, competitive pricing, and real FBA fee estimates —
  all for the marketplace your account is registered in.
- **SP-API does not give you:** customer reviews, or supplier FOB prices. Those still come from scraping
  (reviews from Amazon, factory prices from Made-in-China.com).

So the review-pain-point analysis, the product blueprint, and the landed-cost/margin math (which needs
supplier FOB prices) depend on scraping even when SP-API is configured. Tier 1 makes the core metrics
accurate; Tier 2 makes the rest reliable.

## Tier 0 — scraping only (no keys)

Works out of the box. Copy the template and start the stack:

```bash
cp .env.example .env      # PROXY_PROVIDER=none, no keys — fine to start
docker compose up --build # the backend container migrates the DB on start
```

Open http://localhost:3000. Honest limits: you can only reliably analyse the Amazon marketplace your own IP
is in (from an Australian network, `marketplace: US` fails with a clear `wrong_marketplace` message, because
Amazon redirects you to the local store), and sales numbers are power-law estimates. Supplier FOB prices
come from Made-in-China.com, which needs no login and works from a datacenter IP; 1688 is only a fallback and
does require a login. Good for trying the engine; not what you charge a customer to rely on.

## Tier 1 — recommended: your SP-API + a free local LLM

This is the sweet spot for a seller: accurate account data and zero running cost.

### 1. Amazon SP-API credentials

Register as a developer in Seller Central (Settings → User Permissions → Developer, or the Solution Provider
Portal) and create a self-authorization to get a refresh token. Then in `.env`:

```
SP_API_CLIENT_ID=amzn1.application-oa2-client...
SP_API_CLIENT_SECRET=...
SP_API_REFRESH_TOKEN=Atzr|...
SP_API_MARKETPLACE_ID=ATVPDKIKX0DER      # US; use your marketplace's ID
```

When all three of client id, secret, and refresh token are set, the pipeline automatically prefers SP-API
for catalog and rank data (`product_source_for` returns `spapi`) and only uses the SERP to enrich page one.

### 2. A free local LLM (Ollama)

The AI steps (review clustering, product spec, blueprint, marketing) run against any OpenAI-compatible
endpoint. Ollama runs a capable model on your own machine for free:

```bash
# on the host, once
ollama pull qwen2.5:14b        # or llama3.1:8b on a smaller machine
```

In `.env`:

```
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:14b
```

The Docker compose file already points the backend and worker at `http://host.docker.internal:11434/v1`, so
the container reaches Ollama on your host with no extra config. Prefer a hosted model instead? Set
`LLM_PROVIDER=anthropic` / `openai` / `qwen` and the matching API key — those cost per token but need no
local GPU.

Without any LLM the pipeline still scrapes, scores, forecasts, and sources; the AI-written sections are
skipped and logged, not errored.

## Tier 2 — add a proxy for the data SP-API can't reach

Reviews and 1688 supplier prices need scraping, and reliable scraping (especially of a marketplace you are
not physically in) needs an IP in the right place. Options, cheapest first:

- **A free-tier cloud VM in the target region** (Oracle Always Free, or a 12-month AWS/GCP free tier) as a
  proxy or as the host you run the stack on. One stable IP, free, but a datacenter IP that Amazon blocks
  more readily — the `wrong_marketplace` / `captcha` verdicts on `/api/v1/niches/scrape-health` will tell
  you honestly whether it's holding up.
- **A paid residential proxy** (`PROXY_PROVIDER=brightdata` or `smartproxy` with host/port/user/pass). This
  is the only thing that reliably beats Amazon's blocking at volume, and it is the one place money genuinely
  helps. Everything else in this tool is designed to avoid needing it.

Set the review-velocity hard filter only after you trust your data:

```
REVIEW_VELOCITY_FILTER_ENABLED=false   # leave off until the velocity threshold is calibrated
```

## If your machine already runs Redis or Postgres

The stack publishes 5432 and 6379. If those are taken, add a git-ignored `docker-compose.override.yml`:

```yaml
services:
  redis:
    ports: !override []          # keep Redis on the internal network only
```

## Test the AI features for free (local model, no API key)

The LLM-powered steps (review analysis, product blueprint, PPC and marketing
strategy) normally need a provider key. To try them with no key and no cost,
use a local model with [Ollama](https://ollama.com).

**If you already have Ollama installed** (the common case), just pull a model
and point the app at it:

```bash
ollama pull qwen2.5:3b
```

Then open **Settings → LLM Provider**, choose **Ollama (Local)**, set the model
to **qwen2.5:3b**, and save. The containers reach your host Ollama at
`http://host.docker.internal:11434` automatically (`OLLAMA_BASE_URL`), so no
other setup is needed. CPU inference is slow but free; a larger model
(e.g. `qwen2.5:7b`) is more capable if your machine can spare the RAM.

**If you do NOT have Ollama installed**, a containerized one is bundled as a
fallback. Start it and pull a model, then point `OLLAMA_BASE_URL` at it:

```bash
docker compose --profile llm up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
# set OLLAMA_BASE_URL=http://ollama:11434/v1 for the backend/worker
```

## Licensing — unlocking Pro features

Note: these **license tiers** are different from the **setup tiers** above. The
setup tiers (0/1/2) are about which *data* you can reach. The license tiers are
about which *features* are unlocked.

Omniscient is open-core. The base research runs free. Some features need a paid
license key: CSV/PDF **export**, the product **blueprint**, the consolidated
**financial report**, **multi-marketplace**, the **api**, and **white-label**.

- Set `LICENSE_KEY` in your `.env` to unlock them; the app verifies it offline
  against `LICENSE_PUBLIC_KEY`. No key = free tier (everything still runs; the
  paid tabs just stay empty and premium routes return 402).
- License tiers: `free`, `pro`, `agency`. Maintainers issue keys per
  `internal/ISSUING-LICENSES.md`.

## Where to go next

- `GUIDE.md` — full provider setup, local vs cloud LLM options, proxy configuration, and troubleshooting.
- `README.md` — what Omniscient does and how it compares to other Amazon seller tools.
