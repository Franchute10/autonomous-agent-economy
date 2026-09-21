from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from aeos.core import Currency, CurrencyMismatch, Money


def test_money_constructs_exactly_and_normalizes_currency() -> None:
    money = Money("0.10000000000000000001", " usd ")
    assert money.amount == Decimal("0.10000000000000000001")
    assert money.currency == Currency("USD")
    assert str(money.currency) == "USD"


@pytest.mark.parametrize("value", ["not-a-number", ""])
def test_invalid_money_amount_string_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        Money(value, "USD")


@pytest.mark.parametrize("value", [1.5, True])
def test_float_and_bool_money_amounts_are_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        Money(value, "USD")  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_amount_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        Money(value, "USD")


@pytest.mark.parametrize("value", ["", " ", "US", "USDX", "U$D"])
def test_invalid_currency_code_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        Currency(value)


def test_currency_rejects_non_string_input() -> None:
    with pytest.raises(ValueError):
        Currency(123)  # type: ignore[arg-type]


def test_currency_normalization_equality_and_hashing() -> None:
    normalized = Currency(" usd ")
    equivalent = Currency("USD")
    assert normalized.code == "USD"
    assert normalized == equivalent
    assert hash(normalized) == hash(equivalent)


def test_money_arithmetic_comparison_and_exactness() -> None:
    five = Money("5", "USD")
    three = Money("3", "USD")
    assert five + three == Money("8", "USD")
    assert five - three == Money("2", "USD")
    assert Money("0.1", "USD") + Money("0.2", "USD") == Money("0.3", "USD")
    assert Money("5", "USD") > three
    assert Money("5", "USD") >= three
    assert three < five
    assert three <= five


def test_money_supports_zero_signed_values_and_negation() -> None:
    assert Money("0", "USD") == Money(Decimal("0"), "USD")
    assert Money("-1.25", "USD") == Money(Decimal("-1.25"), "USD")
    assert -Money("1.25", "USD") == Money("-1.25", "USD")


def test_money_wrong_operand_types_raise_type_error() -> None:
    with pytest.raises(TypeError):
        Money("1", "USD") + 1
    with pytest.raises(TypeError):
        Money("1", "USD") < 1


@pytest.mark.parametrize("operation", [lambda a, b: a + b, lambda a, b: a - b])
def test_cross_currency_arithmetic_is_rejected(operation: object) -> None:
    with pytest.raises(CurrencyMismatch):
        operation(Money("5", "USD"), Money("3", "PEN"))  # type: ignore[operator]


def test_cross_currency_comparison_is_rejected() -> None:
    with pytest.raises(CurrencyMismatch):
        Money("5", "USD") < Money("3", "PEN")


def test_money_is_hashable_reconstructable_and_immutable() -> None:
    value = Money.from_primitives("5.000", "usd")
    assert value == Money(Decimal("5.000"), Currency("USD"))
    assert hash(value) == hash(Money("5.000", "USD"))
    with pytest.raises(FrozenInstanceError):
        value.amount = Decimal("6")  # type: ignore[misc]
