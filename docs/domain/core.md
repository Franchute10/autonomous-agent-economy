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

## Money and resource quantities

`Currency` is an immutable, structural ISO-style currency code. It normalizes
surrounding whitespace and lowercase input to a three-letter uppercase code;
it does not contain a currency registry or exchange-rate behavior.

`Money(amount, currency)` is an immutable signed value object. Amounts use
`Decimal` exactly and accept only `Decimal`, `int`, or numeric `str` inputs;
float input is rejected. No automatic two-decimal quantization occurs, so
arbitrary supported decimal precision is preserved. Same-currency values may
be added, subtracted, negated, and compared. Currency mismatches raise
`CurrencyMismatch`; there is no implicit FX conversion.

```python
Money("5", "USD") + Money("3", "USD")  # USD 8
Money("5", "USD") + Money("3", "PEN")  # CurrencyMismatch
```

Money is not an account balance, budget, availability, ledger posting, or
pricing result. Negative and zero values are valid; later business concepts
may impose their own sign rules.

`ResourceUnit` is an immutable non-blank canonical resource label. It has no
dimensional-analysis or conversion semantics. `ResourceQuantity(quantity,
unit)` is an immutable signed exact quantity using the same accepted numeric
forms and float rejection as `Money`. Same-unit values may be added,
subtracted, negated, and compared. Unit mismatches raise
`ResourceUnitMismatch`; there is no implicit unit conversion or pricing.

```python
ResourceQuantity("100", "input_tokens") + ResourceQuantity("50", "input_tokens")
# 150 input_tokens
ResourceQuantity("100", "input_tokens") + ResourceQuantity("50", "output_tokens")
# ResourceUnitMismatch
```

These primitives do not implement accounts, budgets, reservations, ledgers,
pricing, cost allocation, or persistence.
