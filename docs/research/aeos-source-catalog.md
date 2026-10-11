# AEOS source catalog

This catalog identifies where a future research mapping may find authoritative
product facts. “Current” means the product domain currently models the fact;
it does not imply persistence, export, runtime collection, or research
readiness. “Future” means the product capability is not implemented and must
remain explicit rather than being invented in a research mapping.

## Catalog

| Source / bounded context | Authoritative facts currently represented | Current status | Example research use | Gaps and future task |
| --- | --- | --- | --- | --- |
| **Economics** | `Resource` / `ResourceQuantity`; `ResourceAccount` identity; `Budget` / `BudgetLimit`; `Reservation`; `EconomicTransaction` / `LedgerPosting`; and related operational economic facts represented by the current domain. | **CURRENT DOMAIN VOCABULARY**, not currently measured or exported research data. No thesis or metric fields, canonical cost dataset, or measurement service exists. | Describe resource endowment, account identity, budget limits, reservations, and economic movements once future contracts define observation and derivation semantics. Future metrics may derive balances, costs, runway, ROI, or sustainability. | Usage attribution, pricing, settlement, persistent observation history, fully defined balance derivation, and deterministic economic metrics are not supplied by THESIS-000. Metric contracts: **AEOS-METRIC-001**; dataset/export: **AEOS-EXP-002**. |
| **Experiments** | Experiment preregistration; declarative hypothesis and objective; success and kill criteria; resource exposure limits; immutable lifecycle state and timestamps from EXP-001. | **CURRENT** after AEOS-EXP-001. It declares and tracks lifecycle; it does not execute experiments or assess criteria. | Identify the product experiment, preregistered terms, lifecycle window, declared exposure, and later link a study requirement to an experiment identity. | Execution observations, treatment assignment, run-level measurements, result payloads, criterion assessment, and controlled protocol are not part of EXP-001. Protocol: **AEOS-SIM-002** or **AEOS-STUDY-002**; dataset/export: **AEOS-EXP-002**. |
| **Workflows** | Workflow definitions, nodes and edges; workflow runs; node runs; attempts; immutable execution lifecycle facts from WF-001/WF-002. | **CURRENT DOMAIN VOCABULARY**. No research interpretation or dataset exporter. | Trace procedure execution, attempt counts, completion state, failures, timing, and operational reproducibility inputs where a future requirement needs them. | Scheduler/execution runtime, complete event collection, resource usage attribution, and research-ready run export are not guaranteed by current domain models. Future workflow/runtime measurement tasks must define authoritative capture. |
| **Governance** | Constitution and policies; permissions; approval requests and decisions; governed authorization facts represented by the current domain. | **CURRENT DOMAIN VOCABULARY**. Governance records are operational controls, not academic evidence by themselves. | Establish whether an action or experiment was permitted, approved, rejected, or constrained under a stated governance context. | Policy/version retrieval at study time, complete decision evidence collection, and joining governance decisions to future observations need explicit future contracts. Reproducibility linkage: **AEOS-REPRO-001**. |
| **Knowledge / Audit** | `Artifact`, `Evidence`, `ProvenanceLink`, and `AuditEvent`; content identity, support claims, directed derivation/support relations, and append-only operational audit facts. | **CURRENT DOMAIN VOCABULARY**. Storage and graph-wide traversal are intentionally limited; artifact content does not become evidence automatically. | Preserve source material, support a measurement or claim, show derivation, and identify that an operational action occurred. | A research evidence package, manifest assembly, repository/query layer, complete provenance traversal, and dataset packaging are not implemented. Manifest: **AEOS-REPRO-001**; thesis package: **AEOS-THESIS-001**. |
| **Runtime** | Agent execution, model calls, tool calls, decision traces, latency, token/resource usage, and runtime outcomes would be potential facts. | **FUTURE — NOT YET PRODUCED** in the current product baseline. | Analyze runtime behavior, autonomy, model/tool usage, decision quality, or attribution of cost and outcome. | No runtime bounded context or telemetry contract exists in this task. Do not claim these facts are available. Future runtime task must define ownership, capture, retention, and evidence. |
| **Metrics** | A future deterministic measurement layer could provide metric definitions, calculations, units, derivations, and measurement results. | **FUTURE — AEOS-METRIC-001**. No metric engine or derived metric persistence is implemented here. | Operationalize indicators and calculate reproducible measures from declared data requirements. | Metric contract, calculator, aggregation, missing-data behavior, and persistence are all future scope. |

## Source ownership rules

`CURRENT DOMAIN VOCABULARY` is not the same as currently measured or exported
research data. A modeled economic fact is not automatically a canonical cost,
balance, runway, ROI, or sustainability measure. Those derived measures require
future usage, pricing, settlement, observation, and deterministic derivation
contracts.

1. The source is the bounded context that owns the operational fact, not the
   context that later interprets it academically.
2. A mapping must distinguish a fact currently represented in the domain from a
   fact that is actually persisted, exported, or collected in an experiment.
3. A future source must be labelled **NOT YET PRODUCED** until its product task
   exists and is verified.
4. Research mappings may combine facts from several sources, but they must not
   duplicate or re-home ownership.
5. Derived values must identify their source facts, derivation contract, and
   supporting evidence. A derived research result is not a new product fact.

## Minimum source citation in a future mapping

A future measurement or study record should identify, at minimum, the source
bounded context, product identity or event type, observation time/window,
version or lifecycle context when available, evidence/provenance references,
and any missing or derived inputs. These are future contract requirements, not
fields to add to current product entities in THESIS-000.
