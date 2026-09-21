# AEOS Architecture Rules

These rules preserve the approved Working Technical Architecture v0.1. They
apply to future code and documentation changes.

1. Domain code may import only its own module and the small shared kernel.
2. Application code may import domain code and ports, but never concrete
   infrastructure.
3. Infrastructure implements ports defined inward by the application/domain
   boundary.
4. Interface handlers translate requests and responses; they contain no
   business rules.
5. Module ownership is respected even when modules use one database.
6. Cross-module state mutation occurs through application contracts or events,
   never through direct table manipulation.
7. Published definitions are immutable.
8. Material commands/actions preserve actor, correlation, causation, and
   idempotency metadata whenever those concepts exist.
9. Material state mutations eventually produce append-only audit history.
10. External effects eventually originate from durable intent.

## Architecture fitness checklist

Before accepting a future task, answer each question and record any required
follow-up:

- Does this task introduce a domain → infrastructure dependency?
- Does this task introduce a provider SDK into domain or application code?
- Does this task bypass module ownership?
- Does this task create mutable history where append-only history is required?
- Does this task introduce an unapproved framework?
- Does this task add a dependency without justification?
- Does this task change an approved architecture decision?
- If yes, is an ADR or Architecture Change Request required?

A task that cannot answer these questions consistently must not silently
proceed. Resolve the architecture question through the ADR/change process
before implementation.
