# Research traceability specification

**Task:** AEOS-THESIS-000 — Research Traceability Specification
**Status:** Documentation / specification only
**Authority:** Working Technical Architecture v0.1
**Scope:** Reproducible research traceability, not thesis content or runtime
research infrastructure.

## 1. Purpose

This specification defines the minimum chain needed for a future researcher to
answer:

- what question is being investigated;
- which objective addresses it;
- which construct or variable is relevant;
- how that construct is operationalized;
- which indicator represents it;
- which future metric would measure it;
- which raw or derived facts the metric requires;
- which AEOS bounded context owns each authoritative fact;
- what evidence supports a measurement or claim;
- which AEOS experiment can generate or test relevant facts; and
- how a future dataset or result could be analyzed and reproduced.

THESIS-000 does not perform those measurements. It records the contract and
the missing capabilities so future work can be explicit about what exists,
what is planned, and what must come from external academic work.

## 2. Product/research boundary

### Product layer

AEOS product bounded contexts remain operationally focused:

- Economics;
- Experiments;
- Workflows;
- Governance;
- Knowledge / Audit;
- future Runtime; and
- future Metrics.

They own operational facts such as transactions, resource state, experiment
lifecycle, workflow execution state, permissions, approvals, artifacts,
evidence, provenance, and audit events. They do not know that a fact may later
support a thesis.

### Research layer

The research specification uses documentation concepts such as questions,
objectives, constructs, indicators, hypotheses, data requirements, evidence
requirements, experiment links, and analysis mappings. These concepts refer to
product-generated facts by documented identity or source ownership; they do
not modify the product entities that produced those facts.

No fields such as `research_question`, `research_construct`,
`academic_hypothesis_id`, `thesis_variable`, or `thesis_chapter` may be added
to Economics, Experiments, Workflows, Governance, Knowledge/Audit, Shared
Kernel, Runtime, or any other product model.

The separation is intentionally one-way in the conceptual model:

```text
product facts  ->  research traceability mapping  ->  future study analysis
```

Research conclusions are interpretations. They must never be written back as
product facts.

## 3. Canonical traceability chain

```text
ResearchQuestion
  -> ResearchObjective
  -> Construct / Variable
  -> Indicator
  -> MetricDefinition
  -> DataRequirement
  -> AEOSSource
  -> EvidenceRequirement
  -> ExperimentLink
  -> AnalysisPlan / Study Mapping
```

The arrows mean the following:

| From | To | Documented semantics |
| --- | --- | --- |
| ResearchQuestion | ResearchObjective | The objective states what must be evaluated, compared, measured, explained, or established to address the question. |
| ResearchObjective | Construct / Variable | The objective identifies the research concept whose properties are relevant to the objective. This is a traceability choice, not a product classification. |
| Construct / Variable | Indicator | The indicator is an observable representation of a defined part of the construct or variable. |
| Indicator | MetricDefinition | A future deterministic metric contract specifies how the indicator will be measured. THESIS-000 does not implement that contract. |
| MetricDefinition | DataRequirement | The future metric declares the raw or derived facts it needs and the required temporal, identity, and derivation semantics. |
| DataRequirement | AEOSSource | Each required fact is mapped to the product bounded context that owns it, or explicitly marked `NOT YET PRODUCED`. |
| AEOSSource | EvidenceRequirement | The source mapping states what artifact, evidence, audit event, provenance relation, or external material must support the fact or derived result. |
| EvidenceRequirement | ExperimentLink | The evidence requirement is connected to the experiment identity, lifecycle, run, or future dataset that can produce or preserve the supporting observation. |
| ExperimentLink | AnalysisPlan / Study Mapping | A future study records how the experiment output will be assembled into an analysis input, comparison, result, or limitation without putting analysis into the experiment product model. |

The chain is a documentation relationship, not a request to create a generic
research graph, registry, or JSON metadata framework.

