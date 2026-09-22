# AEOS Governance Domain

The Governance domain models immutable governance definitions and normalized
governance outcomes. It does not evaluate policies, grant permissions, run
approvals, enforce execution, or persist state.

## Versioned definitions

`ConstitutionVersion` is one exact constitutional baseline owned by one
`OrganizationId`. It contains a typed identity, exact `VersionRef`, exact
`ContentHash`, descriptive title, and UTC-normalized publication time. A
published version is frozen; changing constitutional content means creating a
new version.

`PolicyVersion` is one exact policy definition owned by one organization. It
uses the same `VersionRef`, `ContentHash`, and UTC publication rules. It is a
definition, not an evaluator: it has no executable conditions or evaluation
behavior. Published policy changes create a new version.

```python
from datetime import datetime, timezone
from aeos.core import (
    ContentHash,
    ConstitutionVersionId,
    GovernanceDecisionId,
    OrganizationId,
    PolicyVersionId,
    VersionRef,
)
from aeos.governance import ConstitutionVersion, PolicyVersion

organization_id = OrganizationId("org-1")
constitution = ConstitutionVersion(
    ConstitutionVersionId("constitution-version-1"),
    organization_id,
    VersionRef("constitution", "3"),
    ContentHash.from_bytes(b"constitution"),
    "Founding Constitution",
    datetime(2026, 1, 1, tzinfo=timezone.utc),
)
policy = PolicyVersion(
    PolicyVersionId("policy-version-1"),
    organization_id,
    VersionRef("spending-policy", "7"),
    ContentHash.from_bytes(b"policy"),
    "spending-limit",
    datetime(2026, 1, 1, tzinfo=timezone.utc),
)
```

## Normalized decisions

`GovernanceDecision` is an immutable result produced by governance evaluation
elsewhere. Its exact constitutional and policy references, organization,
reason, optional evaluated actor, `TraceContext`, and UTC decision time answer
what was in force and what outcome was normalized.

The only result values are `ALLOW`, `DENY`, and `REQUIRE_APPROVAL`.

```python
from aeos.core import ActorKind, ActorRef, CorrelationId, IdempotencyKey, TraceContext
from aeos.governance import GovernanceDecision, GovernanceDecisionResult

trace_context = TraceContext(
    actor=ActorRef(organization_id, ActorKind.SYSTEM),
    correlation_id=CorrelationId("correlation-1"),
    idempotency_key=IdempotencyKey("idempotency-1"),
)

decision = GovernanceDecision(
    governance_decision_id=GovernanceDecisionId("decision-1"),
    organization_id=organization_id,
    result=GovernanceDecisionResult.ALLOW,
    reason="policy requirements satisfied",
    constitution_version=constitution.version_ref,
    policy_versions=(policy.version_ref,),
    trace=trace_context,
    decided_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
)
```

`REQUIRE_APPROVAL` means only that approval is required before execution; it
does not create or execute an approval. `ALLOW` does not execute anything and
`DENY` does not itself enforce runtime blocking. Organization defines who and
what exists; Governance models which authority/policy result applies; runtime
enforcement comes later.

This domain intentionally has no permission evaluation, policy engine,
approval workflow, authorization engine, persistence, economics,
workflow/runtime enforcement, model providers, or Tool Gateway.

## Permission grants

`PermissionGrant` is immutable governance state describing one exact
capability granted to one explicit grantee (`ActorRef`, `RoleId`, or
`RoleAssignmentId`) for one organization-scoped `PermissionScope`. The
capability is an exact, non-wildcard `PermissionCapability`; it is not a
policy expression. Grants preserve exact `VersionRef` values for the policy
and optional constitution baseline, and have UTC temporal bounds. Its
`is_effective_at` helper checks only those bounds. A grant is not an
authorization engine and does not answer whether an arbitrary action is
authorized.

## Approval state

`ApprovalRequest` is the concrete request created by application/domain logic
after a `GovernanceDecision` has the normalized result
`GovernanceDecisionResult.REQUIRE_APPROVAL`. `REQUIRE_APPROVAL` says approval
is required; it is not itself an approval request. A request starts in
`PENDING` and can transition only to `DECIDED`, `EXPIRED`, or `CANCELLED`.
Expiry uses an explicit UTC timestamp and is not scheduled by this domain.

`ApprovalDecision` is an immutable `APPROVE` or `DENY` fact linked to exactly
one request. `decided_by` records an `ActorRef`; it records who made the fact
but does not prove that the actor was authorized to approve. A request and
decision must share both `ApprovalRequestId` and `OrganizationId`, and a
terminal request cannot receive another normal decision.

The minimal pure-domain lifecycle is:

```text
GovernanceDecision(REQUIRE_APPROVAL)
  -> ApprovalRequest(PENDING)
  -> ApprovalDecision(APPROVE)
  -> ApprovalRequest(DECIDED)
```

There is no policy evaluation, authorization or permission evaluation engine,
approval orchestration, runtime enforcement, persistence, event bus,
economics, or workflow implementation here.
