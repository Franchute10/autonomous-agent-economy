# Workflow Definition Domain

## WF-002 execution state

WF-001 definitions and WF-002 execution state are deliberately separate:
`WorkflowDefinition` is an immutable, versioned static graph, while
`WorkflowRun` is one logical execution instance identified by a
`WorkflowDefinitionId`. `NodeDefinition` is a static node description;
`NodeRun` is that node's logical occurrence inside a `WorkflowRun`; and
`NodeAttempt` is one concrete execution attempt of a `NodeRun`. One `NodeRun`
may therefore have zero or more separately stored `NodeAttempt` records over
its lifetime. These models contain references, not embedded definitions,
graphs, attempts, payloads, or execution callbacks.

The status sets and permitted transitions are:

| Model | Statuses | Permitted transitions |
| --- | --- | --- |
| `WorkflowRun` | `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED` | `PENDING → RUNNING/CANCELLED`; `RUNNING → SUCCEEDED/FAILED/CANCELLED` |
| `NodeRun` | `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED` | `PENDING → RUNNING/CANCELLED`; `RUNNING → SUCCEEDED/FAILED/CANCELLED` |
| `NodeAttempt` | `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED` | `PENDING → RUNNING/CANCELLED`; `RUNNING → SUCCEEDED/FAILED/CANCELLED` |

Terminal states cannot be reopened. WF-002 does not model readiness or
readiness evaluation. WF-002 does not implement `WAITING` or `PAUSED`
behavior. WAIT/RESUME comes later.

All three entities are frozen immutable snapshots. Lifecycle methods return a
new snapshot and never mutate the original. `created_at` is required;
`started_at` is populated when the entity enters `RUNNING`; and `finished_at`
is populated on a terminal transition. Timestamps are timezone-aware and
normalized through the Shared Kernel UTC helper; naive timestamps are
rejected. The ordering is `created_at ≤ started_at ≤ finished_at` wherever
the values exist. Cancellation before start is valid and records
`finished_at` while leaving `started_at` unset.

`NodeAttempt.attempt_number` is an exact Python `int`, must be at least 1,
rejects `bool`, and is immutable. Global uniqueness of
`(NodeRunId, attempt_number)` is **not yet** enforced; it belongs to future
persistence/application coordination.

There is no automatic orchestration in WF-002: creating a `WorkflowRun` does
not create `NodeRun` records, creating a `NodeRun` does not create attempts,
attempt state does not propagate to its node, node state does not propagate to
its workflow, and a failed attempt does not create a retry. A conceptual
lifecycle is `WorkflowRun: PENDING → RUNNING → SUCCEEDED`,
`NodeRun: PENDING → RUNNING → SUCCEEDED`, and
`NodeAttempt: PENDING → RUNNING → FAILED`, followed later by a separately
created `NodeAttempt #2`; automatic creation is not implemented.

Readiness evaluation, executors, retries and retry policy, WAIT/RESUME, leases,
scheduling, concurrency, persistence, recovery, governance gates, budget
reservations, model/tool calls, and Artifact/Audit integration are explicitly
deferred. The domain remains independent of runtime and infrastructure.

WF-001 contains only immutable workflow structure. `WorkflowDefinition` is an
exactly versioned graph owned by one `OrganizationId`; it is not a
`WorkflowRun`. Likewise, `NodeDefinition` is static structure, not a
`NodeRun` or `NodeAttempt`.

Nodes and edges are tuples and the entry-node collection is a tuple. A changed
graph is a new workflow definition/version. `NodeDefinition` has an identity,
name, approved descriptive `NodeKind`, and optional description. It contains
no executable implementation and no arbitrary configuration or JSON payload.
`EdgeDefinition` contains only an identity and unconditional source/target
node IDs; it has no executable condition.

The minimal node categories are `ACTION`, `DECISION`, and `END`. `ACTION`
describes future work without selecting an agent, model, tool, provider, or
implementation. `DECISION` is only a structural branching classification;
WF-001 contains no decision expressions or routing rules. `END` is an
explicit semantic end marker with no runtime behavior. An `END` node may not
be the source of an edge, but ordinary `ACTION` or `DECISION` nodes may still
be structural terminals.

Entries are explicit, one or more are supported, and an entry may have an
incoming edge. Terminal nodes are derived as nodes with no outgoing edges;
zero terminal nodes are allowed. A structural terminal is not runtime success
or completion.

Workflows are not required to be DAGs: multi-node cycles are allowed, while a
direct self-edge is rejected. Runtime loop bounds are not implemented here.
Every node must be reachable from an explicit entry, so disconnected nodes and
disconnected cycles are rejected.

WF-001 rejects duplicate node IDs, duplicate edge IDs, duplicate structural
source-to-target pairs, and missing edge references. It does not implement
`WorkflowRun`, `NodeRun`, `NodeAttempt`, WAIT/RESUME behavior, retries, leases,
scheduling, runtime execution, persistence, governance/economics execution,
models/tools, or automatic audit/artifact emission.

## Examples

- Single node: `A`, entry `A`, no edges; valid and structurally terminal.
- Linear: `A → B → C`, entry `A`; `C` is terminal.
- Cyclic: `A → B`, `B → A`, entry `A`; valid with no terminal nodes.
- Disconnected: entry `A`, `A → B`, plus `C → D → C`; invalid because `C` and
  `D` are unreachable.
