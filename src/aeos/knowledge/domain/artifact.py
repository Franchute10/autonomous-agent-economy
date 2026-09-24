"""Immutable metadata describing one exact stored payload."""

from dataclasses import dataclass
from datetime import datetime

from aeos.core import ArtifactId, ContentHash, OrganizationId
from aeos.core.time import UtcTimestamp, normalize_utc
from aeos.knowledge.domain.errors import (
    InvalidArtifact,
    InvalidArtifactStorageRef,
    InvalidMediaType,
)


@dataclass(frozen=True, slots=True)
class Artifact:
    """An immutable record for bytes stored behind an :class:`ArtifactPort`.

    ``ArtifactId`` identifies this domain record; ``ContentHash`` identifies
    the exact payload and is deliberately not replaced by the artifact ID.
    """

    artifact_id: ArtifactId
    organization_id: OrganizationId
    content_hash: ContentHash
    media_type: str
    size_bytes: int
    storage_ref: str
    created_at: UtcTimestamp
    logical_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_id, ArtifactId):
            raise InvalidArtifact("artifact_id must be an ArtifactId")
        if not isinstance(self.organization_id, OrganizationId):
            raise InvalidArtifact("organization_id must be an OrganizationId")
        if not isinstance(self.content_hash, ContentHash):
            raise InvalidArtifact("content_hash must be a ContentHash")
        if not isinstance(self.media_type, str) or not self.media_type.strip():
            raise InvalidMediaType()
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
            raise InvalidArtifact("size_bytes must be an integer")
        if self.size_bytes < 0:
            raise InvalidArtifact("size_bytes must be greater than or equal to zero")
        if not isinstance(self.storage_ref, str) or not self.storage_ref.strip():
            raise InvalidArtifactStorageRef()
        if not isinstance(self.created_at, datetime):
            raise InvalidArtifact("created_at must be a datetime")
        object.__setattr__(self, "created_at", normalize_utc(self.created_at))
        if self.logical_name is not None and not isinstance(self.logical_name, str):
            raise InvalidArtifact("logical_name must be a string or None")
