# Future measurement roadmap

This roadmap records dependency intent only. None of the tasks below is
implemented by AEOS-THESIS-000.

## Dependency sequence

```text
THESIS-000 traceability specification
        |
        +--> AEOS-METRIC-001 --+
        |                       |
        +--> AEOS-SIM-002 -----+--> AEOS-EXP-002
        |                       |        |
        +--> AEOS-REPRO-001 ---+        +--> AEOS-STUDY-001
        |                                +--> AEOS-STUDY-002
        |                                         |
        +-----------------------------------------+--> AEOS-THESIS-001
```

The sequence is directional intent, not a locked project plan. Each future
task must preserve the product/research boundary and verify its own scope.

## Future tasks

| Task | Dependency intent | Explicit non-implementation in THESIS-000 |
| --- | --- | --- |
| **AEOS-METRIC-001 — Experimental metrics & measurement contracts** | Turn an indicator into a deterministic metric contract with inputs, units, scope, time semantics, derivation, missing-data rules, and evidence expectations. | No `MetricDefinition` class, calculator, aggregation engine, or derived metric persistence is created. |
| **AEOS-REPRO-001 — Reproducibility Manifest** | Define how source identities, versions, protocol references, artifacts, evidence, provenance, and environment information can be assembled for replay or audit. | No manifest model, replay engine, runner, or research repository is created. |
| **AEOS-SIM-002 — Experimental scenario protocol** | Define a reproducible scenario/procedure and its controlled inputs before execution or simulation work. | No simulation protocol or scenario executor is created. |
| **AEOS-EXP-002 — Experimental dataset/export** | Define how observations and supporting facts are selected, frozen, traced, and exported for study use. | No dataset model, CSV/Parquet export, research database, or export service is created. |
| **AEOS-STUDY-001 — Baseline/comparative experiment** | Specify a baseline or comparison that can test a future objective with explicit controls, measurements, and limitations. | No study runner, baseline execution, statistical test, or comparison result is created. |
| **AEOS-STUDY-002 — 30-day $50 experiment protocol** | Apply the provisional anchor to a future controlled protocol after metrics, reproducibility, and dataset contracts exist. | No `$50`/30-day experiment is executed, simulated, or frozen as the final academic method. |
| **AEOS-THESIS-001 — Thesis evidence package** | Assemble traceable AEOS evidence and external references for future academic work while keeping interpretation and thesis writing outside AEOS product models. | No thesis package, chapter, literature review, discussion, conclusion, or academic repository is created. |

## Handoff requirements

Future tasks should consume this specification by preserving:

1. explicit source ownership;
2. `NOT YET PRODUCED` for unavailable facts;
3. product experiment hypothesis versus research hypothesis distinction;
4. Artifact/Evidence/ProvenanceLink/AuditEvent compatibility;
5. immutable operational facts and deterministic derivation where applicable;
6. no thesis-specific fields in product entities; and
7. no generic academic framework, arbitrary JSON blob, callback, or
   `dict[str, Any]` research model.

The final academic formulation, variables, indicators, protocol, analysis, and
research conclusions remain decisions for future study and thesis work.
