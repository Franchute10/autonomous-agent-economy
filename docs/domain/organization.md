# Organization domain

The Organization domain describes who and what exists structurally. It
contains `Organization`, `Role`, and `RoleAssignment`; it does not decide what
any actor may do. Governance later defines what the structure may do.

`Organization` is the aggregate root. It has a typed `OrganizationId`, a
non-blank name, explicit `OrganizationStatus` (`ACTIVE` or `INACTIVE`), and an
optional exact `VersionRef` to a current constitution. The reference is not a
constitution and is never interpreted here. Roles and assignments are exposed
through read-only mapping views and can be added only through aggregate methods.

`Role` is an immutable organizational position with a typed `RoleId`, its
owning `OrganizationId`, a name, and optional descriptive responsibility text.
Responsibilities explain what the position is responsible for; they are not
permissions or authorization rules.

`RoleAssignment` is an immutable relationship between an `ActorRef`, a
`RoleId`, and an `OrganizationId`. Its UTC-normalized period is inclusive at
both bounds; `ends_at=None` means open-ended. `is_effective_at()` evaluates
only those time bounds. An assignment never grants permission.

The models reuse `OrganizationId`, `RoleId`, `RoleAssignmentId`, `ActorRef`,
`VersionRef`, `UtcTimestamp`, and `DomainError` from the Shared Kernel. A role
assignment must reference a role in the same organization, and duplicate
structural identities are rejected.

## Minimal usage

```python
from datetime import datetime, timezone

from aeos.core import ActorKind, ActorRef, OrganizationId, RoleAssignmentId, RoleId
from aeos.organization import Organization, OrganizationStatus, Role, RoleAssignment

organization = Organization(OrganizationId.new(), "AEOS", OrganizationStatus.ACTIVE)
role = Role(RoleId.new(), organization.organization_id, "Research Analyst")
organization.add_role(role)
assignment = RoleAssignment(
    RoleAssignmentId.new(),
    organization.organization_id,
    role.role_id,
    ActorRef(OrganizationId.new(), ActorKind.HUMAN),
    datetime.now(timezone.utc),
)
organization.add_assignment(assignment)
```

This module has no permissions, policies, approvals, authorization, budgets,
economics, workflows, experiments, agents, persistence, or provider logic.
