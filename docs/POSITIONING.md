# Positioning — where Omniscient's engine beats Helium 10 and Jungle Scout, and where it doesn't

This document is the honest competitive case for Omniscient. It is written for two readers: a potential
buyer deciding whether this is worth paying for, and a contributor deciding what to build next. It does
not pretend to beat the incumbents at everything — the places it loses are named as plainly as the places
it wins, because a product people pay money to make sourcing decisions with cannot afford a flattering lie.

## The one-sentence frame

**Helium 10 and Jungle Scout are data platforms. Omniscient is a decision engine.**

They give you the raw numbers — search volume, estimated sales, competitor lists — and leave the analysis
and the go/no-go call to you. Omniscient runs those numbers (its own, or yours) through an opinionated
sourcing methodology and hands back a defensible GO / NO-GO with the reasons, a 52-week P&L, and a spec for
the product you would actually build. The incumbents answer "what is selling?" Omniscient answers "should
*I* build this, and what happens if I do?"

That distinction is the whole business. It is also why Omniscient works best sitting **on top of** the data
you already have rather than trying to out-collect the companies whose entire moat is data.

## What the engine does that the incumbents don't

These are real, verifiable capabilities in this codebase, not roadmap wishes.

### 1. A single opinionated verdict, with its reasons

`ScoringService` produces one 0-100 Omniscient Score from nine weighted sub-scores, and then applies nine
**hard disqualification filters** — price band, review moat, BSR ceiling, minimum margin, Amazon-as-seller
share, hazmat, IP risk, seasonality, review-velocity trap. Any single filter failing forces a FAIL tier no
matter how high the weighted score is. That is an encoded sourcing thesis, not a dashboard. Helium 10's
Black Box and Jungle Scout's Opportunity Finder surface metrics and a rough opportunity number; the seller
still has to decide what disqualifies a niche. Omniscient decides, and shows the failed filters so the
seller can disagree with a specific rule instead of a black box.

### 2. It closes the loop to profit, not just revenue

This is the biggest genuine gap in the incumbents. Helium 10 and Jungle Scout mostly stop at *estimated
revenue*. Omniscient scrapes real 1688 factory prices, computes a full landed cost (FOB, freight, duty,
Section 301 tariff, insurance, inspection, FBA prep, inbound), pulls real FBA fees from SP-API when
configured, and feeds the resulting margin straight into the score and a 52-week bull/base/bear P&L with
break-even week. The question a seller actually cares about — "after China sourcing, freight, FBA, and PPC,
does this make money?" — is the one the incumbents leave to a separate spreadsheet, and the one Omniscient
answers inline.

### 3. It tells you what to build, from the complaints

The complaint-driven product blueprint reads competitor reviews, clusters the pain points with an LLM, and
proposes a differentiated product spec keyed to the one-star reviews of the incumbents. That is a design
step, not a data step, and it is the kind of judgment work the data platforms have only started to touch.

### 4. It admits what it is guessing

Every recommendation carries `risk_flags.data_gaps`: an explicit list of the inputs that were assumed
rather than measured (no supplier data, estimated FOB, assumed search volume, and so on), and the supplier
sub-score returns a neutral value instead of a fabricated one when 1688 is unreachable. No commercial tool
does this — they present every number with the same confidence. For a paid decision tool this is a trust
feature, not an apology: the buyer knows exactly which numbers to double-check before wiring money to a
factory.

### 5. Grey-hat detection

The review-velocity trap filter flags listings whose review counts grow faster than their sales can
explain — a signal of manufactured reviews. It is a niche check, but it protects a seller from entering a
niche whose "demand" is partly fake, and it is not a standard feature elsewhere.

### 6. Your data, your machine, no subscription

Self-hosted and open. With your own SP-API credentials the catalog, rank, competitive pricing, and FBA-fee
numbers are **your account's ground truth**, not a vendor's modeled estimate. There is no per-seat monthly
fee and no vendor holding your research. For an agency or aggregator that runs hundreds of evaluations,
owning the methodology and the data outright is a different proposition from renting seats.

## Where the incumbents win — read this before you claim otherwise

