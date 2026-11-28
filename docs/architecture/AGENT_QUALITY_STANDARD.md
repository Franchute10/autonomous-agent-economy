# AEOS Agent Quality Standard

**Status:** normative evaluation and promotion standard; it does not implement an evaluator or runtime.
**Scope:** AEOS Core and its applications, including AEOS Starter and the Agentes Mype application layer.

## Purpose and boundaries

Use this standard to measure whether a particular agent-definition version and skill version can complete a bounded task safely and reproducibly. AEOS Core remains the organizational and economic kernel; AEOS Starter is its first supervised SaaS application; Agentes Mype is the application vision, not a parallel runtime.

The existing AgentDefinition is immutable and declarative. AgentCapability is a conceptual declaration, not permission. AgentInvocation records an occurrence, not execution. PermissionGrant, PolicyVersion, ApprovalDecision, and GovernanceDecision are immutable state/fact models; they do not by themselves evaluate or enforce authorization. Do not report these domain objects as a working runtime, memory service, evaluator, or authorization gateway.

Preserve ADR-001 through ADR-008: modular monolith; relational current state with append-only material history; balanced resource ledger; explicit workflow/experiment state machines; provider ports; transactional outbox/inbox; simulation composition profile; and the distinction between AgentDefinition and AgentInvocation.

## Evaluation unit and reproducibility

A case is one bounded task with a versioned input fixture, independent expected result, hard constraints, deterministic evaluator version, and explicit environment. A run records the source commit; exact agent and skill versions; input and dataset versions; policy and constitution references; tool and model configuration (or none); evaluator versions; runtime/environment; command; result; evidence; latency; and cost.

Freeze the baseline before comparing a candidate. Run baseline and candidate against the same cases, evaluator, environment, and applicable configuration. Record all attempted cases. Do not remove failures, errors, abstentions, blocked actions, or timeouts from the denominator. Report exclusions and not-run cases separately with reasons. A cost that was not measured is unknown, not zero.

Fixtures must be synthetic or explicitly approved, contain no secrets or personal/customer data, and run without network access, credentials, paid inference, or external side effects.

## Hard constraints

Hard constraints are pass/fail gates and cannot be offset by a high quality score.

| Gate | Required result |
|---|---|
| Authorization boundary | No action without an independent, code-enforced authorization decision for actor, organization, capability, resource scope, and current policy. A declared capability is never sufficient. |
| Tenant isolation | No cross-organization or cross-project read, write, memory retrieval, or evidence disclosure. |
| Human approval | An irreversible or externally visible action is blocked unless a valid, scoped approval is present and checked at the actual action boundary. |
| Evidence and provenance | Required factual claims and material decisions retain their source/evidence references and trace context. Missing required evidence fails the case. |
| Tool and data scope | Only allowlisted operations and bounded inputs/outputs are accepted. Untrusted external content cannot change authority or policy. |
| Reliability and recovery | Timeouts, errors, retries, and duplicate delivery are recorded; unsafe retries do not cause duplicate side effects. |
| Privacy and secrets | No secret or unapproved sensitive data appears in logs, traces, evaluation artifacts, or cross-tenant memory. |
| Resource limits | Execution respects the task's approved budget and limits. Exceeding or unknown required cost blocks promotion. |

Any unauthorized side effect, cross-tenant disclosure, missing required approval, or secret leak is a hard failure. The test must also verify that a rejected action produced no side effect.

## Quality dimensions

Report each dimension separately; do not hide a safety failure inside an average score.

| Dimension | Measurement |
|---|---|
| Correctness | Deterministic assertions against independently authored expected results. |
| Completeness | Required output fields, steps, or evidence present, divided by the total required for the case. |
| Evidence quality | Required claims supported by valid, relevant, attributable evidence. |
| Security | Hard-constraint violations and denied-action side effects; release requires zero violations. |
| Reliability | Successful eligible cases divided by all attempted cases, with failures, errors, and timeouts included and shown separately. |
| Latency | Per-case wall time and aggregate distribution, including p50/p95 where sample size supports it. |
| Cost | Measured resource/provider cost per attempted and successful case; disclose unavailable or unpriced components. |

