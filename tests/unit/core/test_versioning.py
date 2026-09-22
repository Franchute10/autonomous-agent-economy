import pytest

from aeos.core import VersionRef


def test_version_ref_is_exact_and_reconstructable() -> None:
    reference = VersionRef("workflow:abc", "7")
    assert str(reference) == "workflow:abc:7"
    assert VersionRef.from_string(str(reference)) == reference
    assert hash(reference) == hash(VersionRef("workflow:abc", "7"))


def test_version_ref_parsing_rejects_missing_or_blank_parts() -> None:
    with pytest.raises(ValueError):
        VersionRef.from_string("workflow-7")
    with pytest.raises(ValueError):
        VersionRef.from_string(":7")
    with pytest.raises(ValueError):
        VersionRef.from_string("workflow:")


def test_version_ref_subject_colons_round_trip() -> None:
    reference = VersionRef("workflow:abc", "7")
    assert VersionRef.from_string(str(reference)) == reference


def test_version_ref_rejects_colon_in_direct_version() -> None:
    with pytest.raises(ValueError):
        VersionRef("workflow", "1:2")


def test_version_ref_equality_includes_subject_and_version() -> None:
    assert VersionRef("workflow:A", "1") != VersionRef("workflow:B", "1")
    assert VersionRef("workflow:A", "1") != VersionRef("workflow:A", "2")


@pytest.mark.parametrize(
    "subject, version", [("", "1"), ("   ", "1"), ("x", ""), ("x", " ")]
)
def test_version_ref_rejects_blank_parts(subject: str, version: str) -> None:
    with pytest.raises(ValueError):
        VersionRef(subject, version)


@pytest.mark.parametrize(
    "version", ["latest", "LATEST", " current ", "ACTIVE", " active "]
)
def test_version_ref_rejects_mutable_aliases(version: str) -> None:
    with pytest.raises(ValueError):
        VersionRef("workflow", version)


def test_version_ref_is_immutable() -> None:
    reference = VersionRef("workflow", "1")
    with pytest.raises(AttributeError):
        reference.version = "2"  # type: ignore[misc]
