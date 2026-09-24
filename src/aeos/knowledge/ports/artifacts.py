"""Port for exact payload bytes, intentionally not an artifact repository."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from aeos.core import ContentHash


class ArtifactIntegrityError(IOError):
    """Stored bytes do not match their content address."""


class ArtifactNotFound(FileNotFoundError):
    """No payload exists for the requested content address."""


@dataclass(frozen=True, slots=True)
class ArtifactStorageResult:
    """Facts returned after content-addressed storage."""

    content_hash: ContentHash
    size_bytes: int
    storage_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.content_hash, ContentHash):
            raise ValueError("content_hash must be a ContentHash")
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
            raise ValueError("size_bytes must be an integer")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be greater than or equal to zero")
        if not isinstance(self.storage_ref, str) or not self.storage_ref.strip():
            raise ValueError("storage_ref must be a non-blank string")


@runtime_checkable
class ArtifactPort(Protocol):
    """Store and retrieve exact bytes by content identity."""

    def put(self, content: bytes) -> ArtifactStorageResult:
        """Store bytes idempotently and return their address and size."""

    def get(self, content_hash: ContentHash) -> bytes:
        """Return exact bytes or raise an explicit missing/integrity error."""

    def exists(self, content_hash: ContentHash) -> bool:
        """Check whether the content-addressed payload is present."""
