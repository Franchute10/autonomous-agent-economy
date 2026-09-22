from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import cast

import pytest

from aeos.core import (
    ActorKind,
    ActorRef,
    ContentHash,
    CorrelationId,
    ConstitutionVersionId,
    GovernanceDecisionId,
    IdempotencyKey,
    OrganizationId,
    PolicyVersionId,
    TraceContext,
    VersionRef,
)
from aeos.governance import (
    ConstitutionVersion,
    GovernanceDecision,
    GovernanceDecisionResult,
    PolicyVersion,
)
from aeos.governance.domain.errors import (
    InvalidConstitutionTitle,
    InvalidGovernanceDecisionReason,
    InvalidPolicyKey,
)


HASH = ContentHash.from_bytes(b"governance-definition")
ORG = OrganizationId("org-1")
TRACE = TraceContext(
    actor=ActorRef(OrganizationId("system-1"), ActorKind.SYSTEM),
    correlation_id=CorrelationId("correlation-1"),
    idempotency_key=IdempotencyKey("idempotency-1"),
)


def test_constitution_version_is_immutable_and_preserves_primitives() -> None:
    version = ConstitutionVersion(
        ConstitutionVersionId("constitution-version-1"),
        ORG,
        VersionRef("constitution", "3"),
        HASH,
        "Founding Constitution",
        datetime(2026, 1, 1, 3, tzinfo=timezone.utc),
    )
    assert version.organization_id is ORG
    assert version.version_ref == VersionRef("constitution", "3")
    assert version.content_hash is HASH
    assert version.published_at == datetime(2026, 1, 1, 3, tzinfo=timezone.utc)
    with pytest.raises(FrozenInstanceError):
        version.title = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("constitution_version_id", object()),
        ("organization_id", object()),
        ("version_ref", object()),
        ("content_hash", object()),
        ("published_at", object()),
    ],
)
def test_constitution_version_rejects_invalid_boundary_types(
    field: str, value: object
) -> None:
    arguments: dict[str, object] = {
        "constitution_version_id": ConstitutionVersionId("constitution-version-1"),
        "organization_id": ORG,
        "version_ref": VersionRef("constitution", "3"),
        "content_hash": HASH,
        "title": "Founding Constitution",
        "published_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    arguments[field] = value
    with pytest.raises(ValueError):
        ConstitutionVersion(**arguments)  # type: ignore[arg-type]


def test_constitution_version_rejects_naive_time_and_normalizes_non_utc_time() -> None:
    with pytest.raises(ValueError):
        ConstitutionVersion(
            ConstitutionVersionId("constitution-version-1"),
            ORG,
            VersionRef("constitution", "3"),
            HASH,
            "Founding Constitution",
            datetime(2026, 1, 1),
        )
    normalized = ConstitutionVersion(
        ConstitutionVersionId("constitution-version-1"),
        ORG,
        VersionRef("constitution", "3"),
        HASH,
        "Founding Constitution",
        datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3))),
    )
    assert normalized.published_at == datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize("title", ["", "   "])
def test_constitution_version_rejects_blank_title(title: str) -> None:
    with pytest.raises(InvalidConstitutionTitle):
        ConstitutionVersion(
            ConstitutionVersionId("constitution-version-1"),
            ORG,
            VersionRef("constitution", "3"),
            HASH,
            title,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )


def test_policy_version_is_immutable_and_has_no_evaluation_behavior() -> None:
    version = PolicyVersion(
        PolicyVersionId("policy-version-1"),
        ORG,
        VersionRef("spending-policy", "7"),
        HASH,
        "spending-limit",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert version.policy_key == "spending-limit"
    with pytest.raises(FrozenInstanceError):
        version.policy_key = "other"  # type: ignore[misc]
    assert not hasattr(version, "evaluate")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("policy_version_id", object()),
        ("organization_id", object()),
        ("version_ref", object()),
        ("content_hash", object()),
        ("published_at", object()),
    ],
)
def test_policy_version_rejects_invalid_boundary_types(
    field: str, value: object
) -> None:
    arguments: dict[str, object] = {
        "policy_version_id": PolicyVersionId("policy-version-1"),
        "organization_id": ORG,
        "version_ref": VersionRef("policy", "1"),
        "content_hash": HASH,
        "policy_key": "spending-limit",
        "published_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    arguments[field] = value
    with pytest.raises(ValueError):
        PolicyVersion(**arguments)  # type: ignore[arg-type]


def test_policy_version_rejects_naive_time_and_normalizes_non_utc_time() -> None:
    with pytest.raises(ValueError):
        PolicyVersion(
            PolicyVersionId("policy-version-1"),
            ORG,
            VersionRef("policy", "1"),
            HASH,
            "spending-limit",
            datetime(2026, 1, 1),
        )
    normalized = PolicyVersion(
        PolicyVersionId("policy-version-1"),
        ORG,
        VersionRef("policy", "1"),
        HASH,
        "spending-limit",
        datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3))),
    )
    assert normalized.published_at == datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize("policy_key", ["", "   "])
