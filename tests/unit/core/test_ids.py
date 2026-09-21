from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from aeos.core.ids import (
    _AeosId,
    CausationId,
    CorrelationId,
    ExperimentId,
    IdempotencyKey,
    OrganizationId,
)


@pytest.mark.parametrize(
    "id_type", [OrganizationId, ExperimentId, CorrelationId, CausationId]
)
def test_ids_support_generation_and_reconstruction(
    id_type: type[_AeosId],
) -> None:
    generated = id_type.new()
    reconstructed = id_type.from_string(str(generated))
    assert generated == reconstructed
    assert hash(generated) == hash(reconstructed)
    assert str(generated) == generated.value


def test_different_id_types_are_not_equal() -> None:
    assert OrganizationId("same") != cast(object, ExperimentId("same"))


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_ids_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        OrganizationId(value)


def test_ids_are_immutable() -> None:
    identifier = OrganizationId("org-1")
    with pytest.raises(FrozenInstanceError):
        identifier.value = "org-2"  # type: ignore[misc]


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_idempotency_keys_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        IdempotencyKey(value)


def test_idempotency_keys_are_reconstructable_immutable_and_hashable() -> None:
    key = IdempotencyKey("operation-1")
    reconstructed = IdempotencyKey.from_string("operation-1")
    assert key == reconstructed
    assert hash(key) == hash(reconstructed)
    with pytest.raises(FrozenInstanceError):
        key.value = "operation-2"  # type: ignore[misc]
