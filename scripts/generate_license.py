#!/usr/bin/env python3
"""Maintainer CLI for issuing Omniscient license keys. See internal/ISSUING-LICENSES.md.

Run from the backend/ directory (so `app` is importable):

    cd backend
    python ../scripts/generate_license.py keygen
    LICENSE_SIGNING_KEY=<priv> python ../scripts/generate_license.py issue \
        --customer acme@example.com --tier pro --days 365

The private key never belongs in the repository. Keep it in a password manager and
pass it via --signing-key or the LICENSE_SIGNING_KEY environment variable.
"""

import argparse
import os
import sys

from app.licensing import generate_keypair, issue_license
from app.licensing.features import TIER_FEATURES


def _cmd_keygen(_args: argparse.Namespace) -> None:
    private_key, public_key = generate_keypair()
    print("PRIVATE KEY (keep secret, never commit):")
    print(f"  {private_key}")
    print()
    print("PUBLIC KEY (embed in app/licensing/signing.py or set LICENSE_PUBLIC_KEY):")
    print(f"  {public_key}")


def _cmd_issue(args: argparse.Namespace) -> None:
    signing_key = args.signing_key or os.environ.get("LICENSE_SIGNING_KEY", "")
    if not signing_key:
        sys.exit("No signing key. Pass --signing-key or set LICENSE_SIGNING_KEY.")
    features = args.features.split(",") if args.features else None
    key = issue_license(
        signing_key,
        customer=args.customer,
        tier=args.tier,
        days=args.days,
        features=features,
    )
    print(key)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Issue Omniscient license keys.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("keygen", help="Create a new signing keypair.").set_defaults(func=_cmd_keygen)

    issue = sub.add_parser("issue", help="Mint a signed license key.")
    issue.add_argument("--customer", required=True, help="Customer identifier, e.g. their email.")
    issue.add_argument("--tier", default="pro", choices=sorted(TIER_FEATURES), help="Tier preset.")
    issue.add_argument("--days", type=int, default=365, help="Validity in days.")
    issue.add_argument("--features", default="", help="Comma-separated feature list overriding the tier.")
    issue.add_argument("--signing-key", default="", help="Private key (else LICENSE_SIGNING_KEY env).")
    issue.set_defaults(func=_cmd_issue)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
