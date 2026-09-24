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
