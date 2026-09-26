# Supplier data — how it works today and how to make it real

This is the honest state of supplier sourcing in Omniscient, why it is the way it is, and the
exact plan to make it reliable. Read it before promising a buyer that "supplier data works".

## The short version

- **Free, reliable 1688 scraping from a datacenter IP does not work.** 1688.com serves a login
  wall and blocks datacenter IPs, so a plain server-side scrape returns nothing most of the time.
- **The app never fabricates supplier data.** When a scrape returns nothing, the recommendation
  says so: the supplier score goes neutral (not a penalty), and a "Data gaps" banner flags any
  assumed input (assumed MOQ, FOB cost estimated from price). A seller is never shown a made-up
  supplier as if it were real.
- **The durable fix needs the user.** The official Alibaba Open API is the right answer, and it
  requires developer approval and API keys that only the account owner can obtain.

## What runs today

1. **`AlibabaLoginService`** warms a logged-in 1688 session from `ALIBABA_1688_EMAIL` /
   `ALIBABA_1688_PASSWORD`, caching cookies. This is the free fallback. It helps but is fragile:
   a CAPTCHA or SMS challenge can still block it.
2. **`SupplierScraper`** scrapes 1688 search and product pages with Playwright, through the
   configured proxy. With a warmed session and a residential proxy it can work; from a bare
   datacenter IP it usually returns an empty list.
3. **`SupplierMatchService`** translates each product title to Chinese, scrapes candidates, and
   LLM-scores the matches. It has a circuit breaker: after three empty products in a row it stops
   scraping and returns empty matches, assuming 1688 is blocking.
4. **`SupplierService`** turns a FOB unit cost into a landed cost and margin using per-marketplace
   duty and freight profiles. When there is no scraped FOB cost, it estimates one from the selling
   price and flags that estimate as a data gap.

## How "no supplier data" is disclosed

- Supplier sub-score returns a neutral value (missing data is not the same as a bad supplier).
- Data-gap flags: `supplier_data_unavailable`, `moq_assumed`, `fob_estimated_from_price`.
- The recommendation's Suppliers tab shows an empty state that tells the seller what to do:
  add a proxy or an Alibaba key, then re-analyse.

## The plan to make it reliable (needs the account owner)

Best option first. None of these can be finished without the user, because each needs an account,
approval, or paid access that only they can grant.

1. **Official Alibaba Open API** (reserved config: `ALIBABA_APP_KEY` / `ALIBABA_APP_SECRET`).
   Legitimate, durable, and translation-free if the English catalog is used. Requires developer
   registration and approval, and has request quotas. Integration shape when keys exist:
   - Add an `AlibabaApiClient` in `backend/app/services/` that signs requests with the app key and
     secret per Alibaba's gateway spec, exposing `search_suppliers(keyword)` and
     `get_supplier_detail(id)` with the same return shape as `SupplierScraper`, so the pipeline is
     a drop-in swap.
   - In `tasks.py`, prefer the API client when `ALIBABA_APP_KEY`/`SECRET` are set, and fall back to
     the scraper otherwise — the same pattern SP-API already uses over scraping.
   - Keep the CNY→USD conversion and the landed-cost model unchanged.
2. **Residential or paid proxy** (`PROXY_PROVIDER=brightdata`/`smartproxy`). Makes the existing
   scraper work far more often, at a per-request cost. Verifiable as soon as proxy credentials are
   set.
3. **Warmed logged-in session** (already built) as the free best-effort fallback.

## What is deliberately not done

- No blind Alibaba API client is shipped. Signing against a real gateway cannot be verified without
  keys, and shipping unverifiable code against the "no broken things" bar is worse than a clear
  gap. The client is a well-scoped next step for when keys arrive, per the shape above.
