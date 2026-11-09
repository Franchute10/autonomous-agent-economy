from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, cast

import pytest

from aeos.application.live.opportunity_inbox import (
    approve_contact as _approve_contact,
    approve_quote as _approve_quote,
    import_record as _import_record,
    opportunity_from_mapping,
    record_manual_contact,
    record_open_verification,
    record_quote,
    record_response,
    render_opportunity_report_markdown as _render_opportunity_report_markdown,
    flag_possible_duplicate,
    link_duplicate_source,
    resolve_possible_duplicate_pair,
    update_status,
)
from aeos.live.adapters.opportunity_inbox import (
    LocalOpportunityInbox as _LocalOpportunityInbox,
    ingest_thumbtack_event,
    thumbtack_source_state,
)
from aeos.application.tenancy import RegisterOrganization, TenantContextResolver
from aeos.core import ActorKind, ActorRef, OrganizationId
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind, SourceEvidence
from aeos.live.domain.profile import (
    BusinessModel,
    BusinessProfile,
    ProfileFieldStatus,
)
from aeos.live.domain.url_policy import sanitize_report_data
from aeos.live.domain.opportunity_inbox import (
    DemandType,
    DuplicateMatchType,
    LeadClassification,
    OpportunityEventAction,
    Opportunity,
    OpportunityAssessment,
    OpportunityPreviewAssessment,
    OpportunityRecord,
    OpportunityStatus,
    ProcurementStatus,
    SourceState,
    SourceProvenance,
    classify_opportunity as _classify_opportunity,
    duplicate_match_evidence,
    possible_duplicate_candidate,
    score_opportunity_preview,
    history_issues,
)
from aeos.live.opportunity_inbox_pilot import main as inbox_cli_main
from aeos.organization.domain.organization import Organization
from aeos.tenancy.domain import TenantContext, TenantPrincipal


AS_OF = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 16, 0, tzinfo=timezone.utc)
FIXTURE_DIR = Path(__file__).parents[2] / "live" / "fixtures" / "opportunity_inbox"


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
            if any(
                assignment.actor == actor
                for assignment in organization.assignments.values()
            )
        )


def _tenant_manager() -> TenantContext:
    organizations = _MemoryOrganizations()
    principal = TenantPrincipal(ActorRef(OrganizationId.new(), ActorKind.HUMAN))
    organization = RegisterOrganization(organizations).execute(
        principal, "Synthetic test tenant", at=NOW
    )
    return TenantContextResolver(organizations).resolve(
        principal, organization.organization_id, at=NOW
    )


def import_record(
    payload: Mapping[str, object], *, imported_at: datetime | None = None
) -> OpportunityRecord:
    """Parse the payload without upgrading caller-supplied provenance flags."""

    return _import_record(payload, imported_at=imported_at)


class LocalOpportunityInbox(_LocalOpportunityInbox):
    """Test adapter supplies a resolved synthetic manager attestation."""

    def add(
        self,
        record: OpportunityRecord,
        *,
        operator_context: TenantContext | None = None,
        attested_evidence_ids: tuple[str, ...] = (),
    ) -> tuple[OpportunityRecord, bool]:
        context = operator_context or _tenant_manager()
        ids = attested_evidence_ids or tuple(
            item.evidence_id
            for item in record.opportunity.evidence
            if item.kind is EvidenceKind.OBSERVED
        )
        return super().add(
            record,
            operator_context=context,
            attested_evidence_ids=ids,
        )


def _seed_test_store(store: LocalOpportunityInbox, *records: OpportunityRecord) -> None:
    """Create pre-existing fixture state without exercising persistent import."""

    store._write({record.opportunity.opportunity_id: record for record in records})


