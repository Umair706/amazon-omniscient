"""License feature names and the tier presets that bundle them.

Feature names are stable strings stored inside issued keys, so renaming one
invalidates every key that granted it. Add new features; do not rename old ones.
"""

FEATURE_EXPORT = "export"
FEATURE_BLUEPRINT = "blueprint"
FEATURE_FINANCIAL_REPORT = "financial_report"
FEATURE_MULTI_MARKETPLACE = "multi_marketplace"
FEATURE_API = "api"
FEATURE_WHITE_LABEL = "white_label"

# Tier presets. A key may also carry a custom feature list that overrides these,
# so a one-off deal never needs a code change.
_PRO_FEATURES = [
    FEATURE_EXPORT,
    FEATURE_BLUEPRINT,
    FEATURE_FINANCIAL_REPORT,
    FEATURE_MULTI_MARKETPLACE,
]
TIER_FEATURES: dict[str, list[str]] = {
    "free": [],
    "pro": _PRO_FEATURES,
    "agency": _PRO_FEATURES + [FEATURE_API, FEATURE_WHITE_LABEL],
}


def resolve_features(tier: str) -> list[str]:
    """Default feature list for a tier name. An unknown tier grants nothing."""
    return list(TIER_FEATURES.get(tier, []))
