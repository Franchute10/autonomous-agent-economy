# Architecture

The approved baseline is documented in
[`AEOS_Minimum_Viable_Technical_Architecture_v0.1.md`](AEOS_Minimum_Viable_Technical_Architecture_v0.1.md).
The governing dependency rules and fitness checklist are in
[`architecture-rules.md`](architecture-rules.md), and the decision index is
in [`../adr/README.md`](../adr/README.md).

The repository uses four provisional layers:

## Domain

Business concepts and invariants. The domain must remain independent from
databases, model providers, and external tools.

## Application

Coordinates use cases using domain objects.

## Infrastructure

Contains external technologies such as databases, LLM providers, tools, and
connectors.

## Interfaces

Contains CLI, API, and other user-facing entry points.

These boundaries are provisional and will evolve through explicit architecture
decisions.

No detailed AEOS models are defined yet. The baseline is approved, but the
capabilities it describes are not implemented by this documentation task.


## Agent quality, skills, evaluation and security

- [Agent quality standard](AGENT_QUALITY_STANDARD.md) — hard gates, reproducible baselines, evidence levels, and promotion/rollback criteria.
- [Agent and skill contract](../domain/AGENT_SKILL_CONTRACT.md) — versioned declarations and run-record requirements; capabilities do not grant permission.
- [Evaluation records](../evals/README.md) and [synthetic evaluation fixture format](../../tests/evals/README.md).
- [Security threat and test matrix](../../tests/security/README.md).

These are specifications and review criteria, not proof that an evaluator, memory service, authorization gateway, or agent runtime is implemented. See the code and ADRs for current implementation status.
