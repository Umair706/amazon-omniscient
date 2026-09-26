"""Issuing and verifying license keys: round trip, expiry, tampering, wrong key, free default."""

from app.licensing import (
    FEATURE_API,
    FEATURE_BLUEPRINT,
    FEATURE_EXPORT,
    generate_keypair,
    issue_license,
    verify_license,
)


def test_issue_and_verify_round_trip():
    private_key, public_key = generate_keypair()
    key = issue_license(private_key, customer="acme@example.com", tier="pro", days=365)
    lic = verify_license(key, public_key)
    assert lic.valid
    assert lic.tier == "pro"
    assert lic.customer == "acme@example.com"
    assert FEATURE_EXPORT in lic.features
    assert FEATURE_BLUEPRINT in lic.features
    assert FEATURE_API not in lic.features  # api is agency-only


def test_expired_key_is_free_tier_with_a_reason():
    private_key, public_key = generate_keypair()
    key = issue_license(private_key, customer="x", tier="pro", days=-1)
    lic = verify_license(key, public_key)
    assert not lic.valid
    assert lic.features == frozenset()
    assert "expired" in lic.reason


def test_tampered_payload_is_rejected():
    private_key, public_key = generate_keypair()
    key = issue_license(private_key, customer="x", tier="agency", days=365)
    prefix, payload, signature = key.split(".")
    # Flip a character in the payload so the signature no longer matches.
    forged_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    lic = verify_license(".".join([prefix, forged_payload, signature]), public_key)
    assert not lic.valid
    assert lic.features == frozenset()


def test_key_signed_by_another_private_key_is_rejected():
    attacker_private, _ = generate_keypair()
    _, our_public = generate_keypair()
    key = issue_license(attacker_private, customer="x", tier="agency", days=365)
    lic = verify_license(key, our_public)
    assert not lic.valid


def test_no_key_or_no_public_key_is_free_tier():
    _, public_key = generate_keypair()
    assert verify_license("", public_key).tier == "free"
    assert verify_license("omni1.abc.def", "").tier == "free"
    assert "no license" in verify_license("", "").reason


def test_custom_feature_list_overrides_the_tier_preset():
    private_key, public_key = generate_keypair()
    key = issue_license(private_key, customer="x", tier="pro", days=30, features=[FEATURE_EXPORT])
    lic = verify_license(key, public_key)
    assert lic.features == frozenset({FEATURE_EXPORT})
    assert FEATURE_BLUEPRINT not in lic.features
