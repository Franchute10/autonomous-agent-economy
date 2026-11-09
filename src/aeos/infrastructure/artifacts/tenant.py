"""Tenant-scoped local artifact storage for private commercial payloads."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from aeos.core import ContentHash, OrganizationId
from aeos.infrastructure.artifacts.local import LocalFilesystemArtifactAdapter
from aeos.knowledge.ports.artifacts import ArtifactIntegrityError
from aeos.tenancy.domain import TenantContext
from aeos.tenancy.errors import TenantAccessDenied


@dataclass(frozen=True, slots=True)
class TenantArtifactStorageResult:
    """Storage facts bound to the organization that owns the payload."""

    organization_id: OrganizationId
    content_hash: ContentHash
    size_bytes: int
    storage_ref: str


class LocalTenantArtifactStorage:
    """Store payloads under a non-shared directory for each authorized tenant.

    The raw ``LocalFilesystemArtifactAdapter`` remains a platform-level port.
    Tenant-facing application code should use this adapter so identical hashes
    in two organizations still resolve to different files.
    """

    def __init__(self, root: str | Path) -> None:
        configured_root = Path(root)
        if configured_root.exists() and not configured_root.is_dir():
            raise NotADirectoryError(f"artifact root is not a directory: {root}")
        self._root = configured_root.resolve()

    def put(
        self, context: TenantContext, content: bytes
    ) -> TenantArtifactStorageResult:
        adapter = self._adapter(context)
        result = adapter.put(content)
        return TenantArtifactStorageResult(
            context.organization_id,
            result.content_hash,
            result.size_bytes,
            result.storage_ref,
        )

    def get(self, context: TenantContext, content_hash: ContentHash) -> bytes:
        return self._adapter(context).get(content_hash)

    def exists(self, context: TenantContext, content_hash: ContentHash) -> bool:
        return self._adapter(context).exists(content_hash)

    def _adapter(self, context: TenantContext) -> LocalFilesystemArtifactAdapter:
        if not isinstance(context, TenantContext) or not context.is_active():
            raise TenantAccessDenied()
        tenant_key = hashlib.sha256(
            context.organization_id.value.encode("utf-8")
        ).hexdigest()
        tenant_root = self._root / tenant_key
        if tenant_root.is_symlink():
            raise ArtifactIntegrityError(
                "tenant artifact directory cannot be a symlink"
            )
        try:
            tenant_root.resolve().relative_to(self._root)
        except ValueError as error:
            raise ArtifactIntegrityError(
                "tenant artifact directory escapes storage root"
            ) from error
        return LocalFilesystemArtifactAdapter(tenant_root)


__all__ = ["LocalTenantArtifactStorage", "TenantArtifactStorageResult"]