def test_policy_version_rejects_blank_key(policy_key: str) -> None:
    with pytest.raises(InvalidPolicyKey):
        PolicyVersion(
            PolicyVersionId("policy-version-1"),
            ORG,
            VersionRef("policy", "1"),
            HASH,
            policy_key,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    "result",
    [
        GovernanceDecisionResult.ALLOW,
        GovernanceDecisionResult.DENY,
        GovernanceDecisionResult.REQUIRE_APPROVAL,
    ],
)
def test_governance_decision_preserves_result_versions_and_trace(
    result: GovernanceDecisionResult,
) -> None:
    constitution = VersionRef("constitution", "3")
    policy = VersionRef("spending-policy", "7")
    decision = GovernanceDecision(
        GovernanceDecisionId("decision-1"),
        ORG,
        result,
        "deterministic governance outcome",
        constitution,
        (policy,),
        TRACE,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert decision.constitution_version is constitution
    assert decision.policy_versions == (policy,)
    assert decision.trace is TRACE
    assert decision.organization_id is ORG
    with pytest.raises(FrozenInstanceError):
        decision.result = GovernanceDecisionResult.DENY  # type: ignore[misc]


def test_governance_result_has_exactly_three_values() -> None:
    assert {result.name for result in GovernanceDecisionResult} == {
        "ALLOW",
        "DENY",
        "REQUIRE_APPROVAL",
    }


def test_governance_decision_rejects_blank_reason() -> None:
    arguments = (
        GovernanceDecisionId("decision-1"),
        ORG,
        GovernanceDecisionResult.ALLOW,
        " ",
        VersionRef("constitution", "3"),
        (),
        TRACE,
        datetime(2026, 1, 1),
    )
    with pytest.raises(InvalidGovernanceDecisionReason):
        GovernanceDecision(*arguments)


def test_governance_decision_rejects_naive_decided_at() -> None:
    with pytest.raises(ValueError):
        GovernanceDecision(
            GovernanceDecisionId("decision-1"),
            ORG,
            GovernanceDecisionResult.ALLOW,
            "valid reason",
            VersionRef("constitution", "3"),
            (),
            TRACE,
            datetime(2026, 1, 1),
        )


def test_governance_decision_rejects_non_datetime_decided_at() -> None:
    with pytest.raises(ValueError):
        GovernanceDecision(
            GovernanceDecisionId("decision-1"),
            ORG,
            GovernanceDecisionResult.ALLOW,
            "valid reason",
            VersionRef("constitution", "3"),
            (),
            TRACE,
            cast(datetime, object()),
        )


def test_governance_decision_normalizes_non_utc_decided_at() -> None:
    decision = GovernanceDecision(
        GovernanceDecisionId("decision-1"),
        ORG,
        GovernanceDecisionResult.ALLOW,
        "valid reason",
        VersionRef("constitution", "3"),
        (),
        TRACE,
        datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3))),
    )
    assert decision.decided_at == datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("governance_decision_id", object()),
        ("organization_id", object()),
        ("result", object()),
        ("constitution_version", object()),
        ("policy_versions", [VersionRef("policy", "1")]),
        ("policy_versions", (object(),)),
        ("trace", object()),
        ("evaluated_actor", object()),
    ],
)
def test_governance_decision_rejects_invalid_boundary_types(
    field: str, value: object
) -> None:
    arguments: dict[str, object] = {
        "governance_decision_id": GovernanceDecisionId("decision-1"),
        "organization_id": ORG,
        "result": GovernanceDecisionResult.ALLOW,
        "reason": "valid reason",
        "constitution_version": VersionRef("constitution", "3"),
        "policy_versions": (),
        "trace": TRACE,
        "decided_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    arguments[field] = value
    with pytest.raises(ValueError):
        GovernanceDecision(**arguments)  # type: ignore[arg-type]


def test_governance_decision_actor_options_and_empty_policies_are_valid() -> None:
    actor = ActorRef(OrganizationId("actor-1"), ActorKind.AGENT)
    decision = GovernanceDecision(
        GovernanceDecisionId("decision-1"),
        ORG,
        GovernanceDecisionResult.REQUIRE_APPROVAL,
        "approval required",
        VersionRef("constitution", "3"),
        (),
        TRACE,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        actor,
    )
    assert decision.policy_versions == ()
    assert decision.evaluated_actor is actor
    assert (
        GovernanceDecision(
            GovernanceDecisionId("decision-2"),
            ORG,
            GovernanceDecisionResult.DENY,
            "denied by policy",
            VersionRef("constitution", "3"),
            (),
            TRACE,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            None,
        ).evaluated_actor
        is None
    )
