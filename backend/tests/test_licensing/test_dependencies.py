"""get_license reads the configured key; require_feature gates on the granted features."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.dependencies import get_license, require_feature
from app.licensing import FEATURE_BLUEPRINT, FEATURE_EXPORT, License, generate_keypair, issue_license


def _settings(key: str, public_key: str) -> SimpleNamespace:
    return SimpleNamespace(LICENSE_KEY=key, LICENSE_PUBLIC_KEY=public_key)


def test_get_license_verifies_the_configured_key():
    private_key, public_key = generate_keypair()
    key = issue_license(private_key, customer="acme", tier="pro", days=365)
    lic = get_license(_settings(key, public_key))
    assert lic.valid
    assert FEATURE_EXPORT in lic.features


def test_get_license_is_free_tier_without_a_key():
    _, public_key = generate_keypair()
    assert get_license(_settings("", public_key)).tier == "free"


def test_require_feature_allows_when_granted():
    lic = License.licensed(
        customer="acme", tier="pro", features=frozenset({FEATURE_EXPORT}), issued_at=0, expires_at=9_999_999_999
    )
    gate = require_feature(FEATURE_EXPORT)
    assert gate(license=lic) is lic


def test_require_feature_402s_when_absent():
    lic = License.licensed(
        customer="acme", tier="pro", features=frozenset({FEATURE_EXPORT}), issued_at=0, expires_at=9_999_999_999
    )
    gate = require_feature(FEATURE_BLUEPRINT)
    with pytest.raises(HTTPException) as raised:
        gate(license=lic)
    assert raised.value.status_code == 402
    assert raised.value.detail["feature"] == FEATURE_BLUEPRINT


def test_require_feature_402s_on_the_free_tier():
    gate = require_feature(FEATURE_EXPORT)
    with pytest.raises(HTTPException) as raised:
        gate(license=License.free("no license configured"))
    assert raised.value.status_code == 402
