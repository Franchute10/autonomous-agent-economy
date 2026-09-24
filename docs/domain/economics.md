# Economics domain

The Economics domain currently defines economic identity and account structure.
It does not store or calculate amounts.

## Resource

`Resource` is an immutable definition owned by exactly one `OrganizationId`.
It has a typed `ResourceId`, a stable non-blank name, and exactly one explicit
`ResourceUnit`. A resource describes what is tracked and how it is measured;
it does not contain a quantity or balance.

## ResourceAccount

`ResourceAccount` is immutable structural metadata for one `ResourceId` and one
account category. The approved categories are:

- `AVAILABLE`
- `RESERVED`
- `COMMITTED`
- `CONSUMED`
- `EXTERNAL_SOURCE_OR_SINK`

An account type is a structural bucket, not a stored balance. Accounts do not
independently redefine `ResourceUnit`; unit semantics come from the referenced
resource. When both objects are available, account validation requires matching
organization ownership and resource identity.

Minimal structure:

```text
OrganizationId
  -> Resource(ResourceUnit)
      -> ResourceAccount(AVAILABLE)
```

There is no authoritative balance on a resource account. Balances will later
be derived from the balanced append-only journal.

## EconomicTransaction and LedgerPosting

`EconomicTransaction` is one immutable journal fact. Its exact transaction
type is one of `OPENING`, `ALLOCATE`, `RESERVE`, `RELEASE`, `COMMIT`,
`CONSUME`, `CREDIT`, `REFUND`, or `ADJUST`. `LedgerPosting` is an immutable
signed `ResourceQuantity` movement on exactly one `ResourceAccountId` and
`ResourceId`; zero postings are rejected.

Direct construction requires `postings` to be a tuple of `LedgerPosting`
values; that tuple is preserved unchanged. The `from_definitions()` convenience
factory accepts a sequence but validates every element before definition lookup.

Trace metadata is carried as the shared-kernel `TraceContext`, preserving the
actor, correlation, causation, and idempotency values without duplicating that
contract in Economics.

For every resource represented in a transaction, signed quantities must sum to
exact zero independently:

```text
AVAILABLE -5
RESERVED  +5
          = 0
```

Multi-resource transactions balance each resource separately:

```text
CASH   AVAILABLE -1, CONSUMED +1
TOKENS AVAILABLE -100, CONSUMED +100
```

Different resources are never summed together merely because their numeric
values happen to use compatible Decimal representations. Quantities for one
resource must use one unit; units are not converted. When supplied, resource
and account definitions are checked locally for resource identity, unit, and
organization consistency. A transaction's postings and metadata cannot be
edited after construction. Corrections are represented as new
`EconomicTransaction` instances; prior facts are not mutated.

Minimal construction:

```python
EconomicTransaction(
    EconomicTransactionId("tx-1"),
    organization_id,
    EconomicTransactionType.ALLOCATE,
    occurred_at,
    effective_at,
    trace,
    (
        LedgerPosting(resource_id, available_id, ResourceQuantity("-5", unit)),
        LedgerPosting(resource_id, reserved_id, ResourceQuantity("5", unit)),
    ),
)
```

## Budget and reservation

`Budget` is an immutable, purpose-bound authorization containing one or more
`BudgetLimit` values. Each limit is for one resource, positive, unit-specific,
and bounded by a UTC period. A budget cannot contain duplicate limits and each
limit must fit inside the budget period.

`Reservation` is an immutable positive hold created before execution. It must
reference the same organization and budget, fall within the budget period, and
be covered by a matching limit. `released(at)`, `committed(at)`, and
`expired(at)` return new reservation facts with caller-supplied UTC
`resolved_at` timestamps; they never mutate the original reservation. A
reservation always starts `ACTIVE`, and terminal state cannot be injected
through construction. Expiration and state are facts, not balance calculations.

These models provide local invariants only. They do not query current account
availability, sum concurrent reservations, persist state, or replace an
atomic application service.

## Non-goals

This implementation includes no persistent ledger, balances, pricing,
settlement, or persistence. It also includes no
repositories, runtime accounting, workflows, experiments, or provider code.
