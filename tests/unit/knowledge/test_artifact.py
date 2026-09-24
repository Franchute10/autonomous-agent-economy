from datetime import datetime, timezone

import pytest

from aeos.core import ArtifactId, ContentHash, OrganizationId
from aeos.knowledge.domain.artifact import Artifact
from aeos.knowledge.domain.errors import InvalidArtifact, InvalidMediaType


WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_artifact(**changes: object) -> Artifact:
    values: dict[str, object] = {
        "artifact_id": ArtifactId("artifact-1"),
        "organization_id": OrganizationId("org-1"),
        "content_hash": ContentHash.from_bytes(b"AEOS"),
        "media_type": "text/plain",
        "size_bytes": 4,
        "storage_ref": "sha256:address",
        "created_at": WHEN,
    }
    values.update(changes)
    return Artifact(**values)  # type: ignore[arg-type]


def test_artifact_preserves_typed_metadata_and_normalizes_utc() -> None:
    artifact = make_artifact(created_at=datetime(2026, 1, 1, 3, tzinfo=timezone.utc))

    assert artifact.artifact_id == ArtifactId("artifact-1")
    assert artifact.organization_id == OrganizationId("org-1")
    assert artifact.content_hash == ContentHash.from_bytes(b"AEOS")
    assert artifact.media_type == "text/plain"
    assert artifact.size_bytes == 4
    assert artifact.storage_ref == "sha256:address"
    assert artifact.created_at == datetime(2026, 1, 1, 3, tzinfo=timezone.utc)


@pytest.mark.parametrize("media_type", ["", "   "])
def test_artifact_rejects_blank_media_type(media_type: str) -> None:
    with pytest.raises(InvalidMediaType):
        make_artifact(media_type=media_type)


def test_artifact_rejects_negative_size_and_naive_timestamp() -> None:
    with pytest.raises(InvalidArtifact):
        make_artifact(size_bytes=-1)
    with pytest.raises(ValueError, match="timezone-aware"):
        make_artifact(created_at=datetime(2026, 1, 1))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("artifact_id", object()),
        ("organization_id", object()),
        ("content_hash", object()),
        ("size_bytes", "4"),
        ("size_bytes", True),
        ("storage_ref", ""),
        ("storage_ref", "   "),
        ("created_at", object()),
        ("logical_name", 42),
    ],
)
def test_artifact_rejects_invalid_field_types_or_values(
    field: str, value: object
) -> None:
    with pytest.raises((InvalidArtifact, ValueError)):
        make_artifact(**{field: value})


def test_artifact_accepts_zero_size_and_logical_names() -> None:
    zero = make_artifact(size_bytes=0, logical_name=None)
    named = make_artifact(logical_name="report.txt")

    assert zero.size_bytes == 0
    assert zero.logical_name is None
    assert named.logical_name == "report.txt"


def test_artifact_normalizes_aware_non_utc_timestamp() -> None:
    from datetime import timedelta, timezone as dt_timezone

    artifact = make_artifact(
        created_at=datetime(2026, 1, 1, 3, tzinfo=dt_timezone(timedelta(hours=3)))
    )

    assert artifact.created_at == WHEN


def test_artifact_is_immutable() -> None:
    artifact = make_artifact()
    with pytest.raises(AttributeError):
        artifact.media_type = "application/json"  # type: ignore[misc]
