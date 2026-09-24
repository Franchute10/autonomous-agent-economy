# Knowledge & Audit domain

This bounded context defines immutable content metadata and the smallest
vocabulary for audit and provenance. It contains domain models only: there is
no persistence, repository, audit store, graph store, search, or automatic
audit emission.

## Artifact semantics

An Artifact has an `ArtifactId`, one owning `OrganizationId`, an explicit `media_type`, exact `size_bytes`, an opaque `storage_ref`, a UTC `created_at`, and a `ContentHash`. Metadata is frozen and does not contain the payload. `logical_name`, when present, is descriptive metadata only.

`ArtifactId` identifies the AEOS domain record. `ContentHash` identifies the exact bytes. They are intentionally different identities. ContentHash uses the existing SHA-256 primitive over the exact supplied bytes; it does not canonicalize arbitrary Python objects. ContentHash proves byte identity, not truth, quality, or provenance.

## ArtifactPort and local storage

`ArtifactPort` exposes only:

- `put(content: bytes) -> ArtifactStorageResult`;
- `get(content_hash: ContentHash) -> bytes`;
- `exists(content_hash: ContentHash) -> bool`.

The port stores payload bytes. It is not an Artifact metadata repository and has no save, query, list, or delete operation. The dependency direction is:

```text
Knowledge domain/port  <- implemented by -  Infrastructure local adapter
```

`LocalFilesystemArtifactAdapter` stores under a configured root at a deterministic SHA-256-derived path (`sha256/<digest-prefix>/<digest>`). Identical bytes are idempotent. Existing files are verified rather than overwritten, and exclusive same-filesystem publication prevents replacement races. Reads and existence checks verify the hash before returning or reporting presence. Missing or corrupted content fails explicitly. Paths are derived only from validated ContentHash values, never filenames or arbitrary references. No database, network, or cloud storage is used.

The port accepts `ContentHash`, not `storage_ref`, for retrieval and existence checks. `storage_ref` is opaque metadata returned for constructing an Artifact; its current local representation must not be treated as a content identity by callers.

The minimal flow is:

```text
bytes -> ContentHash -> ArtifactPort.put -> storage_ref -> Artifact metadata
      -> ArtifactPort.get -> identical bytes
```

Artifact is stored content; it is not Evidence and is not an AuditEvent.
Evidence and AuditEvent are implemented KNOW-002 vocabulary. Persistence,
repositories, audit storage, provenance graph traversal, indirect cycle
detection, graph databases, search, embeddings, semantic retrieval, agent
memory, workflow/experiment/runtime integration, and automatic audit emission
remain explicit non-goals.

## Evidence

`Evidence` is an immutable support claim with a non-blank `statement` and at
least one explicit source: an `ArtifactId` or a typed `FactRef`. `FactRef`
accepts only the implemented material fact ID set; ArtifactId and EvidenceId
are not FactRef sources. It never
contains payload bytes, changes Artifact metadata, calculates a hash, or
performs storage, ranking, confidence, or retrieval. Artifact content does not
automatically become Evidence.

## AuditEvent

`AuditEvent` is an immutable append-only material historical fact that an
action or mutation occurred. It has an `AuditEventId`, stable event type,
canonical dot-separated symbolic event type, `AuditSubjectRef`, UTC
`occurred_at`, required shared-kernel `TraceContext`,
and optional typed Artifact/Evidence references. Existing audit events are
never edited; corrections are represented by new facts. `DomainEvent` and
`AuditEvent` are distinct concepts: AuditEvent is neither a subclass nor an
alias of DomainEvent and only reuses shared primitives.

## ProvenanceLink

`ProvenanceLink` is an immutable directed `source -> target` relation. The
direction means that the target derives from, or is supported by, the source,
according to its closed `ProvenanceRelation` (`DERIVED_FROM` or
`SUPPORTED_BY`). Endpoints are closed `ProvenanceRef` values for Artifact,
Evidence, AuditEvent, or an explicitly supported material domain fact. Direct self-links are
rejected. Global graph traversal, indirect cycle detection, duplicate
detection, and repository lookup are intentionally not implemented.

All model timestamps use the shared UTC normalization rules, and trace metadata
uses the shared `TraceContext` type. Organization ownership is optional local
context; cross-organization checks requiring object loading are deferred.

Minimal examples:

```text
Artifact A -> Evidence E supporting statement S
Artifact A -> ProvenanceLink(DERIVED_FROM) -> Artifact B
material action -> AuditEvent with TraceContext and optional references
```
