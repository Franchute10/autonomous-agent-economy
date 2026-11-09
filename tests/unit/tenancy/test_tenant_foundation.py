from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
import json
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import create_engine

from aeos.application.live.profile_assessment import assess_business_profile
from aeos.application.live.opportunity_inbox import import_record
from aeos.application.tenant_data import TenantCommercialDataService
from aeos.application.tenancy import (
    GetBusinessProfile,
    ListOrganizationsForActor,
    RegisterBusinessProfile,
    RegisterOrganization,
    TenantContextResolver,
    UpdateBusinessProfile,
)
from aeos.core import ActorKind, ActorRef, OrganizationId, RoleAssignmentId, RoleId
from aeos.infrastructure.artifacts import LocalTenantArtifactStorage
from aeos.infrastructure.persistence import schema
from aeos.infrastructure.persistence.uow import SqlAlchemyUnitOfWork
from aeos.live.adapters.tenant_storage import (
    LocalTenantDataRepository,
    LocalTenantFileReferenceRepository,
)
from aeos.live.adapters.opportunity_inbox import ingest_thumbtack_event
from aeos.live.domain import (
    BusinessProfile,
    ProfileFieldStatus,
    Vertical,
    vertical_profile_for,
)
from aeos.live.domain.profile import parse_business_profile_document
from aeos.live.domain.opportunity_activation import PipelineRecord, PipelineStatus
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.ports import MarketDiscoveryResult
from aeos.organization.domain import Organization, Role, RoleAssignment
from aeos.tenancy.domain import TenantContext, TenantPrincipal, TenantRole
from aeos.tenancy.errors import (
    OrganizationAlreadyExists,
    TenantAccessDenied,
    TenantRecordNotFound,
)
from aeos.tenancy.ports import TenantDataCollection


ROOT = Path(__file__).parents[3]
AS_OF = datetime(2026, 11, 7, tzinfo=timezone.utc)


def _principal(value: str) -> TenantPrincipal:
    return TenantPrincipal(ActorRef(OrganizationId.from_string(value), ActorKind.HUMAN))


class _MemoryOrganizations:
    def __init__(self) -> None:
        self.values: dict[str, Organization] = {}

    def add(self, organization: Organization) -> None:
        self.values[organization.organization_id.value] = organization

    def get(self, organization_id: OrganizationId) -> Organization | None:
        return self.values.get(organization_id.value)

    def list_for_actor(self, actor: ActorRef) -> tuple[Organization, ...]:
        return tuple(
            organization
            for organization in self.values.values()
            if any(item.actor == actor for item in organization.assignments.values())
        )


class _MemoryProfiles:
    def __init__(self) -> None:
        self.values: dict[str, BusinessProfile] = {}

    def add(self, context: TenantContext, profile: BusinessProfile) -> None:
        self.values[context.organization_id.value] = profile

    def get(self, context: TenantContext) -> BusinessProfile | None:
        return self.values.get(context.organization_id.value)

    def update(self, context: TenantContext, profile: BusinessProfile) -> None:
        self.add(context, profile)


def _profile(path: str) -> BusinessProfile:
    return parse_business_profile_document(
        json.loads((ROOT / path).read_text(encoding="utf-8"))
    )


def _fixture_tenants() -> tuple[
    _MemoryOrganizations,
    _MemoryProfiles,
    TenantPrincipal,
    TenantPrincipal,
    Organization,
    Organization,
    BusinessProfile,
    BusinessProfile,
]:
    organizations = _MemoryOrganizations()
    profiles = _MemoryProfiles()
    fictional_cleaning_owner = _principal("test-actor-fictional_cleaning")
    hz_owner = _principal("test-actor-hvac")
    register_organization = RegisterOrganization(organizations)
    fictional_cleaning = register_organization.execute(
        fictional_cleaning_owner,
        "Sample Cleaning Company (Fictional)",
        at=AS_OF,
        organization_id=OrganizationId.from_string("org-fixture-cleaning"),
    )
    hz = register_organization.execute(
        hz_owner,
        "Sample HVAC Company (Fictional)",
        at=AS_OF,
        organization_id=OrganizationId.from_string("org-fixture-hvac"),
    )
    resolver = TenantContextResolver(organizations)
    register_profile = RegisterBusinessProfile(resolver, profiles)
    fictional_cleaning_profile = register_profile.execute(
        fictional_cleaning_owner,
        fictional_cleaning.organization_id,
        _profile("examples/live/business_profiles/fictional_cleaning_company.json"),
        at=AS_OF,
    )
    hz_profile = register_profile.execute(
        hz_owner,
        hz.organization_id,
        _profile("examples/live/business_profiles/fictional_hvac_company.json"),
        at=AS_OF,
    )
    return (
        organizations,
        profiles,
        fictional_cleaning_owner,
        hz_owner,
        fictional_cleaning,
        hz,
        fictional_cleaning_profile,
        hz_profile,
    )