This is a semantic traceability sequence, **not a one-to-one cardinality
requirement**. One question may have multiple objectives; one objective may
involve multiple constructs or variables; one indicator may require multiple
data sources; one research hypothesis may require multiple product
experiments; and one experiment may support multiple research mappings. The
specification describes these relationships without implementing a graph or
registry.

## 4. Concept definitions and classification

Every concept is classified before any future implementation decision.

| Concept | Specification meaning | Classification |
| --- | --- | --- |
| **ResearchQuestion** | A question the future study seeks to answer. It traces to one or more objectives and may be refined without changing product code. | **DOCUMENTATION NOW** |
| **ResearchObjective** | What the study must evaluate, compare, measure, explain, or establish. It traces to a question. | **DOCUMENTATION NOW** |
| **Construct / Variable** | A research concept whose properties may be operationalized. Final AEOS research constructs are not frozen by this task. | **DOCUMENTATION NOW** |
| **Indicator** | An observable representation of part of a construct or variable, with semantics explicit enough to support later operationalization. | **DOCUMENTATION NOW** |
| **MetricDefinition** | A deterministic future measurement definition that operationalizes an indicator, including inputs, units, scope, temporal rules, derivation, missing-data behavior, and evidence expectations. | **FUTURE CODE** — AEOS-METRIC-001 |
| **DataRequirement** | The raw or derived fact needed to calculate a future metric or answer a research need. It names expected semantics without claiming unavailable data exists. | **DOCUMENTATION NOW** |
| **AEOSSource** | A mapping to the authoritative AEOS product module owning a required fact. It is not a product service or academic interpretation. | **DOCUMENTATION NOW** |
| **EvidenceRequirement** | The evidence that must accompany or support a measurement, claim, or result, compatible with Artifact, Evidence, ProvenanceLink, and AuditEvent. | **DOCUMENTATION NOW** |
| **ExperimentLink** | A mapping from a question, objective, indicator, or future metric requirement to an AEOS experiment identity, lifecycle, run, or future dataset. It does not add fields to `Experiment`. | **DOCUMENTATION NOW** |
| **AnalysisPlan / Study Mapping** | A future record of how a dataset or result is intended to support comparison, analysis, interpretation, and limitations. It does not implement statistics. | **DOCUMENTATION NOW**; future ownership is the study/thesis analysis layer |

Hypothesis and protocol are supporting research concepts documented by this
specification, but no final academic hypothesis, statistical model, or
protocol is frozen here. A future study may represent a research hypothesis,
including null and alternative forms where methodology requires them.

## 5. Traceability invariants

The following are specification-level invariants. They are not runtime
validators in THESIS-000:

1. Every `ResearchObjective` traces to at least one `ResearchQuestion`.
2. Every construct or variable used in a study traces to at least one objective
   or an explicit research hypothesis.
3. Every `Indicator` traces to a construct or variable with identified
   semantics.
4. Every future `MetricDefinition` traces to an indicator.
5. Every future `MetricDefinition` identifies its required
   `DataRequirement` items.
6. Every `DataRequirement` identifies an authoritative `AEOSSource`, or is
   explicitly marked **NOT YET PRODUCED**.
7. Every `EvidenceRequirement` states which measurement, claim, or result it
   supports.
8. Every `ExperimentLink` states which question, objective, indicator, or
   future metric need the experiment can inform.
9. An `AEOSSource` represents the product module that owns a fact, not an
   academic interpretation of the fact.
10. Missing capabilities remain explicit gaps. Telemetry is never invented to
    complete a mapping.
11. Academic traceability metadata is not added to product models.
12. Research conclusions are never treated as product facts.

## 6. Provisional research anchor

The project's original question is recorded as a **PROVISIONAL RESEARCH
ANCHOR**:

> “¿Puede un ecosistema de agentes IA convertir USD 50 en un sistema
> autosostenible y rentable durante 30 días?”

It is explicitly:

- **PROVISIONAL**;
- **NOT FINAL ACADEMIC FORMULATION**; and
- **SUBJECT TO REFINEMENT**.

