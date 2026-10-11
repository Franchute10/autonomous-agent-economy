# Research traceability

This directory defines the documentation contract that lets future research
refer to AEOS-generated facts without making AEOS product domains academic.
It is not a runtime bounded context, research database, thesis repository, or
statistical analysis package.

## Documents

- [`research-traceability-spec.md`](research-traceability-spec.md) — boundary,
  concepts, chain semantics, invariants, and the provisional anchor.
- [`aeos-source-catalog.md`](aeos-source-catalog.md) — authoritative product
  sources, current availability, research uses, and explicit gaps.
- [`unprg-requirements-map.md`](unprg-requirements-map.md) — future evidence
  and academic-work requirements associated with EPG-UNPRG expectations.
- [`future-measurement-roadmap.md`](future-measurement-roadmap.md) — dependency
  intent for later measurement, reproducibility, study, and thesis tasks.

## Scope rule

These documents describe a traceability contract only. They do not create
`src/aeos/research/` or `src/aeos/thesis/`, add thesis fields to product
entities, define a generic academic schema, perform measurements, create
datasets, run experiments, or write thesis sections.

The product baseline remains the operational AEOS domains. Research may point
to their facts through documented mappings; product domains must not import or
model academic interpretation.
