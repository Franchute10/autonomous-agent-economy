# AEOS-CORE-001 Shared Kernel

The Shared Kernel contains small provider-free value objects shared by later
AEOS modules. It has no persistence, authorization, economics, workflow,
experiment, model-provider, or tool behavior.

## Public contract

`aeos.core.ids` exposes concrete immutable ID types for organizations, roles,
agents, governance, economics, experiments, workflows, runtime, knowledge,
and model/tool calls, plus `CorrelationId`, `CausationId`, and
`IdempotencyKey`. Each type supports `new()` for local generation and
`from_string(value)` for reconstruction. IDs reject blank values, are hashable,
and remain distinct by concrete type.

`normalize_utc(datetime_value)` accepts only timezone-aware datetimes and
normalizes non-UTC values to UTC. Naive datetimes are invalid.
`UtcTimestamp` is currently a lightweight alias for `datetime`; domain and
application code must call `normalize_utc()` on external datetime values
before treating them as UTC timestamps.

`ActorRef` records an actor ID and generic `ActorKind` (`HUMAN`, `AGENT`, or
`SYSTEM`). Actor identity is not authority: it contains no role or permission
decision. `CorrelationId` connects operations in one logical trace, while an
optional `CausationId` identifies the prior operation that caused an action.
`TraceContext` groups actor, correlation, mandatory idempotency, and optional
causation metadata without adding deduplication or execution behavior.

Example:

```python
from aeos.core import (
    ActorKind,
    ActorRef,
    CorrelationId,
    IdempotencyKey,
    OrganizationId,
    TraceContext,
)

organization_id = OrganizationId.new()
trace = TraceContext(
    actor=ActorRef(organization_id, ActorKind.SYSTEM),
    correlation_id=CorrelationId.new(),
    idempotency_key=IdempotencyKey.new(),
)
```

IDs are serialized by `str(id)` and reconstructed with the matching concrete
class. No JSON encoder, database mapping, or framework integration is defined.
