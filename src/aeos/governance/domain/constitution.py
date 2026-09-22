"""Immutable published constitution versions."""

from dataclasses import dataclass
from datetime import datetime

from aeos.core import ContentHash, ConstitutionVersionId, OrganizationId, VersionRef
from aeos.core.time import UtcTimestamp, normalize_utc
from aeos.governance.domain.errors import InvalidConstitutionTitle


@dataclass(frozen=True, slots=True)
class ConstitutionVersion:
    """One exact, immutable constitutional baseline owned by an organization."""

    constitution_version_id: ConstitutionVersionId
    organization_id: OrganizationId
    version_ref: VersionRef
    content_hash: ContentHash
    title: str
    published_at: UtcTimestamp

    def __post_init__(self) -> None:
        if not isinstance(self.constitution_version_id, ConstitutionVersionId):
            raise ValueError("constitution_version_id must be a ConstitutionVersionId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.version_ref, VersionRef):
            raise ValueError("version_ref must be a VersionRef")
        if not isinstance(self.content_hash, ContentHash):
            raise ValueError("content_hash must be a ContentHash")
        if not isinstance(self.title, str) or not self.title.strip():
            raise InvalidConstitutionTitle()
        if not isinstance(self.published_at, datetime):
            raise ValueError("published_at must be a datetime")
        object.__setattr__(self, "published_at", normalize_utc(self.published_at))
