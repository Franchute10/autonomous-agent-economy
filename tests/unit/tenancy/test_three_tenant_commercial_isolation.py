"""Synthetic commercial records remain scoped by the tenant application service."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from aeos.application.tenant_data import TenantCommercialDataService
from aeos.application.tenancy import RegisterOrganization, TenantContextResolver
from aeos.core import ActorKind, ActorRef, OrganizationId
from aeos.live.adapters.tenant_storage import LocalTenantDataRepository
from aeos.organization.domain import Organization
from aeos.tenancy.domain import TenantPrincipal
from aeos.tenancy.errors import TenantAccessDenied
from aeos.tenancy.ports import TenantDataCollection


TENANTS = (
    ("fictional_cleaning", "Sample Cleaning Company (Fictional)"),
    ("hz", "Sample HVAC Company (Fictional)"),
    ("fictional_builder", "Sample Builder Company (Fictional)"),
)


class _MemoryOrganizations:
    def __init__(self) -> None:
        self._organizations: dict[str, Organization] = {}

    def add(self, organization: Organization) -> None:
        self._organizations[organization.organization_id.value] = organization

    def get(self, organization_id: OrganizationId) -> Organization | None:
        return self._organizations.get(organization_id.value)

    def list_for_actor(self, actor: ActorRef) -> tuple[Organization, ...]:
        return tuple(
            organization
            for organization in self._organizations.values()
            if any(
                assignment.actor == actor
                for assignment in organization.assignments.values()
            )
        )


def test_three_named_tenants_keep_synthetic_commercial_records_separate(
    tmp_path: Path,
) -> None:
    as_of = datetime.now(timezone.utc)
    organizations = _MemoryOrganizations()
    principals = {
        key: TenantPrincipal(ActorRef(OrganizationId(f"actor-{key}"), ActorKind.HUMAN))
        for key, _ in TENANTS
    }
    organization_ids = {key: OrganizationId(f"org-{key}") for key, _ in TENANTS}
    record_ids = {key: f"synthetic-lead-{key}" for key, _ in TENANTS}

    register = RegisterOrganization(organizations)
    for key, name in TENANTS:
        register.execute(
            principals[key],
            name,
            at=as_of,
            organization_id=organization_ids[key],
        )

    service = TenantCommercialDataService(
        TenantContextResolver(organizations), LocalTenantDataRepository(tmp_path)
    )
    expected_records: dict[str, tuple[tuple[str, object], ...]] = {}
    for key, name in TENANTS:
        payload = {
            "record_type": "synthetic_lead",
            "business_name": name,
            "summary": f"Synthetic private opportunity for {name}.",
        }
        service.create(
            principals[key],
            organization_ids[key],
            TenantDataCollection.LEADS,
            record_ids[key],
            payload,
            at=as_of,
        )
        expected_records[key] = (
            (
                record_ids[key],
                {**payload, "organization_id": organization_ids[key].value},
            ),
        )

    for own_key, _ in TENANTS:
        assert (
            service.list(
                principals[own_key],
                organization_ids[own_key],
                TenantDataCollection.LEADS,
                at=as_of,
            )
            == expected_records[own_key]
        )
        for foreign_key, _ in TENANTS:
            if foreign_key == own_key:
                continue
            with pytest.raises(TenantAccessDenied):
                service.get(
                    principals[own_key],
                    organization_ids[foreign_key],
                    TenantDataCollection.LEADS,
                    record_ids[foreign_key],
                    at=as_of,
                )
            with pytest.raises(TenantAccessDenied):
                service.create(
                    principals[own_key],
                    organization_ids[foreign_key],
                    TenantDataCollection.LEADS,
                    "forged-cross-tenant-lead",
                    {"summary": "forged cross-tenant insert"},
                    at=as_of,
                )
            with pytest.raises(TenantAccessDenied):
                service.update(
                    principals[own_key],
                    organization_ids[foreign_key],
                    TenantDataCollection.LEADS,
                    record_ids[foreign_key],
                    {"summary": "forged cross-tenant update"},
                    at=as_of,
                )
            with pytest.raises(TenantAccessDenied):
                service.delete(
                    principals[own_key],
                    organization_ids[foreign_key],
                    TenantDataCollection.LEADS,
                    record_ids[foreign_key],
                    at=as_of,
                )

    for key, _ in TENANTS:
        assert (
            service.list(
                principals[key],
                organization_ids[key],
                TenantDataCollection.LEADS,
                at=as_of,
            )
            == expected_records[key]
        )