def test_two_initial_businesses_register_and_use_the_same_assessment_engine() -> None:
    (
        organizations,
        profiles,
        fictional_cleaning_owner,
        hz_owner,
        fictional_cleaning,
        hz,
        clean,
        hvac,
    ) = _fixture_tenants()
    resolver = TenantContextResolver(organizations)
    get_profile = GetBusinessProfile(resolver, profiles)

    assert fictional_cleaning.organization_id != hz.organization_id
    assert (
        get_profile.execute(
            fictional_cleaning_owner, fictional_cleaning.organization_id, at=AS_OF
        )
        == clean
    )
    assert get_profile.execute(hz_owner, hz.organization_id, at=AS_OF) == hvac
    assert clean.organization_id == fictional_cleaning.organization_id
    assert hvac.organization_id == hz.organization_id
    assert clean.vertical == Vertical.HOUSE_CLEANING.value
    assert hvac.vertical == Vertical.HVAC.value
    assert clean.owner_confirmed_service_areas is not None
    assert {"Sample City One", "Sample City Two"} <= set(
        clean.owner_confirmed_service_areas
    )
    assert (
        clean.primary_services
        == _profile(
            "examples/live/business_profiles/fictional_cleaning_company.json"
        ).primary_services
    )
    assert (clean.base_capacity_jobs_per_day, clean.expanded_capacity_jobs_per_day) == (
        3,
        4,
    )

    discovery = MarketDiscoveryResult((), (), ("No tenant-specific sample loaded.",))
    clean_assessment = assess_business_profile(clean, discovery)
    hvac_assessment = assess_business_profile(hvac, discovery)
    assert clean_assessment.business.industry == Vertical.HOUSE_CLEANING.value
    assert hvac_assessment.business.industry == Vertical.HVAC.value
    assert vertical_profile_for(clean_assessment.business.industry) is not None
    assert vertical_profile_for(hvac_assessment.business.industry) is not None

    assert hvac.business_model.value == "UNKNOWN"
    assert hvac.field_statuses["primary_services"] is ProfileFieldStatus.UNKNOWN
    assert (
        hvac.field_statuses["owner_confirmed_service_areas"]
        is ProfileFieldStatus.UNKNOWN
    )
    assert hvac.field_statuses["website_url"] is ProfileFieldStatus.NOT_PROVIDED
    assert hvac.primary_services == ()
    assert hvac.additional_service_areas is None
    assert hvac.approximate_employees is None
    assert hvac.subcontractor_count is None
    assert hvac.licenses is None
    assert hvac.insurance is None
    assert hvac.technical_certifications is None
    assert all(item.kind.value == "REPORTED" for item in hvac.reported_evidence())


def test_synthetic_tenant_manifest_and_inferred_evidence() -> None:
    profile_path = "examples/live/business_profiles/fictional_hvac_company.json"
    profile = _profile(profile_path)
    assert profile.business_name == "Sample HVAC Company (Fictional)"

    manifest_path = "examples/live/tenants/fictional_hvac_company.json"
    manifest = json.loads((ROOT / manifest_path).read_text(encoding="utf-8"))
    assert manifest["ownership"] == "synthetic_example"
    assert manifest["organization_name"] == profile.business_name
    assert (
        manifest["profile_file"] == "../business_profiles/fictional_hvac_company.json"
    )

    organizations = _MemoryOrganizations()
    organization_id = OrganizationId.from_string(manifest["organization_id"])
    principal = _principal("fictional-hvac-profile-reader")
    organization = RegisterOrganization(organizations).execute(
        principal,
        manifest["organization_name"],
        at=AS_OF,
        organization_id=organization_id,
    )
    context = TenantContextResolver(organizations).resolve(
        principal, organization.organization_id, at=AS_OF
    )
    references = LocalTenantFileReferenceRepository.from_manifest_files(
        ROOT,
        {organization_id: manifest_path},
    )
    referenced_profile = references.read_profile(context)
    assert isinstance(referenced_profile, dict)
    assert referenced_profile["business_name"] == profile.business_name
    assert referenced_profile["organization_id"] == organization_id.value

    inferred_payload = profile.to_dict()
    inferred_payload["business_model"] = "B2C"
    inferred_statuses = cast(dict[str, str], inferred_payload["field_statuses"])
    inferred_statuses["business_model"] = "INFERRED"
    inferred_evidence = {
        "evidence_id": "synthetic-business-model-inference",
        "kind": "INFERRED",
        "subject": profile.business_name,
        "field": "business_model",
        "value": "B2C",
        "source_name": "Synthetic inference test",
        "source_url": "https://fixture.example/profile",
        "retrieved_at": "2026-11-07T00:00:00+00:00",
        "excerpt": "Synthetic test evidence only.",
        "confidence": 0.5,
        "assumptions": ["The example is used only to exercise INFERRED status."],
        "owner_entity_id": None,
    }
    inferred_field_evidence = cast(
        list[dict[str, object]], inferred_payload["field_evidence"]
    )
    inferred_field_evidence.append(inferred_evidence)
    inferred_profile = BusinessProfile.from_dict(inferred_payload)
    assert (
        inferred_profile.field_statuses["business_model"] is ProfileFieldStatus.INFERRED
    )
    inferred_payload["field_evidence"] = [
        item for item in inferred_field_evidence if item["field"] != "business_model"
    ]
    with pytest.raises(InvalidLiveContract, match="matching INFERRED field evidence"):
        BusinessProfile.from_dict(inferred_payload)


