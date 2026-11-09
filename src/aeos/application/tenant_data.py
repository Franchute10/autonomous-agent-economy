"""Tenant-authorized operations over private LIVE commercial records."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime

from aeos.application.tenancy import TenantContextResolver
from aeos.core.ids import OrganizationId
from aeos.tenancy.domain import TenantContext, TenantPrincipal
from aeos.tenancy.errors import (
    TenantAccessDenied,
    TenantRecordAlreadyExists,
    TenantRecordNotFound,
)
from aeos.tenancy.ports import TenantDataCollection, TenantDataRepository


class TenantCommercialDataService:
    """Resolve membership afresh for each read or mutation.

    Repositories receive only a resolved context, and the context also checks
    that its membership is still active when a storage operation is performed.
    """

    def __init__(
        self,
        resolver: TenantContextResolver,
        repository: TenantDataRepository,
    ) -> None:
        self._resolver = resolver
        self._repository = repository

    def get(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        collection: TenantDataCollection,
        record_id: str,
        *,
        at: datetime | None = None,
    ) -> object:
        context = self._resolver.resolve(principal, organization_id, at=at)
        value = self._repository.get(context, collection, record_id)
        if value is None:
            raise TenantRecordNotFound()
        return value

    def list(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        collection: TenantDataCollection,
        *,
        at: datetime | None = None,
    ) -> tuple[tuple[str, object], ...]:
        context = self._resolver.resolve(principal, organization_id, at=at)
        return self._repository.list(context, collection)

    def create(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        collection: TenantDataCollection,
        record_id: str,
        payload: object,
        *,
        at: datetime | None = None,
    ) -> None:
        context = self._resolver.resolve(principal, organization_id, at=at)
        self._require_profile_admin(context, collection)
        owned = _attach_owner(payload, context.organization_id.value)
        try:
            self._repository.add(context, collection, record_id, owned)
        except FileExistsError as error:
            raise TenantRecordAlreadyExists() from error

    def update(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        collection: TenantDataCollection,
        record_id: str,
        payload: object,
        *,
        at: datetime | None = None,
    ) -> None:
        context = self._resolver.resolve(principal, organization_id, at=at)
        self._require_profile_admin(context, collection)
        if self._repository.get(context, collection, record_id) is None:
            raise TenantRecordNotFound()
        self._repository.put(
            context,
            collection,
            record_id,
            _attach_owner(payload, context.organization_id.value),
        )

    def delete(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        collection: TenantDataCollection,
        record_id: str,
        *,
        at: datetime | None = None,
    ) -> None:
        context = self._resolver.resolve(principal, organization_id, at=at)
        if not context.role.can_manage_profiles:
            raise TenantAccessDenied()
        if not self._repository.delete(context, collection, record_id):
            raise TenantRecordNotFound()

    def search(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        collection: TenantDataCollection,
        query: str,
        *,
        at: datetime | None = None,
    ) -> tuple[tuple[str, object], ...]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("search query must be non-blank")
        needle = query.casefold().strip()
        return tuple(
            (record_id, value)
            for record_id, value in self.list(
                principal, organization_id, collection, at=at
            )
            if any(needle in text.casefold() for text in _text_values(value))
        )

    def export(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        collection: TenantDataCollection,
        *,
        at: datetime | None = None,
    ) -> dict[str, object]:
        records = self.list(principal, organization_id, collection, at=at)
        return {
            "organization_id": organization_id.value,
            "collection": collection.value,
            "records": [
                {"record_id": record_id, "data": value} for record_id, value in records
            ],
        }

    def find_duplicates(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        collection: TenantDataCollection,
        candidate: object,
        *,
        at: datetime | None = None,
    ) -> tuple[str, ...]:
        """Match only against records visible in the selected tenant."""

        context = self._resolver.resolve(principal, organization_id, at=at)
        owned = _attach_owner(candidate, context.organization_id.value)
        signature = _canonical_json(owned)
        return tuple(
            record_id
            for record_id, value in self._repository.list(context, collection)
            if _canonical_json(value) == signature
        )

    def generate_report(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        source_collection: TenantDataCollection,
        report_id: str,
        build: Callable[[tuple[tuple[str, object], ...]], object],
        *,
        at: datetime | None = None,
    ) -> object:
        """Build and persist a report exclusively from this tenant's records."""

        source = self.list(principal, organization_id, source_collection, at=at)
        report = build(source)
        self.create(
            principal,
            organization_id,
            TenantDataCollection.REPORTS,
            report_id,
            report,
            at=at,
        )
        return _attach_owner(report, organization_id.value)

    @staticmethod
    def _require_profile_admin(
        context: TenantContext, collection: TenantDataCollection
    ) -> None:
        if (
            collection is TenantDataCollection.BUSINESS_PROFILES
            and not context.role.can_manage_profiles
        ):
            raise TenantAccessDenied()


def _attach_owner(value: object, organization_id: str) -> object:
    _validate_nested_owners(value, organization_id)
    if isinstance(value, Mapping):
        result: dict[str, object] = dict(value)
        result["organization_id"] = organization_id
        return result
    return value


def _validate_nested_owners(value: object, organization_id: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in {"organization_id", "owner_organization_id", "tenant_id"}:
                if item is not None and item != organization_id:
                    raise TenantAccessDenied()
            _validate_nested_owners(item, organization_id)
    elif isinstance(value, list | tuple):
        for item in value:
            _validate_nested_owners(item, organization_id)


def _text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(
            text
            for key, item in value.items()
            for text in (str(key), *_text_values(item))
        )
    if isinstance(value, list | tuple):
        return tuple(text for item in value for text in _text_values(item))
    if value is None or isinstance(value, bool | int | float):
        return ()
    return (str(value),)


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "tenant records used for duplicate checks must be JSON data"
        ) from error


__all__ = ["TenantCommercialDataService"]