Task owners define numerical acceptance thresholds before candidate results are viewed. This standard does not invent a universal quality, latency, or cost threshold. Hard constraints remain mandatory regardless of task-specific thresholds.

## Evidence levels

- **Q0 — Unmeasured:** definition exists; no reproducible evidence.
- **Q1 — Contract checked:** schemas, invariants, and deterministic unit cases pass. This is not task-quality evidence.
- **Q2 — Baseline measured:** representative versioned cases, independent expectations, evaluator and environment are recorded with full denominators.
- **Q3 — Candidate compared:** candidate is run against the frozen baseline; task thresholds and all hard constraints pass; regressions and failures are disclosed.
- **Q4 — Promotion eligible:** Q3 evidence is reviewed independently; rollback and monitoring are prepared; ownership and approval are recorded.

A level applies only to the exact agent/skill versions and configuration evaluated. It is not a general certification.

## Evaluation method

1. Define the task, owner, representative cases, success thresholds, hard constraints, and allowed effects.
2. Run deterministic checks first: schema, exact invariants, policy outcomes, evidence references, and side-effect absence.
3. Establish and preserve a baseline before changing prompts, skills, model, or runtime.
4. Change one hypothesis at a time; compare baseline and candidate with the same frozen cases and evaluator.
5. Add human labels for subjective quality where needed. An LLM judge may supplement them only after calibration against a representative human-labeled set; report disagreement and do not use it as sole release authority.
6. Record the exact run and independently review the evidence.
7. Promote only through an explicit gate that includes regression results, a rollback path, and approval. Never auto-promote from self-evaluation.

## Promotion and rollback

Promotion is denied when any hard gate fails, a required threshold is absent, the denominator is incomplete, cost is unknown where required, evidence cannot be reproduced, or rollback is unavailable. A promoted version retains its immutable definition/skill references and evaluation record. Roll back to the last approved version when a hard constraint regresses, monitoring detects a material regression, or the runtime cannot reproduce the approved policy/configuration.

## Current implementation limit

This file defines the standard only. The repository does not yet implement the evaluation runner, quality score store, promotion service, or production agent runtime. Tests described in the evaluation and security READMEs are specifications until executable checks are added and run.


## Learning and promotion

Run outcomes may produce a proposed lesson, never an automatic change to a shared skill or policy. Keep raw evidence append-only and the derived lesson scoped to its source organization/project. A promotion candidate records the originating run IDs, intended scope, evidence, reviewer, transformation/anonymization, and target immutable version. Evaluate the candidate against the frozen regression set before adoption. Cross-project promotion requires explicit owner review, privacy minimization/anonymization, a new version, and a rollback path. No universal confidence threshold is implied by this standard.

## Source adaptation

This AEOS standard selectively adapts reproducibility, baseline comparison, boundary-first security, project-scoped learning, and structured failure capture from the upstream references below. It does not import ECC as an AEOS framework, runtime, toolset, or project dependency. These upstream URLs point to a mutable main branch; for a future change that depends on a specific detail, record the inspected commit SHA in that change.

- [Agent Eval](https://github.com/affaan-m/ecc/tree/main/skills/agent-eval)
- [Agent Architecture Audit](https://github.com/affaan-m/ecc/tree/main/skills/agent-architecture-audit)
- [Agent Security Hardening](https://github.com/affaan-m/ecc/tree/main/skills/agent-security-hardening)
- [Continuous Learning v2](https://github.com/affaan-m/ecc/tree/main/skills/continuous-learning-v2)
- [Agent Introspection Debugging](https://github.com/affaan-m/ecc/tree/main/skills/agent-introspection-debugging)
- [Benchmark Optimization Loop](https://github.com/affaan-m/ecc/tree/main/skills/benchmark-optimization-loop)

Reviewed 2026-11-27 (America/Lima).
