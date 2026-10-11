# Experiments domain

An AEOS Experiment is a controlled unit of learning. EXP-001 records the
terms that must be declared before execution and the immutable lifecycle
snapshot that preserves those terms. It does not execute an experiment.

## Preregistration

`ExperimentPreregistration` is an immutable declaration owned by exactly one
`OrganizationId` and identified by one `ExperimentId`. It contains trimmed,
non-blank declarative `hypothesis` and `objective` text, at least one success
criterion, at least one kill/failure criterion, one or more maximum resource
exposure limits, and a required `preregistered_at` timestamp.

`ExperimentCriterion` contains only trimmed non-blank text. Criteria are
declarations, not executable predicates: they are not callbacks, expressions,
queries, metrics, or a rule language. EXP-001 does not evaluate them.

Success and kill criteria are strict immutable tuples, so caller ordering is
preserved. The maximum exposure collection is also a strict immutable tuple;
each `ExperimentResourceExposureLimit` pairs one existing `ResourceId` with
one existing `ResourceQuantity`. Limits must be strictly positive and a
resource may occur only once. Different resources remain independent: AEOS
does not sum, convert, price, or compare them.

Maximum exposure is a declared upper bound only. It is **not** a Reservation,
does not mutate a Budget, and performs no ledger movement. Preregistration and
lifecycle transitions create no reservation, balance query, transaction,
posting, settlement, or usage record.

## Lifecycle

`Experiment` is a frozen immutable snapshot containing one
`ExperimentPreregistration` plus lifecycle state. Lifecycle methods return a
new snapshot; the original snapshot and every preregistered term remain
unchanged. There is no amendment workflow in EXP-001. Future revisions will
be a separate task/model.

The exact states and transition matrix are:

| State | Permitted transitions |
| --- | --- |
| `PREREGISTERED` | `RUNNING`, `CANCELLED` |
| `RUNNING` | `SUCCEEDED`, `FAILED`, `KILLED`, `CANCELLED` |
| `SUCCEEDED` | none |
| `FAILED` | none |
| `KILLED` | none |
| `CANCELLED` | none |

The terminal states are `SUCCEEDED`, `FAILED`, `KILLED`, and `CANCELLED`; they
cannot reopen. An experiment starts `PREREGISTERED`. Cancellation before start
is valid and records `finished_at` while leaving `started_at` unset.

`preregistered_at` is required on the declaration. A running experiment has a
`started_at` and no `finished_at`. A terminal experiment has a `finished_at`;
the non-cancellation terminal states also require `started_at`. Timestamps
must be timezone-aware, are normalized to UTC through the Shared Kernel
`normalize_utc`, and obey `preregistered_at ≤ started_at ≤ finished_at` where
the values exist. Equality is valid.

## Boundaries and deferred work

Experiment lifecycle is **not** Workflow lifecycle. EXP-001 has no
`WorkflowRun`, scheduler, execution runtime, governance gate, or automatic
workflow creation. It does not store measured Evidence, observations, result
payloads, artifacts, provenance, metrics, statistical analysis, or criterion
assessments. Execution, governance enforcement, reservations, budget
enforcement, pricing, settlement, agents, models, tools, persistence,
simulation, and all related integrations are deferred.

`TraceContext` is optional on `ExperimentPreregistration` because it records
the causal creation metadata when a caller has that context. It is reused
without duplicating actor, correlation, causation, or idempotency fields;
lifecycle transitions do not invent new trace metadata. `VersionRef` is not
used: immutable declaration identity is sufficient for this bounded context.

No thesis-specific fields exist in the AEOS Experiment domain. Future research
traceability will map academic constructs to product-generated AEOS data in a
separate specification, without contaminating this product model.
