"""Lease signing and verification.

The lease is the object that grants authority, so it must not be forgeable by
anything downstream of the trusted computing base -- including a compromised
plugin, a tampered scorecard, or a replayed lease from an earlier demo. Every
lease is signed with HMAC-SHA256 over its canonical payload, and the gateway
verifies the signature on every authorization.

The secret comes from ``ARBITER_RACP_SECRET`` when set. Otherwise a random
per-process secret is generated: leases stay unforgeable within the run, but
do not survive a restart -- which is the correct failure mode, since a lease
issued by a previous process has no live evidence behind it anyway.
"""

from __future__ import annotations

import hmac
import logging
import os
import secrets
from hashlib import sha256

from src.racp.models import BehaviorLease

logger = logging.getLogger(__name__)

_ENV_SECRET = "ARBITER_RACP_SECRET"


class LeaseSigner:
    """Signs and verifies behavior leases with a shared secret.

    Args:
        secret: Explicit secret. When omitted, ``ARBITER_RACP_SECRET`` is used,
            falling back to a random per-process secret.
    """

    def __init__(self, secret: str | bytes | None = None) -> None:
        if secret is None:
            env_secret = os.environ.get(_ENV_SECRET, "")
            if env_secret:
                secret = env_secret
            else:
                secret = secrets.token_bytes(32)
                logger.info(
                    "%s not set — using an ephemeral per-process lease secret. "
                    "Leases will not verify across restarts.",
                    _ENV_SECRET,
                )
        self._secret = secret.encode("utf-8") if isinstance(secret, str) else secret

    def sign(self, lease: BehaviorLease) -> BehaviorLease:
        """Attach a signature to the lease and return it."""
        lease.signature = hmac.new(
            self._secret, lease.signing_payload(), sha256
        ).hexdigest()
        return lease

    def verify(self, lease: BehaviorLease) -> bool:
        """Return True when the lease signature matches its current content.

        Any mutation of a field that grants authority (capabilities,
        assumptions, expiry, revision, task) breaks the signature.
        """
        if not lease.signature:
            return False
        expected = hmac.new(self._secret, lease.signing_payload(), sha256).hexdigest()
        return hmac.compare_digest(expected, lease.signature)
