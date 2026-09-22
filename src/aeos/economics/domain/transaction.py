"""Immutable balanced economic journal facts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Mapping, Sequence

from aeos.core import (
    EconomicTransactionId,
    OrganizationId,
    ResourceAccountId,
    ResourceId,
    ResourceQuantity,
    TraceContext,
    normalize_utc,
)
from aeos.economics.domain.account import ResourceAccount
from aeos.economics.domain.errors import (
    EmptyTransaction,
    MissingResourceAccountDefinition,
    MissingResourceDefinition,
    PostingUnitMismatch,
    UnbalancedEconomicTransaction,
)
from aeos.economics.domain.posting import LedgerPosting
from aeos.economics.domain.resource import Resource


class EconomicTransactionType(StrEnum):
    OPENING = "opening"
    ALLOCATE = "allocate"
    RESERVE = "reserve"
    RELEASE = "release"
    COMMIT = "commit"
    CONSUME = "consume"
    CREDIT = "credit"
    REFUND = "refund"
    ADJUST = "adjust"


@dataclass(frozen=True, slots=True)
class EconomicTransaction:
    """A complete, balanced, immutable economic fact."""

    economic_transaction_id: EconomicTransactionId
    organization_id: OrganizationId
    transaction_type: EconomicTransactionType
    occurred_at: datetime
    effective_at: datetime
    trace: TraceContext
    postings: tuple[LedgerPosting, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.economic_transaction_id, EconomicTransactionId):
            raise ValueError("economic_transaction_id must be an EconomicTransactionId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.transaction_type, EconomicTransactionType):
            raise ValueError("transaction_type must be an EconomicTransactionType")
        if not isinstance(self.trace, TraceContext):
            raise ValueError("trace must be a TraceContext")
        if not isinstance(self.occurred_at, datetime):
            raise ValueError("occurred_at must be a datetime")
        if not isinstance(self.effective_at, datetime):
            raise ValueError("effective_at must be a datetime")
        object.__setattr__(self, "occurred_at", normalize_utc(self.occurred_at))
        object.__setattr__(self, "effective_at", normalize_utc(self.effective_at))
        if not isinstance(self.postings, tuple):
            raise ValueError("postings must be a tuple of LedgerPosting values")
        postings = self.postings
        if len(postings) < 2:
            raise EmptyTransaction()
        if any(not isinstance(posting, LedgerPosting) for posting in postings):
            raise ValueError("postings must contain LedgerPosting values")
        object.__setattr__(self, "postings", postings)
        self._validate_balances()

    def _validate_balances(self) -> None:
        totals: dict[ResourceId, ResourceQuantity] = {}
        for posting in self.postings:
            posting.validate_against(self.organization_id)
            current = totals.get(posting.resource_id)
            if current is not None and current.unit != posting.quantity.unit:
                raise PostingUnitMismatch()
            totals[posting.resource_id] = (
                posting.quantity if current is None else current + posting.quantity
            )
        for resource_id, total in totals.items():
            if total.quantity != 0:
                raise UnbalancedEconomicTransaction(resource_id)

    @classmethod
    def from_definitions(
        cls,
        *,
        economic_transaction_id: EconomicTransactionId,
        organization_id: OrganizationId,
        transaction_type: EconomicTransactionType,
        occurred_at: datetime,
        effective_at: datetime,
        trace: TraceContext,
        postings: Sequence[LedgerPosting],
        resources: Mapping[ResourceId, Resource] | None = None,
        resource_accounts: Mapping[ResourceAccountId, ResourceAccount] | None = None,
    ) -> "EconomicTransaction":
        """Construct with caller-supplied definitions for local consistency checks."""
        for posting in postings:
            if not isinstance(posting, LedgerPosting):
                raise ValueError("postings must contain LedgerPosting values")
            resource = None
            resource_account = None
            if resources is not None:
                try:
                    resource = resources[posting.resource_id]
                except KeyError as error:
                    raise MissingResourceDefinition(posting.resource_id) from error
            if resource_accounts is not None:
                try:
                    resource_account = resource_accounts[posting.resource_account_id]
                except KeyError as error:
                    raise MissingResourceAccountDefinition(
                        posting.resource_account_id
                    ) from error
            posting.validate_against(
                organization_id,
                resource,
                resource_account,
            )
        return cls(
            economic_transaction_id,
            organization_id,
            transaction_type,
            occurred_at,
            effective_at,
            trace,
            tuple(postings),
        )
