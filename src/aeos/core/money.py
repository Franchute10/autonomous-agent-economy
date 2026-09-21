"""Exact monetary value objects for the AEOS Shared Kernel."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Self


class CurrencyMismatch(ValueError):
    """Raised when an operation combines Money values in different currencies."""


_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class Currency:
    """A canonical, structural ISO-style currency code."""

    code: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str):
            raise ValueError("currency code must be a string")
        canonical = self.code.strip().upper()
        if not _CURRENCY_CODE.fullmatch(canonical):
            raise ValueError("currency code must be exactly three letters")
        object.__setattr__(self, "code", canonical)

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Construct a currency from its primitive string representation."""
        return cls(value)

    def __str__(self) -> str:
        return self.code


def _decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{field_name} must be a Decimal, int, or numeric string")
    if not isinstance(value, (Decimal, int, str)):
        raise ValueError(f"{field_name} must be a Decimal, int, or numeric string")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError(f"invalid {field_name}") from None
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return result


@dataclass(frozen=True, slots=True, init=False)
class Money:
    """An exact signed amount paired with an explicit currency."""

    amount: Decimal
    currency: Currency

    def __init__(self, amount: Decimal | int | str, currency: Currency | str) -> None:
        object.__setattr__(self, "amount", _decimal(amount, "amount"))
        if isinstance(currency, str):
            currency = Currency(currency)
        elif not isinstance(currency, Currency):
            raise ValueError("currency must be a Currency or string")
        object.__setattr__(self, "currency", currency)

    @classmethod
    def from_primitives(cls, amount: Decimal | int | str, currency: str) -> Self:
        return cls(amount, currency)

    def _check_currency(self, other: object) -> "Money":
        if not isinstance(other, Money):
            raise TypeError("Money operation requires another Money value")
        if self.currency != other.currency:
            raise CurrencyMismatch(
                f"cannot combine {self.currency} with {other.currency}"
            )
        return other

    def __add__(self, other: object) -> "Money":
        value = self._check_currency(other)
        return Money(self.amount + value.amount, self.currency)

    def __sub__(self, other: object) -> "Money":
        value = self._check_currency(other)
        return Money(self.amount - value.amount, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def _compare(self, other: object) -> Decimal:
        value = self._check_currency(other)
        return self.amount - value.amount

    def __lt__(self, other: object) -> bool:
        return self._compare(other) < 0

    def __le__(self, other: object) -> bool:
        return self._compare(other) <= 0

    def __gt__(self, other: object) -> bool:
        return self._compare(other) > 0

    def __ge__(self, other: object) -> bool:
        return self._compare(other) >= 0
