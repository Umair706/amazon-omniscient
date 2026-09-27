"""The tunable scoring thesis: built-in defaults plus a seller's overrides.

This is the single source of truth for what "a good product" means. The app
ships opinionated defaults (per marketplace), and a seller can override any of
them to match their own strategy. Everything here is pure — no database, no I/O
— so it is trivial to test and reason about.

Four groups of knobs:
- thresholds: the numeric hard-filter cut-offs, per marketplace (price band,
  review moat, BSR ceiling, minimum margin, Amazon dominance, review-velocity
  trap).
- allow_seasonal: whether seasonal-only niches pass, per marketplace.
- weights: how the nine sub-scores combine into the Omniscient Score. Global,
  not per marketplace. Must cover all nine and sum to 1.
- sales_multiplier: scales the BSR-to-sales estimate per marketplace, so a
  seller can calibrate it against real known figures (the AU model especially).
"""

from __future__ import annotations

import hashlib
import json

# Bump ONLY when the scoring logic itself changes (new sub-score, changed
# formula), not when a default value changes. A recommendation stores this so a
# result computed under old logic is never silently compared to a new one.
SCORING_ENGINE_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Built-in defaults (the app's own opinion of a good product)
# ---------------------------------------------------------------------------

# The nine sub-score weights. Must sum to 1.0.
DEFAULT_WEIGHTS: dict[str, float] = {
    "demand": 0.15,
    "competition": 0.15,
    "revenue": 0.10,
    "margin": 0.15,
    "trend": 0.10,
    "review_feasibility": 0.10,
    "supplier": 0.10,
    "ppc_viability": 0.10,
    "launch_feasibility": 0.05,
}

# Hard-filter thresholds per marketplace. AU has a wider price band (AUD), a
# lower review moat (smaller market), and a lower BSR ceiling (smaller catalog).
DEFAULT_MARKETPLACE_THRESHOLDS: dict[str, dict] = {
    "US": {
        "price_min": 15,
        "price_max": 70,
        "review_moat_max": 2000,
        "bsr_max": 50000,
        "margin_min": 25,
        "amazon_dominance_max": 30,
        "review_velocity_max": 5.0,
    },
    "AU": {
        "price_min": 20,
        "price_max": 100,
        "review_moat_max": 500,
        "bsr_max": 20000,
        "margin_min": 25,
        "amazon_dominance_max": 30,
        "review_velocity_max": 3.0,
    },
}

# Seasonal-only niches are disqualified by default in every marketplace.
DEFAULT_ALLOW_SEASONAL: bool = False

# One sales figure per marketplace scales the BSR-to-sales estimate. 1.0 keeps
# the built-in curve. AU is uncalibrated, so a seller may tune it here.
DEFAULT_SALES_MULTIPLIER: float = 1.0

# The numeric threshold keys, with their valid ranges (min, max) used for
# validation. allow_seasonal is a boolean and handled separately.
_NUMERIC_THRESHOLD_RANGES: dict[str, tuple[float, float]] = {
    "price_min": (0, 100000),
    "price_max": (0, 100000),
    "review_moat_max": (0, 1000000),
    "bsr_max": (1, 100000000),
    "margin_min": (0, 100),
    "amazon_dominance_max": (0, 100),
    "review_velocity_max": (0, 1000),
}

WEIGHT_KEYS: tuple[str, ...] = tuple(DEFAULT_WEIGHTS.keys())
THRESHOLD_KEYS: tuple[str, ...] = tuple(DEFAULT_MARKETPLACE_THRESHOLDS["US"].keys())

# Weights are allowed to drift from an exact sum of 1 by this much (rounding).
_WEIGHT_SUM_TOLERANCE = 0.001


def _default_marketplace_thresholds(marketplace: str) -> dict:
    """Return a fresh copy of the default thresholds for a marketplace."""
    key = (marketplace or "US").strip().upper()
    base = DEFAULT_MARKETPLACE_THRESHOLDS.get(key, DEFAULT_MARKETPLACE_THRESHOLDS["US"])
    return dict(base)


def resolve_thresholds(marketplace: str, config: dict | None) -> dict:
    """Return the effective thresholds: defaults with the seller's overrides on top."""
    thresholds = _default_marketplace_thresholds(marketplace)
    if not config:
        return thresholds

    key = (marketplace or "US").strip().upper()
    overrides = (config.get("thresholds") or {}).get(key) or {}
    for name, value in overrides.items():
        # Ignore unknown keys so a stale config never injects junk.
        if name in thresholds and value is not None:
            thresholds[name] = value
    return thresholds


def resolve_weights(config: dict | None) -> dict:
    """Return the effective sub-score weights: the seller's full set, or the defaults."""
    if not config:
        return dict(DEFAULT_WEIGHTS)
    overrides = config.get("weights")
    if not overrides:
        return dict(DEFAULT_WEIGHTS)
    # Weights are all-or-nothing: a complete set replaces the defaults. Any
    # missing key falls back to its default so a partial set can't break scoring.
    return {key: float(overrides.get(key, DEFAULT_WEIGHTS[key])) for key in WEIGHT_KEYS}


def resolve_allow_seasonal(marketplace: str, config: dict | None) -> bool:
    """Return whether seasonal-only niches are allowed for a marketplace."""
    if not config:
        return DEFAULT_ALLOW_SEASONAL
    key = (marketplace or "US").strip().upper()
    by_market = config.get("allow_seasonal") or {}
    value = by_market.get(key)
    if value is None:
        return DEFAULT_ALLOW_SEASONAL
    return bool(value)


def resolve_sales_multiplier(marketplace: str, config: dict | None) -> float:
    """Return the effective sales multiplier for a marketplace (default 1.0)."""
    if not config:
        return DEFAULT_SALES_MULTIPLIER
    key = (marketplace or "US").strip().upper()
    by_market = config.get("sales_multiplier") or {}
    value = by_market.get(key)
    if value is None:
        return DEFAULT_SALES_MULTIPLIER
    return float(value)


def resolve_effective_config(marketplace: str, config: dict | None) -> dict:
    """Return the fully-resolved rules a niche was scored under (defaults + overrides).

    This is the snapshot stored on a recommendation so the result is reproducible
    and self-explanatory. `is_custom` says whether the seller overrode anything.
    """
    return {
        "engine_version": SCORING_ENGINE_VERSION,
        "marketplace": (marketplace or "US").strip().upper(),
        "is_custom": bool(config),
        "thresholds": resolve_thresholds(marketplace, config),
        "weights": resolve_weights(config),
        "sales_multiplier": resolve_sales_multiplier(marketplace, config),
        "allow_seasonal": resolve_allow_seasonal(marketplace, config),
    }


def fingerprint_effective_config(effective: dict) -> str:
    """Return a short stable fingerprint of a resolved config.

    Two recommendations with the same fingerprint were scored under identical
    rules, so their scores are directly comparable. Different fingerprints are a
    warning that they are not.
    """
    canonical = json.dumps(effective, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def validate_scoring_config(config: dict | None) -> list[str]:
    """Return a list of human-readable errors. Empty means the config is valid.

    Rejects bad input loudly so a seller cannot silently save a config that
    would make scoring nonsense (e.g. price_min above price_max, weights that
    don't sum to 1, a negative sales multiplier).
    """
    if config is None:
        return []
    if not isinstance(config, dict):
        return ["Scoring config must be an object."]

    errors: list[str] = []
    errors.extend(_validate_thresholds(config.get("thresholds")))
    errors.extend(_validate_weights(config.get("weights")))
    errors.extend(_validate_sales_multiplier(config.get("sales_multiplier")))
    errors.extend(_validate_allow_seasonal(config.get("allow_seasonal")))
    return errors


def _validate_thresholds(thresholds: object) -> list[str]:
    if thresholds is None:
        return []
    if not isinstance(thresholds, dict):
        return ["thresholds must be an object keyed by marketplace."]

    errors: list[str] = []
    for marketplace, values in thresholds.items():
        if not isinstance(values, dict):
            errors.append(f"thresholds.{marketplace} must be an object.")
            continue
        errors.extend(_validate_one_marketplace(marketplace, values))
    return errors


def _validate_one_marketplace(marketplace: str, values: dict) -> list[str]:
    errors: list[str] = []
    for name, value in values.items():
        if value is None:
            continue
        if name not in _NUMERIC_THRESHOLD_RANGES:
            errors.append(f"thresholds.{marketplace}.{name} is not a known threshold.")
            continue
        low, high = _NUMERIC_THRESHOLD_RANGES[name]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"thresholds.{marketplace}.{name} must be a number.")
        elif not (low <= value <= high):
            errors.append(f"thresholds.{marketplace}.{name} must be between {low} and {high}.")

    price_min = values.get("price_min")
    price_max = values.get("price_max")
    if isinstance(price_min, (int, float)) and isinstance(price_max, (int, float)):
        if price_min >= price_max:
            errors.append(f"thresholds.{marketplace}: price_min must be below price_max.")
    return errors


def _validate_weights(weights: object) -> list[str]:
    if weights is None:
        return []
    if not isinstance(weights, dict):
        return ["weights must be an object with all nine sub-scores."]

    errors: list[str] = []
    missing = [key for key in WEIGHT_KEYS if key not in weights]
    if missing:
        errors.append(f"weights must include every sub-score; missing: {', '.join(missing)}.")

    total = 0.0
    for key, value in weights.items():
        if key not in DEFAULT_WEIGHTS:
            errors.append(f"weights.{key} is not a known sub-score.")
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"weights.{key} must be a number.")
            continue
        if not (0 <= value <= 1):
            errors.append(f"weights.{key} must be between 0 and 1.")
        total += value

    if not missing and abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
        errors.append(f"weights must sum to 1.0 (they sum to {round(total, 4)}).")
    return errors


def _validate_sales_multiplier(sales_multiplier: object) -> list[str]:
    if sales_multiplier is None:
        return []
    if not isinstance(sales_multiplier, dict):
        return ["sales_multiplier must be an object keyed by marketplace."]

    errors: list[str] = []
    for marketplace, value in sales_multiplier.items():
        if value is None:
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"sales_multiplier.{marketplace} must be a number.")
        elif not (0 < value <= 100):
            errors.append(f"sales_multiplier.{marketplace} must be greater than 0 and at most 100.")
    return errors


def _validate_allow_seasonal(allow_seasonal: object) -> list[str]:
    if allow_seasonal is None:
        return []
    if not isinstance(allow_seasonal, dict):
        return ["allow_seasonal must be an object keyed by marketplace."]

    errors: list[str] = []
    for marketplace, value in allow_seasonal.items():
        if value is not None and not isinstance(value, bool):
            errors.append(f"allow_seasonal.{marketplace} must be true or false.")
    return errors
