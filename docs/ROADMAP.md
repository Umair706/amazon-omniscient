# Roadmap — from analysis tool to a sellable seller-grade research product

This turns the feature and product asks into sequenced tranches, each shippable on its own.
It is honest about what is a quick win, what is a real project, and what is a hard external
constraint. Read `docs/POSITIONING.md` for the market framing this serves.

## The gap, stated plainly

Today Omniscient *analyses a niche you already named*. A seller's harder problem is *finding*
the niche worth naming, sourcing it for real, and trusting the numbers. The product is a strong
decision engine bolted to a weak front door. The tranches below fix that, in priority order.

---

## Tranche 1 — Trust & UX polish (fast, makes it feel production-grade)

The loudest recent feedback: tabs are empty with no reason, navigation is clunky, no theme,
no favourites. None of this is hard; together it decides whether the product feels finished.

- **Explanatory empty states.** Every empty section says *why* and *what to do*: "No supplier
  data — 1688 was unreachable; add a proxy or Alibaba key", "Add an LLM key in Settings to
  generate the blueprint", "Charts appear after the 6-hourly tracker runs". No more silent blanks.
- **Navigation.** Put the active tab in the URL (shareable, refresh-safe), add breadcrumbs, tidy
  the sidebar, and make list rows link cleanly.
- **Theme toggle** (light/dark/system) — the palette already exists; it's hardcoded to dark.
- **Favourites / star.** Star niches and recommendations; a "Starred" view. Start local per-browser,
  optionally DB-backed later.
- **Metric explanations** (started): info tooltips on every number and column.

Effort: small–medium. Risk: low. This is the cheapest way to move from "internal script" to "product".

## Tranche 2 — Niche discovery engine (the flagship differentiator)

The feature that makes it *research*, not just *analysis*. Instead of typing a keyword, a seller
browses opportunities.

- **Category opportunity feed.** Scrape Amazon Best Sellers / Movers & Shakers / New Releases for a
  category, cluster into candidate niches, and pre-score each cheaply (price band, review moat, BSR,
  Amazon share) so the good ones surface first — then one click runs the full analysis.
- **Seed expansion.** From a term, use autocomplete + related searches to propose adjacent niches
  (the discovery/sub-niche plumbing already exists; this widens it).
- **Saved searches / watchlist** that re-scores over time so a seller sees a niche improving.

Effort: large. Risk: medium (scraping surface). This is the single biggest lever on "sellable".

## Tranche 3 — Supplier data that actually works

The honest constraint: **free, reliable 1688 scraping from a datacenter IP is not achievable** —
1688 serves a login wall, which is why supplier data is empty now. Real options, best first:

- **Official Alibaba/1688 open API** (`ALIBABA_APP_KEY`/`SECRET` already in config). Legitimate,
  integrable, durable. Needs developer approval and has quotas, but it's the right answer.
- **Alibaba.com (English) instead of 1688** — a supplier surface that blocks less aggressively and
  needs no Chinese-field translation.
- **Warmed logged-in session** (the repo has `CookieManager` + `AlibabaLoginService`) as the free
  fallback, plus honest "assumed supplier" labelling (already done via data gaps) when it fails.

Recommendation: integrate the Alibaba API as the durable path and improve the logged-in-session
fallback; stop pretending free datacenter 1688 scraping will work.

Effort: medium. Risk: external (API access/quotas).

## Tranche 4 — Seller-perspective depth (not textbook theory)

Make the engine reason the way a working FBA seller does.

- **Calibrate the sales model** per marketplace against real known-ASIN sales (the AU curve is a
  US-scaled guess today; disclosed but not accurate).
- **Signals sellers actually weigh:** seasonality/trend from BSR history, review velocity, variation
  count, brand/Amazon dominance, PPC competitiveness, differentiation from 1-star complaints.
- **Configurable thesis** — let a seller tune the hard-filter thresholds (price band, review moat,
  margin) to their own risk appetite, per marketplace.

Effort: medium. Risk: needs reference data for calibration.

## Tranche 5 — Docs that teach (useful, digestible, intuitive)

Expand the in-app docs from an API list into a real guide:

- How to read every metric and what a good/bad value looks like.
- A worked example: from discovery → brief → sourcing → go/no-go.
- How to research efficiently, and how the scoring encodes a real sourcing thesis (not theory).

Effort: medium. Risk: low.

## Suggested sequence

1 (fast trust wins) → 2 (discovery, the differentiator) → 3 (suppliers, the credibility fix) →
4 (seller depth) → 5 (docs), with 5 growing alongside each tranche. Whitelabel is already a
licensed feature (the "Powered by Omniscient" badge hides with a key); deeper custom branding
belongs in Tranche 1's theming if wanted.
