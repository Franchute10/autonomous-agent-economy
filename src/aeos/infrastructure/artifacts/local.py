"""Small local content-addressed implementation of the ArtifactPort."""

from pathlib import Path
import os
import tempfile

from aeos.core import ContentHash
from aeos.knowledge.ports.artifacts import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    ArtifactPort,
    ArtifactStorageResult,
)


class LocalFilesystemArtifactAdapter(ArtifactPort):
    """Store payloads below a configured root using SHA-256 addresses."""

    def __init__(self, root: str | Path) -> None:
        configured_root = Path(root)
        if configured_root.exists() and not configured_root.is_dir():
            raise NotADirectoryError(f"artifact root is not a directory: {root}")
        self._root = configured_root.resolve()

    def put(self, content: bytes) -> ArtifactStorageResult:
        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")
        content_hash = ContentHash.from_bytes(content)
        target = self._path_for(content_hash)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            self._verify_file(target, content_hash)
        else:
            temporary_path: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb", dir=target.parent, prefix=".artifact-", delete=False
                ) as temporary:
                    temporary_path = temporary.name
                    temporary.write(content)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                try:
                    # On Windows, same-directory rename is atomic and refuses
                    # to replace an existing target. POSIX uses an exclusive
                    # hard link because rename would replace an existing file.
                    if os.name == "nt":
                        os.rename(temporary_path, target)
                    else:
                        os.link(temporary_path, target)
                except FileExistsError:
                    self._verify_file(target, content_hash)
            finally:
                if temporary_path is not None and os.path.exists(temporary_path):
                    os.unlink(temporary_path)

        return ArtifactStorageResult(
            content_hash, len(content), self._storage_ref(content_hash)
        )

    def get(self, content_hash: ContentHash) -> bytes:
        self._require_hash(content_hash)
        target = self._path_for(content_hash)
        if not target.is_file():
            raise ArtifactNotFound(str(content_hash))
        self._verify_file(target, content_hash)
        return target.read_bytes()

    def exists(self, content_hash: ContentHash) -> bool:
        self._require_hash(content_hash)
        target = self._path_for(content_hash)
        if not target.is_file():
            return False
        self._verify_file(target, content_hash)
        return True

    @staticmethod
    def _require_hash(value: ContentHash) -> None:
        if not isinstance(value, ContentHash):
            raise TypeError("content_hash must be a ContentHash")

    def _storage_ref(self, content_hash: ContentHash) -> str:
        return content_hash.canonical

    def _path_for(self, content_hash: ContentHash) -> Path:
        digest = content_hash.digest
        candidate = (
            self._root / content_hash.algorithm / digest[:2] / digest[2:4] / digest
        ).resolve()
        if not candidate.is_relative_to(self._root):
            raise ArtifactIntegrityError("derived artifact path escapes storage root")
        return candidate

    @staticmethod
    def _verify_file(path: Path, expected: ContentHash) -> None:
        actual = ContentHash.from_bytes(path.read_bytes())
        if actual != expected:
            raise ArtifactIntegrityError(f"content at {path} does not match {expected}")
