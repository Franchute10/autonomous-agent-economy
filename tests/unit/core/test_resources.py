from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from aeos.core import ResourceQuantity, ResourceUnit, ResourceUnitMismatch


def test_resource_quantity_constructs_exactly_and_reconstructs() -> None:
    value = ResourceQuantity.from_primitives("100.0001", " input_tokens ")
    assert value.quantity == Decimal("100.0001")
    assert value.unit == ResourceUnit("input_tokens")
    assert value == ResourceQuantity(Decimal("100.0001"), "input_tokens")


@pytest.mark.parametrize("value", ["not-a-number", ""])
def test_invalid_quantity_string_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        ResourceQuantity(value, "input_tokens")


@pytest.mark.parametrize("value", [1.5, True])
def test_float_and_bool_quantity_values_are_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        ResourceQuantity(value, "input_tokens")  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_quantity_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        ResourceQuantity(value, "input_tokens")


@pytest.mark.parametrize("value", ["", " "])
def test_invalid_resource_unit_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        ResourceUnit(value)


def test_resource_unit_rejects_non_string_input() -> None:
    with pytest.raises(ValueError):
        ResourceUnit(123)  # type: ignore[arg-type]


def test_resource_unit_normalization_equality_and_hashing() -> None:
    normalized = ResourceUnit(" input_tokens ")
    equivalent = ResourceUnit("input_tokens")
    assert normalized.value == "input_tokens"
    assert normalized == equivalent
    assert hash(normalized) == hash(equivalent)


def test_resource_quantity_arithmetic_comparison_and_exactness() -> None:
    hundred = ResourceQuantity("100", "input_tokens")
    fifty = ResourceQuantity("50", "input_tokens")
    assert hundred + fifty == ResourceQuantity("150", "input_tokens")
    assert hundred - ResourceQuantity("25", "input_tokens") == ResourceQuantity(
        "75", "input_tokens"
    )
    assert ResourceQuantity("0.1", "requests") + ResourceQuantity(
        "0.2", "requests"
    ) == ResourceQuantity("0.3", "requests")
    assert fifty < hundred
    assert fifty <= hundred
    assert hundred > fifty
    assert hundred >= fifty


def test_resource_quantity_supports_zero_signed_values_and_negation() -> None:
    assert ResourceQuantity("0", "input_tokens") == ResourceQuantity(
        Decimal("0"), "input_tokens"
    )
    assert ResourceQuantity("-5", "input_tokens") == ResourceQuantity(
        Decimal("-5"), "input_tokens"
    )
    assert -ResourceQuantity("5", "input_tokens") == ResourceQuantity(
        "-5", "input_tokens"
    )


def test_resource_quantity_wrong_operand_types_raise_type_error() -> None:
    with pytest.raises(TypeError):
        ResourceQuantity("1", "requests") + 1
    with pytest.raises(TypeError):
        ResourceQuantity("1", "requests") < 1


@pytest.mark.parametrize("operation", [lambda a, b: a + b, lambda a, b: a - b])
def test_cross_unit_arithmetic_is_rejected(operation: object) -> None:
    with pytest.raises(ResourceUnitMismatch):
        operation(
            ResourceQuantity("100", "input_tokens"),
            ResourceQuantity("50", "output_tokens"),
        )  # type: ignore[operator]


def test_cross_unit_comparison_is_rejected() -> None:
    with pytest.raises(ResourceUnitMismatch):
        ResourceQuantity("100", "input_tokens") < ResourceQuantity(
            "50", "output_tokens"
        )


def test_resource_quantity_is_hashable_and_immutable() -> None:
    value = ResourceQuantity("100", "input_tokens")
    assert hash(value) == hash(ResourceQuantity(100, ResourceUnit("input_tokens")))
    with pytest.raises(FrozenInstanceError):
        value.quantity = Decimal("200")  # type: ignore[misc]
