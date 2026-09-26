"""Offline license-key gate for the open-core tiers. See docs/LICENSING.md."""

from app.licensing.features import (
    FEATURE_API,
    FEATURE_BLUEPRINT,
    FEATURE_EXPORT,
    FEATURE_FINANCIAL_REPORT,
    FEATURE_MULTI_MARKETPLACE,
    FEATURE_WHITE_LABEL,
    TIER_FEATURES,
    resolve_features,
)
from app.licensing.model import License
from app.licensing.signing import (
    generate_keypair,
    issue_license,
    resolve_public_key,
    verify_license,
)


def current_license() -> License:
    """Verify the license from the process environment.

    For non-request contexts such as Celery workers, which have no FastAPI
    dependency injection but do have the same LICENSE_KEY in their environment.
    """
    from app.config import Settings

    settings = Settings()
    return verify_license(settings.LICENSE_KEY, resolve_public_key(settings))


__all__ = [
    "FEATURE_API",
    "FEATURE_BLUEPRINT",
    "FEATURE_EXPORT",
    "FEATURE_FINANCIAL_REPORT",
    "FEATURE_MULTI_MARKETPLACE",
    "FEATURE_WHITE_LABEL",
    "TIER_FEATURES",
    "License",
    "current_license",
    "generate_keypair",
    "issue_license",
    "resolve_features",
    "resolve_public_key",
    "verify_license",
]
