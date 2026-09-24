from pathlib import Path

import pytest

from aeos.core import ContentHash
from aeos.infrastructure.artifacts import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    LocalFilesystemArtifactAdapter,
)
from aeos.knowledge.ports import ArtifactPort


def test_round_trip_empty_and_binary_content(tmp_path: Path) -> None:
    port = LocalFilesystemArtifactAdapter(tmp_path)
    empty = port.put(b"")
    binary = b"\x00\xff\x10AEOS\x80"

    assert empty.size_bytes == 0
    assert port.get(empty.content_hash) == b""
    binary_result = port.put(binary)
    assert port.get(binary_result.content_hash) == binary


def test_put_is_idempotent_and_filename_is_not_involved(tmp_path: Path) -> None:
    port = LocalFilesystemArtifactAdapter(tmp_path)

    first = port.put(b"same bytes")
    second = port.put(b"same bytes")

    assert first == second
    target = (
        tmp_path
        / "sha256"
        / first.content_hash.digest[:2]
        / first.content_hash.digest[2:4]
        / first.content_hash.digest
    )
    assert target.is_file()
    assert target.read_bytes() == b"same bytes"


def test_different_content_has_different_address(tmp_path: Path) -> None:
    port = LocalFilesystemArtifactAdapter(tmp_path)
    first = port.put(b"A")
    second = port.put(b"B")

    assert first.content_hash != second.content_hash
    assert first.storage_ref != second.storage_ref


def test_missing_and_corrupt_content_fail_explicitly(tmp_path: Path) -> None:
    port = LocalFilesystemArtifactAdapter(tmp_path)
    stored = port.put(b"original")
    target = (
        tmp_path
        / "sha256"
        / stored.content_hash.digest[:2]
        / stored.content_hash.digest[2:4]
        / stored.content_hash.digest
    )
    target.write_bytes(b"corrupt")

    with pytest.raises(ArtifactIntegrityError):
        port.get(stored.content_hash)
    with pytest.raises(ArtifactIntegrityError):
        port.exists(stored.content_hash)
    with pytest.raises(ArtifactNotFound):
        port.get(ContentHash.from_bytes(b"missing"))


def test_port_contract_does_not_require_metadata_repository(tmp_path: Path) -> None:
    port = LocalFilesystemArtifactAdapter(tmp_path)
    assert isinstance(port, ArtifactPort)


def test_missing_exists_is_false(tmp_path: Path) -> None:
    port = LocalFilesystemArtifactAdapter(tmp_path)
    assert not port.exists(ContentHash.from_bytes(b"missing"))


@pytest.mark.parametrize("method", ["get", "exists"])
def test_retrieval_requires_content_hash(tmp_path: Path, method: str) -> None:
    port = LocalFilesystemArtifactAdapter(tmp_path)
    with pytest.raises(TypeError):
        getattr(port, method)("sha256:" + "0" * 64)


def test_put_rejects_non_bytes(tmp_path: Path) -> None:
    port = LocalFilesystemArtifactAdapter(tmp_path)
    with pytest.raises(TypeError):
        port.put("text")  # type: ignore[arg-type]


def test_existing_corrupt_target_is_not_overwritten(tmp_path: Path) -> None:
    port = LocalFilesystemArtifactAdapter(tmp_path)
    content = b"original"
    stored = port.put(content)
    target = (
        tmp_path
        / "sha256"
        / stored.content_hash.digest[:2]
        / stored.content_hash.digest[2:4]
        / stored.content_hash.digest
    )
    target.write_bytes(b"corrupt")

    with pytest.raises(ArtifactIntegrityError):
        port.put(content)
    assert target.read_bytes() == b"corrupt"


def test_existing_file_root_is_rejected(tmp_path: Path) -> None:
    root_file = tmp_path / "not-a-directory"
    root_file.write_bytes(b"file")

    with pytest.raises(NotADirectoryError):
        LocalFilesystemArtifactAdapter(root_file)


def test_derived_path_is_below_configured_root(tmp_path: Path) -> None:
    port = LocalFilesystemArtifactAdapter(tmp_path)
    stored = port.put(b"safe")
    target = (
        tmp_path
        / "sha256"
        / stored.content_hash.digest[:2]
        / stored.content_hash.digest[2:4]
        / stored.content_hash.digest
    ).resolve()

    assert target.is_relative_to(tmp_path.resolve())
