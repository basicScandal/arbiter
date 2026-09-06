"""Lease lifecycle tests: compilation, signing, expiry, and invalidation.

These exercise the primitive the whole control plane rests on -- an expiring,
signed, evidence-backed authorization -- with no mocks in the path.
"""

from __future__ import annotations

import time

import pytest

from src.racp.compiler import (
    CLAIM_NO_INJECTION,
    CLAIM_POLICY_INTACT,
    LeaseCompiler,
    TaskContext,
)
from src.racp.models import ActionKind, LeaseState
from src.racp.signing import LeaseSigner


@pytest.fixture
def signer() -> LeaseSigner:
    return LeaseSigner(secret="test-secret")


@pytest.fixture
def compiler(signer: LeaseSigner) -> LeaseCompiler:
    return LeaseCompiler(signer)


@pytest.fixture
def context() -> TaskContext:
    return TaskContext(
        team_name="Team Nebula",
        track="ROGUE::AGENT",
        model="gemini-test",
        policy_names=["ignore_previous", "score_manipulation"],
    )


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------


def test_compiled_lease_is_scoped_to_the_task(compiler, context):
    lease = compiler.compile(context)

    assert lease.task["team_name"] == "Team Nebula"
    assert lease.task["track"] == "ROGUE::AGENT"
    assert lease.subject["model"] == "gemini-test"
    assert lease.expires_at > lease.issued_at


def test_policy_hash_is_recorded_as_provenance(compiler, context):
    lease = compiler.compile(context)

    assert f"detector:{context.policy_hash()}" in lease.policy_provenance


def test_policy_hash_changes_when_patterns_change(context):
    other = TaskContext(team_name="Team Nebula", policy_names=["ignore_previous"])

    assert context.policy_hash() != other.policy_hash()


def test_fresh_lease_is_not_usable_before_preflight(compiler, context):
    """A lease starts with its policy-intact claim falsified on purpose."""
    lease = compiler.compile(context)

    assert lease.assumption(CLAIM_POLICY_INTACT).holds is False
    assert lease.is_usable() is False


def test_capabilities_default_deny_unknown_actions(compiler, context):
    lease = compiler.compile(context)

    assert lease.capabilities.permits(ActionKind.SCORE_DEMO.value) is True
    assert lease.capabilities.permits("wire_transfer") is False


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


def test_signed_lease_verifies(compiler, signer, context):
    lease = compiler.compile(context)

    assert signer.verify(lease) is True


def test_widening_capabilities_breaks_the_signature(compiler, signer, context):
    lease = compiler.compile(context)
    lease.capabilities.allow.append("exfiltrate_scores")

    assert signer.verify(lease) is False


def test_extending_expiry_breaks_the_signature(compiler, signer, context):
    lease = compiler.compile(context)
    lease.expires_at += 10_000

    assert signer.verify(lease) is False


def test_a_different_secret_does_not_verify(compiler, context):
    lease = compiler.compile(context)

    assert LeaseSigner(secret="other-secret").verify(lease) is False


def test_unsigned_lease_does_not_verify(compiler, signer, context):
    lease = compiler.compile(context)
    lease.signature = ""

    assert signer.verify(lease) is False


# ---------------------------------------------------------------------------
# Expiry and invalidation
# ---------------------------------------------------------------------------


def test_lease_expires_after_its_ttl(compiler):
    context = TaskContext(team_name="T", ttl_seconds=1.0)
    lease = compiler.compile(context, now=time.time() - 5)

    assert lease.is_expired() is True
    assert lease.is_usable() is False


def test_invalidated_assumption_makes_lease_unusable(compiler, context):
    lease = compiler.compile(context)
    lease = compiler.renew(lease, context, "preflight", restore_claims=[CLAIM_POLICY_INTACT])
    assert lease.is_usable() is True

    lease.invalidate_assumption(CLAIM_NO_INJECTION, "slide carried an override")

    assert lease.is_usable() is False
    assert CLAIM_NO_INJECTION in {a.claim for a in lease.stale_assumptions()}


def test_invalidating_an_unknown_claim_reports_failure(compiler, context):
    lease = compiler.compile(context)

    assert lease.invalidate_assumption("no_such_claim", "reason") is False


# ---------------------------------------------------------------------------
# Renewal
# ---------------------------------------------------------------------------


def test_renewal_bumps_revision_and_extends_expiry(compiler, context):
    lease = compiler.compile(context)
    renewed = compiler.renew(lease, context, "ttl expiry")

    assert renewed.revision == lease.revision + 1
    assert renewed.expires_at > lease.expires_at


def test_renewal_does_not_silently_restore_falsified_claims(compiler, context):
    """The central safety property: renewal is not a rubber stamp."""
    lease = compiler.compile(context)
    lease.invalidate_assumption(CLAIM_NO_INJECTION, "injection observed")

    renewed = compiler.renew(lease, context, "ttl expiry")

    assert renewed.assumption(CLAIM_NO_INJECTION).holds is False


def test_renewal_restores_only_claims_with_fresh_evidence(compiler, context):
    lease = compiler.compile(context)
    lease.invalidate_assumption(CLAIM_NO_INJECTION, "injection observed")

    renewed = compiler.renew(
        lease, context, "preflight passed", restore_claims=[CLAIM_POLICY_INTACT]
    )

    assert renewed.assumption(CLAIM_POLICY_INTACT).holds is True
    assert renewed.assumption(CLAIM_NO_INJECTION).holds is False


def test_renewal_can_narrow_capabilities(compiler, context):
    lease = compiler.compile(context)

    renewed = compiler.renew(
        lease, context, "risk", narrow=[ActionKind.SPEAK_COMMENTARY.value]
    )

    assert renewed.capabilities.permits(ActionKind.SPEAK_COMMENTARY.value) is False
    assert renewed.capabilities.permits(ActionKind.SCORE_DEMO.value) is True


def test_renewed_lease_is_re_signed(compiler, signer, context):
    lease = compiler.compile(context)
    renewed = compiler.renew(lease, context, "ttl expiry")

    assert signer.verify(renewed) is True
    assert renewed.signature != lease.signature


def test_quarantine_and_revoke_change_state(compiler, signer, context):
    lease = compiler.compile(context)

    quarantined = compiler.quarantine(lease, "preflight failed")
    revoked = compiler.revoke(lease, "policy drift")

    assert quarantined.state is LeaseState.QUARANTINED
    assert revoked.state is LeaseState.REVOKED
    assert signer.verify(quarantined) and signer.verify(revoked)
