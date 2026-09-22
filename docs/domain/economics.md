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

This task defines no persistent ledger, account balance query, budget,
reservation, pricing, usage settlement, cost allocation, persistence, or
runtime accounting. It defines no transaction service or repository.

## Non-goals

This implementation includes no persistent ledger, balances, budgets,
reservations, pricing, settlement, or persistence. It also includes no
repositories, runtime accounting, workflows, experiments, or provider code.
