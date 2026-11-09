from dataclasses import replace
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any, cast

import pytest

from aeos.application.tenancy import RegisterOrganization, TenantContextResolver
from aeos.core import ActorKind, ActorRef, OrganizationId
from aeos.organization.domain.organization import Organization
from aeos.tenancy.domain import TenantContext, TenantPrincipal

from aeos.application.live.opportunity_activation import (
    attach_research_evidence,
    assess_synthetic_prospect_preview,
    approve_contact as _approve_contact,
    approve_quote as _approve_quote,
    assess_capacity,
    assess_prospect,
    build_activation_report,
    due_followups,
    generate_outreach_materials,
    generate_synthetic_preview_drafts,
    new_pipeline_record,
    operational_capacity_from_profile,
    record_manual_contact,
    record_quote_sent,
    record_response,
    render_activation_report_markdown,
    transition_pipeline,
)
from aeos.live.opportunity_activation import (
    approve_quote as _domain_approve_quote,
    record_quote_sent as _domain_record_quote_sent,
)
from aeos.live.adapters.market_research import load_manual_market_research
from aeos.live.adapters.opportunity_pipeline import LocalOpportunityPipeline
from aeos.live.adapters.prospect_research import (
    build_activation_prospects,
    load_prospect_research,
)
from aeos.live.domain.evidence import EvidenceKind
from aeos.live.domain.opportunity_activation import (
    ActivationProspect,
    CapacityState,
    OperationalCapacity,
    PipelineRecord,
    PipelineStatus,
    ProspectClassification,
    ProspectAssessment,
    ProspectEvidence,
    VendorOnboardingState,
)
from aeos.live.domain.profile import BusinessProfile, parse_business_profile_document


ROOT = Path(__file__).resolve().parents[4]
AS_OF = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


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
        principal, "Synthetic test tenant"
    )
    return TenantContextResolver(organizations).resolve(
        principal, organization.organization_id
    )


def approve_contact(
    record: PipelineRecord, *, approver: TenantContext, note: str, occurred_at: datetime
) -> PipelineRecord:
    """Call production approval with test-only resolved tenant identity."""

    return _approve_contact(
        record, approver=approver, note=note, occurred_at=occurred_at
    )


def approve_quote(
    record: PipelineRecord, *, approver: TenantContext, note: str, occurred_at: datetime
) -> PipelineRecord:
    return _approve_quote(record, approver=approver, note=note, occurred_at=occurred_at)


def _context() -> tuple[
    BusinessProfile,
    tuple[ActivationProspect, ...],
    OperationalCapacity,
    tuple[ProspectAssessment, ...],
]:
    profile = parse_business_profile_document(
        json.loads(
            (
                ROOT / "examples/live/business_profiles/fictional_cleaning_company.json"
            ).read_text(encoding="utf-8")
        )
    )
    _, markets = load_manual_market_research(
        ROOT / "examples/live/market_research/fictional_cleaning_markets.json"
    )
    sources = load_prospect_research(
        ROOT / "examples/live/opportunity_activation/fictional_cleaning_prospects.json"
    )
    prospects = build_activation_prospects(markets, sources)
    capacity = operational_capacity_from_profile(profile)
    assessments = tuple(
        assess_prospect(item, profile, capacity, as_of=AS_OF) for item in prospects
    )
    return profile, prospects, capacity, assessments


def _primary_buyer(assessments: tuple[ProspectAssessment, ...]) -> ProspectAssessment:
    assessment = next(
        item for item in assessments if item.prospect.prospect_id == "buyer-sample-1"
    )
    return assessment


