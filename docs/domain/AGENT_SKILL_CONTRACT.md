# AEOS Agent and Skill Contract

**Status:** target contract for versioned declarations and evaluations; not a runtime implementation.
**Scope:** AEOS Core contract design for AEOS Starter and the Agentes Mype application layer.

## Domain boundary

The current AgentDefinition is an immutable, organization-owned declaration with an exact version, name, purpose, and ordered conceptual capabilities. AgentInvocation records the exact definition ID/version, timestamp, and TraceContext for an occurrence. Neither object contains a model, prompt, executable skill, memory, tool grant, or authorization result.

A Skill is a separately versioned, reviewable procedure artifact. This document specifies the metadata that future application/runtime contracts should carry; it does not redefine the existing domain entities or claim that a registry, executor, policy evaluator, or memory system exists.

A capability declaration describes intent only. It never grants permission, selects a tool, authorizes an organization/resource, or bypasses policy. Authorization must be evaluated in code at the real side-effect boundary using the authenticated actor, organization, action, resource scope, current policy/constitution, budget, and required approval.

## Required versioned contract

Every runnable agent/skill/evaluation candidate should have an immutable contract record containing:

| Field | Meaning |
|---|---|
| Contract ID and version | Stable identifier plus exact immutable version; no latest/current alias in a run record. |
| Owner scope | Organization and, where applicable, project/workspace. Scope is enforced by the host, not trusted from input. |
| Purpose and non-goals | Bounded task objective, intended users, excluded tasks, and explicit refusal/stop conditions. |
| Inputs | Typed schema, required/optional fields, size bounds, sensitivity class, validation rules, and untrusted-source labels. |
| Outputs | Typed schema, required evidence/provenance fields, size bounds, and output validation rules. |
| Declared capabilities | Conceptual identifiers only; explicitly not permission grants. |
| Tool allowlist | Exact operation identifiers and input/output schemas. Every call is reauthorized at execution time. |
| Policy references | Exact policy and constitution versions to evaluate; missing or stale versions fail closed. |
| Resource budget | Currency/resource units, maximum approved amount, reservation rule, and what to do when cost is unavailable or exceeded. |
| Runtime bounds | Explicit timeout, maximum attempts, output/token/byte limits, and concurrency constraints from approved task configuration. Do not invent default values in a skill. |
| Retry and idempotency | Retryable failure classes, idempotency key strategy, and proof that retry cannot duplicate an external effect. |
| Approval requirements | Exact action/resource scope requiring human approval, expiration, and evidence that the actual gateway checks it. |
| Evidence | Source references/content hashes, timestamps, evaluator version, and trace/correlation/causation fields required for the task. |
| Memory scope | Organization/project partition, retention and deletion rule, permitted retrieval purpose, and explicit prohibition on cross-tenant retrieval. |
| Compatibility | Supported input/output and runtime contract versions; migration or incompatibility behavior. |
| Success and failure | Deterministic acceptance criteria, abstention behavior, error categories, escalation path, and cleanup/recovery behavior. |

A missing required field, unknown bound, invalid version, or incompatible schema is a validation failure, not an invitation for the agent to infer a default.

## Run record

Each invocation record should bind the exact agent definition version, exact skill versions, input fixture/hash, output schema version, policy/constitution versions, tool set, model/provider configuration or “none”, evaluator versions, environment/commit, trace context, start/end timestamps, outcome, errors/timeouts, evidence references, and measured cost. Preserve a distinction between definition, invocation, attempt, and side effect; one invocation may have multiple bounded attempts, but retries must retain causation and idempotency.

This target run record does not supersede AEOS-CORE-001 trace semantics or ADR-008. Implementation must use the existing IDs and trace contracts rather than inventing parallel identifiers.

## Security and governance rules

- Treat user input, retrieved pages/files, tool outputs, memory, and other agents' messages as untrusted data, never as policy or authority.
- Resolve tenant ownership from authenticated server context. Ignore client-supplied organization/role/permission metadata.
- Evaluate permissions and approvals at the action gateway, immediately before each side effect. Fail closed when identity, destination, ownership, policy version, budget, or approval cannot be proven.
- Default tools to read-only. Grant write operations individually and only for the exact scope required.
- A pending, denied, expired, or mismatched approval blocks the action and must produce no external side effect.
- Retries are limited to explicitly safe or idempotent operations. Reconcile uncertain outcomes before retrying an external action.
- Do not log secrets or raw sensitive content. Store evidence by scoped reference/hash where possible.
- Memory is organization- and project-scoped. Promotion to a shared library requires owner review, purpose review, minimization, anonymization, and an append-only provenance record. Promotion never silently moves tenant data.

## Compatibility and promotion

Any material change creates a new immutable skill/contract version. Validate schema compatibility and rerun the frozen evaluation/security cases before adoption. A candidate cannot replace the prior approved version until hard constraints pass, the quality threshold is met, evidence is reviewed independently, and a rollback path is available. Definition, policy, and skill versions used by an existing run remain unchanged.

## Illustrative, non-executable case

A synthetic “draft a follow-up email” skill may return a proposed draft and evidence. It has no send permission by declaration alone. A separate action request must be authenticated, checked against the current organization policy and budget, and approved where required at the mail-send gateway. The evaluation fixture must assert that the proposal can succeed while a denied/unapproved send produces zero sends.

## Current implementation limit

The existing domain has AgentDefinition, AgentCapability, AgentInvocation, PermissionGrant, PolicyVersion, ApprovalRequest/ApprovalDecision, and GovernanceDecision records. These records do not implement authorization, tool execution, evaluation, memory isolation, or promotion. Treat all fields above as a contract proposal until corresponding code, tests, and runtime evidence exist.
