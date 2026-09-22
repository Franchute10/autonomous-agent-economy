"""Deterministic cryptographic identity for already-canonical bytes."""

from dataclasses import dataclass
import hashlib
import re
from typing import Self


_SHA256 = "sha256"
_SHA256_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ContentHash:
    """An immutable algorithm/digest pair; it does not canonicalize objects."""

    algorithm: str
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.algorithm, str) or not self.algorithm.strip():
            raise ValueError("hash algorithm must be a non-blank string")
        algorithm = self.algorithm.strip().casefold().replace("-", "")
        if algorithm != _SHA256:
            raise ValueError(f"unsupported hash algorithm: {self.algorithm}")
        if not isinstance(self.digest, str) or not self.digest.strip():
            raise ValueError("hash digest must be a non-blank string")
        digest = self.digest.strip().casefold()
        if not _SHA256_DIGEST.fullmatch(digest):
            raise ValueError("sha256 digest must be exactly 64 hexadecimal characters")
        object.__setattr__(self, "algorithm", algorithm)
        object.__setattr__(self, "digest", digest)

    @classmethod
    def from_bytes(cls, content: bytes) -> Self:
        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")
        return cls(_SHA256, hashlib.sha256(content).hexdigest())

    @classmethod
    def from_string(cls, value: str) -> Self:
        if not isinstance(value, str):
            raise ValueError("content hash must be a string")
        algorithm, separator, digest = value.partition(":")
        if not separator:
            raise ValueError("content hash must use 'algorithm:digest'")
        return cls(algorithm, digest)

    @property
    def canonical(self) -> str:
        return f"{self.algorithm}:{self.digest}"

    def __str__(self) -> str:
        return self.canonical


def hash_bytes(content: bytes) -> ContentHash:
    """Hash the exact supplied bytes with SHA-256."""
    return ContentHash.from_bytes(content)