def test_private_artifacts_are_isolated_by_tenant(tmp_path: Path) -> None:
    organizations, _, fictional_cleaning_owner, hz_owner, fictional_cleaning, hz, *_ = (
        _fixture_tenants()
    )
    resolver = TenantContextResolver(organizations)
    fictional_cleaning_context = resolver.resolve(
        fictional_cleaning_owner, fictional_cleaning.organization_id, at=AS_OF
    )
    hz_context = resolver.resolve(hz_owner, hz.organization_id, at=AS_OF)
    storage = LocalTenantArtifactStorage(tmp_path / "artifacts")

    stored = storage.put(
        fictional_cleaning_context, b"private Sample Cleaning Company assessment"
    )

    assert stored.organization_id == fictional_cleaning.organization_id
    assert storage.exists(fictional_cleaning_context, stored.content_hash)
    assert storage.get(fictional_cleaning_context, stored.content_hash) == (
        b"private Sample Cleaning Company assessment"
    )
    assert not storage.exists(hz_context, stored.content_hash)
    with pytest.raises(FileNotFoundError):
        storage.get(hz_context, stored.content_hash)


def test_tenant_membership_scopes_profiles_opportunities_and_reports(
    tmp_path: Path,
) -> None:
    (
        organizations,
        profiles,
        fictional_cleaning_owner,
        hz_owner,
        fictional_cleaning,
        hz,
        clean,
        hvac,
    ) = _fixture_tenants()
    resolver = TenantContextResolver(organizations)
    get_profile = GetBusinessProfile(resolver, profiles)
    with pytest.raises(TenantAccessDenied):
        get_profile.execute(fictional_cleaning_owner, hz.organization_id, at=AS_OF)
    with pytest.raises(TenantAccessDenied):
        get_profile.execute(hz_owner, fictional_cleaning.organization_id, at=AS_OF)
    before_profiles = dict(profiles.values)
    with pytest.raises(TenantAccessDenied):
        UpdateBusinessProfile(resolver, profiles).execute(
            fictional_cleaning_owner, hz.organization_id, hvac, at=AS_OF
        )
    assert profiles.values == before_profiles

    listed = ListOrganizationsForActor(organizations)
    assert [
        item.organization_id
        for item in listed.execute(fictional_cleaning_owner, at=AS_OF)
    ] == [fictional_cleaning.organization_id]

    member = _principal("test-actor-fictional-cleaning-member")
    member_role = Role(
        RoleId.new(), fictional_cleaning.organization_id, TenantRole.MEMBER.value
    )
    fictional_cleaning.add_role(member_role)
    fictional_cleaning.add_assignment(
        RoleAssignment(
            RoleAssignmentId.new(),
            fictional_cleaning.organization_id,
            member_role.role_id,
            member.actor,
            AS_OF,
        )
    )
    with pytest.raises(TenantAccessDenied):
        RegisterBusinessProfile(
            resolver,
            profiles,
        ).execute(member, fictional_cleaning.organization_id, clean, at=AS_OF)
    with pytest.raises(TenantAccessDenied):
        UpdateBusinessProfile(
            resolver,
            profiles,
        ).execute(member, fictional_cleaning.organization_id, clean, at=AS_OF)
    with pytest.raises(TenantAccessDenied):
        RegisterBusinessProfile(
            resolver,
            profiles,
        ).execute(
            _principal("unassigned-actor"),
            fictional_cleaning.organization_id,
            clean,
            at=AS_OF,
        )

    context_a = resolver.resolve(
        fictional_cleaning_owner, fictional_cleaning.organization_id, at=AS_OF
    )
    context_b = resolver.resolve(hz_owner, hz.organization_id, at=AS_OF)
    references = LocalTenantFileReferenceRepository.from_manifest_files(
        ROOT,
        {
            fictional_cleaning.organization_id: "examples/live/tenants/fictional_cleaning_company.json",
            hz.organization_id: "examples/live/tenants/fictional_hvac_company.json",
        },
    )
    fictional_cleaning_profile_reference = references.read_profile(context_a)
    hz_profile_reference = references.read_profile(context_b)
    assert isinstance(fictional_cleaning_profile_reference, dict)
    assert fictional_cleaning_profile_reference["business_name"] == clean.business_name
    assert (
        fictional_cleaning_profile_reference["organization_id"]
        == fictional_cleaning.organization_id.value
    )
    assert isinstance(hz_profile_reference, dict)
    assert hz_profile_reference["business_name"] == hvac.business_name
    assert hz_profile_reference["organization_id"] == hz.organization_id.value
    assert references.read_reference(
        context_a, TenantDataCollection.MARKET_RESEARCH
    ) == {
        "organization_id": fictional_cleaning.organization_id.value,
        "data": json.loads(
            (
                ROOT / "examples/live/market_research/fictional_cleaning_markets.json"
            ).read_text(encoding="utf-8")
        ),
    }
    assert (
        references.read_reference(context_b, TenantDataCollection.MARKET_RESEARCH)
        is None
    )
    assert references.read_reference(context_a, TenantDataCollection.PROSPECTS) == {
        "organization_id": fictional_cleaning.organization_id.value,
        "data": json.loads(
            (
                ROOT
                / "examples/live/opportunity_activation/fictional_cleaning_prospects.json"
            ).read_text(encoding="utf-8")
        ),
    }

    store = LocalTenantDataRepository(tmp_path)
    store.put(
        context_a,
        TenantDataCollection.OPPORTUNITY_INBOX,
        "fictional-cleaning-opportunity-1",
        {"title": "Tenant A opportunity"},
    )
    store.put(
        context_a,
        TenantDataCollection.REPORTS,
        "fictional-cleaning-report-1",
        {"business": "Sample Cleaning Company (Fictional)"},
    )
    assert (
        store.get(
            context_b,
            TenantDataCollection.OPPORTUNITY_INBOX,
            "fictional-cleaning-opportunity-1",
        )
        is None
    )
    assert store.list(context_b, TenantDataCollection.REPORTS) == ()
    assert store.opportunity_inbox(context_b).list_records() == ()
    assert store._collection_path(
        context_a, TenantDataCollection.OPPORTUNITY_INBOX
    ) != store._collection_path(context_b, TenantDataCollection.OPPORTUNITY_INBOX)
    with pytest.raises(InvalidLiveContract, match="organization_id"):
        store.put(
            context_b,
            TenantDataCollection.REPORTS,
            "forged-report",
            {"organization_id": fictional_cleaning.organization_id.value},
        )


