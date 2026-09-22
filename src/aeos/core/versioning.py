"""Exact references to published, versioned definitions."""

from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True, slots=True)
class VersionRef:
    """An immutable reference to one exact version of a named subject."""

    subject: str
    version: str

    def __post_init__(self) -> None:
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError("version subject must be a non-blank string")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version identifier must be a non-blank string")
        if self.version.strip().casefold() in {"latest", "current", "active"}:
            raise ValueError("VersionRef requires an exact version identifier")
        if ":" in self.version:
            raise ValueError("version identifier cannot contain ':'")
        object.__setattr__(self, "subject", self.subject.strip())
        object.__setattr__(self, "version", self.version.strip())

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Reconstruct a reference from ``subject:version``."""
        if not isinstance(value, str):
            raise ValueError("version reference must be a string")
        subject, separator, version = value.rpartition(":")
        if not separator:
            raise ValueError("version reference must use 'subject:version'")
        return cls(subject, version)

    @property
    def canonical(self) -> str:
        return f"{self.subject}:{self.version}"

    def __str__(self) -> str:
        return self.canonical
