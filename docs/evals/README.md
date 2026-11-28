# AEOS Evaluation Records

These documents define a future evaluation format; they are not an implemented evaluator.

- [Quality standard](../architecture/AGENT_QUALITY_STANDARD.md): quality dimensions, hard gates, evidence levels, comparison and promotion rules.
- [Agent and skill contract](../domain/AGENT_SKILL_CONTRACT.md): immutable versions, schemas, scope, bounds, policy references, evidence, and run records.
- [Evaluation fixtures and deterministic checks](../../tests/evals/README.md): synthetic case format, run record, denominators, evaluator order, and offline rules.
- [Security test matrix](../../tests/security/README.md): threat cases and proof required at actual action boundaries.
- [ADR index](../adr/README.md): accepted architecture decisions; documentation does not change implementation status.

For every comparison, preserve the exact commit, dataset and case versions, evaluator, environment, policy configuration, and agent/skill versions. Report every attempted case, including errors and timeouts. Keep human acceptance separate from benchmark scores and from user outcomes. LLM-as-judge is supplemental and must be calibrated; it cannot promote itself.

No evaluation harness, quality store, promotion service, or runtime is claimed to exist until code and checks demonstrate it.
