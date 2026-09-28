"""GET /license — report the installed license so the UI can lock premium controls.

This is a soft gate for display only. The backend `require_feature` dependency on each
premium route is what actually enforces the tier.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_license
from app.licensing import License

router = APIRouter(prefix="/license", tags=["license"])


class LicenseStatusResponse(BaseModel):
    tier: str
    features: list[str]
    valid: bool
    reason: str
    expires: str | None = None


@router.get("", response_model=LicenseStatusResponse)
async def license_status(
    license: License = Depends(get_license),
) -> LicenseStatusResponse:
    """Return the current tier, granted features, and expiry."""
    return LicenseStatusResponse(
        tier=license.tier,
        features=sorted(license.features),
        valid=license.valid,
        reason=license.reason,
        expires=license.expires_iso,
    )