def test_fictional_cleaning_operational_facts_are_owner_reported() -> None:
    profile, _, capacity, _ = _context()
    assert (
        capacity.base_capacity_jobs_per_day,
        capacity.expanded_capacity_jobs_per_day,
    ) == (3, 4)
    assert "subcontractor" in capacity.expansion_dependency.casefold()
    assert capacity.weekend_available is True
    assert capacity.urgent_service_available is True
    assert capacity.legal_business_established_reported is True
    assert capacity.documents_and_insurance_in_order_reported is True
    reported = {item.field: item.kind for item in profile.reported_evidence()}
    assert reported["base_capacity_jobs_per_day"] is EvidenceKind.REPORTED
    assert reported["expanded_capacity_jobs_per_day"] is EvidenceKind.REPORTED
    assert reported["weekend_available"] is EvidenceKind.REPORTED
    assert reported["urgent_service_available"] is EvidenceKind.REPORTED
    assert reported["documentation_and_insurance_in_order"] is EvidenceKind.REPORTED


@pytest.mark.parametrize(
    ("jobs", "expected_state"),
    [
        (None, CapacityState.CAPACITY_NOT_SCOPED),
        (3, CapacityState.BASE_CAPACITY),
        (4, CapacityState.EXPANDED_CAPACITY),
        (5, CapacityState.OVER_CAPACITY),
        (6, CapacityState.OVER_CAPACITY),
    ],
)
def test_capacity_respects_base_and_conditional_maximum(
    jobs: int | None, expected_state: CapacityState
) -> None:
    _, _, facts, _ = _context()
    assessment = assess_capacity(
        facts, expected_jobs_per_day=jobs, evidence_ids=facts.evidence_ids
    )
    assert assessment.state is expected_state
    assert assessment.expanded_capacity_jobs_per_day == 4
    if jobs is not None and jobs > 4:
        assert "no prometa" in assessment.recommendation.casefold()


def test_capacity_expansion_requires_subcontractor_availability() -> None:
    _, _, facts, _ = _context()
    assessment = assess_capacity(
        facts, expected_jobs_per_day=4, evidence_ids=facts.evidence_ids
    )
    assert assessment.state is CapacityState.EXPANDED_CAPACITY
    assert "disponibilidad de subcontratistas" in assessment.recommendation.casefold()
    assert assessment.expansion_dependency == facts.expansion_dependency


def test_geographic_compatibility_uses_confirmed_service_areas() -> None:
    profile, prospects, facts, _ = _context()
    sky = next(item for item in prospects if item.prospect_id == "buyer-sample-3")
    assessment = assess_prospect(
        replace(sky, service_areas=("Unrelated Sample City",)),
        profile,
        facts,
        as_of=AS_OF,
    )
    assert assessment.fit_classification is ProspectClassification.NOT_QUALIFIED
    assert assessment.score_components[1].score == 0
    outside_market = assess_prospect(
        replace(
            next(item for item in prospects if item.prospect_id == "buyer-sample-1"),
            market="Sample City Nine",
        ),
        profile,
        facts,
        as_of=AS_OF,
    )
    assert outside_market.fit_classification is ProspectClassification.NOT_QUALIFIED
    assert outside_market.score_components[1].score == 0


def test_synthetic_prospect_fixture_marks_records_and_reports_evidence() -> None:
    path = (
        ROOT / "examples/live/opportunity_activation/fictional_cleaning_prospects.json"
    )
    payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    prospects = cast(list[dict[str, object]], payload["prospects"])
    evidence = cast(list[dict[str, object]], payload["evidence"])
    assert payload["synthetic_fixture"] is True
    assert all(item["synthetic_record"] is True for item in prospects)
    assert all(item["synthetic_record"] is True for item in evidence)
    assert all(
        item["classification"] == EvidenceKind.REPORTED.value for item in evidence
    )


