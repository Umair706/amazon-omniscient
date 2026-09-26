# Omniscient — Complete Setup & Configuration Guide

This guide covers everything you need to get Omniscient running: LLM provider setup (cloud and local), Amazon API registration, proxy configuration, current limitations, common issues, and areas for future improvement.

---

## Table of Contents

1. [LLM Provider Setup](#1-llm-provider-setup)
   - [Option A: Qwen via DashScope (Default)](#option-a-qwen-via-dashscope-default)
   - [Option B: Local Qwen via Ollama (Free, No API Key)](#option-b-local-qwen-via-ollama-free-no-api-key)
   - [Option C: Local Qwen via vLLM (Production-Grade Local)](#option-c-local-qwen-via-vllm-production-grade-local)
   - [Option D: Anthropic Claude](#option-d-anthropic-claude)
   - [Option E: OpenAI GPT](#option-e-openai-gpt)
   - [LLM Provider Comparison](#llm-provider-comparison)
2. [Amazon SP-API Setup (Private Developer)](#2-amazon-sp-api-setup-private-developer)
3. [Amazon Advertising API Setup](#3-amazon-advertising-api-setup)
4. [Proxy Setup for Scraping](#4-proxy-setup-for-scraping)
5. [Supplier Data APIs](#5-supplier-data-apis)
6. [Limitations](#6-limitations)
7. [Common Issues & Troubleshooting](#7-common-issues--troubleshooting)
8. [Areas for Improvement](#8-areas-for-improvement)

---

## 1. LLM Provider Setup

Omniscient uses an LLM for review sentiment analysis, pain point clustering, product spec generation, competitive insights, and launch playbook generation. You need at least one provider configured.

Set the provider in your `.env` file:

```bash
LLM_PROVIDER=qwen          # Qwen via DashScope API (default)
LLM_PROVIDER=ollama        # Local Qwen via Ollama (free)
LLM_PROVIDER=local         # Local model via vLLM / llama.cpp
LLM_PROVIDER=anthropic     # Anthropic Claude
LLM_PROVIDER=openai        # OpenAI GPT
```

### Option A: Qwen via DashScope (Default)

Qwen is the default provider. It runs via Alibaba Cloud's DashScope API.

**Get your API key:**

1. Go to https://dashscope.console.aliyun.com/
2. Create an Alibaba Cloud account (international accounts accepted)
3. Navigate to **DashScope** > **API Keys**
4. Click **Create API Key** and copy it

**Configure:**

```bash
LLM_PROVIDER=qwen
LLM_MODEL=qwen-max-latest
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

**Available Qwen models:**

| Model | Context | Notes |
|-------|---------|-------|
| `qwen-max-latest` | 32K | Best quality, recommended |
| `qwen-plus-latest` | 128K | Good balance of quality and cost |
| `qwen-turbo-latest` | 128K | Fastest, cheapest |
| `qwen2.5-72b-instruct` | 128K | Open-weight, strong reasoning |

**Pricing:** Qwen-Max costs roughly $0.004/1K input tokens, $0.012/1K output tokens. A full niche analysis uses ~50K-100K tokens total, costing approximately $0.50-$1.00 per analysis.

---

### Option B: Local Qwen via Ollama (Free, No API Key)

Run Qwen models locally on your machine using Ollama. No API key, no cost per query, no data leaves your machine.

**Requirements:**

- 16GB RAM minimum (for 7B models)
- 32GB RAM recommended (for 14B models)
- GPU with 8GB+ VRAM significantly improves speed (NVIDIA or Apple Silicon)

**Step 1: Install Ollama**

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows — download from https://ollama.com/download
```

**Step 2: Pull a Qwen model**

```bash
# Recommended: 14B parameter model (needs ~10GB RAM, ~8GB disk)
ollama pull qwen2.5:14b

# Lighter option: 7B parameter model (needs ~6GB RAM, ~4.5GB disk)
ollama pull qwen2.5:7b

# Strongest local option: 32B parameter model (needs ~20GB RAM, ~18GB disk)
ollama pull qwen2.5:32b

# Coding-focused variant
ollama pull qwen2.5-coder:14b
```

**Step 3: Start Ollama**

```bash
ollama serve
```

Ollama runs on `http://localhost:11434` by default. Verify it's running:

```bash
curl http://localhost:11434/v1/models
```

**Step 4: Configure Omniscient**

```bash
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:14b
# No API key needed
# No OPENAI_BASE_URL needed (defaults to http://localhost:11434/v1)
```

**Step 5: Test it**

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:14b",
    "messages": [{"role": "user", "content": "Summarize the benefits of private label Amazon FBA in 3 bullet points."}]
  }'
```

**Performance expectations (Apple M2 Pro, 32GB RAM):**

| Model | Speed | Quality |
|-------|-------|---------|
| `qwen2.5:7b` | ~30 tokens/sec | Good for basic analysis |
| `qwen2.5:14b` | ~15 tokens/sec | Recommended balance |
| `qwen2.5:32b` | ~5 tokens/sec | Closest to API quality |

A full niche analysis generates ~5K-10K output tokens across multiple LLM calls, so expect 5-15 minutes with the 14B model on CPU. GPU acceleration cuts this to 1-3 minutes.

---

### Option C: Local Qwen via vLLM (Production-Grade Local)

vLLM provides higher throughput than Ollama, particularly with GPU. Best for running Omniscient on a dedicated server.

**Requirements:**

- Linux (recommended) or macOS
- NVIDIA GPU with 16GB+ VRAM (A10, A100, RTX 4090)
- Python 3.10+

**Step 1: Install vLLM**

```bash
pip install vllm
```

**Step 2: Start the server**

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-14B-Instruct \
  --port 8080 \
  --max-model-len 32768
```

**Step 3: Configure Omniscient**

```bash
LLM_PROVIDER=local
LLM_MODEL=Qwen/Qwen2.5-14B-Instruct
OPENAI_BASE_URL=http://localhost:8080/v1
# No API key needed
```

**Other compatible servers:**

| Server | Install | Start Command |
|--------|---------|---------------|
| llama.cpp | `brew install llama.cpp` | `llama-server -m model.gguf --port 8080` |
| LocalAI | Docker | `docker run -p 8080:8080 localai/localai` |
| LM Studio | GUI app | Start server from UI, port 1234 |
| text-generation-inference | Docker | `docker run -p 8080:80 ghcr.io/huggingface/text-generation-inference` |

All of these expose an OpenAI-compatible API that Omniscient can connect to via the `local` provider.

---

### Option D: Anthropic Claude

**Get your API key:**

1. Go to https://console.anthropic.com/
2. Create an account and add a payment method
3. Navigate to **API Keys**
4. Click **Create Key** and copy it

**Configure:**

```bash
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxx
```

**Available models:**

| Model | Notes |
|-------|-------|
| `claude-sonnet-4-20250514` | Default, good balance |
| `claude-opus-4-20250514` | Highest quality, higher cost |
| `claude-haiku-3-20250307` | Fastest, cheapest |

---

### Option E: OpenAI GPT

**Get your API key:**

1. Go to https://platform.openai.com/
2. Create an account and add a payment method
3. Navigate to **API Keys** (left sidebar)
4. Click **Create new secret key** and copy it

**Configure:**

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

**Available models:**

| Model | Notes |
|-------|-------|
| `gpt-4o` | Default, best quality/cost ratio |
| `gpt-4o-mini` | Cheaper, still capable |
| `gpt-4-turbo` | Older, higher cost |

---

### LLM Provider Comparison

| Provider | Cost | Quality | Speed | Privacy | Setup |
|----------|------|---------|-------|---------|-------|
| Qwen (DashScope) | Low ($0.50-1/analysis) | High | Fast | Data sent to Alibaba Cloud | Easy (API key) |
| Ollama (local) | Free | Medium-High (depends on model size) | Slow on CPU | Full privacy | Medium (install + download model) |
| vLLM (local) | Free (needs GPU) | High | Fast with GPU | Full privacy | Complex (GPU setup) |
| Anthropic Claude | Medium ($1-3/analysis) | Highest | Fast | Data sent to Anthropic | Easy (API key) |
| OpenAI GPT | Medium ($1-2/analysis) | High | Fast | Data sent to OpenAI | Easy (API key) |

### LLM Provider Selection Flow

```mermaid
flowchart TD
    START(["Choose LLM Provider"]) --> Q1{"Need full<br/>data privacy?"}

    Q1 -->|Yes| Q2{"Have a<br/>GPU?"}
    Q1 -->|No| Q3{"Budget<br/>priority?"}

    Q2 -->|Yes, 16GB+ VRAM| VLLM["vLLM<br/>LLM_PROVIDER=local<br/>Best local throughput"]
    Q2 -->|No / Apple Silicon| OLLAMA["Ollama<br/>LLM_PROVIDER=ollama<br/>Easy local setup"]

    Q3 -->|Lowest cost| QWEN["Qwen via DashScope<br/>LLM_PROVIDER=qwen<br/>~$0.50/analysis"]
    Q3 -->|Best quality| CLAUDE["Anthropic Claude<br/>LLM_PROVIDER=anthropic<br/>~$1-3/analysis"]
    Q3 -->|Balanced| GPT["OpenAI GPT<br/>LLM_PROVIDER=openai<br/>~$1-2/analysis"]

    style START fill:#3b82f6,color:#fff
    style QWEN fill:#10b981,color:#fff
    style CLAUDE fill:#8b5cf6,color:#fff
    style GPT fill:#06b6d4,color:#fff
    style OLLAMA fill:#f59e0b,color:#fff
    style VLLM fill:#ef4444,color:#fff
```

### LLM Integration Architecture

```mermaid
graph TB
    subgraph "LLM Abstraction Layer"
        BASE["BaseLLMClient<br/>(abstract)"]
        BASE --> QWEN["QwenClient"]
        BASE --> ANTH["AnthropicClient"]
        BASE --> OAI["OpenAIClient"]
    end

    subgraph "Services Using LLM"
        RA["ReviewAnalyzer"]
        NI["NicheIntelligence"]
        PB["ProductBlueprint"]
        SG["SpecGenerator"]
        SM["SupplierMatch"]
        PPC["PPCService"]
        RS["ReviewStrategy"]
        MK["Marketing"]
        FR["FinancialReport"]
    end

    RA --> BASE
    NI --> BASE
    PB --> BASE
    SG --> BASE
    SM --> BASE
    PPC --> BASE
    RS --> BASE
    MK --> BASE
    FR --> BASE

    QWEN -->|API| DS["DashScope API"]
    ANTH -->|API| AC["Anthropic API"]
    OAI -->|API| OA["OpenAI API /<br/>Ollama / vLLM"]

    style BASE fill:#6366f1,color:#fff
    style QWEN fill:#10b981,color:#fff
    style ANTH fill:#8b5cf6,color:#fff
    style OAI fill:#06b6d4,color:#fff
```

---

## 2. Amazon SP-API Setup (Private Developer)

The Selling Partner API (SP-API) provides official access to product catalog data, pricing, fees, and sales rank. It is optional — Omniscient can fall back to Playwright scraping — but SP-API is more reliable and faster.

### Register as a Private Developer

**Important:** Apply as a **Private Developer**, not Public/Third-Party. Public developer profiles require SOC2 security audits, insurance documentation, and a lengthy approval process. Private developer access is granted to sellers who want to access their own data and is much simpler.

**Step 1: Have an Amazon Seller Central account**

You need an active Professional selling account ($39.99/month). Register at https://sellercentral.amazon.com/ if you don't have one.

**Step 2: Register as a developer**

1. Log into Seller Central
2. Go to **Apps & Services** > **Develop Apps**
3. Click **Register as a Developer** (if prompted)
4. Select **Private Developer** when asked about your profile type
5. Fill out the form:
   - **Organization name:** Your business name
   - **Organization URL:** Your website (or your seller storefront URL)
   - **Data access purpose:** Select "Analyze my own selling data"
6. Submit and wait for approval (usually 1-3 business days)

**Step 3: Create an application**

1. In Seller Central, go to **Apps & Services** > **Develop Apps**
2. Click **Add new app client**
3. Under **API Type**, select **SP API**
4. Under **IAM ARN**, you'll need to create an IAM role (see next step)
5. Fill in the app name and description
6. Select the roles you need:
   - **Product Listing** — for catalog data
   - **Pricing** — for Buy Box and competitive pricing
   - **Reports** — for sales and inventory reports

**Step 4: Create an AWS IAM role**

SP-API requires an IAM role for authentication:

1. Go to https://console.aws.amazon.com/iam/
2. Create a new role with the trust policy for SP-API (Amazon provides the exact JSON in their docs)
3. Attach the `AmazonSPAPIRole` policy
4. Copy the role ARN and paste it into your app registration

**Step 5: Get your credentials**

After approval, go to your app details in Seller Central to find:

- **Client ID** (`SP_API_CLIENT_ID`)
- **Client Secret** (`SP_API_CLIENT_SECRET`)

**Step 6: Generate a refresh token**

1. In your app details, click **Authorize** under the **OAuth** section
2. This generates a refresh token that doesn't expire
3. Copy the refresh token (`SP_API_REFRESH_TOKEN`)

**Configure:**

```bash
SP_API_CLIENT_ID=amzn1.application-oa2-client.xxxxxxxx
SP_API_CLIENT_SECRET=amzn1.oa2-cs.v1.xxxxxxxx
SP_API_REFRESH_TOKEN=Atzr|xxxxxxxx
SP_API_MARKETPLACE_ID=ATVPDKIKX0DER   # US marketplace (default)
```

**Marketplace IDs for other regions:**

| Marketplace | ID |
|------------|-----|
| US | `ATVPDKIKX0DER` |
| UK | `A1F83G8C2ARO7P` |
| Germany | `A1PA6795UKMFR9` |
| Canada | `A2EUQ1WTGCTBG2` |
| Japan | `A1VC38T7YXB528` |

---

## 3. Amazon Advertising API Setup

The Advertising API provides keyword search volume, CPC estimates, and campaign data. This powers the PPC Viability sub-score in the Omniscient Score.

**Step 1: Request access**

1. Go to https://advertising.amazon.com/API
2. Click **Request Access**
3. Fill out the form with your business details
4. Approval takes 3-7 business days

**Step 2: Create an application**

1. Once approved, go to the **Advertising Console** > **API** > **Applications**
2. Register a new application
3. Get your **Client ID** and **Client Secret**

**Step 3: Generate a refresh token**

1. Go through the OAuth flow via:
   ```
   https://www.amazon.com/ap/oa?client_id=YOUR_CLIENT_ID&scope=advertising::campaign_management&response_type=code&redirect_uri=YOUR_REDIRECT_URI
   ```
2. Exchange the authorization code for tokens via the token endpoint
3. Save the refresh token

**Step 4: Get your Profile ID**

```bash
curl -H "Amazon-Advertising-API-ClientId: YOUR_CLIENT_ID" \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     https://advertising-api.amazon.com/v2/profiles
```

The response contains your profile ID for the US marketplace.

**Configure:**

```bash
AMAZON_ADS_CLIENT_ID=amzn1.application-oa2-client.xxxxxxxx
AMAZON_ADS_CLIENT_SECRET=xxxxxxxx
AMAZON_ADS_REFRESH_TOKEN=Atzr|xxxxxxxx
AMAZON_ADS_PROFILE_ID=1234567890
```

**Without Advertising API:** Omniscient falls back to estimated CPC data based on category averages. The PPC Viability sub-score will be less accurate but still functional.

---

## 4. Proxy Setup for Scraping

Omniscient uses Playwright (headless Chromium) to scrape Amazon search results and product pages. Amazon aggressively blocks automated requests, so you need a rotating residential proxy for reliable scraping.

### Recommended Proxy Providers

| Provider | Type | Approx. Cost | Notes |
|----------|------|-------------|-------|
| BrightData | Residential | $10-15/GB | Largest proxy network, best success rates |
| SmartProxy | Residential | $8-12/GB | Good alternative, simple setup |
| Oxylabs | Residential | $10-15/GB | Strong Amazon scraping support |

### BrightData Setup

1. Register at https://brightdata.com/
2. Go to **Proxies & Scraping** > **Residential Proxies**
3. Create a new zone (e.g., "omniscient")
4. Set targeting to **United States**
5. Get your credentials from the zone settings

```bash
PROXY_PROVIDER=brightdata
PROXY_HOST=brd.superproxy.io
PROXY_PORT=22225
PROXY_USERNAME=brd-customer-xxxxx-zone-omniscient
PROXY_PASSWORD=xxxxxxxx
```

### SmartProxy Setup

1. Register at https://smartproxy.com/
2. Go to **Residential Proxies** > **Setup**
3. Get your credentials

```bash
PROXY_PROVIDER=smartproxy
PROXY_HOST=gate.smartproxy.com
PROXY_PORT=10001
PROXY_USERNAME=spxxxxxxxx
PROXY_PASSWORD=xxxxxxxx
```

### Proxy System Architecture

```mermaid
flowchart TD
    SCRAPER["ScraperService /<br/>SupplierScraper"] --> PM["ProxyManager"]

    PM --> Q{"PROXY_PROVIDER?"}

    Q -->|none| DIRECT["Direct Connection<br/>No proxy"]
    Q -->|free| FREE["Free Proxies<br/>proxyscrape.com API"]
    Q -->|brightdata| BD["BrightData<br/>Residential Proxy"]
    Q -->|smartproxy| SP["SmartProxy<br/>Residential Proxy"]

    FREE --> ROTATE["Auto-Rotation<br/>+ Failure Tracking"]
    ROTATE --> BL["Blacklist Failed IPs"]
    ROTATE --> FALL["Fallback to Direct<br/>if API unavailable"]

    BD --> SESSION["Session-Based Rotation<br/>username-session-{rand}"]
    SP --> SESSION

    DIRECT --> BS["BrowserSession<br/>1 per pipeline run"]
    FREE --> BS
    BD --> BS
    SP --> BS

    BS --> PACER["Pacer<br/>jittered per-domain gap"]
    PACER --> LOAD["Page load<br/>(images/media/fonts blocked)"]
    LOAD --> CLASSIFY["classify_page()<br/>ok / captcha / soft_block / server_error"]
    CLASSIFY -->|ok| AMZ["Amazon.com"]
    CLASSIFY -->|ok| ALI["1688.com"]
    CLASSIFY -->|captcha or server_error| ROTATE["rotate()<br/>new proxy + new persona<br/>max 3x per session"]
    ROTATE --> BS
    ROTATE -->|cap exceeded| FAIL["ScrapingError<br/>niche marked failed"]

    style SCRAPER fill:#3b82f6,color:#fff
    style PM fill:#f59e0b,color:#fff
    style BS fill:#10b981,color:#fff
    style CLASSIFY fill:#8b5cf6,color:#fff
    style ROTATE fill:#ef4444,color:#fff
```

### Without a Proxy

If you don't configure a proxy:
- SP-API calls still work (they don't need a proxy)
- Playwright scraping will likely fail after 5-10 requests due to Amazon's bot detection
- You can insert test data into the database manually for development

---

### Scraping resilience (how the scraper avoids getting blocked)

Beyond the proxy itself, the scraper has a second layer of defenses against Amazon's
bot detection. These live in `backend/app/scraping/` and are used by
`ScraperService` (`backend/app/services/scraper_service.py`).

**One browser session per analysis run, with a coherent persona**

`BrowserSession` (`app/scraping/session.py`) launches a single Chromium browser +
context for a whole pipeline run and reuses it for every page load. This matters
because a mismatched user-agent/platform/locale, or a fresh cookie jar on every
single page request, are two of the strongest signals Amazon uses to flag automated
traffic. `app/scraping/persona.py` builds one coherent `Persona` per session — the
user-agent, `navigator.platform`, viewport, locale and timezone are all derived
from the same random platform choice, so they never contradict each other.

**Per-domain jittered pacing**

`app/scraping/pacing.py` enforces a minimum, randomized gap between requests to the
same domain, shared process-wide:

- Amazon: `AMAZON_GAP_SECONDS = (3.0, 7.0)` seconds
- 1688.com: `ALIBABA_GAP_SECONDS = (5.0, 10.0)` seconds

Each `BrowserSession.load()` call waits its turn before navigating.

**Shared pacing across worker processes**

With Celery running at `--concurrency=4`, four in-process `Pacer` instances used
to let four workers hit Amazon at once — four times the configured rate. Every
`BrowserSession` and the 1688 `SupplierScraper` (including `SupplierMatchService`
searches) now pace through `SharedPacer` (`app/scraping/pacing.py`) instead: it
holds the "last request wins" slot in Redis under the key `pace:{domain}` (a
`SET pace:{domain} NX PX <gap>`), so one gap is shared by every worker process,
not one gap per process. `REDIS_URL` must be reachable from every worker for
this coordination to happen. If a `SharedPacer` call to Redis fails for any
reason, that instance switches to its local `Pacer` fallback for the rest of the
run and logs "Shared pacing unavailable" once — pacing degrades back to
per-process instead of the run failing.

**Image/media/font blocking**

`BrowserSession` aborts `image`, `media`, and `font` requests before they reach the
proxy, with one exception: any URL containing `/captcha/` is always let through, in
case a challenge image is ever needed to identify or solve a block. This exists
because residential proxy bandwidth is billed per GB, and Omniscient never parses
images, fonts, or media from a scraped page.

**Block detection and rotation**

Every loaded page is classified by `classify_page()` (`app/scraping/block_detection.py`)
into one of four verdicts:

- `ok` — the page we asked for actually rendered
- `captcha` — Amazon's "Robot Check" / "Enter the characters you see below" challenge
- `soft_block` — a 200 OK response, but the expected content selector never appeared
- `server_error` — HTTP 5xx

`ScraperService._load()` rotates the session (new proxy identity + new persona,
`BrowserSession.rotate()`) whenever it sees `captcha` or `server_error`, and also
on a Playwright navigation error (timeout, dead proxy tunnel) — that case is
recorded as its own `timeout` verdict since `BrowserSession.load()` raises rather
than returning a verdict for it. `soft_block` does not trigger a rotation; it is
used for cases like "no more review pages" where a fresh identity would not help.

A session can rotate at most `MAX_ROTATIONS_PER_SESSION = 3` times. On the fourth
consecutive block, `BrowserSession.rotate()` raises, `ScraperService` wraps that in
a `ScrapingError`, the niche's pipeline run is marked failed, and Celery's own
retry policy for that task decides whether to try again later.

**Redis page cache**

`PageCache` (`app/scraping/page_cache.py`) caches parsed scrape results in Redis so
repeated requests for the same page (sub-niche flows re-querying a parent niche's
products, or a niche revisited soon after) don't re-scrape it:

- Search result pages (`serp`, `serp_meta`): `SERP_TTL_SECONDS = 6` hours
- Product pages (`product`): `PRODUCT_TTL_SECONDS = 24` hours

Only pages classified `ok` are ever written to the cache — a captcha or soft-block
response is never stored as if it were real data. A forced re-run (`force=true` on
the analyze endpoints) bypasses the cache entirely and always re-scrapes. The cache
is failure-tolerant: a Redis outage is treated as a cache miss, not an error, so
scraping keeps working with Redis down, just without the speedup.

**Telemetry: `scrape_events` and `GET /api/v1/niches/scrape-health`**

Every page load attempt writes one row to the `scrape_events` table (migration
014, `app/models/scrape_event.py`) — including ones that needed a rotation, so a
load that took two rotations shows up as three rows. Each row records the site,
`url_kind` (`serp` | `product` | `reviews` | `serp_meta` | `rank`), verdict (`ok` |
`captcha` | `soft_block` | `server_error` | `timeout`), proxy label, and duration.
Recording is fire-and-forget (`app/scraping/events.py`) — a telemetry failure never
breaks scraping.

`GET /api/v1/niches/scrape-health` returns counts by site and verdict over the
last `SCRAPE_HEALTH_WINDOW_HOURS = 24` hours. Concrete thresholds to act on:

- **`captcha` > 20% of loads in the last 24h** — the current proxy is burned out
  or too small a pool. Switch `PROXY_PROVIDER` to a residential provider
  (`brightdata`/`smartproxy`) if you're on `free` or `none`, or if already on a
  paid provider, reduce concurrent analysis volume.
- **A spike in `timeout` verdicts** — the proxy itself is dead (tunnel failures,
  connection refused), not being blocked by Amazon. Check proxy credentials and
  provider status before touching pacing or personas.

**SP-API-first when credentials exist**

When `SP_API_CLIENT_ID`, `SP_API_CLIENT_SECRET`, and `SP_API_REFRESH_TOKEN` are all
set (`app/workers/pipeline_steps/product_source.py`), the pipeline prefers the
official, unblockable SP-API over scraping wherever it can:

- **Keyword search:** uses SP-API Catalog Items (`search_catalog_products`)
  instead of scraping search result pages, as long as it returns at least
  `MIN_SPAPI_SEARCH_RESULTS = 10` results. Page 1 of the SERP is still scraped
  once, purely to enrich the catalog results with price, rating, and badges
  (sponsored/Amazon's Choice/Best Seller/FBA) that Catalog Items doesn't provide.
  Too few catalog results, or an SP-API error, falls back to the old 3-page SERP
  scrape.
- **6-hourly BSR/price tracker:** uses SP-API `get_rank_snapshot` for BSR instead
  of scraping every product page. The page is still scraped for price/stock, but
  only for products already below `LOW_STOCK_THRESHOLD = 20` units, since those
  are the ones whose price/stock is likely to have moved since the last snapshot.

Without SP-API credentials configured, everything falls back to full Playwright
scraping as before.

**Current Amazon limitations**

- `/product-reviews/` now redirects to a sign-in page on some marketplaces (seen
  on Amazon AU in 2026). When that happens, `scrape_reviews` returns `[]` for that
  ASIN rather than treating the redirect as a block (rotating a proxy would not
  help — it's a genuine sign-in wall). Review data instead comes entirely from the
  "Top reviews" section embedded in the product page itself, capped at 10 reviews
  per ASIN (`_MAX_PAGE_REVIEWS`) to keep one listing from dominating a niche's
  review set.

---

## 5. Supplier Data APIs

These are optional and enhance the supplier sourcing and landed cost calculation.

### Alibaba/1688 API

Used to fetch supplier data, MOQ, and FOB pricing from Alibaba and 1688 (domestic China marketplace).

1. Register at https://open.alibaba.com/
2. Create an application
3. Get your App Key and App Secret

```bash
ALIBABA_APP_KEY=xxxxxxxx
ALIBABA_APP_SECRET=xxxxxxxx
```

### Freightos API

Used for real-time freight rate estimation (China to US FBA warehouse).

1. Register at https://www.freightos.com/api/
2. Request API access
3. Get your API key

```bash
FREIGHTOS_API_KEY=xxxxxxxx
```

**Without these APIs:** Omniscient uses hardcoded freight rate estimates ($4-6/kg sea freight, $8-12/kg air freight) and estimated supplier pricing based on category averages. The Supplier sub-score will be less accurate but functional.

### End-to-End Data Flow

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as FastAPI
    participant Redis
    participant Worker as Celery Worker
    participant DB as PostgreSQL
    participant AMZ as Amazon
    participant ALI as 1688.com
    participant LLM as LLM Provider

    User->>FE: Enter keyword
    FE->>API: POST /jobs/analyze
    API->>DB: Create Niche (status=pending)
    API->>Redis: Dispatch run_full_analysis task
    API-->>FE: Return job_id

    loop Poll every 2s
        FE->>API: GET /jobs/{id}/status
        API-->>FE: {progress: N%, status}
    end

    Redis->>Worker: Consume task

    rect rgb(255, 243, 224)
        Note over Worker,AMZ: Phase 1 — Scraping
        Worker->>AMZ: Scrape search results (3 pages)
        AMZ-->>Worker: 60 products
        Worker->>DB: Save products
        Worker->>AMZ: Scrape top 20 detail pages
        AMZ-->>Worker: Enriched data + reviews
        Worker->>DB: Save reviews + BSR/price history
    end

    rect rgb(219, 234, 254)
        Note over Worker,LLM: Phase 2 — AI Analysis
        Worker->>LLM: Analyze reviews
        LLM-->>Worker: Pain points + sentiment
        Worker->>LLM: Generate blueprint + specs
        LLM-->>Worker: Product design
        Worker->>DB: Save competitors + pain points
    end

    rect rgb(252, 231, 243)
        Note over Worker,ALI: Phase 3 — Suppliers
        Worker->>ALI: Scrape suppliers
        ALI-->>Worker: Factory prices + MOQ
        Worker->>LLM: Translate + match suppliers
        Worker->>DB: Save suppliers + matches
    end

    rect rgb(209, 250, 229)
        Note over Worker,LLM: Phase 4 — Strategy
        Worker->>LLM: PPC + review + marketing strategy
        LLM-->>Worker: Full strategies
        Worker->>DB: Save projections + recommendation
    end

    Worker->>DB: Update niche status=completed
    Worker->>Redis: Store result

    FE->>API: GET /recommendations/{id}
    API->>DB: Load full recommendation
    API-->>FE: Complete opportunity brief
    FE-->>User: Display 5-tab report
```

---

## 6. Limitations

### Data Collection

- **No official Amazon scraping API:** Playwright scraping is against Amazon's ToS. Use at your own risk. SP-API is the legal path but provides less data (no review text, no search result page scraping).
- **Proxy costs:** Reliable scraping requires residential proxies, which cost $8-15/GB. A full niche analysis scrapes 30-60 pages (~50-100MB), costing roughly $0.50-$1.50 per analysis in proxy bandwidth.
- **Rate limits:** Amazon throttles requests. The scraper has built-in delays (2-5 seconds between requests) but high-volume use may still trigger CAPTCHAs.
- **SP-API throttling:** SP-API has strict rate limits (varies by endpoint, typically 1-15 requests/second). The service handles retries with exponential backoff, but bulk operations are slow.

### BSR-to-Sales Estimation

- **Regression coefficients are estimates:** The power-law model (`sales = A * BSR^(-B)`) uses coefficients calibrated against publicly available data. Accuracy varies by category and season.
- **Sub-category BSR:** The 10x scaling factor for sub-category BSR is an approximation. Actual ratios vary from 5x-20x depending on the sub-category relative to its parent.
- **Seasonal products:** BSR fluctuates significantly for seasonal products. A point-in-time BSR snapshot may not represent annual averages.
- **New vs. established products:** BSR behaves differently for newly launched products (volatile) vs. established ones (stable). The model doesn't distinguish between these.
- **Review-velocity trap (hard filter #9) is observe-only by default:** the reviews-per-100-sales ratio is computed from tracked review-count snapshots and stored as `risk_flags.review_velocity_gap_ratio`, but it disqualifies a niche only when `REVIEW_VELOCITY_FILTER_ENABLED=true`. The count comes from Amazon's global ratings count, which grows faster than written reviews, so the 5 %/3 % trap thresholds are not yet calibrated for it. SP-API-tracked products never get a review count, so the window only accumulates from page scrapes (analysis-time and scrape-based tracking).

### LLM Analysis

- **Quality depends on model:** Local models (7B-14B parameters) produce noticeably lower quality analysis compared to cloud APIs (Qwen-Max, GPT-4o, Claude Sonnet). The 32B model closes most of the gap.
- **JSON parsing:** The LLM must return valid JSON for structured analysis. Smaller models sometimes produce malformed JSON, triggering retries (doubling LLM costs/time).
- **Hallucination risk:** LLMs may generate plausible but incorrect product specifications, supplier recommendations, or market insights. Always verify critical data points manually.
- **No real-time knowledge:** LLMs don't have access to current Amazon data. They analyze the data provided to them by the scraper and other services.

### Financial Projections

- **Estimates, not guarantees:** The 52-week projections are modeled scenarios, not predictions. Actual results depend on execution quality, market changes, competition, and many other factors.
- **FBA fee estimates:** FBA fees are calculated based on known fee schedules but Amazon changes fees periodically. The calculator may be slightly outdated.
- **Tariff rates:** Section 301 tariff rates and customs duty percentages are hardcoded estimates. Actual rates depend on the specific HTS code and current trade policy.

### Infrastructure

- **Single-user design:** The current implementation has no user authentication or multi-tenancy. It's designed for personal use on a local machine or private server.
- **No real-time updates:** Data is collected at analysis time and stored. There's no continuous monitoring or automatic re-analysis unless Celery beat tasks are configured.
- **TimescaleDB dependency:** The BSR and price time-series features require TimescaleDB. Standard PostgreSQL works for everything else, but hypertable queries will fail without the extension.
- **Not every browser is on the shared Redis pacer yet:** `AlibabaLoginService` (the 1688 login page, used only when stored cookies are invalid), the keyword-research scraper session behind `POST /niches/{id}/keywords/research`, and `AmazonLoginService` (currently has no callers) still pace themselves per process rather than through `SharedPacer`.

---

## 7. Common Issues & Troubleshooting

### LLM Issues

**"Unknown LLM_PROVIDER" error**
```
ValueError: Unknown LLM_PROVIDER: 'xxx'. Supported: qwen, anthropic, openai, local, ollama
```
Check your `LLM_PROVIDER` value in `.env`. Must be one of: `qwen`, `anthropic`, `openai`, `local`, `ollama`.

**Ollama "connection refused"**
```
httpx.ConnectError: [Errno 61] Connection refused
```
Ollama server isn't running. Start it with `ollama serve`. If running Omniscient in Docker and Ollama on the host, use `host.docker.internal` instead of `localhost`:
```bash
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

**Ollama "model not found"**
```
Error: model 'qwen2.5:14b' not found
```
Pull the model first: `ollama pull qwen2.5:14b`. List available models with `ollama list`.

**Ollama very slow response**
- Check if the model fits in RAM: `ollama ps` shows memory usage
- If swapping to disk, use a smaller model (`qwen2.5:7b` instead of `14b`)
- On macOS, ensure Ollama is using the GPU: Activity Monitor > GPU History should show usage
- Set `OLLAMA_NUM_PARALLEL=1` to prevent concurrent requests from competing for RAM

**LLM JSON parse failure (retries exhausted)**
```
LLMError: Failed to parse LLM response as JSON after retry
```
The model returned text that isn't valid JSON. Common with smaller local models. Solutions:
- Use a larger model (14B+ parameters)
- Switch to a cloud provider for production use
- The system retries once automatically; persistent failures indicate the model struggles with structured output

**DashScope "InvalidApiKey" error**
Double-check your `DASHSCOPE_API_KEY`. Keys start with `sk-`. Ensure there are no extra spaces or newlines in your `.env` file.

### Database Issues

**"relation does not exist"**
```
sqlalchemy.exc.ProgrammingError: relation "products" does not exist
```
Run migrations: `alembic upgrade head` (from the `backend/` directory).

**"could not connect to server"**
```
asyncpg.exceptions.ConnectionError: could not connect to server
```
PostgreSQL isn't running or isn't accepting connections. If using Docker: `docker compose ps` should show the `db` service as healthy. If local: check that PostgreSQL is running on port 5432.

**TimescaleDB "extension does not exist"**
```
ERROR: extension "timescaledb" is not available
```
You need the TimescaleDB extension. The Docker Compose setup uses the `timescale/timescaledb` image which includes it. For local Postgres, install TimescaleDB separately: https://docs.timescale.com/install/

### Scraping Issues

**"Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED"**
Proxy connection failed. Check your `PROXY_*` credentials. Test the proxy:
```bash
curl -x http://user:pass@host:port https://httpbin.org/ip
```

**Amazon CAPTCHA / "Something went wrong" page**
Amazon detected automated browsing. Solutions:
- Use residential proxies (not datacenter)
- Increase delays between requests in scraper config
- Reduce concurrent scraping threads
- Try at different times (Amazon is less aggressive during off-peak US hours)

**"Browser closed unexpectedly" or Playwright crash**
- Ensure Playwright browsers are installed: `playwright install chromium`
- In Docker: `python -m playwright install chromium --with-deps`
- Check available memory — headless Chromium needs ~200MB per instance

### Celery Issues

**"No module named 'app'"**
Run Celery from the `backend/` directory, not the project root:
```bash
cd backend && celery -A app.workers.celery_app worker --loglevel=info
```

**Tasks stuck in "PENDING" forever**
- Check that Redis is running: `redis-cli ping` should return `PONG`
- Check that the Celery worker is running and consuming tasks
- Check worker logs for errors: `docker compose logs celery-worker`

### Frontend Issues

**API calls return 404**
The frontend expects the backend at `http://localhost:8000`. If the backend is on a different port or host, update `frontend/src/lib/api.ts`.

**Blank page / hydration errors**
```bash
cd frontend && rm -rf .next && npm run dev
```
This clears the Next.js cache and rebuilds.

---

## 8. Areas for Improvement

### High Priority

**1. User authentication and multi-tenancy**
Currently single-user with no login. Adding auth would allow multiple users, saved preferences, and access control. Suggested approach: NextAuth.js on frontend + JWT middleware on FastAPI backend.

**2. Continuous BSR/price monitoring**
The Celery beat scheduler is set up but needs task definitions for periodic BSR and price tracking. Currently, data is only captured during initial analysis. Adding hourly/daily tracking would enable trend detection and alert-based notifications.

**3. Webhook / notification system**
Alert users when an analysis completes, when BSR drops significantly, or when a new opportunity reaches a high score. Email, Slack, or Discord integration.

**4. SP-API data enrichment**
Currently the SP-API client fetches basic catalog and pricing data. Could be extended to pull:
- Fee estimates (GetMyFeesEstimate)
- Sales rank history (via Reports API)
- Inventory health data
- FBA inbound shipment costs

**5. Real review scraping and analysis**
Current review analysis depends on reviews scraped from product pages. Adding dedicated review pagination (scraping all reviews, not just the first page) would significantly improve sentiment analysis accuracy.

### Medium Priority

**6. Historical data comparison**
Track how niches change over time — are they growing, shrinking, getting more competitive? Compare Omniscient Scores across multiple analysis runs.

**7. Keyword research integration**
Integrate with keyword research sources beyond just the Advertising API:
- Google Trends API for demand validation
- Merchant Words or similar third-party keyword databases
- Auto-complete suggestion scraping from Amazon search bar

**8. Smarter BSR regression**
The current power-law model uses static coefficients. Improvements:
- Category-specific coefficient fine-tuning with more data points
- Time-series aware estimation (BSR from 3 months ago vs. today)
- Machine learning model trained on actual sales data (requires seller data contributions)

**9. PDF report generation**
Export full opportunity briefs as formatted PDFs with charts, tables, and recommendations. Currently only CSV export is supported.

**10. Supplier sourcing depth**
Expand beyond Alibaba/1688 to include:
- IndiaMART for Indian suppliers
- Global Sources
- Direct factory contact via Made-in-China.com
- Trade show exhibitor databases

### Lower Priority

**11. Browser extension**
Chrome extension that shows Omniscient Score and quick metrics when browsing Amazon product pages. Similar to Helium 10's Chrome extension.

**12. Bulk analysis mode**
Analyze multiple niches from a CSV upload or keyword list. Current flow is one-at-a-time through the dashboard.

**13. Competitor tracking**
Track specific ASINs over time — monitor their BSR, price changes, review velocity, and listing changes. Alert when a competitor makes significant changes.

**14. FBA fee calculator accuracy**
Replace hardcoded fee estimates with real-time fee calculation using Amazon's fee schedule. Account for product dimensions, weight, and storage duration (including long-term storage fees and aged inventory surcharges).

**15. International marketplace support**
Currently focused on the US marketplace (ATVPDKIKX0DER). Adding support for UK, Germany, Japan, Canada, and other marketplaces would require:
- Marketplace-specific BSR regression coefficients
- Currency conversion
- Region-specific FBA fee schedules
- Localized scraping (different Amazon domains)

**16. Test coverage expansion**
71 tests cover scoring, forecasting, supplier, and recommendation services. Missing coverage:
- API route integration tests
- Scraper service tests (with mocked Playwright)
- LLM client tests (with mocked API responses)
- Frontend component tests
- End-to-end tests (Playwright or Cypress)

**17. Caching layer optimization**
Redis caching is implemented but could be more granular:
- Cache individual ASIN lookups (TTL: 24 hours)
- Cache BSR regression results (TTL: 1 hour)
- Cache LLM analysis results by content hash (avoid re-analyzing identical reviews)
- Invalidation strategies for stale data