It is not frozen as a thesis title, final problem statement, academic
hypothesis, variable model, methodology, or final indicator set. Refinement is
expected to occur in later study work without changing product-domain code.

## 7. Hypothesis distinction

The `hypothesis` in an AEOS `ExperimentPreregistration` is a product-level
declaration for one specific AEOS experiment. It belongs to the experiment's
operational preregistration and lifecycle.

A future **research hypothesis** is an academic proposition investigated by a
study. It may align with one or more product experiment declarations, but it
is not automatically the same domain concept. A product experiment can inform
a research hypothesis without proving it, and a research hypothesis may need
multiple experiments or external evidence. This distinction requires no field
in `Experiment`.

## 8. Evidence, provenance, and missing-data handling

Evidence expectations remain compatible with the existing Knowledge/Audit
vocabulary:

- `Artifact` identifies preserved content metadata and exact content identity;
- `Evidence` records a support claim with an explicit artifact or typed fact
  source;
- `ProvenanceLink` records a directed derivation or support relationship; and
- `AuditEvent` records that an operational action or mutation occurred.

A research mapping must state whether evidence supports an observed product
fact, a derived value, a protocol decision, a claim, or a result. An artifact
alone is not automatically evidence, and evidence is not automatically a
research conclusion. The future reproducibility task may define how these
references are assembled into a manifest; THESIS-000 does not implement it.

If a required fact is absent, the mapping must use **NOT YET PRODUCED** and
identify the capability gap or future task. Examples include runtime model and
tool usage, a canonical metric service, a dataset export, or a controlled
30-day protocol. A future source is not evidence of current availability.

## 9. Provisional illustrative traceability item

The following is **PROVISIONAL / ILLUSTRATIVE ONLY**. It is not a final thesis
variable or indicator:

| Chain item | Illustrative mapping |
| --- | --- |
| ResearchQuestion | Can AEOS achieve economic sustainability under a constrained initial resource endowment? |
| ResearchObjective | Evaluate economic performance under a defined future experiment protocol. |
| Construct | Economic sustainability. |
| Indicator | Resource-value preservation or growth over a defined period. |
| MetricDefinition | **FUTURE — AEOS-METRIC-001**; deterministic unit, scope, time window, inputs, derivation, and missing-data rules are not implemented here. |
| DataRequirement | Economic transactions; resource balances derived later; experiment start/end state; cost and usage facts. |
| AEOSSource | Economics and Experiments; future Runtime and Metrics where applicable. Each unavailable source remains `NOT YET PRODUCED`. |
| EvidenceRequirement | Artifact, Evidence, AuditEvent, and provenance sufficient to establish the origin and derivation of observed values. |
| ExperimentLink | Future controlled study / future `$50` protocol; no experiment is executed by THESIS-000. |
| AnalysisPlan / Study Mapping | **FUTURE**; specifies comparison, limitations, and interpretation only after a study protocol and data contract exist. |

## 10. Future study and analysis mapping

A future study mapping should identify the research question and objective,
the exact experiment or dataset identity, the observation window, inclusion
and exclusion rules, required source facts, derivations, evidence references,
missing-data decisions, comparison or baseline, and the limits of the result.
It may describe a planned descriptive or inferential analysis, but the
analysis implementation and statistical decisions belong to future study work.

The mapping must preserve the difference between:

- a product experiment lifecycle and its operational facts;
- a future dataset assembled from those facts; and
- an academic interpretation or conclusion.

## 11. Explicit non-goals

THESIS-000 does not write thesis chapters, finalize the academic problem,
hypothesis, objectives, constructs, variables, indicators, or methodology. It
does not implement `MetricDefinition`, a metrics engine, datasets or exports,
statistical analysis, reproducibility manifests, simulation or study runners,
academic repositories, research APIs, dashboards, callbacks, generic JSON
blobs, or a research/thesis Python bounded context.