def test_candidates_preserve_fit_vs_buying_intent_and_overflow() -> None:
    profile, prospects, capacity, assessments = _context()
    results = {item.prospect.prospect_id: item for item in assessments}
    assert len(prospects) == 4
    assert (
        results["buyer-sample-1"].fit_classification
        is ProspectClassification.POTENTIAL_BUYER
    )
    assert all(
        item.fit_classification is not ProspectClassification.QUALIFIED_PROSPECT
        for item in assessments
    )
    assert all(item.buying_intent_status == "NOT_ESTABLISHED" for item in assessments)
    assert all(not item.buying_intent_evidence_ids for item in assessments)
    assert all(item.overflow_hypothesis_only for item in assessments)
    assert all(
        item.opportunity_type.value == "OVERFLOW_CLEANING_PARTNER"
        for item in assessments
    )
    assert all(
        "staffing shortage" not in item.overflow_hypothesis for item in assessments
    )
    preview_prospect = next(
        item for item in prospects if item.prospect_id == "buyer-sample-1"
    )
    preview = assess_synthetic_prospect_preview(
        preview_prospect, profile, capacity, as_of=AS_OF
    )
    assert preview.fit_scenario_matches is True
    assert preview.actionable is False
    assert (
        preview.assessment.fit_classification is ProspectClassification.POTENTIAL_BUYER
    )


def test_synthetic_reported_solicitation_does_not_count_as_buying_intent() -> None:
    profile, _, facts, assessments = _context()
    pmi = _primary_buyer(assessments).prospect
    signal = ProspectEvidence(
        evidence_id="synthetic-cleaning-vendor-request",
        entity_id=pmi.prospect_id,
        field="public_vendor_solicitation",
        value="We are looking for cleaning providers for our Sample City One rentals.",
        source_name="Synthetic owner report",
        source_url="https://sources.example/synthetic/vendor-notice",
        observed_on=AS_OF,
        classification=EvidenceKind.REPORTED,
        confidence=0.99,
        supporting_information="Synthetic reported request for cleaning providers.",
    )
    active = assess_prospect(
        replace(
            pmi,
            evidence=(*pmi.evidence, signal),
            buying_intent_evidence_ids=(signal.evidence_id,),
        ),
        profile,
        facts,
        as_of=AS_OF,
    )
    assert pmi.synthetic_fixture is True
    assert active.buying_intent_status == "NOT_ESTABLISHED"
    assert ProspectClassification.ACTIVE_BUYING_INTENT not in active.classifications


def test_score_evidence_references_resolve_to_source_or_owner_report() -> None:
    profile, _, facts, assessments = _context()
    owner_evidence_ids = {item.evidence_id for item in profile.reported_evidence()}
    for assessment in assessments:
        prospect_evidence_ids = {
            item.evidence_id for item in assessment.prospect.evidence
        }
        for component in assessment.score_components:
            assert (
                set(component.evidence_ids)
                <= prospect_evidence_ids | owner_evidence_ids
            )
        assert set(assessment.capacity.evidence_ids) <= owner_evidence_ids
    assert facts.evidence_ids


def test_synthetic_preview_gets_six_personalized_dual_language_drafts() -> None:
    profile, prospects, capacity, assessments = _context()
    preview_prospect = next(
        item for item in prospects if item.prospect_id == "buyer-sample-1"
    )
    preview = assess_synthetic_prospect_preview(
        preview_prospect, profile, capacity, as_of=AS_OF
    )
    drafts = generate_synthetic_preview_drafts(preview, profile)
    assert set(drafts) == {
        "introductory_email",
        "contact_form_message",
        "telephone_opening",
        "follow_up_email",
        "vendor_onboarding_inquiry",
        "overflow_cleaning_partnership",
    }
    for key, draft in drafts.items():
        assert draft["en"]
        assert draft["es"]
        assert draft["approval_required"] == "true"
        assert draft["auto_send"] == "false"
        assert draft["preview_only"] == "true"
        assert "SYNTHETIC PREVIEW — DO NOT SEND" in draft["en"]
        assert "VISTA PREVIA SINTÉTICA — NO ENVIAR" in draft["es"]
        assert "insurance is in order" not in draft["en"].casefold()
        assert "unlimited" not in draft["en"].casefold()
        assert "4 per day" not in draft["en"] or "conditional maximum" in draft["en"]
    assert "Synthetic Example Organization 11" in drafts["introductory_email"]["en"]
    assert "Sample City One" in drafts["introductory_email"]["en"]
    out_of_area = assess_synthetic_prospect_preview(
        replace(preview_prospect, market="Sample City Nine"),
        profile,
        capacity,
        as_of=AS_OF,
    )
    with pytest.raises(ValueError, match="outside the owner's confirmed service areas"):
        generate_synthetic_preview_drafts(out_of_area, profile)
    with pytest.raises(ValueError, match="isolated preview contract"):
        generate_outreach_materials(assessments[1], profile)


