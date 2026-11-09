"""Tenant-scoped repository contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from aeos.core.actors import ActorRef
from aeos.core.ids import OrganizationId
from aeos.live.domain.profile import BusinessProfile
from aeos.organization.domain.organization import Organization
from aeos.tenancy.domain import TenantContext


class TenantOrganizationRepository(Protocol):
    def add(self, organization: Organization) -> None: ...

    def get(self, organization_id: OrganizationId) -> Organization | None: ...

    def list_for_actor(self, actor: ActorRef) -> tuple[Organization, ...]: ...


class TenantBusinessProfileRepository(Protocol):
    def add(self, context: TenantContext, profile: BusinessProfile) -> None: ...

    def get(self, context: TenantContext) -> BusinessProfile | None: ...

    def update(self, context: TenantContext, profile: BusinessProfile) -> None: ...


class TenantDataCollection(StrEnum):
    PUBLIC_MARKET_SOURCES = "public_market_sources"
    MARKET_RESEARCH = "market_research"
    COMPETITORS = "competitors"
    PROSPECTS = "prospects"
    LEADS = "leads"
    OPPORTUNITY_INBOX = "opportunity_inbox"
    CONTACT_APPROVALS = "contact_approvals"
    QUOTE_APPROVALS = "quote_approvals"
    FOLLOW_UP_HISTORY = "follow_up_history"
    REPORTS = "reports"
    ASSESSMENTS = "assessments"
    BUSINESS_PROFILES = "business_profiles"


class TenantDataRepository(Protocol):
    def get(
        self, context: TenantContext, collection: TenantDataCollection, record_id: str
    ) -> object | None: ...

    def list(
        self, context: TenantContext, collection: TenantDataCollection
    ) -> tuple[tuple[str, object], ...]: ...

    def add(
        self,
        context: TenantContext,
        collection: TenantDataCollection,
        record_id: str,
        payload: object,
    ) -> None: ...

    def put(
        self,
        context: TenantContext,
        collection: TenantDataCollection,
        record_id: str,
        payload: object,
    ) -> None: ...

    def delete(
        self, context: TenantContext, collection: TenantDataCollection, record_id: str
    ) -> bool: ...


class TenantFileReferenceRepository(Protocol):
    def read_reference(
        self, context: TenantContext, collection: TenantDataCollection
    ) -> object | None: ...
