# Workflow Definition Domain

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