def test_missing_contact_prevents_qualification_and_outreach() -> None:
    profile, _, facts, assessments = _context()
    pmi = _primary_buyer(assessments).prospect
    missing_contact = replace(
        pmi,
        public_contact_channels=(),
        public_contact_details=(),
        vendor_onboarding=VendorOnboardingState.UNKNOWN,
        vendor_onboarding_evidence_ids=(),
    )
    result = assess_prospect(missing_contact, profile, facts, as_of=AS_OF)
    assert result.fit_classification is ProspectClassification.INSUFFICIENT_DATA
    with pytest.raises(ValueError, match="isolated preview contract"):
        generate_outreach_materials(result, profile)


def test_reported_synthetic_sources_do_not_supply_freshness_or_qualification() -> None:
    profile, _, facts, assessments = _context()
    pmi = _primary_buyer(assessments).prospect
    result = assess_prospect(pmi, profile, facts, as_of=AS_OF)
    assert result.stale_evidence_ids == ()
    freshness = next(
        item
        for item in result.score_components
        if item.key == "evidence_quality_freshness"
    )
    assert freshness.score == 0
    assert result.fit_classification is ProspectClassification.POTENTIAL_BUYER
    assert result.buying_intent_status == "NOT_ESTABLISHED"


def test_pipeline_requires_manual_status_approval_before_contact() -> None:
    assessment = _primary_buyer(_context()[3])
    record = new_pipeline_record(assessment)
    assert record.status is PipelineStatus.RESEARCHED
    with pytest.raises(ValueError, match="manual contact requires"):
        record_manual_contact(
            record,
            actor="Owner",
            channel="email",
            details="Sent manually",
            occurred_at=NOW,
            next_action="Wait for reply",
            follow_up_date=None,
        )
    qualified = transition_pipeline(
        record,
        PipelineStatus.QUALIFIED,
        actor="Owner",
        details="Reviewed fit score and vendor route",
        occurred_at=NOW,
    )
    ready = transition_pipeline(
        qualified,
        PipelineStatus.READY_FOR_APPROVAL,
        actor="Owner",
        details="Review the outreach draft",
        occurred_at=NOW,
    )
    with pytest.raises(TypeError):
        cast(Any, _approve_contact)(
            ready,
            approved_by="forged-operator",
            note="Approved this contact",
            occurred_at=NOW,
        )
    approved = approve_contact(
        ready, approver=_tenant_manager(), note="Approved this contact", occurred_at=NOW
    )
    contacted = record_manual_contact(
        approved,
        actor="Owner",
        channel="public vendor email",
        details="Sent the approved introduction manually",
        occurred_at=NOW,
        next_action="Follow up once",
        follow_up_date=date(2026, 11, 16),
    )
    assert contacted.status is PipelineStatus.CONTACTED
    assert contacted.contact_channel == "public vendor email"
    assert contacted.events[-1].action == "manual_contact_recorded"
    assert contacted.follow_up_date == "2026-11-16"
    with pytest.raises(ValueError, match="manual contact requires"):
        record_manual_contact(
            contacted,
            actor="Owner",
            channel="public vendor email",
            details="Followed up manually",
            occurred_at=NOW,
            next_action="Wait for reply",
            follow_up_date=None,
        )
    stale_approval = replace(contacted, status=PipelineStatus.APPROVED_FOR_CONTACT)
    with pytest.raises(ValueError, match="own approval event"):
        record_manual_contact(
            stale_approval,
            actor="Owner",
            channel="public vendor email",
            details="Followed up manually",
            occurred_at=NOW,
            next_action="Wait for reply",
            follow_up_date=None,
        )
    follow_up_approved = approve_contact(
        contacted,
        approver=_tenant_manager(),
        note="Approved the follow-up",
        occurred_at=NOW,
    )
    follow_up = record_manual_contact(
        follow_up_approved,
        actor="Owner",
        channel="public vendor email",
        details="Followed up manually",
        occurred_at=NOW,
        next_action="Wait for reply",
        follow_up_date=None,
    )
    assert follow_up.status is PipelineStatus.CONTACTED