@pytest.fixture
def synthetic_hot_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate lifecycle authorization from source authenticity classification."""

    classifier = _classify_opportunity

    def classify_as_hot(
        opportunity: Opportunity,
        *,
        as_of: date,
        organization_profile: BusinessProfile | None = None,
    ) -> OpportunityAssessment:
        assessment = classifier(
            opportunity,
            as_of=as_of,
            organization_profile=organization_profile,
        )
        return replace(assessment, classification=LeadClassification.HOT)

    monkeypatch.setattr(
        "aeos.application.live.opportunity_inbox.classify_opportunity",
        classify_as_hot,
    )


_CLEANING_PROFILE_EVIDENCE: dict[str, tuple[str | int, ...]] = {
    "primary_services": (
        "Residential cleaning",
        "Vacation rental turnover cleaning",
        "Deep cleaning",
        "Recurring cleaning",
        "Commercial cleaning",
    ),
    "target_customer_segments": (
        "Residential customers",
        "Vacation rental managers",
    ),
    "owner_confirmed_service_areas": ("Sample City One, FL", "Sample City Two, FL"),
    "base_capacity_jobs_per_day": (2,),
    "expanded_capacity_jobs_per_day": (5,),
}
_CLEANING_PROFILE = BusinessProfile(
    business_name="Fictional Cleaning Test Organization",
    industry="Cleaning Services",
    vertical="CLEANING_SERVICES",
    description="Synthetic test profile with reported services and coverage.",
    business_model=BusinessModel.B2B2C,
    country="US",
    state_region="FL",
    city="Sample City One",
    service_radius=None,
    service_radius_unit=None,
    primary_services=(
        "Residential cleaning",
        "Vacation rental turnover cleaning",
        "Deep cleaning",
        "Recurring cleaning",
        "Commercial cleaning",
    ),
    target_customer_segments=("Residential customers", "Vacation rental managers"),
    owner_confirmed_service_areas=("Sample City One, FL", "Sample City Two, FL"),
    base_capacity_jobs_per_day=2,
    expanded_capacity_jobs_per_day=5,
    capacity_expansion_dependency="subcontratistas de confianza",
    is_fictional_example=True,
    field_statuses={
        field: ProfileFieldStatus.REPORTED for field in _CLEANING_PROFILE_EVIDENCE
    },
    field_evidence=tuple(
        SourceEvidence(
            evidence_id=f"synthetic-profile-{field}-{index + 1}",
            kind=EvidenceKind.REPORTED,
            subject="synthetic-cleaning-profile",
            field=field,
            value=value,
            source_name="Synthetic profile fixture",
            excerpt="Synthetic test claim; not an actual owner confirmation.",
            confidence=0.95,
            owner_entity_id="synthetic-cleaning-profile",
        )
        for field, values in _CLEANING_PROFILE_EVIDENCE.items()
        for index, value in enumerate(values)
    ),
)


def _profile(
    *,
    business_name: str,
    vertical: str,
    industry: str,
    services: tuple[str, ...],
    city: str,
    state: str,
    segments: tuple[str, ...],
    business_model: BusinessModel = BusinessModel.B2B2C,
) -> BusinessProfile:
    return BusinessProfile(
        business_name=business_name,
        industry=industry,
        vertical=vertical,
        description="Synthetic profile used only by offline regression tests.",
        business_model=business_model,
        country="US",
        state_region=state,
        city=city,
        service_radius=None,
        service_radius_unit=None,
        primary_services=services,
        target_customer_segments=segments,
        owner_confirmed_service_areas=(f"{city}, {state}",),
    )


def classify_opportunity(
    opportunity: Opportunity, *, as_of: date
) -> OpportunityAssessment | OpportunityPreviewAssessment:
    """Keep legacy scenarios explicit about their fictional cleaning profile."""

    if opportunity.source_provenance is SourceProvenance.SYNTHETIC:
        return score_opportunity_preview(
            opportunity, as_of=as_of, organization_profile=_CLEANING_PROFILE
        )
    return _classify_opportunity(
        opportunity, as_of=as_of, organization_profile=_CLEANING_PROFILE
    )


def approve_contact(
    record: OpportunityRecord,
    *,
    approver: TenantContext,
    note: str,
    occurred_at: datetime,
) -> OpportunityRecord:
    return _approve_contact(
        record,
        approver=approver,
        note=note,
        occurred_at=occurred_at,
        business_profile=_CLEANING_PROFILE,
    )


def approve_quote(
    record: OpportunityRecord,
    *,
    approver: TenantContext,
    note: str,
    occurred_at: datetime,
) -> OpportunityRecord:
    return _approve_quote(
        record,
        approver=approver,
        note=note,
        occurred_at=occurred_at,
    )


def test_approval_string_alone_is_not_an_authenticated_actor() -> None:
    record = import_record(_payload(), imported_at=NOW)

    with pytest.raises(TypeError):
        cast(Any, _approve_contact)(
            record,
            approved_by="forged-operator",
            note="Approve contact",
            occurred_at=NOW,
        )


def render_opportunity_report_markdown(
    records: tuple[OpportunityRecord, ...], *, as_of: date
) -> str:
    return _render_opportunity_report_markdown(
        records, as_of=as_of, business_profile=_CLEANING_PROFILE
    )


def _evidence(
    field: str, value: object, *, kind: str = "REPORTED"
) -> dict[str, object]:
    return {
        "field": field,
        "value": value,
        "kind": kind,
        "confidence": 0.95,
        "excerpt": f"Synthetic preview claim for {field}; no source observation was made.",
    }


def _evidence_items(payload: dict[str, object]) -> list[dict[str, object]]:
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or any(
        not isinstance(item, dict) for item in evidence
    ):
        raise TypeError("test opportunity evidence must be a list of objects")
    return cast(list[dict[str, object]], evidence)


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "opportunity_id": "synthetic-cleaning-request-001",
        "title": "Residential cleaning request in Sample City Two",
        "source_platform": "Facebook public Groups and Marketplace",
        "demand_type": DemandType.DIRECT_CUSTOMER_DEMAND.value,
        "publication_date": "2026-11-06",
        "discovered_at": NOW.isoformat(),
        "service_requested": "Residential cleaning",
        "summary": "Manually captured public request; no customer details.",
        "source_url": "https://manual-source.aeos/community/sample-city-two/001?utm_source=fixture",
        "source_event_ref": None,
        "city": "Sample City Two",
        "state": "FL",
        "explicit_intent": True,
        "is_open": True,
        "response_method": "Public source native response form",
        "publicly_accessible": True,
        "business_authorized": True,
        "source_provenance": "SYNTHETIC",
        "account_holder_authorized": False,
        "permission_basis": "PUBLIC_NOTICE",
        "source_terms_note": "Owner confirmed permitted manual use of the reviewed source.",
        "procurement_status": None,
        "official_deadline": None,
        "eligibility_requirements": [],
        "expected_jobs_per_day": 1,
        "ongoing_need": False,
        "evidence": [
            _evidence("city", "Sample City Two"),
            _evidence("state", "FL"),
            _evidence("service_requested", "Residential cleaning"),
            _evidence("explicit_intent", True),
            _evidence("response_method", "Public source native response form"),
            _evidence("publication_date", "2026-11-06"),
            _evidence("open_status", True),
        ],
    }
    payload.update(overrides)
    if "evidence" not in overrides:
        evidence = _evidence_items(payload)
        values: dict[str, object] = {
            "city": payload.get("city"),
            "state": payload.get("state"),
            "service_requested": payload.get("service_requested"),
            "customer_segment": payload.get("customer_segment"),
            "explicit_intent": payload.get("explicit_intent"),
            "response_method": payload.get("response_method"),
            "publication_date": payload.get("publication_date"),
            "open_status": payload.get("is_open"),
        }
        if (
            "expected_jobs_per_day" in overrides
            and payload.get("expected_jobs_per_day") is not None
            and payload.get("publicly_accessible") is True
        ):
            values["expected_jobs_per_day"] = payload.get("expected_jobs_per_day")
            if not any(
                item.get("field") == "expected_jobs_per_day" for item in evidence
            ):
                evidence.append(
                    _evidence("expected_jobs_per_day", payload["expected_jobs_per_day"])
                )
        if payload.get("procurement_status") is not None:
            values["procurement_status"] = payload.get("procurement_status")
            values["procurement_scope"] = payload.get("procurement_scope")
            values["eligibility_reviewed"] = payload.get("eligibility_reviewed")
            values["expected_jobs_per_day"] = payload.get("expected_jobs_per_day")
        for item in evidence:
            field = item.get("field")
            if isinstance(field, str) and field in values:
                item["value"] = values[field]
        if payload.get("procurement_status") is not None:
            evidence.append(
                _evidence("procurement_status", payload["procurement_status"])
            )
            for field in (
                "procurement_scope",
                "eligibility_reviewed",
                "expected_jobs_per_day",
            ):
                if payload.get(field) is not None:
                    evidence.append(_evidence(field, payload[field]))
        evidence[:] = [
            item
            for item in evidence
            if item.get("field") not in {"publication_date", "open_status"}
            or item.get("value") is not None
        ]
    return payload


def _opportunity(**overrides: object) -> Opportunity:
    return opportunity_from_mapping(_payload(**overrides), imported_at=NOW)


def _move_to_needs_review(record: OpportunityRecord) -> OpportunityRecord:
    verified = record_open_verification(
        record, actor="Synthetic owner", note="Verified the source", occurred_at=NOW
    )
    return update_status(
        verified,
        OpportunityStatus.NEEDS_REVIEW,
        actor="Synthetic owner",
        note="Reviewed source, permission, and capacity",
        occurred_at=NOW,
    )


def test_recent_residential_request_is_hot_with_explainable_commercial_score() -> None:
    assessment = classify_opportunity(_opportunity(), as_of=AS_OF)
    assert assessment.classification is LeadClassification.HOT
    assert 0 <= assessment.commercial_fit_score <= 100
    assert len(assessment.score_components) == 9
    assert (
        sum(item.score for item in assessment.score_components)
        == assessment.commercial_fit_score
    )
    assert all(item.explanation_es for item in assessment.score_components)
    assert all(
        item.evidence_ids for item in assessment.score_components if item.score > 0
    )
    assert "no estima probabilidad" not in assessment.priority_reason_es


def test_vacation_turnover_marketplace_lead_remains_distinct_from_direct_demand() -> (
    None
):
    payload = _payload(
        demand_type=DemandType.MARKETPLACE_LEAD.value,
        service_requested="Airbnb turnover",
        response_method="Native provider account",
        evidence=[
            _evidence("city", "Sample City One"),
            _evidence("state", "FL"),
            _evidence("service_requested", "Airbnb turnover"),
            _evidence("explicit_intent", True),
            _evidence("response_method", "Native provider account"),
            _evidence("publication_date", "2026-11-06"),
            _evidence("open_status", True),
        ],
        city="Sample City One",
    )
    assessment = classify_opportunity(opportunity_from_mapping(payload), as_of=AS_OF)
    assert assessment.opportunity.demand_type is DemandType.MARKETPLACE_LEAD
    assert assessment.opportunity.service_requested == "Airbnb turnover"
    assert assessment.classification is LeadClassification.HOT


def test_expired_request_and_historical_award_are_not_live_leads() -> None:
    expired = classify_opportunity(
        _opportunity(publication_date="2026-09-20"), as_of=AS_OF
    )
    assert expired.classification is LeadClassification.EXPIRED
    award_payload = _payload(
        opportunity_id="synthetic-award-001",
        demand_type=DemandType.PUBLIC_PROCUREMENT.value,
        procurement_status=ProcurementStatus.AWARD_NOTICE.value,
        publication_date="2026-07-14",
        official_deadline="2026-08-01",
        is_open=False,
    )
    award = classify_opportunity(opportunity_from_mapping(award_payload), as_of=AS_OF)
    assert award.classification is LeadClassification.EXPIRED
    report = render_opportunity_report_markdown(
        (import_record(award_payload),), as_of=AS_OF
    )
    assert "No hay oportunidades HOT o WARM" in report
    assert "AWARD_NOTICE" in report


def test_recommendation_discussion_is_cold_and_not_direct_purchase_intent() -> None:
    payload = _payload(
        demand_type=DemandType.RECOMMENDATION_SIGNAL.value,
        explicit_intent=False,
        response_method="Public discussion thread",
        evidence=[
            _evidence("city", "Sample City Two"),
            _evidence("state", "FL"),
            _evidence("service_requested", "Residential cleaning"),
            _evidence("explicit_intent", False),
            _evidence("response_method", "Public discussion thread"),
            _evidence("publication_date", "2026-11-06"),
        ],
    )
    assessment = classify_opportunity(opportunity_from_mapping(payload), as_of=AS_OF)
    assert assessment.classification is LeadClassification.COLD
    assert assessment.opportunity.demand_type is DemandType.RECOMMENDATION_SIGNAL


def test_missing_publication_date_cannot_be_hot() -> None:
    payload = _payload(publication_date=None)
    assessment = classify_opportunity(opportunity_from_mapping(payload), as_of=AS_OF)
    assert assessment.classification is LeadClassification.INSUFFICIENT_EVIDENCE


def test_manual_open_revalidation_promotes_a_recent_warm_lead_for_review() -> None:
    record = import_record(_payload(is_open=None), imported_at=NOW)
    before = classify_opportunity(record.opportunity, as_of=AS_OF)
    assert before.classification is LeadClassification.WARM
    verified = record_open_verification(
        record,
        actor="Owner",
        note="Source still showed an open request",
        occurred_at=NOW,
    )
    after = classify_opportunity(verified.opportunity, as_of=AS_OF)
    assert verified.status is OpportunityStatus.VERIFIED
    assert after.classification is LeadClassification.HOT
    assert verified.opportunity.evidence[-1].field == "open_status"


def test_different_city_and_unsupported_service_do_not_qualify() -> None:
    outside = classify_opportunity(_opportunity(city="Naples"), as_of=AS_OF)
    assert outside.classification is LeadClassification.COLD
    unsupported_payload = _payload(
        service_requested="Window cleaning",
        evidence=[
            _evidence("city", "Sample City Two"),
            _evidence("state", "FL"),
            _evidence("service_requested", "Window cleaning"),
            _evidence("explicit_intent", True),
            _evidence("response_method", "Public source native response form"),
            _evidence("publication_date", "2026-11-06"),
        ],
    )
    unsupported = classify_opportunity(
        opportunity_from_mapping(unsupported_payload), as_of=AS_OF
    )
    assert unsupported.classification is LeadClassification.COLD
    assert unsupported.score_components[2].score == 0


def test_geography_and_evidence_confidence_are_required_for_hot() -> None:
    missing_state_payload = _payload(
        evidence=[
            _evidence("city", "Sample City Two"),
            _evidence("service_requested", "Residential cleaning"),
            _evidence("explicit_intent", True),
            _evidence("response_method", "Public source native response form"),
            _evidence("publication_date", "2026-11-06"),
            _evidence("open_status", True),
        ]
    )
    missing_state = classify_opportunity(
        opportunity_from_mapping(missing_state_payload), as_of=AS_OF
    )
    assert missing_state.classification is LeadClassification.INSUFFICIENT_EVIDENCE

    low_confidence_payload = _payload()
    evidence = _evidence_items(low_confidence_payload)
    city_evidence = next(item for item in evidence if item["field"] == "city")
    city_evidence["confidence"] = 0.4
    low_confidence = classify_opportunity(
        opportunity_from_mapping(low_confidence_payload), as_of=AS_OF
    )
    assert low_confidence.classification is LeadClassification.INSUFFICIENT_EVIDENCE

    outside_state = classify_opportunity(_opportunity(state="CA"), as_of=AS_OF)
    assert outside_state.classification is LeadClassification.COLD


@pytest.mark.parametrize(
    ("jobs", "expected_score", "oversized"),
    [(4, 2, False), (6, 0, True)],
)
def test_capacity_overflow_changes_recommendation(
    jobs: int, expected_score: int, oversized: bool
) -> None:
    assessment = classify_opportunity(
        _opportunity(expected_jobs_per_day=jobs), as_of=AS_OF
    )
    assert assessment.classification is LeadClassification.WARM
    assert assessment.capacity_review_required is True
    assert assessment.potentially_oversized is oversized
    assert assessment.score_components[-1].score == expected_score
    assert "subcontratistas" in assessment.capacity_note_es or oversized


def test_active_public_procurement_is_open_but_requires_capacity_review() -> None:
    payload = _payload(
        opportunity_id="synthetic-open-solicitation",
        title="Janitorial services solicitation",
        source_platform="Official procurement portal",
        demand_type=DemandType.PUBLIC_PROCUREMENT.value,
        procurement_status=ProcurementStatus.OPEN_SOLICITATION.value,
        official_deadline="2026-12-01",
        eligibility_requirements=["Vendor registration required"],
        expected_jobs_per_day=None,
    )
    assessment = classify_opportunity(opportunity_from_mapping(payload), as_of=AS_OF)
    assert assessment.classification is LeadClassification.WARM
    assert assessment.capacity_review_required is True
    assert assessment.potentially_oversized is True
    assert "revisar el pliego" in assessment.recommended_action_es.casefold()
    assert "alcance" in assessment.recommended_action_es.casefold()
    report = render_opportunity_report_markdown(
        (import_record(payload, imported_at=NOW),), as_of=AS_OF
    )
    assert "Elegibilidad revisada: no" in report
    assert "alcance desconocido" in report
    assert "carga desconocida" in report
    assert "no contacta ni presenta bids" in report
    unknown_payload = _payload(
        opportunity_id="synthetic-unknown-solicitation",
        demand_type=DemandType.PUBLIC_PROCUREMENT.value,
        procurement_status=ProcurementStatus.UNKNOWN_STATUS.value,
        official_deadline=None,
    )
    unknown = classify_opportunity(
        opportunity_from_mapping(unknown_payload), as_of=AS_OF
    )
    assert unknown.classification is LeadClassification.WARM


def test_open_procurement_is_hot_only_after_scope_eligibility_and_workload_review() -> (
    None
):
    payload = _payload(
        opportunity_id="synthetic-qualified-solicitation",
        demand_type=DemandType.PUBLIC_PROCUREMENT.value,
        procurement_status=ProcurementStatus.OPEN_SOLICITATION.value,
        official_deadline="2026-12-01",
        eligibility_requirements=["Vendor registration required"],
        eligibility_reviewed=True,
        procurement_scope="One Sample City Two office, five-day schedule, one crew.",
        expected_jobs_per_day=2,
    )
    assessment = classify_opportunity(opportunity_from_mapping(payload), as_of=AS_OF)
    assert assessment.classification is LeadClassification.HOT
    assert assessment.capacity_review_required is False
    report = render_opportunity_report_markdown(
        (import_record(payload, imported_at=NOW),), as_of=AS_OF
    )
    assert "One Sample City Two office" in report
    assert "2 trabajo(s)/día" in report
    assert "no se identificaron requisitos adicionales" not in report


def test_unauthorized_public_source_is_insufficient_and_not_actionable() -> None:
    payload = _payload(
        business_authorized=False,
        permission_basis="NOT_APPROVED",
        source_terms_note="The source terms do not authorize company lead use.",
    )
    assessment = classify_opportunity(opportunity_from_mapping(payload), as_of=AS_OF)
    assert assessment.classification is LeadClassification.INSUFFICIENT_EVIDENCE


def test_private_marketplace_data_is_minimized_and_requires_owner_authorization() -> (
    None
):
    private = _payload(
        title="Do not retain this private title",
        source_platform="Thumbtack Pro",
        demand_type=DemandType.MARKETPLACE_LEAD.value,
        source_url=None,
        source_event_ref="synthetic-negotiation-001",
        publicly_accessible=False,
        business_authorized=True,
        account_holder_authorized=True,
        permission_basis="AUTHORIZED_ACCOUNT",
        summary="Do not retain this private summary",
        evidence=[
            _evidence("source_event_ref", "synthetic-negotiation-001"),
            _evidence("city", "Sample City Two"),
            _evidence("state", "FL"),
            _evidence("service_requested", "Residential cleaning"),
            _evidence("explicit_intent", True),
            _evidence("response_method", "Thumbtack Pro account"),
        ],
    )
    opportunity = opportunity_from_mapping(private)
    assert opportunity.title == "Lead privado de Thumbtack Pro: Residential cleaning"
    assert (
        opportunity.summary
        == "Detalles del cliente conservados en la plataforma autorizada."
    )
    assert all(
        item.excerpt is None and item.source_url is None
        for item in opportunity.evidence
    )
    report = render_opportunity_report_markdown((import_record(private),), as_of=AS_OF)
    assert "Do not retain" not in report
    assert "synthetic-negotiation-001" not in report
    assert "[private reference redacted]" in report
    with pytest.raises(InvalidLiveContract, match="account-holder authorization"):
        opportunity_from_mapping({**private, "account_holder_authorized": False})


def test_thumbtack_offline_adapter_is_fixture_only_and_discards_description() -> None:
    payload = json.loads(
        (FIXTURE_DIR / "thumbtack_lead_event.json").read_text(encoding="utf-8")
    )
    state, record = ingest_thumbtack_event(
        payload,
        authorized_business_id="synthetic-fictional_cleaning-business",
        account_holder_authorized=True,
        received_at=NOW,
    )
    assert state is SourceState.FIXTURE_ONLY
    assert record is not None
    assert record.opportunity.source_event_ref == "synthetic-negotiation-001"
    assert "intentionally discarded" not in record.opportunity.summary
    assert all(
        "intentionally discarded" not in str(item.value)
        for item in record.opportunity.evidence
    )


def test_missing_thumbtack_configuration_is_source_state_not_lead_classification() -> (
    None
):
    state, record = ingest_thumbtack_event(
        {},
        authorized_business_id=None,
        account_holder_authorized=False,
        received_at=NOW,
    )
    assert state is SourceState.PROVIDER_NOT_CONFIGURED
    assert record is None
    assert (
        thumbtack_source_state(provider_configured=True, provider_available=False)
        is SourceState.PROVIDER_UNAVAILABLE
    )
    assert (
        thumbtack_source_state(provider_configured=True, provider_available=True)
        is SourceState.FIXTURE_ONLY
    )
    with pytest.raises(InvalidLiveContract, match="account-holder authorization"):
        ingest_thumbtack_event(
            {},
            authorized_business_id="synthetic-business",
            account_holder_authorized=False,
            received_at=NOW,
        )


def test_same_url_and_tracking_variations_preserve_provenance_idempotently(
    tmp_path: Path,
) -> None:
    store = LocalOpportunityInbox(tmp_path / "opportunities.json")
    first = import_record(_payload(), imported_at=NOW)
    same_source = import_record(
        _payload(opportunity_id="synthetic-cleaning-request-duplicate"),
        imported_at=NOW,
    )
    assert (
        duplicate_match_evidence(first.opportunity, same_source.opportunity)[0]
        is DuplicateMatchType.EXACT
    )

    tracking_variation = import_record(
        _payload(
            opportunity_id="synthetic-tracking-variation",
            source_url="https://manual-source.aeos/community/sample-city-two/001?utm_campaign=other",
        ),
        imported_at=NOW,
    )
    assert (
        duplicate_match_evidence(first.opportunity, tracking_variation.opportunity)[0]
        is DuplicateMatchType.EXACT
    )
    _seed_test_store(store, first)
    assert store.find_duplicate(tracking_variation) == first

    canonical, linked = link_duplicate_source(
        first,
        tracking_variation,
        match_type=DuplicateMatchType.EXACT,
        actor="AEOS duplicate matcher",
        note="Tracking parameters do not change source identity",
        occurred_at=NOW,
    )
    assert canonical.duplicate_source_ids == ("synthetic-tracking-variation",)
    assert linked.status is OpportunityStatus.DUPLICATE
    assert linked.duplicate_of == first.opportunity.opportunity_id
    assert linked.opportunity.source_url == tracking_variation.opportunity.source_url
    assert [(item.field, item.value) for item in linked.opportunity.evidence] == [
        (item.field, item.value) for item in tracking_variation.opportunity.evidence
    ]


def test_same_request_at_two_urls_is_strongly_linked_not_counted_twice(
    tmp_path: Path,
) -> None:
    first = import_record(
        _payload(
            title="Move-out cleaning, 3 bedroom, 2 bathroom townhouse",
            summary="Need a move-out cleaning for a 3 bedroom and 2 bathroom townhouse.",
        ),
        imported_at=NOW,
    )
    second = import_record(
        _payload(
            opportunity_id="synthetic-cross-source-copy",
            source_platform="Second public source",
            source_url="https://manual-source.aeos/community/sample-city-two/77",
            title="Townhouse move-out clean: 3 bedroom, 2 bathroom",
            summary="Move-out cleaning needed for 3 bedroom, 2 bathroom townhouse.",
        ),
        imported_at=NOW,
    )
    match, evidence = duplicate_match_evidence(first.opportunity, second.opportunity)
    assert match is DuplicateMatchType.STRONG
    assert "detalles específicos" in evidence
    canonical, linked = link_duplicate_source(
        first,
        second,
        match_type=match,
        actor="AEOS duplicate matcher",
        note=evidence,
        occurred_at=NOW,
    )
    assert canonical.duplicate_source_ids == ("synthetic-cross-source-copy",)
    assert linked.status is OpportunityStatus.DUPLICATE
    assert linked.duplicate_match is DuplicateMatchType.STRONG
    assert linked.opportunity.source_url == second.opportunity.source_url
    assert [(item.field, item.value) for item in linked.opportunity.evidence] == [
        (item.field, item.value) for item in second.opportunity.evidence
    ]
    report = render_opportunity_report_markdown((canonical, linked), as_of=AS_OF)
    assert "synthetic-cross-source-copy" in report
    assert "No hay oportunidades HOT o WARM calificadas en el registro." in report


def test_similar_generic_requests_remain_independent_and_require_review(
    tmp_path: Path,
    synthetic_hot_lifecycle: None,
) -> None:
    store = LocalOpportunityInbox(tmp_path / "opportunities.json")
    first = import_record(
        _payload(summary="Looking for house cleaning help: breakfast."),
        imported_at=NOW,
    )
    second = import_record(
        _payload(
            opportunity_id="synthetic-second-person",
            source_url="https://manual-source.aeos/community/sample-city-two/2",
            summary="Looking for house cleaning help: breakfast.",
        ),
        imported_at=NOW,
    )
    assert possible_duplicate_candidate(first.opportunity, second.opportunity)
    left = flag_possible_duplicate(
        first,
        second.opportunity.opportunity_id,
        actor="AEOS duplicate matcher",
        note="POSSIBLE_DUPLICATE: similar generic requests need human review",
        occurred_at=NOW,
    )
    saved = flag_possible_duplicate(
        second,
        first.opportunity.opportunity_id,
        actor="AEOS duplicate matcher",
        note="POSSIBLE_DUPLICATE: similar generic requests need human review",
        occurred_at=NOW,
    )
    store = LocalOpportunityInbox(tmp_path / "opportunities.json")
    _seed_test_store(store, first, second)
    store.put_many((left, saved))
    assert len(store.list_records()) == 2
    assert saved.status is OpportunityStatus.NEEDS_REVIEW
    assert saved.possible_duplicate_ids == (first.opportunity.opportunity_id,)
    prior = store.get(first.opportunity.opportunity_id)
    assert prior is not None
    assert prior.possible_duplicate_ids == (second.opportunity.opportunity_id,)
    assert not saved.duplicate_of
    assert not prior.duplicate_of
    with pytest.raises(InvalidLiveContract):
        approve_contact(
            prior,
            approver=_tenant_manager(),
            note="Approve one contact",
            occurred_at=NOW,
        )
    report = render_opportunity_report_markdown(store.list_records(), as_of=AS_OF)
    assert "POSSIBLE_DUPLICATE" in report
    assert "no se presenta como demanda única verificada" in report


def test_possible_duplicate_resolution_is_audited_and_atomic(
    tmp_path: Path, synthetic_hot_lifecycle: None
) -> None:
    store = LocalOpportunityInbox(tmp_path / "opportunities.json")
    first = import_record(
        _payload(summary="Looking for house cleaning help: breakfast."),
        imported_at=NOW,
    )
    second = import_record(
        _payload(
            opportunity_id="synthetic-pair-review",
            source_url="https://manual-source.aeos/community/sample-city-two/review",
            summary="Looking for house cleaning help: breakfast.",
        ),
        imported_at=NOW,
    )
    left = flag_possible_duplicate(
        first,
        second.opportunity.opportunity_id,
        actor="AEOS duplicate matcher",
        note="POSSIBLE_DUPLICATE: needs review",
        occurred_at=NOW,
    )
    right = flag_possible_duplicate(
        second,
        first.opportunity.opportunity_id,
        actor="AEOS duplicate matcher",
        note="POSSIBLE_DUPLICATE: needs review",
        occurred_at=NOW,
    )
    _seed_test_store(store, left, right)
    resolved = resolve_possible_duplicate_pair(
        left,
        right,
        is_same_request=False,
        canonical_opportunity_id=None,
        actor="Owner",
        note="Reviewed sources; these are independent requests",
        occurred_at=NOW,
    )
    store.put_many(resolved)
    assert all(not record.possible_duplicate_ids for record in store.list_records())
    assert all(
        record.events[-1].action is OpportunityEventAction.POSSIBLE_DUPLICATE_RESOLVED
        for record in store.list_records()
    )
    reviewed_candidate = next(
        record
        for record in store.list_records()
        if record.opportunity.opportunity_id == second.opportunity.opportunity_id
    )
    reverified = record_open_verification(
        reviewed_candidate,
        actor="Owner",
        note="Rechecked the independent request after review",
        occurred_at=NOW,
    )
    assert reverified.status is OpportunityStatus.NEEDS_REVIEW
    approved = approve_contact(
        reverified,
        approver=_tenant_manager(),
        note="Approve this now-distinct request",
        occurred_at=NOW,
    )
    assert approved.status is OpportunityStatus.APPROVED_FOR_CONTACT


def test_confirmed_possible_duplicate_links_records_and_blocks_second_outreach(
    tmp_path: Path,
    synthetic_hot_lifecycle: None,
) -> None:
    store = LocalOpportunityInbox(tmp_path / "opportunities.json")
    first = import_record(
        _payload(summary="Looking for house cleaning help: breakfast."),
        imported_at=NOW,
    )
    second = import_record(
        _payload(
            opportunity_id="synthetic-human-confirmed-copy",
            source_url="https://manual-source.aeos/community/sample-city-two/confirmed",
            summary="Looking for house cleaning help: breakfast.",
        ),
        imported_at=NOW,
    )
    left = flag_possible_duplicate(
        first,
        second.opportunity.opportunity_id,
        actor="AEOS duplicate matcher",
        note="POSSIBLE_DUPLICATE: needs review",
        occurred_at=NOW,
    )
    right = flag_possible_duplicate(
        second,
        first.opportunity.opportunity_id,
        actor="AEOS duplicate matcher",
        note="POSSIBLE_DUPLICATE: needs review",
        occurred_at=NOW,
    )
    _seed_test_store(store, left, right)
    resolved = resolve_possible_duplicate_pair(
        left,
        right,
        is_same_request=True,
        canonical_opportunity_id=left.opportunity.opportunity_id,
        actor="Owner",
        note="Owner confirmed both source pages describe the same request",
        occurred_at=NOW,
    )
    store.put_many(resolved)
    duplicate = store.get(second.opportunity.opportunity_id)
    assert duplicate is not None
    assert duplicate.status is OpportunityStatus.DUPLICATE
    assert duplicate.duplicate_match is DuplicateMatchType.HUMAN_CONFIRMED
    assert duplicate.duplicate_of == first.opportunity.opportunity_id
    with pytest.raises(InvalidLiveContract):
        approve_contact(
            duplicate,
            approver=_tenant_manager(),
            note="Attempt contact to duplicate source",
            occurred_at=NOW,
        )


def test_same_city_and_service_with_different_dates_stays_independent(
    tmp_path: Path,
) -> None:
    first = import_record(
        _payload(summary="Looking for weekly house cleaning help."), imported_at=NOW
    )
    second = import_record(
        _payload(
            opportunity_id="synthetic-later-request",
            source_url="https://manual-source.aeos/community/sample-city-two/3",
            publication_date="2026-11-04",
            summary="Looking for weekly house cleaning help.",
            evidence=[
                _evidence("city", "Sample City Two"),
                _evidence("state", "FL"),
                _evidence("service_requested", "Residential cleaning"),
                _evidence("explicit_intent", True),
                _evidence("response_method", "Public source native response form"),
                _evidence("publication_date", "2026-11-04"),
                _evidence("open_status", True),
            ],
        ),
        imported_at=NOW,
    )
    assert duplicate_match_evidence(first.opportunity, second.opportunity) == (None, "")
    assert not possible_duplicate_candidate(first.opportunity, second.opportunity)


def test_missing_publication_date_cannot_enter_persistent_inbox(
    tmp_path: Path,
) -> None:
    missing_date_payload = _payload(
        opportunity_id="synthetic-missing-date-copy",
        source_url="https://manual-source.aeos/community/sample-city-two/4",
        publication_date=None,
        title="Move-out cleaning, 3 bedroom, 2 bathroom townhouse",
        summary="Move-out cleaning for 3 bedroom, 2 bathroom townhouse.",
    )
    missing_date_payload["evidence"] = [
        item
        for item in cast(list[dict[str, object]], missing_date_payload["evidence"])
        if item.get("field") != "publication_date"
    ]
    second = import_record(missing_date_payload, imported_at=NOW)
    preview = score_opportunity_preview(
        second.opportunity, as_of=AS_OF, organization_profile=_CLEANING_PROFILE
    )
    assert preview.classification is LeadClassification.INSUFFICIENT_EVIDENCE
    store = LocalOpportunityInbox(tmp_path / "opportunities.json")
    with pytest.raises(InvalidLiveContract, match="Synthetic records"):
        store.add(second)
    assert not store.path.exists()


def test_synthetic_webhook_fixture_cannot_enter_persistent_inbox(
    tmp_path: Path,
) -> None:
    store = LocalOpportunityInbox(tmp_path / "opportunities.json")

    fixture = json.loads(
        (FIXTURE_DIR / "thumbtack_lead_event.json").read_text(encoding="utf-8")
    )
    _, event_record = ingest_thumbtack_event(
        fixture,
        authorized_business_id="synthetic-fictional_cleaning-business",
        account_holder_authorized=True,
        received_at=NOW,
    )
    assert event_record is not None
    with pytest.raises(InvalidLiveContract, match="Synthetic records"):
        store.add(event_record)
    assert not store.path.exists()
    round_trip = LocalOpportunityInbox(tmp_path / "opportunities.json")
    assert round_trip.list_records() == ()


def test_contact_and_each_quote_require_explicit_owner_approval(
    synthetic_hot_lifecycle: None,
) -> None:
    record = import_record(_payload(), imported_at=NOW)
    with pytest.raises(InvalidLiveContract, match="verified review path"):
        record_manual_contact(
            record,
            actor="Owner",
            channel="native form",
            note="Synthetic manual record",
            next_action="Wait for response",
            follow_up_date=None,
            occurred_at=NOW,
        )
    verified = record_open_verification(
        record, actor="Owner", note="Verified the live source", occurred_at=NOW
    )
    review = update_status(
        verified,
        OpportunityStatus.NEEDS_REVIEW,
        actor="Owner",
        note="Reviewed scope and permission",
        occurred_at=NOW,
    )
    approved = approve_contact(
        review,
        approver=_tenant_manager(),
        note="Approved this one contact",
        occurred_at=NOW,
    )
    contacted = record_manual_contact(
        approved,
        actor="Owner",
        channel="native form",
        note="Contact completed manually",
        next_action="Wait for a response",
        follow_up_date=date(2026, 11, 10),
        occurred_at=NOW,
    )
    assert contacted.status is OpportunityStatus.CONTACTED
    assert contacted.events[-1].related_event_id == approved.events[-1].event_id
    with pytest.raises(InvalidLiveContract, match="invalid opportunity transition"):
        update_status(
            review,
            OpportunityStatus.CONTACTED,
            actor="Owner",
            note="Bypass attempt",
            occurred_at=NOW,
        )
    requested = record_response(
        record_response(
            contacted,
            status=OpportunityStatus.REPLIED,
            actor="Owner",
            note="Customer replied through the source",
            next_action="Review the request",
            follow_up_date=None,
            occurred_at=NOW,
        ),
        status=OpportunityStatus.QUOTE_REQUESTED,
        actor="Owner",
        note="Synthetic response requested a quote",
        next_action="Review the scope",
        follow_up_date=None,
        occurred_at=NOW,
    )
    with pytest.raises(InvalidLiveContract, match="specific unused owner approval"):
        record_quote(
            requested,
            actor="Owner",
            channel="native platform",
            note="Quote manually recorded",
            next_action="Wait for decision",
            follow_up_date=None,
            occurred_at=NOW,
        )
    quote_approved = approve_quote(
        requested,
        approver=_tenant_manager(),
        note="Approved this quote only",
        occurred_at=NOW,
    )
    quoted = record_quote(
        quote_approved,
        actor="Owner",
        channel="native platform",
        note="Quote sent by owner outside AEOS",
        next_action="Wait for decision",
        follow_up_date=None,
        occurred_at=NOW,
    )
    assert quoted.status is OpportunityStatus.QUOTE_SENT
    assert quoted.events[-1].action is OpportunityEventAction.QUOTE_RECORDED
    assert quoted.events[-1].related_event_id == quote_approved.events[-1].event_id
    with pytest.raises(InvalidLiveContract, match="invalid opportunity transition"):
        record_quote(
            quoted,
            actor="Owner",
            channel="native platform",
            note="Second quote without approval",
            next_action="Wait",
            follow_up_date=None,
            occurred_at=NOW,
        )


def test_lifecycle_rejects_direct_and_unauthorized_transitions(
    synthetic_hot_lifecycle: None,
) -> None:
    record = import_record(_payload(), imported_at=NOW)
    for target in (OpportunityStatus.WON, OpportunityStatus.CONTACTED):
        with pytest.raises(InvalidLiveContract, match="invalid opportunity transition"):
            update_status(
                record,
                target,
                actor="Owner",
                note="Attempted unsupported status",
                occurred_at=NOW,
            )
    with pytest.raises(InvalidLiveContract, match="invalid opportunity transition"):
        update_status(
            record,
            OpportunityStatus.APPROVED_FOR_CONTACT,
            actor="Owner",
            note="Attempted to bypass approval",
            occurred_at=NOW,
        )
    with pytest.raises(InvalidLiveContract, match="NEEDS_REVIEW"):
        approve_contact(
            record,
            approver=_tenant_manager(),
            note="Approval without review",
            occurred_at=NOW,
        )


def test_valid_won_progression_has_scoped_approval_and_outcome_audit(
    synthetic_hot_lifecycle: None,
) -> None:
    record = import_record(_payload(), imported_at=NOW)
    reviewed = _move_to_needs_review(record)
    approved = approve_contact(
        reviewed,
        approver=_tenant_manager(),
        note="Approve one contact for this request",
        occurred_at=NOW,
    )
    contacted = record_manual_contact(
        approved,
        actor="Owner Frank",
        channel="Native platform",
        note="Contact was made manually",
        next_action="Wait for the customer reply",
        follow_up_date=None,
        occurred_at=NOW,
    )
    replied = record_response(
        contacted,
        status=OpportunityStatus.REPLIED,
        actor="Owner Frank",
        note="Customer replied in the source channel",
        next_action="Review the scope",
        follow_up_date=None,
        occurred_at=NOW,
    )
    requested = record_response(
        replied,
        status=OpportunityStatus.QUOTE_REQUESTED,
        actor="Owner Frank",
        note="Customer requested an estimate",
        next_action="Prepare estimate for review",
        follow_up_date=None,
        occurred_at=NOW,
    )
    quote_approval = approve_quote(
        requested,
        approver=_tenant_manager(),
        note="Approve one quote for this request",
        occurred_at=NOW,
    )
    quote_sent = record_quote(
        quote_approval,
        actor="Owner Frank",
        channel="Native platform",
        note="Quote sent manually outside AEOS",
        next_action="Wait for customer decision",
        follow_up_date=None,
        occurred_at=NOW,
    )
    won = record_response(
        quote_sent,
        status=OpportunityStatus.WON,
        actor="Owner Frank",
        note="Customer accepted the approved quote",
        next_action="Close the opportunity",
        follow_up_date=None,
        occurred_at=NOW,
    )
    assert won.status is OpportunityStatus.WON
    assert contacted.events[-1].related_event_id == approved.events[-1].event_id
    assert quote_sent.events[-1].related_event_id == quote_approval.events[-1].event_id
    assert all(
        event.scope_id == record.opportunity.opportunity_id for event in won.events[1:]
    )
    assert history_issues(won) == ()


def test_lost_expired_and_disqualified_have_reasons_and_terminal_audit(
    synthetic_hot_lifecycle: None,
) -> None:
    record = import_record(_payload(), imported_at=NOW)
    reviewed = _move_to_needs_review(record)
    approved = approve_contact(
        reviewed,
        approver=_tenant_manager(),
        note="Approve one contact",
        occurred_at=NOW,
    )
    contacted = record_manual_contact(
        approved,
        actor="Owner",
        channel="Native platform",
        note="Manual contact completed",
        next_action="Wait for a reply",
        follow_up_date=None,
        occurred_at=NOW,
    )
    lost = record_response(
        contacted,
        status=OpportunityStatus.LOST,
        actor="Owner",
        note="Customer declined due to timing",
        next_action="Close the record",
        follow_up_date=None,
        occurred_at=NOW,
    )
    assert lost.status is OpportunityStatus.LOST
    assert history_issues(lost) == ()

    expired = update_status(
        record,
        OpportunityStatus.EXPIRED,
        actor="Owner",
        note="Original request passed its freshness window",
        occurred_at=NOW,
    )
    assert expired.status is OpportunityStatus.EXPIRED
    assert history_issues(expired) == ()

    disqualified = update_status(
        record,
        OpportunityStatus.DISQUALIFIED,
        actor="Owner",
        note="Source terms prohibit business use",
        occurred_at=NOW,
    )
    assert disqualified.status is OpportunityStatus.DISQUALIFIED
    assert history_issues(disqualified) == ()
    with pytest.raises(InvalidLiveContract, match="invalid opportunity transition"):
        update_status(
            lost,
            OpportunityStatus.NEEDS_REVIEW,
            actor="Owner",
            note="Attempt to reopen a lost record",
            occurred_at=NOW,
        )


def test_failed_transition_does_not_change_json_store(tmp_path: Path) -> None:
    path = tmp_path / "opportunities.json"
    store = LocalOpportunityInbox(path)
    record = import_record(_payload(), imported_at=NOW)
    _seed_test_store(store, record)
    before = path.read_bytes()
    invalid = replace(record, status=OpportunityStatus.WON)
    with pytest.raises(InvalidLiveContract, match="each mutation"):
        store.put(invalid)
    assert path.read_bytes() == before


def test_schema_v1_json_without_new_fields_round_trips_without_data_loss(
    tmp_path: Path,
) -> None:
    path = tmp_path / "opportunities.json"
    store = LocalOpportunityInbox(path)
    record = import_record(_payload(), imported_at=NOW)
    _seed_test_store(store, record)
    payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    records = cast(list[dict[str, object]], payload["records"])
    saved = records[0]
    for field in (
        "duplicate_of",
        "duplicate_match",
        "duplicate_source_ids",
        "possible_duplicate_ids",
    ):
        saved.pop(field, None)
    opportunity = cast(dict[str, object], saved["opportunity"])
    for field in ("stable_request_id", "procurement_scope", "eligibility_reviewed"):
        opportunity.pop(field, None)
    events = cast(list[dict[str, object]], saved["events"])
    for event in events:
        for field in (
            "scope_id",
            "related_event_id",
            "from_status",
            "to_status",
        ):
            event.pop(field, None)
    path.write_text(json.dumps(payload), encoding="utf-8")

    legacy = LocalOpportunityInbox(path).get(record.opportunity.opportunity_id)
    assert legacy is not None
    assert legacy.opportunity.summary == record.opportunity.summary
    verified = record_open_verification(
        legacy, actor="Owner", note="Legacy source was rechecked", occurred_at=NOW
    )
    LocalOpportunityInbox(path).put(verified)
    round_trip = LocalOpportunityInbox(path).get(record.opportunity.opportunity_id)
    assert round_trip is not None
    assert round_trip.opportunity.summary == record.opportunity.summary
    assert round_trip.status is OpportunityStatus.VERIFIED


def test_legacy_invalid_terminal_history_is_reported_without_repair(
    tmp_path: Path,
) -> None:
    path = tmp_path / "opportunities.json"
    store = LocalOpportunityInbox(path)
    imported = import_record(_payload(), imported_at=NOW)
    _seed_test_store(store, imported)
    payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    records = cast(list[dict[str, object]], payload["records"])
    record = records[0]
    record["status"] = OpportunityStatus.WON.value
    events = cast(list[dict[str, object]], record["events"])
    events.append(
        {
            "event_id": "legacy-invalid-won",
            "action": OpportunityEventAction.STATUS_UPDATED.value,
            "actor": "Historical operator",
            "note": "Direct status bypass",
            "occurred_at": NOW.isoformat(),
        }
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    legacy_store = LocalOpportunityInbox(path)
    assert "lacks required audit action" in "; ".join(
        legacy_store.audit_history()[imported.opportunity.opportunity_id]
    )
    legacy_record = legacy_store.get(imported.opportunity.opportunity_id)
    assert legacy_record is not None
    with pytest.raises(InvalidLiveContract, match="invalid opportunity transition"):
        update_status(
            legacy_record,
            OpportunityStatus.NEEDS_REVIEW,
            actor="Owner",
            note="Review invalid legacy status",
            occurred_at=NOW,
        )


def test_report_shows_queue_evidence_capacity_and_no_contact_automation() -> None:
    record = import_record(_payload(), imported_at=NOW)
    markdown = render_opportunity_report_markdown((record,), as_of=AS_OF)
    assert "Cola prioritaria" in markdown
    assert "Evidencia" in markdown
    assert "Compatibilidad de capacidad" in markdown
    assert "No se envía contacto" in markdown
    assert "probabilidad de cierre" in markdown
    assert "fuente no autorizada" not in markdown.casefold()


def test_shareable_report_redacts_private_event_reference() -> None:
    private_ref = "synthetic-private-event-reference"
    record = import_record(
        _payload(
            source_url=None,
            source_event_ref=private_ref,
            publicly_accessible=False,
            account_holder_authorized=True,
            permission_basis="AUTHORIZED_ACCOUNT",
            evidence=[_evidence("source_event_ref", private_ref)],
        ),
        imported_at=NOW,
    )

    report = render_opportunity_report_markdown((record,), as_of=AS_OF)

    assert private_ref not in report
    assert "referencia interna" in report
    assert "[private reference redacted]" in report
    shareable_json = sanitize_report_data(
        {
            "source_event_ref": private_ref,
            "evidence": [{"field": "source_event_ref", "value": private_ref}],
        }
    )
    assert private_ref not in json.dumps(shareable_json)
    assert "[private reference redacted]" in json.dumps(shareable_json)


def test_cli_import_is_blocked_without_authenticated_tenant_context(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "manual-opportunity.json"
    store_path = tmp_path / "opportunities.json"
    input_path.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")

    assert (
        inbox_cli_main(
            ["import", "--input", str(input_path), "--store", str(store_path)]
        )
        == 2
    )
    assert not store_path.exists()


def test_manual_template_cannot_be_imported_unchanged() -> None:
    template = json.loads(
        (
            Path(__file__).parents[4]
            / "examples/live/opportunity_inbox/manual_opportunity.template.json"
        ).read_text(encoding="utf-8")
    )
    with pytest.raises(InvalidLiveContract, match="template cannot be imported"):
        opportunity_from_mapping(template)


@pytest.mark.parametrize(
    "source_url",
    [
        "https://example.org/requests/fake",
        "https://example.org\u3002/requests/fake",
        "https://sub.example.com/requests/fake",
        "https://192.0.2.44/requests/fake",
    ],
)
def test_reserved_example_source_is_rejected_without_template_marker(
    source_url: str,
) -> None:
    payload = _payload(
        source_url=source_url,
        source_provenance="REAL",
        template_only=False,
    )
    with pytest.raises(InvalidLiveContract, match="reserved example and test domains"):
        opportunity_from_mapping(payload, imported_at=NOW)


def test_synthetic_manual_record_is_rejected_without_changing_store(
    tmp_path: Path,
) -> None:
    store = LocalOpportunityInbox(tmp_path / "opportunities.json")
    existing_fixture = import_record(
        _payload(opportunity_id="synthetic-existing-fixture"), imported_at=NOW
    )
    _seed_test_store(store, existing_fixture)
    before = store.path.read_bytes()

    synthetic = import_record(
        _payload(
            opportunity_id="synthetic-only-record",
            source_provenance="SYNTHETIC",
        ),
        imported_at=NOW,
    )
    with pytest.raises(InvalidLiveContract, match="Synthetic records"):
        store.add(synthetic)

    assert store.path.read_bytes() == before
    assert store.get(existing_fixture.opportunity.opportunity_id) == existing_fixture
    assert store.get("synthetic-only-record") is None


def test_unknown_provenance_is_not_classified_as_a_genuine_opportunity() -> None:
    opportunity = opportunity_from_mapping(
        _payload(source_provenance="UNKNOWN"), imported_at=NOW
    )
    assessment = classify_opportunity(opportunity, as_of=AS_OF)
    assert assessment.classification is LeadClassification.INSUFFICIENT_EVIDENCE


def test_preview_scoring_is_distinct_and_never_actionable() -> None:
    opportunity = _opportunity()
    preview = score_opportunity_preview(
        opportunity, as_of=AS_OF, organization_profile=_CLEANING_PROFILE
    )
    qualified = _classify_opportunity(
        opportunity, as_of=AS_OF, organization_profile=_CLEANING_PROFILE
    )

    assert preview.actionable is False
    assert preview.classification is LeadClassification.HOT
    assert qualified.classification is LeadClassification.INSUFFICIENT_EVIDENCE


def test_unattested_reported_evidence_cannot_create_persistable_provenance(
    tmp_path: Path,
) -> None:
    raw = _import_record(_payload(source_provenance="UNKNOWN"), imported_at=NOW)
    assert raw.opportunity.source_provenance is SourceProvenance.UNKNOWN
    assert all(item.retrieved_at is None for item in raw.opportunity.evidence)
    store = _LocalOpportunityInbox(tmp_path / "opportunities.json")
    with pytest.raises(
        InvalidLiveContract, match="authenticated tenant operator attestation"
    ):
        store.add(raw)
    assert not store.path.exists()


def test_missing_provenance_defaults_to_unknown_and_cannot_be_persisted(
    tmp_path: Path,
) -> None:
    payload = _payload()
    payload.pop("source_provenance")
    record = import_record(payload, imported_at=NOW)
    assert record.opportunity.source_provenance.value == "UNKNOWN"
    store = _LocalOpportunityInbox(tmp_path / "opportunities.json")
    with pytest.raises(
        InvalidLiveContract, match="authenticated tenant operator attestation"
    ):
        store.add(record)
    assert not store.path.exists()


def test_business_authorization_alone_does_not_allow_persistent_import(
    tmp_path: Path,
) -> None:
    record = import_record(
        _payload(
            opportunity_id="authorization-without-origin",
            source_provenance="UNKNOWN",
            business_authorized=True,
        ),
        imported_at=NOW,
    )
    store = _LocalOpportunityInbox(tmp_path / "opportunities.json")
    with pytest.raises(
        InvalidLiveContract, match="authenticated tenant operator attestation"
    ):
        store.add(record)
    assert not store.path.exists()


def test_private_event_reference_must_itself_be_observed(
    tmp_path: Path,
) -> None:
    event_reference = "verified-account-event-001"
    event_evidence = _evidence("source_event_ref", event_reference, kind="REPORTED")
    event_evidence["confidence"] = 0.25
    record = import_record(
        _payload(
            opportunity_id="reported-private-event-reference",
            source_platform="Thumbtack Pro",
            source_url=None,
            source_event_ref=event_reference,
            publicly_accessible=False,
            business_authorized=True,
            source_provenance="UNKNOWN",
            account_holder_authorized=True,
            permission_basis="AUTHORIZED_ACCOUNT",
            is_open=None,
            evidence=[
                event_evidence,
                _evidence("city", "Sample City Two", kind="OBSERVED"),
                _evidence("state", "FL", kind="OBSERVED"),
                _evidence("service_requested", "Residential cleaning", kind="OBSERVED"),
                _evidence("explicit_intent", True, kind="OBSERVED"),
                _evidence("response_method", "Thumbtack Pro account", kind="OBSERVED"),
                _evidence("publication_date", "2026-11-06", kind="OBSERVED"),
            ],
        ),
        imported_at=NOW,
    )
    store = LocalOpportunityInbox(tmp_path / "opportunities.json")
    with pytest.raises(InvalidLiveContract, match="event reference must be observed"):
        store.add(record)
    assert not store.path.exists()


def test_reported_private_event_cannot_be_attested_as_observed(
    tmp_path: Path,
) -> None:
    event_reference = "owner-authorized-event-001"
    record = import_record(
        _payload(
            opportunity_id="authorized-private-event",
            source_platform="Thumbtack Pro",
            source_url=None,
            source_event_ref=event_reference,
            publicly_accessible=False,
            business_authorized=True,
            source_provenance="UNKNOWN",
            account_holder_authorized=True,
            permission_basis="AUTHORIZED_ACCOUNT",
            is_open=None,
            evidence=[
                _evidence("source_event_ref", event_reference, kind="REPORTED"),
                _evidence("city", "Sample City Two"),
                _evidence("state", "FL"),
                _evidence("service_requested", "Residential cleaning"),
                _evidence("explicit_intent", True),
                _evidence("response_method", "Thumbtack Pro account"),
                _evidence("publication_date", "2026-11-06"),
            ],
        ),
        imported_at=NOW,
    )
    store = LocalOpportunityInbox(tmp_path / "opportunities.json")
    with pytest.raises(
        InvalidLiveContract,
        match="operator attestation must identify source evidence marked OBSERVED",
    ):
        store.add(record)
    assert not store.path.exists()


def test_reported_manual_source_requires_observed_evidence_before_import(
    tmp_path: Path,
) -> None:
    record = import_record(
        _payload(
            source_provenance="UNKNOWN",
            business_authorized=True,
        ),
        imported_at=NOW,
    )
    store = LocalOpportunityInbox(tmp_path / "opportunities.json")
    with pytest.raises(
        InvalidLiveContract,
        match="operator attestation must identify source evidence marked OBSERVED",
    ):
        store.add(record)
    assert not store.path.exists()


def test_legacy_cli_cannot_persist_synthetic_record_without_template_marker(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "synthetic.json"
    store_path = tmp_path / "opportunities.json"
    input_path.write_text(
        json.dumps(
            _payload(
                source_provenance="SYNTHETIC",
                template_only=False,
            )
        ),
        encoding="utf-8",
    )
    assert (
        inbox_cli_main(
            ["import", "--input", str(input_path), "--store", str(store_path)]
        )
        == 2
    )
    assert not store_path.exists()


def test_synthetic_fixture_remains_usable_in_an_isolated_preview(
    tmp_path: Path,
) -> None:
    record = import_record(
        _payload(
            opportunity_id="isolated-synthetic-preview",
            source_provenance="SYNTHETIC",
        ),
        imported_at=NOW,
    )
    preview = score_opportunity_preview(
        record.opportunity, as_of=AS_OF, organization_profile=_CLEANING_PROFILE
    )
    assessment = _classify_opportunity(
        record.opportunity, as_of=AS_OF, organization_profile=_CLEANING_PROFILE
    )
    assert preview.classification is LeadClassification.HOT
    assert preview.actionable is False
    assert assessment.classification is LeadClassification.INSUFFICIENT_EVIDENCE
    isolated_store = LocalOpportunityInbox(tmp_path / "isolated" / "store.json")
    assert not isolated_store.path.exists()


def test_legacy_persisted_record_without_provenance_fails_closed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "opportunities.json"
    store = LocalOpportunityInbox(path)
    record = import_record(_payload(), imported_at=NOW)
    _seed_test_store(store, record)
    saved = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    records = cast(list[dict[str, object]], saved["records"])
    opportunity = cast(dict[str, object], records[0]["opportunity"])
    del opportunity["source_provenance"]
    path.write_text(json.dumps(saved), encoding="utf-8")

    legacy = LocalOpportunityInbox(path).get(record.opportunity.opportunity_id)
    assert legacy is not None
    assert legacy.opportunity.source_provenance.value == "UNKNOWN"
    assert (
        classify_opportunity(legacy.opportunity, as_of=AS_OF).classification
        is LeadClassification.INSUFFICIENT_EVIDENCE
    )


def test_three_verticals_use_only_the_selected_profiles_services_and_coverage() -> None:
    hvac = _profile(
        business_name="Synthetic HVAC Organization",
        vertical="HVAC",
        industry="HVAC",
        services=("Air conditioning installation", "Air conditioning repair"),
        city="Fictional City",
        state="WA",
        segments=("Homeowners", "Facility managers"),
    )
    construction = _profile(
        business_name="Synthetic Construction Organization",
        vertical="CONSTRUCTION",
        industry="Construction",
        services=("General contracting", "Remodeling"),
        city="Fictional City",
        state="WA",
        segments=("Property owners", "Developers"),
    )
    cases = (
        (_CLEANING_PROFILE, _opportunity(city="Sample City Two", state="FL")),
        (
            hvac,
            _opportunity(
                service_requested="AC installation",
                city="Fictional City",
                state="WA",
            ),
        ),
        (
            construction,
            _opportunity(
                service_requested="General contractor",
                city="Fictional City",
                state="WA",
            ),
        ),
    )
    for profile, opportunity in cases:
        result = score_opportunity_preview(
            opportunity, as_of=AS_OF, organization_profile=profile
        )
        assert result.classification is LeadClassification.HOT
        service = next(
            item for item in result.score_components if item.key == "service"
        )
        assert service.score == 15
        assert service.evidence_ids


def test_profile_mismatch_and_out_of_coverage_do_not_score_as_compatible() -> None:
    hvac = _profile(
        business_name="Synthetic HVAC Organization",
        vertical="HVAC",
        industry="HVAC",
        services=("Air conditioning repair",),
        city="Fictional City",
        state="WA",
        segments=("Facility managers",),
    )
    incompatible = score_opportunity_preview(
        _opportunity(
            service_requested="Residential cleaning",
            city="Fictional City",
            state="WA",
        ),
        as_of=AS_OF,
        organization_profile=hvac,
    )
    outside = score_opportunity_preview(
        _opportunity(
            service_requested="AC repair",
            city="Other Fictional City",
            state="WA",
        ),
        as_of=AS_OF,
        organization_profile=hvac,
    )
    assert incompatible.classification is LeadClassification.COLD
    assert any(
        "no coincide con los servicios" in item
        for item in incompatible.classification_reasons_es
    )
    assert outside.classification is LeadClassification.COLD
    assert any(
        "fuera de las áreas" in item for item in outside.classification_reasons_es
    )


def test_fit_alone_does_not_make_a_lead_hot_and_missing_profile_is_insufficient() -> (
    None
):
    fit_only = score_opportunity_preview(
        _opportunity(explicit_intent=False),
        as_of=AS_OF,
        organization_profile=_CLEANING_PROFILE,
    )
    unscoped = score_opportunity_preview(_opportunity(), as_of=AS_OF)
    assert fit_only.classification is LeadClassification.WARM
    assert unscoped.classification is LeadClassification.INSUFFICIENT_EVIDENCE


def test_customer_segment_score_requires_matching_observed_segment() -> None:
    profile = _profile(
        business_name="Synthetic HVAC Organization",
        vertical="HVAC",
        industry="HVAC",
        services=("Air conditioning repair",),
        city="Fictional City",
        state="WA",
        segments=("Facility managers",),
    )
    opportunity = _opportunity(
        service_requested="AC repair",
        city="Fictional City",
        state="WA",
        customer_segment="Facility managers",
        evidence=[
            _evidence("city", "Fictional City"),
            _evidence("state", "WA"),
            _evidence("service_requested", "AC repair"),
            _evidence("customer_segment", "Facility managers"),
            _evidence("explicit_intent", True),
            _evidence("response_method", "Public source native response form"),
            _evidence("publication_date", "2026-11-06"),
            _evidence("open_status", True),
        ],
    )
    result = score_opportunity_preview(
        opportunity, as_of=AS_OF, organization_profile=profile
    )
    segment = next(
        item for item in result.score_components if item.key == "customer_segment"
    )
    assert segment.score == 5
    assert segment.evidence_ids
