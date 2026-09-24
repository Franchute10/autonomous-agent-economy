"""Narrow errors for immutable artifact metadata validation."""

from aeos.core.errors import DomainError


class InvalidArtifact(DomainError):
    """Artifact metadata violates a domain invariant."""

    def __init__(self, message: str) -> None:
        super().__init__("knowledge.invalid_artifact", message)


class InvalidMediaType(InvalidArtifact):
    """The artifact media type is blank or otherwise invalid."""

    def __init__(self) -> None:
        super().__init__("media_type must be a non-blank string")


class InvalidArtifactStorageRef(InvalidArtifact):
    """The opaque storage reference is blank or invalid."""

    def __init__(self) -> None:
        super().__init__("storage_ref must be a non-blank string")


class InvalidAuditEvent(DomainError):
    """An audit event violates a local domain invariant."""

    def __init__(self, message: str) -> None:
        super().__init__("knowledge.invalid_audit_event", message)


class InvalidAuditSubject(InvalidAuditEvent):
    """An audit subject reference is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(f"invalid audit subject: {message}")


class InvalidEvidence(DomainError):
    """An evidence record violates a local domain invariant."""

    def __init__(self, message: str) -> None:
        super().__init__("knowledge.invalid_evidence", message)


class EvidenceWithoutSource(InvalidEvidence):
    """Evidence must name at least one explicit supporting source."""

    def __init__(self) -> None:
        super().__init__("evidence must have at least one support source")


class InvalidProvenanceLink(DomainError):
    """A provenance link violates a local domain invariant."""

    def __init__(self, message: str) -> None:
        super().__init__("knowledge.invalid_provenance_link", message)


class ProvenanceSelfReference(InvalidProvenanceLink):
    """A provenance link cannot point from a reference to itself."""

    def __init__(self) -> None:
        super().__init__("source and target must be different")
