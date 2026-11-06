"""Validation errors for LIVE opportunity-intelligence contracts."""

from aeos.core.errors import DomainError


class InvalidLiveContract(DomainError):
    """A LIVE contract violates a local invariant."""

    def __init__(self, message: str) -> None:
        super().__init__("live.invalid_contract", message)