- **Keyword research.** Omniscient's keyword discovery is Amazon-autocomplete-based with SERP-derived volume
  estimates. Helium 10's Cerebro and Magnet, and Jungle Scout's Keyword Scout, run on keyword databases
  with billions of rows, real reverse-ASIN lookups, and calibrated search volume. This is not close.
  Omniscient does not compete here; it consumes keywords, it does not out-research them.
- **Sales-estimate accuracy.** Omniscient converts BSR to sales with a category power-law model, and the
  Australian coefficients are currently a flat 8% scaling of the US curve, which is almost certainly wrong.
  Jungle Scout and Helium 10 calibrate against real sales panels across the whole catalog. Treat
  Omniscient's unit estimates as directional until calibrated.
- **PPC data.** The Amazon Ads API is stored in settings but not yet called. PPC budgets and ACOS in
  Omniscient are modeled estimates, not pulled from real campaign and bid data. Helium 10's Adtomic and the
  Ads-connected tools use live data.
- **Data breadth and history.** The incumbents have years of catalog-wide history, trend charts, and
  databases Omniscient cannot reproduce. Omniscient sees only what it queries or scrapes for one run.
- **Polish.** Chrome extension, onboarding, one-click setup, support, integrations. Omniscient needs setup
  and a little patience.

## The strategy that follows from this

Because the incumbents' moat is data and yours is methodology, do not fight them on data. Three plays,
none of which require you to out-collect a company with a keyword database:

1. **Sit on top of their data.** A seller already paying for Helium 10 can bring a product/ASIN list (or
   SP-API access) and run it through Omniscient's scoring, landed-cost, margin, P&L, and blueprint engine to
   get the decision layer Helium 10 doesn't give. You are the judgment; they are the corpus.
2. **Be the ground-truth tool for the seller's own catalog.** With the seller's SP-API credentials,
   Omniscient reports their real ranks, prices, and fees, not a vendor's estimate. That is a wedge the data
   platforms structurally can't match, because they model the whole market rather than plug into one
   account.
3. **Sell the methodology to the people who advise sellers.** Agencies, sourcing firms, and aggregators
   want a repeatable, defensible scoring methodology and a client-ready opportunity brief. Omniscient's
   opinionated score plus its auto-generated five-tab brief *is* that deliverable. This is the strongest
   B2B angle and the least sensitive to the data-breadth gap.

## Target segments

| Segment | What they pay for | Which strength |
|---|---|---|
| FBA private-label sellers with SP-API | Ground-truth analysis of their own account + go/no-go + P&L | #2, #6, self-host |
| Sellers already on Helium 10 / Jungle Scout | The decision + profit layer on top of data they already buy | #1, #2, #3 |
| Sourcing agencies / product-research firms | Repeatable methodology + client-ready briefs at volume | #1, #3, #4 |
| Aggregators evaluating acquisition targets | Consistent, auditable scoring with explicit data gaps | #1, #4, #5 |

## What would close the gaps (contributor roadmap)

In rough order of value per effort:

1. **Calibrate the sales model** against a reference (even a small hand-labelled set of known ASINs), and
   remove or clearly fence the AU 8% scaling. This is the accuracy-liability item; do it before charging.
2. **Wire the Amazon Ads API** so PPC is real data for sellers who connect it, with the modeled estimate as
   the fallback. The credentials plumbing already exists.
3. **Keyword ingestion**, not keyword competition: import Helium 10 / Jungle Scout / Cerebro exports so the
   engine scores against real search-volume data instead of autocomplete estimates.
4. **A data-source badge** on every brief so the free scraped tier is never mistaken for the SP-API-backed
   accurate tier.

## The honest summary

Omniscient is not a better *data platform* than Helium 10 or Jungle Scout, and it should not be sold as one.
It is a better *decision layer* than either of them ships today: it closes the loop to profit, tells you
what to build, admits what it's guessing, and runs on your own data without a subscription. Point it at the
"should I actually do this?" question the incumbents under-serve, feed it their data or your SP-API, and it
earns its price. Point it at "give me a keyword database" and it will lose. Sell the first one.
