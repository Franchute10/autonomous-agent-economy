# AEOS persistence architecture

INFRA-001 establishes PostgreSQL as the canonical durable store for the modular monolith. SQLAlchemy 2.x Core is used only in Infrastructure, Alembic owns schema evolution, and module/application ports remain inward-facing. Domain objects are not ORM entities: repositories write relational rows and explicitly reconstruct valid domain constructors.

## Scope

Persisted in this baseline:

- organization structure: `Organization`, `Role`, and `RoleAssignment`;
- governance facts needed for authorization inputs: constitution and policy versions, permission grants, governance decisions, approval requests and decisions;
- economics: `Resource`, `ResourceAccount`, `Budget`/`BudgetLimit`, `Reservation`, `EconomicTransaction` and `LedgerPosting`;
- experiments: separate preregistration, ordered criteria/exposure children, and lifecycle snapshot;
- workflows: immutable definitions with ordered nodes, edges and entries, plus current `WorkflowRun`, `NodeRun`, and `NodeAttempt` state;
- agents: exact AGT-001 `AgentDefinition` and `AgentInvocation` contracts.

Knowledge metadata, artifact metadata repositories, usage reporting, pricing, settlement, cost allocation, audit/provenance repositories, and all research/thesis concepts are deferred. The existing local `ArtifactPort` remains the adapter for artifact bytes.

## Mapping and value semantics

Typed IDs are stored as non-blank strings and reconstructed using their exact ID class. Actor references additionally store actor ID class and actor kind, so flattened trace columns do not erase nominal identity. `VersionRef` is always two columns (`subject`, `version`); no latest/current/active alias is introduced.

UTC timestamps use PostgreSQL `TIMESTAMP WITH TIME ZONE`. Adapters reject naive timestamps during reconstruction. Authoritative quantities use `NUMERIC(38,18)` and a separate unit column; no float, FX conversion, or unit conversion is performed. The selected precision is sufficient for the current contracts and is intentionally visible in the schema. Money is not currently present on an in-scope aggregate.

TraceContext is flattened into actor ID/type/kind, correlation ID, idempotency key, and optional causation ID columns wherever a current domain contract has trace data. No second trace object is created.

Ordered tuples are stored with explicit zero-based `ordinal` columns. This applies to capabilities, workflow children, experiment criteria/exposures, budget limits, postings, and version-reference lists.

`AgentDefinition` identity is the exact composite `(id, version_subject, version)`. Agent capabilities and invocations reference that same composite key, so multiple versions of one definition ID can coexist without allowing a capability or invocation to point at a different version. `AgentDefinitionRepository.get` therefore requires both the typed definition ID and its `VersionRef`. The schema defines primary keys and required uniqueness constraints only; no additional secondary indexes are claimed in this baseline.

## Ownership and transactions

Tables and concrete adapters are grouped by bounded context in `schema.py` and `repositories.py`; public contracts are narrow and no repository reaches through another module to implement business behavior. There is no generic repository or generic JSON/domain blob table.

`SqlAlchemyUnitOfWork` creates and owns one session. Repositories use that session and never commit. Callers explicitly call `commit()`; `rollback()` is available and exceptions during context exit roll back before the session closes. The UoW exposes only the currently selected repositories, making future atomic governance/economic/runtime coordination possible without implementing that use case here.

Definitions and economic facts are append-only by API: repositories expose `add`/`append` and no update/delete methods. Workflow, experiment, and execution records are current snapshots; this is not event sourcing. Reservation state remains a hold state and is never translated into ledger movement. Resource accounts and budgets have no stored balance, remaining, or spent columns.

Workflow persistence does not add a DAG check; valid domain cycles remain representable. SQL contains structural keys and simple quantity/ordinal checks only, not state-machine transitions or domain evaluation.

## Migrations and configuration

`migrations/versions/0001_initial_persistence.py` is the frozen Alembic definition: it creates the complete final schema, including exact AgentDefinition version identity and references, from an empty PostgreSQL database with explicit operations and provides a reverse-dependency-order downgrade. It does not import or execute the mutable runtime table metadata. The PostgreSQL integration parity assertion compares the upgraded database with the runtime metadata after migration. `AEOS_DATABASE_URL` is preferred, with `DATABASE_URL` accepted for local tooling. No credentials are committed. Example:

```powershell
$env:AEOS_DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/aeos_test"
\.venv\Scripts\alembic.exe upgrade head
```

The password above is an example only and must be supplied through the environment or a secret manager.

## Testing boundary

The normal unit suite does not require a database. PostgreSQL integration tests must run against a real PostgreSQL DSN, perform Alembic upgrade from an empty database, exercise repository round trips, verify `alembic_version` and representative tables at head, downgrade to base, and cleanly re-upgrade before repeating the round trip. Test cleanup deletes only test data; it never creates or drops the migration-owned schema. SQLite may be used only as a local mapper smoke test; it is not evidence of PostgreSQL compatibility. No PostgreSQL service or DSN was available in the implementation environment, so PostgreSQL integration was not claimed as passed.

Transactional outbox/inbox behavior is deferred. ADR-006 remains compatible because later RUN-003/RUN-004 can add module-owned outbox/inbox tables and adapters without changing these domain contracts; no dispatcher, poller, ExternalAction, or WAIT/RESUME behavior is included here.