def test_pipeline_records_response_meeting_quote_and_outcome() -> None:
    assessment = _primary_buyer(_context()[3])
    initial = new_pipeline_record(assessment)
    qualified = transition_pipeline(
        initial,
        PipelineStatus.QUALIFIED,
        actor="Owner",
        details="Reviewed",
        occurred_at=NOW,
    )
    ready = transition_pipeline(
        qualified,
        PipelineStatus.READY_FOR_APPROVAL,
        actor="Owner",
        details="Ready",
        occurred_at=NOW,
    )
    approved = approve_contact(
        ready, approver=_tenant_manager(), note="Approved", occurred_at=NOW
    )
    contacted = record_manual_contact(
        approved,
        actor="Owner",
        channel="phone",
        details="Asked about vendor intake",
        occurred_at=NOW,
        next_action="Record the response",
        follow_up_date=None,
    )
    meeting = record_response(
        contacted,
        actor="Owner",
        outcome_status=PipelineStatus.MEETING_SCHEDULED,
        outcome="Local operations call booked",
        occurred_at=NOW,
        next_action="Confirm calendar",
        follow_up_date=date(2026, 11, 10),
    )
    requested = record_response(
        meeting,
        actor="Owner",
        outcome_status=PipelineStatus.QUOTE_REQUESTED,
        outcome="Quote for two specified turnovers requested",
        occurred_at=NOW,
        next_action="Prepare the quote manually",
        follow_up_date=date(2026, 11, 11),
    )
    with pytest.raises(TypeError):
        cast(Any, _domain_approve_quote)(
            requested,
            approved_by="forged-operator",
            note="Untrusted quote approval",
            occurred_at=NOW,
        )
    domain_approved = _domain_approve_quote(
        requested,
        approver=_tenant_manager(),
        note="Approved the quote separately",
        occurred_at=NOW,
    )
    assert domain_approved.status is PipelineStatus.QUOTE_REQUESTED
    assert domain_approved.events[-1].action == "quote_approved"
    with pytest.raises(ValueError, match="already pending"):
        _domain_approve_quote(
            domain_approved,
            approver=_tenant_manager(),
            note="Duplicate quote approval",
            occurred_at=NOW,
        )
    domain_quote = _domain_record_quote_sent(
        domain_approved,
        actor="Synthetic test operator",
        channel="email",
        details="Synthetic manual quote record",
        occurred_at=NOW,
        next_action="Wait for decision",
        follow_up_date=date(2026, 11, 15),
    )
    assert domain_quote.status is PipelineStatus.QUOTE_SENT
    with pytest.raises(ValueError, match="explicit approval"):
        record_quote_sent(
            requested,
            actor="Owner",
            channel="email",
            details="Quote sent outside AEOS",
            occurred_at=NOW,
            next_action="Wait for decision",
            follow_up_date=date(2026, 11, 15),
        )
    quote_approved = approve_quote(
        requested,
        approver=_tenant_manager(),
        note="Approved sending this quote",
        occurred_at=NOW,
    )
    assert quote_approved.status is PipelineStatus.QUOTE_REQUESTED
    assert quote_approved.events[-1].action == "quote_approved"
    with pytest.raises(ValueError, match="already pending"):
        approve_quote(
            quote_approved,
            approver=_tenant_manager(),
            note="Duplicate quote approval",
            occurred_at=NOW,
        )
    quote = record_quote_sent(
        quote_approved,
        actor="Owner",
        channel="email",
        details="Quote sent outside AEOS",
        occurred_at=NOW,
        next_action="Wait for decision",
        follow_up_date=date(2026, 11, 15),
    )
    won = record_response(
        quote,
        actor="Owner",
        outcome_status=PipelineStatus.WON,
        outcome="One-job trial accepted",
        occurred_at=NOW,
        next_action="Confirm service date and capacity",
        follow_up_date=date(2026, 11, 18),
    )
    assert won.status is PipelineStatus.WON
    assert len(won.events) == 10
    assert [item.prospect_id for item in due_followups((won,), as_of=AS_OF)] == []


