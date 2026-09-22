import hashlib

import pytest

from aeos.core import ContentHash, hash_bytes


def test_hash_bytes_uses_sha256_on_exact_bytes() -> None:
    content_hash = hash_bytes(b"aeos")
    assert content_hash.algorithm == "sha256"
    assert content_hash.digest == hashlib.sha256(b"aeos").hexdigest()
    assert content_hash == hash_bytes(b"aeos")
    assert content_hash != hash_bytes(b"AEOS")


@pytest.mark.parametrize("factory", [hash_bytes, ContentHash.from_bytes])
def test_hash_factories_reject_non_bytes(factory: object) -> None:
    with pytest.raises(TypeError):
        factory("content")  # type: ignore[operator]


def test_content_hash_is_reconstructable_and_canonical() -> None:
    value = hash_bytes(b"content")
    assert str(value) == f"sha256:{value.digest}"
    assert ContentHash.from_string(str(value)) == value
    assert ContentHash("SHA-256", value.digest.upper()) == value


def test_content_hash_from_string_requires_separator() -> None:
    with pytest.raises(ValueError):
        ContentHash.from_string("sha256" + "0" * 64)


@pytest.mark.parametrize(
    "value",
    [
        ("sha256", ""),
        ("sha256", "0" * 63),
        ("sha256", "g" * 64),
        ("md5", "0" * 32),
    ],
)
def test_content_hash_rejects_invalid_values(value: tuple[str, str]) -> None:
    with pytest.raises(ValueError):
        ContentHash(*value)


@pytest.mark.parametrize("value", ["sha256:", "sha256:0" * 63, "sha256:" + "g" * 64])
def test_content_hash_from_string_rejects_invalid_digests(value: str) -> None:
    with pytest.raises(ValueError):
        ContentHash.from_string(value)


def test_content_hash_is_immutable() -> None:
    content_hash = hash_bytes(b"content")
    with pytest.raises(AttributeError):
        content_hash.digest = "0" * 64  # type: ignore[misc]
