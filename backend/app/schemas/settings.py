"""Pydantic schemas for UserSettings model.

SECURITY: Encrypted API credentials are NEVER exposed in responses.
Only boolean has_* flags indicate whether credentials have been configured.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class UserSettingsUpdate(BaseModel):
    """Payload to update user preferences and/or API credentials.

    Raw credential strings are accepted here for write operations.
    They will be encrypted before storage and NEVER returned in responses.
    """

    # API credentials (write-only, will be encrypted before storage)
    sp_api_credentials: dict | None = Field(
        default=None,
        description="SP-API credentials object (will be encrypted)",
    )
    ads_api_credentials: dict | None = Field(
        default=None,
        description="Amazon Ads API credentials object (will be encrypted)",
    )
    alibaba_credentials: dict | None = Field(
        default=None,
        description="Alibaba API credentials object (will be encrypted)",
    )

    # Preferences
    default_marketplace: str | None = Field(default=None, max_length=20)
    # The seller's scoring thesis. Shape and validation live in
    # app/services/scoring_config.py; the settings route validates it before
    # storing. None here means "not provided" (leave the stored value alone).
    scoring_config: dict | None = None

    @field_validator("default_marketplace")
    @classmethod
    def marketplace_upper(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip().upper()
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UserSettingsResponse(BaseModel):
    """User settings response.

    Encrypted credentials are replaced with boolean flags indicating
    whether the user has configured them. Actual keys are NEVER exposed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str

    # Credential presence flags (never expose actual keys)
    has_sp_api_credentials: bool = False
    has_ads_api_credentials: bool = False
    has_alibaba_credentials: bool = False

    # Preferences
    default_marketplace: str | None = None
    scoring_config: dict | None = None

    @classmethod
    def from_orm_model(cls, obj: object) -> "UserSettingsResponse":
        """Build a response from a UserSettings ORM instance.

        Converts encrypted byte fields to boolean has_* flags.
        """
        return cls(
            id=obj.id,  # type: ignore[attr-defined]
            user_id=obj.user_id,  # type: ignore[attr-defined]
            has_sp_api_credentials=obj.sp_api_credentials_encrypted is not None,  # type: ignore[attr-defined]
            has_ads_api_credentials=obj.ads_api_credentials_encrypted is not None,  # type: ignore[attr-defined]
            has_alibaba_credentials=obj.alibaba_credentials_encrypted is not None,  # type: ignore[attr-defined]
            default_marketplace=obj.default_marketplace,  # type: ignore[attr-defined]
            scoring_config=obj.scoring_config,  # type: ignore[attr-defined]
        )
