from pathlib import Path
from aeos.core import ContentHash
from aeos.infrastructure.artifacts import LocalFilesystemArtifactAdapter
from aeos.knowledge.ports import ArtifactPort, ArtifactStorageResult
import pytest


def test_artifact_port_contract(
    tmp_path: Path,
) -> None:
    port: ArtifactPort = LocalFilesystemArtifactAdapter(tmp_path)
    content = b"AEOS"
    stored = port.put(content)

    assert stored.content_hash == ContentHash.from_bytes(content)
    assert stored.size_bytes == len(content)
    assert port.get(stored.content_hash) == content
    assert port.exists(stored.content_hash)


@pytest.mark.parametrize(
    ("content_hash", "size_bytes", "storage_ref"),
    [
        (object(), 1, "ref"),
        (ContentHash.from_bytes(b"x"), True, "ref"),
        (ContentHash.from_bytes(b"x"), -1, "ref"),
        (ContentHash.from_bytes(b"x"), 1, ""),
        (ContentHash.from_bytes(b"x"), 1, "   "),
    ],
)
def test_storage_result_validates_its_contract(
    content_hash: object, size_bytes: object, storage_ref: object
) -> None:
    with pytest.raises(ValueError):
        ArtifactStorageResult(content_hash, size_bytes, storage_ref)  # type: ignore[arg-type]