def test_local_pipeline_round_trip_and_follow_up_query(tmp_path: Path) -> None:
    assessment = _primary_buyer(_context()[3])
    pipeline = LocalOpportunityPipeline(tmp_path / "pipeline.json")
    record = new_pipeline_record(assessment)
    pipeline.put(record)
    assert pipeline.get(record.prospect_id) == record
    contacted = replace(
        record,
        status=PipelineStatus.CONTACTED,
        follow_up_date="2026-11-06",
        contact_channel="phone",
    )
    pipeline.put(contacted)
    assert len(due_followups(pipeline.list_records(), as_of=AS_OF)) == 1
    assert json.loads((tmp_path / "pipeline.json").read_text())["schema_version"] == 1


def test_new_research_evidence_is_appended_without_auto_qualification() -> None:
    initial_assessment = _primary_buyer(_context()[3])
    record = new_pipeline_record(initial_assessment)
    added = ProspectEvidence(
        evidence_id="fresh-source",
        entity_id=initial_assessment.prospect.prospect_id,
        field="market_coverage",
        value="A verified coverage update.",
        source_name="Official source",
        source_url="https://example.com/current",
        observed_on=AS_OF,
        classification=EvidenceKind.OBSERVED,
        confidence=0.9,
        supporting_information="A dated source update.",
    )
    refreshed_prospect = replace(
        initial_assessment.prospect,
        evidence=(*initial_assessment.prospect.evidence, added),
    )
    refreshed = replace(initial_assessment, prospect=refreshed_prospect)
    updated = attach_research_evidence(record, refreshed, occurred_at=NOW)
    assert updated.status is PipelineStatus.RESEARCHED
    assert added.evidence_id in updated.source_evidence_ids
    assert updated.events[-1].action == "research_evidence_added"


def test_activation_report_json_and_markdown_redact_sensitive_source_urls() -> None:
    profile, _, _, assessments = _context()
    original = assessments[0]
    evidence = (
        replace(
            original.prospect.evidence[0],
            source_url=(
                "https://sources.example/prospect?access_token=synthetic-test-secret"
            ),
        ),
        *original.prospect.evidence[1:],
    )
    prospect = replace(original.prospect, evidence=evidence)
    assessment = replace(original, prospect=prospect)
    report = build_activation_report(profile, (assessment,), snapshot_at=AS_OF)
    json_output = json.dumps(report, ensure_ascii=False)
    markdown = render_activation_report_markdown(report)

    assert "synthetic-test-secret" not in json_output
    assert "access_token" not in json_output
    assert "synthetic-test-secret" not in markdown
    assert "access_token" not in markdown


def test_activation_report_is_spanish_traceable_and_does_not_advance_pipeline() -> None:
    profile, _, _, assessments = _context()
    report = build_activation_report(profile, assessments, snapshot_at=AS_OF)
    markdown = render_activation_report_markdown(report)
    assert report["project"] == "AEOS-LIVE-002C"
    assert report["recommended_first_contact"] is None
    prospects = cast(list[dict[str, object]], report["prospects"])
    assert len(prospects) == 4
    assert all(item["synthetic_fixture"] is True for item in prospects)
    assert all(
        item["fit_classification"] != ProspectClassification.QUALIFIED_PROSPECT.value
        for item in prospects
    )
    assert report["outreach_materials"] == {}
    assert report["pipeline"] == []
    assert "Resumen ejecutivo" in markdown
    assert "Intención de compra" in markdown
    assert "Consulte sus fuentes y estados" in markdown
    assert "APPROVED_FOR_CONTACT" in markdown
    assert "ubicación?." not in markdown
    assert "ubicación?" in markdown
    assert "ubicación.." not in markdown
    assert "insurance is in order" not in markdown
