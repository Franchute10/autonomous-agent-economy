# Knowledge & Audit: Artifact foundation

This module currently provides only immutable `Artifact` metadata and an inward-defined `ArtifactPort` for exact payload bytes. It does not implement Evidence, provenance, audit, search, or metadata persistence.

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

Artifact is stored content; it is not Evidence. Artifact is also not an AuditEvent. Evidence, provenance graphs, AuditEvent, search, embeddings, vector/graph databases, agent memory, database metadata persistence, remote storage, and workflow/model/tool integration are explicit non-goals of this foundation.
