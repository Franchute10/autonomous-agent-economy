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

There is no balance or transaction behavior in this domain slice. Balances will
later be derived from the balanced append-only ledger.

## Non-goals

This implementation includes no ledger, transactions, postings, balances,
budgets, reservations, pricing, settlement, or persistence. It also includes no
repositories, runtime accounting, workflows, experiments, or provider code.