def test_third_company_registers_without_company_specific_application_code() -> None:
    organizations = _MemoryOrganizations()
    profiles = _MemoryProfiles()
    owner = _principal("test-actor-third-company")
    organization = RegisterOrganization(organizations).execute(
        owner, "Sample Roofing Company (Fictional)", at=AS_OF
    )
    template = json.loads(
        (ROOT / "examples/live/business_profiles/template.json").read_text(
            encoding="utf-8"
        )
    )
    template.update(
        {
            "business_name": "Sample Roofing Company (Fictional)",
            "legal_name": "Sample Roofing Company LLC (Fictional)",
            "industry": "Roofing services",
            "vertical": Vertical.ROOFING.value,
            "description": "Fictional test company.",
            "business_model": "B2B",
            "city": "Sample City Nine",
            "primary_services": ["Roof replacement"],
            "target_customer_segments": ["Property managers"],
            "is_fictional_example": True,
        }
    )
    profile = BusinessProfile.from_dict(template)
    RegisterBusinessProfile(
        TenantContextResolver(organizations),
        profiles,
    ).execute(owner, organization.organization_id, profile, at=AS_OF)
    assert (
        GetBusinessProfile(
            TenantContextResolver(organizations),
            profiles,
        )
        .execute(owner, organization.organization_id, at=AS_OF)
        .vertical
        == "ROOFING"
    )


def test_tenant_manifest_cannot_claim_an_existing_organization_id() -> None:
    organizations = _MemoryOrganizations()
    actor = _principal("test-actor-stable-id")
    register = RegisterOrganization(organizations)
    organization_id = OrganizationId.from_string("configured-tenant-id")
    register.execute(
        actor,
        "Configured Tenant",
        at=AS_OF,
        organization_id=organization_id,
    )
    with pytest.raises(OrganizationAlreadyExists):
        register.execute(
            actor,
            "Another Organization",
            at=AS_OF,
            organization_id=organization_id,
        )


