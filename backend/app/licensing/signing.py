"""Sign, issue, and verify Omniscient license keys — offline Ed25519 tokens.

A key is: omni1.<base64url(payload)>.<base64url(signature)>
The payload is compact JSON; the signature is Ed25519 over "omni1.<payload>".
Only the maintainer's private key can mint a key, so a customer cannot forge or
upgrade one. Verification needs only the public key, which is safe to publish.
See internal/ISSUING-LICENSES.md.
"""

import base64
import json
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.licensing.features import resolve_features
from app.licensing.model import License

TOKEN_PREFIX = "omni1"
_SEPARATOR = "."
SECONDS_PER_DAY = 86_400

# Paste your public key here (base64url) to embed it in the build — patching it out
# is then a clear source edit. Empty = read LICENSE_PUBLIC_KEY from the environment
# instead; both empty = free tier for everyone.
EMBEDDED_PUBLIC_KEY = ""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def generate_keypair() -> tuple[str, str]:
    """Return (private_key_b64url, public_key_b64url). Run once; keep the private key secret."""
    private = Ed25519PrivateKey.generate()
    return (
        _b64url_encode(private.private_bytes_raw()),
        _b64url_encode(private.public_key().public_bytes_raw()),
    )


def issue_license(
    signing_key_b64: str,
    *,
    customer: str,
    tier: str,
    days: int,
    features: list[str] | None = None,
) -> str:
    """Mint a signed license key. `features` overrides the tier's preset when given."""
    now = int(time.time())
    payload = {
        "c": customer,
        "t": tier,
        "f": sorted(features if features is not None else resolve_features(tier)),
        "iat": now,
        "exp": now + days * SECONDS_PER_DAY,
    }
    payload_b64 = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    signing_input = f"{TOKEN_PREFIX}{_SEPARATOR}{payload_b64}".encode()
    private = Ed25519PrivateKey.from_private_bytes(_b64url_decode(signing_key_b64))
    signature = private.sign(signing_input)
    return _SEPARATOR.join([TOKEN_PREFIX, payload_b64, _b64url_encode(signature)])


def resolve_public_key(settings) -> str:
    """The public key to verify with: the embedded one, else LICENSE_PUBLIC_KEY, else empty."""
    return EMBEDDED_PUBLIC_KEY or getattr(settings, "LICENSE_PUBLIC_KEY", "") or ""


def verify_license(token: str, public_key_b64: str) -> License:
    """Return the License a token grants. Never raises: a bad or missing key is the free tier."""
    if not token or not public_key_b64:
        return License.free("no license configured")
    parts = token.split(_SEPARATOR)
    if len(parts) != 3 or parts[0] != TOKEN_PREFIX:
        return License.free("malformed license key")
    _, payload_b64, sig_b64 = parts
    if not _signature_ok(public_key_b64, payload_b64, sig_b64):
        return License.free("invalid signature")
    return _license_from_payload(payload_b64)


def _signature_ok(public_key_b64: str, payload_b64: str, sig_b64: str) -> bool:
    """True if sig_b64 is a valid signature of "omni1.<payload>" under public_key_b64."""
    signing_input = f"{TOKEN_PREFIX}{_SEPARATOR}{payload_b64}".encode()
    try:
        public = Ed25519PublicKey.from_public_bytes(_b64url_decode(public_key_b64))
        public.verify(_b64url_decode(sig_b64), signing_input)
        return True
    except (InvalidSignature, ValueError):
        return False


def _license_from_payload(payload_b64: str) -> License:
    """Parse a signature-verified payload into a License, downgrading an expired one to free."""
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return License.free("malformed license payload")
    if int(payload.get("exp", 0)) < int(time.time()):
        return License.free(f"license expired for {payload.get('c', 'unknown')}")
    return License.licensed(
        customer=payload.get("c", ""),
        tier=payload.get("t", ""),
        features=frozenset(payload.get("f", [])),
        issued_at=int(payload.get("iat", 0)),
        expires_at=int(payload.get("exp", 0)),
    )
