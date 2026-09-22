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
