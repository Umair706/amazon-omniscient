"""The License a verified key grants.

`valid` means "a currently-valid paid key is installed". The free tier is a real,
usable state but reports valid=False, because there is no valid *paid* license — the
UI uses that to show premium controls as locked with a reason.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class License:
    tier: str
    features: frozenset[str]
    customer: str = ""
    issued_at: int = 0
    expires_at: int = 0
    valid: bool = True
    reason: str = ""

    @classmethod
    def free(cls, reason: str) -> "License":
        """The free tier: no paid features, carrying the reason there is no valid key."""
        return cls(tier="free", features=frozenset(), valid=False, reason=reason)

    @classmethod
    def licensed(
        cls,
        *,
        customer: str,
        tier: str,
        features: frozenset[str],
        issued_at: int,
        expires_at: int,
    ) -> "License":
        """A verified paid license."""
        return cls(
            tier=tier,
            features=features,
            customer=customer,
            issued_at=issued_at,
            expires_at=expires_at,
            valid=True,
            reason="ok",
        )

    @property
    def expires_iso(self) -> str | None:
        """Expiry as an ISO-8601 UTC string, or None when there is no expiry."""
        if not self.expires_at:
            return None
        return datetime.fromtimestamp(self.expires_at, tz=timezone.utc).isoformat()
