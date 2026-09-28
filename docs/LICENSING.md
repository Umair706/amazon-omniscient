# Licensing — the open-core key gate

This is the design and the operator's manual for Omniscient's license gate. Read `docs/POSITIONING.md`
first for *why* the paid line sits where it does; this document is *how* it is enforced.

## The honest premise

Two facts shape every decision here:

1. **The legal gate already exists.** `LICENSE` is proprietary, all-rights-reserved. Nobody may use this
   software commercially without your permission, key or no key. The license key does not *create* the
   obligation to pay — the license does. The key is an **entitlement and convenience layer** that tells the
   software which paid features a given customer is allowed to use.
2. **No self-hosted check is DRM.** The customer has the source and runs it on their own machine, so a
   determined one can patch the check out. That is acceptable and expected. The key's job is to let honest
   customers pay easily and to make bypassing a deliberate, provable license violation — not to be
   unbreakable. We spend zero effort on obfuscation arms races, because they cost goodwill and buy nothing.

The consequence: the gate is small, offline, tamper-evident, and fails toward helpfulness.

## The free / paid line

| Tier (`t`) | Features (`f`) | Who |
|---|---|---|
| `free` | *(none)* | Anyone. One niche at a time on screen: the Omniscient Score, the nine hard filters with reasons, competitor and product views, the scraped data tier. Proves the methodology. |
| `pro` | `export`, `blueprint`, `financial_report`, `multi_marketplace` | Sellers who take briefs to a factory or analyse more than their home market. |
| `agency` | `pro` + `api`, `white_label` | Firms running evaluations at volume and reselling the output. |

The rule that must never be broken: **the free tier is honest-but-limited, never wrong.** We gate export,
scale, and the AI build spec — we never make the *accurate* path paid and leave a *misleading* one free.
Correctness is not a paid feature; leverage is.

Feature names are stable strings (`export`, `blueprint`, `financial_report`, `multi_marketplace`, `api`,
`white_label`). A license carries an explicit feature list, so tiers are just convenient presets; you can
issue a custom feature set for a one-off deal without a code change.

## How the key works

A license is a compact, offline, signed token — no server to run or pay for.

```
omni1.<base64url(payload)>.<base64url(ed25519 signature)>
```

- `payload` is compact JSON: `{"c": customer, "t": tier, "f": [features], "iat": issued_epoch, "exp": expiry_epoch}`.
- The signature is Ed25519 over the bytes `omni1.<base64url(payload)>`.
- The app verifies the signature with an **embedded public key** (safe to publish) and checks `exp`.

Because it is signed with your private key, a customer cannot forge or upgrade a key. Because it carries an
expiry, a leaked or refunded key simply stops working at renewal — that is your revocation mechanism, no
server required. Verification is a few microseconds and happens per request; there is nothing to cache.

### Why offline signing, not a license server

A phone-home server would add real revocation and usage metering, but it costs a service to run, breaks
air-gapped self-hosting, and raises privacy questions — and it is still patchable in source. For a
zero-infrastructure, source-available product the offline signed key is the right first step. If you later
need mid-term revocation or per-seat metering, add an optional online check then; the token format does not
have to change.

## Operating it (your side, zero infrastructure)

Everything runs from the `generate_license.py` CLI on your own machine. Your **private key never enters the
repository or a customer's machine.**

### One-time: create your keypair

```bash
python scripts/generate_license.py keygen
```

This prints a private key and a public key (both base64url). Do two things with the output:

1. Save the **private key** somewhere only you control (a password manager, an encrypted file). Never commit
   it. The CLI reads it from `--signing-key` or the `LICENSE_SIGNING_KEY` environment variable when issuing.
2. Put the **public key** into the app so it can verify. Either paste it into `EMBEDDED_PUBLIC_KEY` in
   `app/licensing/signing.py` (most tamper-evident — patching it out is a clear source edit) or set it as
   the `LICENSE_PUBLIC_KEY` environment variable. If neither is set, the app runs as free tier for everyone.

### Per sale: issue a key

Take payment through a hosted checkout that you do not run — Gumroad, Lemon Squeezy, or a Stripe Payment
Link. On payment, issue and email the key:

```bash
LICENSE_SIGNING_KEY=... python scripts/generate_license.py issue \
  --customer "acme@example.com" --tier pro --days 365
```

The customer pastes it into their `.env`:

```
LICENSE_KEY=omni1....
```

and restarts. `GET /api/v1/license` confirms the tier, the features, and the expiry.

## How it is enforced in the code

- **`app/licensing/`** — `features.py` (feature constants + tier presets), `model.py` (the `License`
  dataclass), `signing.py` (keypair generation, issuing, verifying, the embedded public key). All pure and
  unit-tested; no I/O.
- **`app/dependencies.py`** — `get_license()` reads `LICENSE_KEY` and verifies it; `require_feature(name)`
  returns a FastAPI dependency that raises `402 Payment Required` with an upgrade message when the feature
  is absent or the license has expired.
- **`app/api/license.py`** — `GET /api/v1/license` returns `{tier, features, expires, valid, reason}` so the
  frontend can show premium controls as locked with an upgrade link. This is a *soft* gate for UX; the
  backend `require_feature` is the one that actually protects the feature.
- **Enforced:**
  - `export` — the CSV and PDF export routes (gated at the exports router).
  - `blueprint` — the AI product-blueprint pipeline step (checked in the worker, which reads the same `LICENSE_KEY`).
  - `financial_report` — the consolidated financial-report pipeline step (also worker-side).
  - `multi_marketplace` — the analyze endpoint. The free tier may analyse one marketplace; a request that
    would introduce a second distinct one returns 402. The first marketplace a user ever analyses is free.
  - `white_label` — the frontend hides the "Powered by Omniscient" badge in the sidebar when granted.
- **License-terms only (not a technical gate):** `api`. On a self-hosted product the customer runs the API
  themselves, so a technical block is meaningless — what a paid key grants is the *contractual right* to
  build a commercial service on the API. Faking a technical gate here would be security theatre, so we
  don't. It travels in the agency preset and is enforced by the license terms.

## Failure behaviour

- No key, or no public key configured → free tier, no error. The app is fully usable at the free tier.
- Expired or tampered key → free tier, and `GET /license` reports `valid: false` with a `reason`. The app
  does not crash; premium routes return a clear 402 with a renewal link.
- A premium route without the feature → `402 Payment Required`, body explains which feature and where to buy.

## What we deliberately do not do

No code obfuscation, no anti-debugging, no invasive telemetry, no breaking offline use, no gating of
security fixes or correctness. Those cost trust and protect nothing that the source-having customer couldn't
undo anyway. The proprietary license plus a clean, signed entitlement key is the whole strategy.
