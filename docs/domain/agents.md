# AEOS-AGT-001 Agents domain

The Agents bounded context defines the smallest provider-free vocabulary for
declaring an agent and recording a concrete invocation. It does not execute
agents, resolve versions, authorize capabilities, or provide an agent
framework.

## AgentDefinition

`AgentDefinition` is an immutable declarative definition owned by one
`OrganizationId`. It contains an `AgentDefinitionId`, an exact `VersionRef`, a
trimmed non-blank name and purpose, and a non-empty ordered tuple of
`AgentCapability` values. A materially changed definition is a different
version. There are no `latest`, `current`, or `active` aliases, no registry,
and no mutable publication workflow here.

`AgentDefinition` is not an `Organization.Role`. A role is an organizational
assignment concept; an agent definition is the exact technical declaration of
an agent. The definition contains no provider, model, prompt, tool, secret,
credential, runtime state, memory, transcript, or executable object.

## AgentCapability

`AgentCapability` is an immutable, trimmed, non-blank conceptual identifier.
The capabilities tuple preserves declaration order, rejects lists, rejects an
empty collection, and rejects duplicate values. A declared capability is not a
`PermissionGrant`: it does not grant authority, authorize execution, imply
tool access, or imply provider access. Governance remains a separate concern.

## AgentInvocation

`AgentInvocation` is a separate immutable historical fact for one concrete
occurrence. It has its own `AgentInvocationId`, records the `AgentDefinitionId`
and exact `VersionRef` that were invoked, and stores a UTC-normalized
`invoked_at` timestamp plus the existing `TraceContext`. It does not duplicate
the definition's organization ownership, embed the full definition, or
duplicate actor, correlation, causation, or idempotency fields. Future
application/runtime work may resolve the definition and its owning
organization when needed; AGT-001 does not invent a separate execution-
organization concept.

`AgentInvocation` is not an `ActorRef`, `NodeAttempt`, `ModelInvocation`, or
`ToolInvocation`. It has no lifecycle status because this contract records an
invocation fact, not an execution process. Runtime, model, tool, workflow,
memory, planning, multi-agent messaging, governance enforcement, economics,
persistence, and evidence/audit integration are deferred to later bounded
contexts or tasks.

## Research boundary

Agent product models carry no thesis or research metadata. Research may refer
to agent facts externally, but the Agents domain does not contain research
objectives, thesis variables, studies, indicators, hypotheses, or thesis
sections.