def test_tenant_manifests_cannot_alias_another_private_profile_file(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text('{"business_name": "Tenant A"}', encoding="utf-8")
    manifest_a = tmp_path / "tenant-a.json"
    manifest_b = tmp_path / "tenant-b.json"
    organization_a = OrganizationId.from_string("manifest-tenant-a")
    organization_b = OrganizationId.from_string("manifest-tenant-b")
    manifest_template = {
        "schema_version": 1,
        "organization_name": "Tenant",
        "profile_file": "profile.json",
        "shared_data_files": {},
    }
    manifest_a.write_text(
        json.dumps({**manifest_template, "organization_id": organization_a.value}),
        encoding="utf-8",
    )
    manifest_b.write_text(
        json.dumps({**manifest_template, "organization_id": organization_b.value}),
        encoding="utf-8",
    )

    with pytest.raises(InvalidLiveContract, match="cannot be shared"):
        LocalTenantFileReferenceRepository.from_manifest_files(
            tmp_path,
            {organization_a: "tenant-a.json", organization_b: "tenant-b.json"},
        )


def test_public_market_source_reference_can_be_reused_explicitly(
    tmp_path: Path,
) -> None:
    source = tmp_path / "public-source.json"
    source.write_text('{"source": "public"}', encoding="utf-8")
    organization_a = OrganizationId.from_string("public-tenant-a")
    organization_b = OrganizationId.from_string("public-tenant-b")

    LocalTenantFileReferenceRepository(
        tmp_path,
        {
            organization_a: {
                TenantDataCollection.PUBLIC_MARKET_SOURCES: source,
            },
            organization_b: {
                TenantDataCollection.PUBLIC_MARKET_SOURCES: source,
            },
        },
    )

    with pytest.raises(InvalidLiveContract, match="private tenant data"):
        LocalTenantFileReferenceRepository(
            tmp_path,
            {
                organization_a: {
                    TenantDataCollection.PUBLIC_MARKET_SOURCES: source,
                },
                organization_b: {
                    TenantDataCollection.MARKET_RESEARCH: source,
                },
            },
        )


def test_observed_profile_fact_requires_retrieved_source_evidence() -> None:
    payload = json.loads(
        (
            ROOT / "examples/live/business_profiles/fictional_hvac_company.json"
        ).read_text(encoding="utf-8")
    )
    payload["field_statuses"]["address"] = "OBSERVED"
    address_evidence = next(
        item for item in payload["field_evidence"] if item["field"] == "address"
    )
    address_evidence["kind"] = "OBSERVED"

    with pytest.raises(InvalidLiveContract, match="retrieval time"):
        BusinessProfile.from_dict(payload)


def test_sqlalchemy_profile_repository_round_trips_with_tenant_scope() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    schema.metadata.create_all(engine)
    actor = _principal("sqlite-test-actor")
    profile = _profile("examples/live/business_profiles/fictional_hvac_company.json")
    organizations = _MemoryOrganizations()
    organization = RegisterOrganization(organizations).execute(
        actor, "Sample HVAC Company (Fictional)", at=AS_OF
    )
    context = TenantContextResolver(organizations).resolve(
        actor, organization.organization_id, at=AS_OF
    )

    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.organizations.add(organization)
        uow.business_profiles.add(
            context, replace(profile, organization_id=organization.organization_id)
        )
        uow.commit()

    with SqlAlchemyUnitOfWork(engine) as uow:
        loaded = uow.business_profiles.get(context)
        assert loaded is not None
        assert loaded.field_statuses == profile.field_statuses
        assert [item.kind.value for item in loaded.reported_evidence()] == [
            item.kind.value for item in profile.reported_evidence()
        ]
        uow.commit()


def test_tenant_commercial_service_isolates_records_search_and_exports(
    tmp_path: Path,
) -> None:
    (
        organizations,
        _profiles,
        fictional_cleaning_owner,
        hz_owner,
        fictional_cleaning,
        hz,
        _clean,
        _hvac,
    ) = _fixture_tenants()
    resolver = TenantContextResolver(organizations)
    repository = LocalTenantDataRepository(tmp_path)
    service = TenantCommercialDataService(resolver, repository)
    candidate = {"title": "Private Sample City Nine opportunity", "status": "NEW"}
    service.create(
        fictional_cleaning_owner,
        fictional_cleaning.organization_id,
        TenantDataCollection.OPPORTUNITY_INBOX,
        "fictional-cleaning-private-opportunity",
        {"title": "Sample Cleaning Company private opportunity", "status": "NEW"},
        at=AS_OF,
    )
    service.create(
        hz_owner,
        hz.organization_id,
        TenantDataCollection.OPPORTUNITY_INBOX,
        "hz-private-opportunity",
        candidate,
        at=AS_OF,
    )
    service.create(
        fictional_cleaning_owner,
        fictional_cleaning.organization_id,
        TenantDataCollection.FOLLOW_UP_HISTORY,
        "fictional-cleaning-follow-up",
        {"note": "Sample Cleaning Company follow-up"},
        at=AS_OF,
    )
    service.create(
        hz_owner,
        hz.organization_id,
        TenantDataCollection.FOLLOW_UP_HISTORY,
        "hz-follow-up",
        {"note": "HZ private follow-up"},
        at=AS_OF,
    )
    service.create(
        fictional_cleaning_owner,
        fictional_cleaning.organization_id,
        TenantDataCollection.REPORTS,
        "fictional-cleaning-report",
        {"summary": "Sample Cleaning Company report"},
        at=AS_OF,
    )
    service.create(
        hz_owner,
        hz.organization_id,
        TenantDataCollection.REPORTS,
        "hz-report",
        {"summary": "HZ private report"},
        at=AS_OF,
    )

    assert [
        record_id
        for record_id, _ in service.list(
            fictional_cleaning_owner,
            fictional_cleaning.organization_id,
            TenantDataCollection.OPPORTUNITY_INBOX,
            at=AS_OF,
        )
    ] == ["fictional-cleaning-private-opportunity"]
    assert (
        service.search(
            fictional_cleaning_owner,
            fictional_cleaning.organization_id,
            TenantDataCollection.FOLLOW_UP_HISTORY,
            "HZ private",
            at=AS_OF,
        )
        == ()
    )
    assert service.export(
        fictional_cleaning_owner,
        fictional_cleaning.organization_id,
        TenantDataCollection.REPORTS,
        at=AS_OF,
    ) == {
        "organization_id": fictional_cleaning.organization_id.value,
        "collection": "reports",
        "records": [
            {
                "record_id": "fictional-cleaning-report",
                "data": {
                    "summary": "Sample Cleaning Company report",
                    "organization_id": fictional_cleaning.organization_id.value,
                },
            }
        ],
    }
    service.update(
        fictional_cleaning_owner,
        fictional_cleaning.organization_id,
        TenantDataCollection.REPORTS,
        "fictional-cleaning-report",
        {"summary": "Sample Cleaning Company updated report"},
        at=AS_OF,
    )
    assert service.get(
        fictional_cleaning_owner,
        fictional_cleaning.organization_id,
        TenantDataCollection.REPORTS,
        "fictional-cleaning-report",
        at=AS_OF,
    ) == {
        "summary": "Sample Cleaning Company updated report",
        "organization_id": fictional_cleaning.organization_id.value,
    }
    report = service.generate_report(
        fictional_cleaning_owner,
        fictional_cleaning.organization_id,
        TenantDataCollection.ASSESSMENTS,
        "fictional-cleaning-generated-report",
        lambda records: {"assessment_count": len(records)},
        at=AS_OF,
    )
    assert report == {
        "assessment_count": 0,
        "organization_id": fictional_cleaning.organization_id.value,
    }
    assert (
        service.find_duplicates(
            fictional_cleaning_owner,
            fictional_cleaning.organization_id,
            TenantDataCollection.OPPORTUNITY_INBOX,
            candidate,
            at=AS_OF,
        )
        == ()
    )
    assert service.find_duplicates(
        hz_owner,
        hz.organization_id,
        TenantDataCollection.OPPORTUNITY_INBOX,
        candidate,
        at=AS_OF,
    ) == ("hz-private-opportunity",)


def test_generic_business_profile_crud_requires_profile_admin_and_membership(
    tmp_path: Path,
) -> None:
    (
        organizations,
        _profiles,
        cleaning_owner,
        hvac_owner,
        cleaning,
        hvac,
        _clean_profile,
        _hvac_profile,
    ) = _fixture_tenants()
    fictional_cleaning_owner = cleaning_owner
    hz = hvac
    fictional_cleaning = cleaning
    admin = _principal("test-actor-cleaning-admin")
    member = _principal("test-actor-cleaning-member")
    for principal, role_name in (
        (admin, TenantRole.ADMIN.value),
        (member, TenantRole.MEMBER.value),
    ):
        role = Role(RoleId.new(), cleaning.organization_id, role_name)
        cleaning.add_role(role)
        cleaning.add_assignment(
            RoleAssignment(
                RoleAssignmentId.new(),
                cleaning.organization_id,
                role.role_id,
                principal.actor,
                AS_OF,
            )
        )

    service = TenantCommercialDataService(
        TenantContextResolver(organizations), LocalTenantDataRepository(tmp_path)
    )
    service.create(
        cleaning_owner,
        cleaning.organization_id,
        TenantDataCollection.BUSINESS_PROFILES,
        "primary-profile",
        {"revision": 1},
        at=AS_OF,
    )
    service.create(
        hvac_owner,
        hvac.organization_id,
        TenantDataCollection.BUSINESS_PROFILES,
        "hvac-profile",
        {"revision": 1},
        at=AS_OF,
    )
    service.update(
        admin,
        cleaning.organization_id,
        TenantDataCollection.BUSINESS_PROFILES,
        "primary-profile",
        {"revision": 2},
        at=AS_OF,
    )
    service.create(
        admin,
        cleaning.organization_id,
        TenantDataCollection.BUSINESS_PROFILES,
        "admin-created-profile",
        {"revision": 1},
        at=AS_OF,
    )
    service.delete(
        admin,
        cleaning.organization_id,
        TenantDataCollection.BUSINESS_PROFILES,
        "admin-created-profile",
        at=AS_OF,
    )
    assert service.get(
        cleaning_owner,
        cleaning.organization_id,
        TenantDataCollection.BUSINESS_PROFILES,
        "primary-profile",
        at=AS_OF,
    ) == {"revision": 2, "organization_id": cleaning.organization_id.value}

    # Profile writes are restricted to administrators; other generic collections
    # retain their existing membership-scoped write policy.
    service.create(
        member,
        cleaning.organization_id,
        TenantDataCollection.REPORTS,
        "member-report",
        {"revision": 1},
        at=AS_OF,
    )
    service.update(
        member,
        cleaning.organization_id,
        TenantDataCollection.REPORTS,
        "member-report",
        {"revision": 2},
        at=AS_OF,
    )
    assert service.get(
        member,
        cleaning.organization_id,
        TenantDataCollection.REPORTS,
        "member-report",
        at=AS_OF,
    ) == {"revision": 2, "organization_id": cleaning.organization_id.value}

    with pytest.raises(TenantAccessDenied):
        service.create(
            member,
            cleaning.organization_id,
            TenantDataCollection.BUSINESS_PROFILES,
            "member-profile",
            {"revision": 1},
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.update(
            member,
            cleaning.organization_id,
            TenantDataCollection.BUSINESS_PROFILES,
            "primary-profile",
            {"revision": 3},
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.delete(
            member,
            cleaning.organization_id,
            TenantDataCollection.BUSINESS_PROFILES,
            "primary-profile",
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.get(
            cleaning_owner,
            hvac.organization_id,
            TenantDataCollection.BUSINESS_PROFILES,
            "primary-profile",
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.create(
            cleaning_owner,
            hvac.organization_id,
            TenantDataCollection.BUSINESS_PROFILES,
            "cross-tenant-profile",
            {"revision": 1},
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.update(
            cleaning_owner,
            hvac.organization_id,
            TenantDataCollection.BUSINESS_PROFILES,
            "hvac-profile",
            {"revision": 2},
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.delete(
            cleaning_owner,
            hvac.organization_id,
            TenantDataCollection.BUSINESS_PROFILES,
            "hvac-profile",
            at=AS_OF,
        )

    assert service.get(
        admin,
        cleaning.organization_id,
        TenantDataCollection.BUSINESS_PROFILES,
        "primary-profile",
        at=AS_OF,
    ) == {"revision": 2, "organization_id": cleaning.organization_id.value}
    assert service.list(
        hvac_owner,
        hvac.organization_id,
        TenantDataCollection.BUSINESS_PROFILES,
        at=AS_OF,
    ) == (
        (
            "hvac-profile",
            {"revision": 1, "organization_id": hvac.organization_id.value},
        ),
    )

    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*.json")
    }
    with pytest.raises(TenantAccessDenied):
        service.get(
            fictional_cleaning_owner,
            hz.organization_id,
            TenantDataCollection.REPORTS,
            "hz-report",
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.update(
            fictional_cleaning_owner,
            hz.organization_id,
            TenantDataCollection.REPORTS,
            "hz-report",
            {"summary": "overwritten"},
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.delete(
            fictional_cleaning_owner,
            hz.organization_id,
            TenantDataCollection.REPORTS,
            "hz-report",
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.export(
            fictional_cleaning_owner,
            hz.organization_id,
            TenantDataCollection.REPORTS,
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.list(
            fictional_cleaning_owner,
            hz.organization_id,
            TenantDataCollection.OPPORTUNITY_INBOX,
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.get(
            fictional_cleaning_owner,
            hz.organization_id,
            TenantDataCollection.FOLLOW_UP_HISTORY,
            "hz-follow-up",
            at=AS_OF,
        )
    with pytest.raises(TenantAccessDenied):
        service.create(
            fictional_cleaning_owner,
            fictional_cleaning.organization_id,
            TenantDataCollection.REPORTS,
            "forged-owner-report",
            {"nested": {"organization_id": hz.organization_id.value}},
            at=AS_OF,
        )
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*.json")
    }
    assert after == before

    service.delete(
        fictional_cleaning_owner,
        fictional_cleaning.organization_id,
        TenantDataCollection.REPORTS,
        "member-report",
        at=AS_OF,
    )
    with pytest.raises(TenantRecordNotFound):
        service.get(
            fictional_cleaning_owner,
            fictional_cleaning.organization_id,
            TenantDataCollection.REPORTS,
            "member-report",
            at=AS_OF,
        )

    unassigned = _principal("actor-without-membership")
    with pytest.raises(TenantAccessDenied):
        service.list(
            unassigned,
            fictional_cleaning.organization_id,
            TenantDataCollection.REPORTS,
            at=AS_OF,
        )
    assert ListOrganizationsForActor(organizations).execute(unassigned, at=AS_OF) == ()


def test_actor_with_two_memberships_gets_only_selected_tenant_data(
    tmp_path: Path,
) -> None:
    organizations = _MemoryOrganizations()
    owner = _principal("multi-tenant-actor")
    register = RegisterOrganization(organizations)
    first = register.execute(owner, "Sample Cleaning Company fixture", at=AS_OF)
    second = register.execute(owner, "Fictional third business", at=AS_OF)
    resolver = TenantContextResolver(organizations)
    repository = LocalTenantDataRepository(tmp_path)
    service = TenantCommercialDataService(resolver, repository)
    service.create(
        owner,
        first.organization_id,
        TenantDataCollection.LEADS,
        "first-lead",
        {"company": "Sample Cleaning Company"},
        at=AS_OF,
    )
    service.create(
        owner,
        second.organization_id,
        TenantDataCollection.LEADS,
        "third-business-lead",
        {"company": "Sample Roofing Company (Fictional)"},
        at=AS_OF,
    )

    assert [
        item.organization_id
        for item in ListOrganizationsForActor(organizations).execute(owner, at=AS_OF)
    ] == [first.organization_id, second.organization_id]
    assert service.list(
        owner,
        first.organization_id,
        TenantDataCollection.LEADS,
        at=AS_OF,
    ) == (
        (
            "first-lead",
            {
                "company": "Sample Cleaning Company",
                "organization_id": first.organization_id.value,
            },
        ),
    )
    assert service.list(
        owner,
        second.organization_id,
        TenantDataCollection.LEADS,
        at=AS_OF,
    ) == (
        (
            "third-business-lead",
            {
                "company": "Sample Roofing Company (Fictional)",
                "organization_id": second.organization_id.value,
            },
        ),
    )


def test_tenant_inbox_keeps_provenance_guard_and_owner_envelope(
    tmp_path: Path,
) -> None:
    organizations, _, owner, _, organization, _, _, _ = _fixture_tenants()
    context = TenantContextResolver(organizations).resolve(
        owner, organization.organization_id, at=AS_OF
    )
    store = LocalTenantDataRepository(tmp_path).opportunity_inbox(context)
    fixture = json.loads(
        (
            ROOT
            / "tests/unit/live/fixtures/opportunity_inbox/thumbtack_lead_event.json"
        ).read_text(encoding="utf-8")
    )
    status, record = ingest_thumbtack_event(
        fixture,
        authorized_business_id="synthetic-fictional_cleaning-business",
        account_holder_authorized=True,
        received_at=AS_OF,
    )
    assert status.value == "FIXTURE_ONLY"
    assert record is not None
    with pytest.raises(InvalidLiveContract, match="Synthetic records"):
        store.add(record, attested_evidence_ids=())
    assert store.list_records() == ()


def test_reused_context_rechecks_current_membership(tmp_path: Path) -> None:
    organizations, _, owner, _, organization, _, _, _ = _fixture_tenants()
    context = TenantContextResolver(organizations).resolve(
        owner, organization.organization_id, at=AS_OF
    )
    store = LocalTenantDataRepository(tmp_path)
    store.put(context, TenantDataCollection.LEADS, "owned", {"lead": "private"})
    organizations.values[organization.organization_id.value] = Organization(
        organization.organization_id,
        organization.name,
        organization.status,
    )

    with pytest.raises(InvalidLiveContract, match="no longer authorized"):
        store.list(context, TenantDataCollection.LEADS)


def test_tenant_inbox_and_pipeline_files_record_owner_and_require_scoped_adapter(
    tmp_path: Path,
) -> None:
    organizations, _, owner, hz_owner, fictional_cleaning, hz, _, _ = _fixture_tenants()
    resolver = TenantContextResolver(organizations)
    context_a = resolver.resolve(owner, fictional_cleaning.organization_id, at=AS_OF)
    context_b = resolver.resolve(hz_owner, hz.organization_id, at=AS_OF)
    storage = LocalTenantDataRepository(tmp_path)
    storage.put(
        context_a,
        TenantDataCollection.OPPORTUNITY_INBOX,
        "generic-opportunity",
        {"title": "Generic tenant record"},
    )
    storage.put(
        context_a,
        TenantDataCollection.FOLLOW_UP_HISTORY,
        "generic-follow-up",
        {"note": "Generic tenant history"},
    )
    inbox = storage.opportunity_inbox(context_a)
    record = import_record(_synthetic_opportunity_mapping(), imported_at=AS_OF)
    with pytest.raises(InvalidLiveContract, match="Synthetic records"):
        inbox.add(record, attested_evidence_ids=())
    pipeline_record = PipelineRecord(
        prospect_id="fictional-cleaning-prospect",
        organization="Sample Cleaning Company (Fictional)",
        market="Sample City One, Example Region",
        status=PipelineStatus.DISCOVERED,
        source_evidence_ids=("source-evidence-1",),
    )
    storage.opportunity_pipeline(context_a).put(pipeline_record)

    inbox_path = (
        storage._collection_path(context_a, TenantDataCollection.OPPORTUNITY_INBOX)
        / "typed"
        / "store.json"
    )
    # Seed an existing test record directly to exercise tenant ownership on reads.
    from aeos.live.adapters.opportunity_inbox import LocalOpportunityInbox

    LocalOpportunityInbox(
        inbox_path, organization_id=fictional_cleaning.organization_id
    )._write({record.opportunity.opportunity_id: record})
    pipeline_path = (
        storage._collection_path(context_a, TenantDataCollection.FOLLOW_UP_HISTORY)
        / "typed"
        / "store.json"
    )
    inbox_owner = json.loads(inbox_path.read_text(encoding="utf-8"))
    pipeline_owner = json.loads(pipeline_path.read_text(encoding="utf-8"))
    assert inbox_owner["organization_id"] == fictional_cleaning.organization_id.value
    assert pipeline_owner["organization_id"] == fictional_cleaning.organization_id.value
    assert [
        record_id
        for record_id, _ in storage.list(
            context_a, TenantDataCollection.OPPORTUNITY_INBOX
        )
    ] == ["generic-opportunity"]
    assert [
        record_id
        for record_id, _ in storage.list(
            context_a, TenantDataCollection.FOLLOW_UP_HISTORY
        )
    ] == ["generic-follow-up"]
    assert storage.opportunity_inbox(context_b).list_records() == ()
    assert storage.opportunity_pipeline(context_b).list_records() == ()

    with pytest.raises(InvalidLiveContract, match="tenant-aware adapter"):
        LocalOpportunityInbox(inbox_path).list_records()


def _synthetic_opportunity_mapping() -> dict[str, object]:
    payload: dict[str, object] = {
        "opportunity_id": "fictional-cleaning-public-lead-1",
        "title": "Residential cleaning request",
        "source_platform": "Public local group",
        "demand_type": "DIRECT_CUSTOMER_DEMAND",
        "publication_date": "2026-11-06",
        "discovered_at": AS_OF.isoformat(),
        "service_requested": "Residential cleaning",
        "summary": "Public request with no customer details.",
        "source_url": "https://www.facebook.com/groups/sample-city-nine-cleaning/posts/lead-1",
        "source_event_ref": None,
        "city": "Sample City One",
        "state": "FL",
        "explicit_intent": True,
        "is_open": True,
        "response_method": "Public native response form",
        "publicly_accessible": True,
        "business_authorized": True,
        "source_provenance": "SYNTHETIC",
        "account_holder_authorized": False,
        "permission_basis": "PUBLIC_NOTICE",
        "source_terms_note": "Reviewed public-source terms.",
        "procurement_status": None,
        "official_deadline": None,
        "eligibility_requirements": [],
        "expected_jobs_per_day": 1,
        "ongoing_need": False,
        "limitations": [],
        "evidence": [
            {"field": "city", "value": "Sample City One", "kind": "REPORTED"},
            {
                "field": "state",
                "value": "FL",
                "kind": "REPORTED",
                "confidence": 0.95,
            },
            {
                "field": "service_requested",
                "value": "Residential cleaning",
                "kind": "REPORTED",
            },
            {"field": "explicit_intent", "value": True, "kind": "REPORTED"},
            {
                "field": "response_method",
                "value": "Public native response form",
                "kind": "REPORTED",
            },
            {
                "field": "publication_date",
                "value": "2026-11-06",
                "kind": "REPORTED",
            },
            {"field": "open_status", "value": True, "kind": "REPORTED"},
        ],
    }
    evidence = payload["evidence"]
    assert isinstance(evidence, list)
    for item in evidence:
        assert isinstance(item, dict)
        item["confidence"] = 0.95
    return payload
