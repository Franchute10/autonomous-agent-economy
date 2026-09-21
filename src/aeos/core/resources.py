"""Exact typed resource quantity value objects for the AEOS Shared Kernel."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from aeos.core.money import _decimal


class ResourceUnitMismatch(ValueError):
    """Raised when an operation combines quantities in different units."""


@dataclass(frozen=True, slots=True)
class ResourceUnit:
    """A canonical resource label with no conversion semantics."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValueError("resource unit must be a string")
        canonical = self.value.strip()
        if not canonical:
            raise ValueError("resource unit must be a non-blank string")
        object.__setattr__(self, "value", canonical)

    @classmethod
    def from_string(cls, value: str) -> Self:
        return cls(value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, init=False)
class ResourceQuantity:
    """An exact signed quantity paired with an explicit resource unit."""

    quantity: Decimal
    unit: ResourceUnit

    def __init__(self, quantity: Decimal | int | str, unit: ResourceUnit | str) -> None:
        object.__setattr__(self, "quantity", _decimal(quantity, "quantity"))
        if isinstance(unit, str):
            unit = ResourceUnit(unit)
        elif not isinstance(unit, ResourceUnit):
            raise ValueError("unit must be a ResourceUnit or string")
        object.__setattr__(self, "unit", unit)

    @classmethod
    def from_primitives(cls, quantity: Decimal | int | str, unit: str) -> Self:
        return cls(quantity, unit)

    def _check_unit(self, other: object) -> "ResourceQuantity":
        if not isinstance(other, ResourceQuantity):
            raise TypeError("ResourceQuantity operation requires another quantity")
        if self.unit != other.unit:
            raise ResourceUnitMismatch(f"cannot combine {self.unit} with {other.unit}")
        return other

    def __add__(self, other: object) -> "ResourceQuantity":
        value = self._check_unit(other)
        return ResourceQuantity(self.quantity + value.quantity, self.unit)

    def __sub__(self, other: object) -> "ResourceQuantity":
        value = self._check_unit(other)
        return ResourceQuantity(self.quantity - value.quantity, self.unit)

    def __neg__(self) -> "ResourceQuantity":
        return ResourceQuantity(-self.quantity, self.unit)

    def _compare(self, other: object) -> Decimal:
        value = self._check_unit(other)
        return self.quantity - value.quantity

    def __lt__(self, other: object) -> bool:
        return self._compare(other) < 0

    def __le__(self, other: object) -> bool:
        return self._compare(other) <= 0

    def __gt__(self, other: object) -> bool:
        return self._compare(other) > 0

    def __ge__(self, other: object) -> bool:
        return self._compare(other) >= 0
