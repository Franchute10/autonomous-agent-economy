"""Immutable published policy versions."""

from dataclasses import dataclass
from datetime import datetime

from aeos.core import ContentHash, OrganizationId, PolicyVersionId, VersionRef
from aeos.core.time import UtcTimestamp, normalize_utc
from aeos.governance.domain.errors import InvalidPolicyKey


@dataclass(frozen=True, slots=True)
class PolicyVersion:
    """One exact, immutable policy definition; it has no evaluation behavior."""

    policy_version_id: PolicyVersionId
    organization_id: OrganizationId
    version_ref: VersionRef
    content_hash: ContentHash
    policy_key: str
    published_at: UtcTimestamp

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version_id, PolicyVersionId):
            raise ValueError("policy_version_id must be a PolicyVersionId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.version_ref, VersionRef):
            raise ValueError("version_ref must be a VersionRef")
        if not isinstance(self.content_hash, ContentHash):
            raise ValueError("content_hash must be a ContentHash")
        if not isinstance(self.policy_key, str) or not self.policy_key.strip():
            raise InvalidPolicyKey()
        if not isinstance(self.published_at, datetime):
            raise ValueError("published_at must be a datetime")
        object.__setattr__(self, "published_at", normalize_utc(self.published_at))
