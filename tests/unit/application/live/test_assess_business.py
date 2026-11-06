from dataclasses import replace
from datetime import datetime, timezone
import importlib
import json
from typing import Any

import pytest

from aeos.application.live import (
    assess_business,
    rank_opportunities,
    render_assessment_summary,
)
from aeos.application.live.assess_business import _ACTION_SCORES
from aeos.live.domain import (
    AssessmentStatus,
    BusinessAssessment,
    BusinessInput,
    EvidenceKind,
    InvalidLiveContract,
    MarketEntity,
    MarketEntityType,
    Opportunity,
    OpportunityType,
    SourceEvidence,
    assessment_to_json,
)
from aeos.live.ports import (
    MarketDiscoveryResult,
    WebsiteInspectionResult,
    WebsiteSignal,
)
from aeos.live.demo import main as demo_main

_FIXTURE_TIME = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


def _business(
    *,
    business_name: str = "Sunrise HVAC (Fictional)",
    industry: str = "HVAC",
    city: str = "Orlando",
    state: str = "Florida",
    service_radius_miles: float | None = None,
    website_url: str | None = None,
    has_structured_follow_up: bool | None = None,
) -> BusinessInput:
    return BusinessInput(
        business_name=business_name,
        industry=industry,
        city=city,
        state=state,
        service_radius_miles=service_radius_miles,
        website_url=website_url,
        has_structured_follow_up=has_structured_follow_up,
    )


def _evidence(
    evidence_id: str,
    *,
    subject: str,
    field: str,
    value: str | int | float | bool | None,
    kind: EvidenceKind = EvidenceKind.OBSERVED,
    owner_entity_id: str | None = None,
    confidence: float | None = None,
    assumptions: tuple[str, ...] = (),
) -> SourceEvidence:
    return SourceEvidence(
        evidence_id=evidence_id,
        kind=kind,
        subject=subject,
        field=field,
        value=value,
        source_name="Fictional test fixture",
        retrieved_at=_FIXTURE_TIME,
        excerpt="Fictional fixture evidence used only in a unit test.",
        confidence=confidence,
        assumptions=assumptions,
        owner_entity_id=owner_entity_id,
    )


def _entity(
    entity_id: str,
    name: str,
    entity_type: MarketEntityType,
    category: str,
    *,
    city: str = "Orlando",
    state: str = "Florida",
    rating: float | None = None,
    review_count: int | None = None,
    services: tuple[str, ...] = (),
) -> tuple[MarketEntity, tuple[SourceEvidence, ...]]:
    evidence = [
        _evidence(
            f"{entity_id}:category",
            subject=name,
            field="category",
            value=category,
            owner_entity_id=entity_id,
        ),
        _evidence(
            f"{entity_id}:city",
            subject=name,
            field="city",
            value=city,
            owner_entity_id=entity_id,
        ),
        _evidence(
            f"{entity_id}:state",
            subject=name,
            field="state",
            value=state,
            owner_entity_id=entity_id,
        ),
    ]
    evidence_ids = [item.evidence_id for item in evidence]
    if rating is not None:
        item = _evidence(
            f"{entity_id}:rating",
            subject=name,
            field="rating",
            value=rating,
            owner_entity_id=entity_id,
        )
        evidence.append(item)
        evidence_ids.append(item.evidence_id)
    if review_count is not None:
        item = _evidence(
            f"{entity_id}:reviews",
            subject=name,
            field="review_count",
            value=review_count,
            owner_entity_id=entity_id,
        )
        evidence.append(item)
        evidence_ids.append(item.evidence_id)
    for index, service in enumerate(services):
        item = _evidence(
            f"{entity_id}:service:{index}",
            subject=name,
            field="services",
            value=service,
            owner_entity_id=entity_id,
        )
        evidence.append(item)
        evidence_ids.append(item.evidence_id)
    entity = MarketEntity(
        entity_id=entity_id,
        name=name,
        entity_type=entity_type,
        category=category,
        city=city,
        state=state,
        rating=rating,
        review_count=review_count,
        services=services,
        evidence_ids=tuple(evidence_ids),
    )
    return entity, tuple(evidence)


def _discovery(
    *entity_fixtures: tuple[MarketEntity, tuple[SourceEvidence, ...]],
    limitations: tuple[str, ...] = (),
) -> MarketDiscoveryResult:
    return MarketDiscoveryResult(
        entities=tuple(item[0] for item in entity_fixtures),
        evidence=tuple(evidence for item in entity_fixtures for evidence in item[1]),
        limitations=limitations,
    )


def _replace_entity_evidence(
    fixture: tuple[MarketEntity, tuple[SourceEvidence, ...]],
    evidence_id: str,
    **changes: Any,
) -> tuple[MarketEntity, tuple[SourceEvidence, ...]]:
    entity, records = fixture
    updated = tuple(
        replace(item, **changes) if item.evidence_id == evidence_id else item
        for item in records
    )
    return entity, updated


def _website_inspection(
    business: BusinessInput, *, quote_request: bool = False
) -> WebsiteInspectionResult:
    signal = WebsiteSignal(
        field="quote_request_path", value=quote_request, evidence_id="website:quote"
    )
    source = _evidence(
        signal.evidence_id,
        subject=business.business_name,
        field=signal.field,
        value=signal.value,
    )
    return WebsiteInspectionResult(signals=(signal,), evidence=(source,))


def _assert_traceability(assessment: BusinessAssessment) -> None:
    evidence_by_id = {item.evidence_id: item for item in assessment.evidence}
    for entity in assessment.market_entities:
        assert entity.evidence_ids
        for evidence_id in entity.evidence_ids:
            assert evidence_id in evidence_by_id
            assert evidence_by_id[evidence_id].owner_entity_id == entity.entity_id
    for opportunity in assessment.opportunities:
        assert opportunity.evidence_ids
        assert set(opportunity.evidence_ids) <= set(evidence_by_id)
    if assessment.best_next_move is not None:
        selected = next(
            item
            for item in assessment.opportunities
            if item.opportunity_id == assessment.best_next_move.selected_opportunity_id
        )
        assert set(assessment.best_next_move.evidence_ids) <= set(selected.evidence_ids)


def test_assesses_website_business_and_compares_matching_competitors() -> None:
    business = _business(website_url="https://sunrise-hvac.example")
    competitors = _discovery(
        _entity(
            "comp-a",
            "Fictional Air Pros",
            MarketEntityType.COMPETITOR,
            "HVAC",
            rating=4.2,
            review_count=55,
        ),
        _entity(
            "comp-b",
            "Fictional Cool Co.",
            MarketEntityType.COMPETITOR,
            "HVAC",
            rating=4.4,
            review_count=48,
        ),
    )
    owner_rating = _evidence(
        "business:rating",
        subject=business.business_name,
        field="rating",
        value=4.8,
    )
    owner_review_count = _evidence(
        "business:review-count",
        subject=business.business_name,
        field="review_count",
        value=76,
    )
    website = _website_inspection(business)

    assessment = assess_business(
        business,
        competitors,
        evidence=(owner_rating, owner_review_count),
        website_inspection=website,
    )

    assert assessment.status is AssessmentStatus.READY
    assert assessment.market_position.comparison_sample_size == 2
    assert assessment.market_position.metrics_compared == ("rating", "review_count")
    assert assessment.market_position.relative_strengths
    assert any(
        item.opportunity_type is OpportunityType.WEBSITE_CONVERSION
        for item in assessment.opportunities
    )
    assert assessment.best_next_move is not None
    assert (
        assessment.best_next_move.selected_opportunity_id
        == "website-conversion-friction"
    )
    _assert_traceability(assessment)


def test_business_without_website_gets_market_opportunities_without_website_penalty() -> (
    None
):
    business = _business(
        business_name="Clear Day Cleaning (Fictional)",
        industry="House Cleaning",
        has_structured_follow_up=False,
        service_radius_miles=15,
    )
    discovery = _discovery(
        _entity(
            "prospect-a",
            "Fictional Apartment Group",
            MarketEntityType.POTENTIAL_CUSTOMER,
            "apartment community",
        ),
        _entity(
            "prospect-b",
            "Fictional Rental Managers",
            MarketEntityType.POTENTIAL_CUSTOMER,
            "vacation rental managers",
        ),
        _entity(
            "partner-a",
            "Fictional Move Team",
            MarketEntityType.PARTNER,
            "moving company",
        ),
    )

    assessment = assess_business(business, discovery)

    assert assessment.status is AssessmentStatus.READY
    assert assessment.business.website_url is None
    assert {item.opportunity_type for item in assessment.opportunities} >= {
        OpportunityType.FOLLOW_UP,
        OpportunityType.CUSTOMER_ACQUISITION,
        OpportunityType.PARTNERSHIP,
    }
    assert all(
        item.opportunity_type is not OpportunityType.WEBSITE_CONVERSION
        for item in assessment.opportunities
    )
    website_coverage = next(
        item
        for item in assessment.market_position.data_coverage
        if item.signal == "website_status"
    )
    assert "absence is not confirmed" in (website_coverage.notes or "")
    assert all(item.kind is not EvidenceKind.ESTIMATED for item in assessment.evidence)
    _assert_traceability(assessment)


def test_limited_business_input_returns_insufficient_data_and_next_information() -> (
    None
):
    assessment = assess_business(_business(), _discovery())

    assert assessment.status is AssessmentStatus.INSUFFICIENT_DATA
    assert assessment.opportunities == ()
    assert assessment.best_next_move is None
    assert any(
        "does not support a defensible" in item for item in assessment.limitations
    )
    summary = render_assessment_summary(assessment)
    assert "INSUFFICIENT_DATA" in summary
    assert "Useful next information to collect" in summary
    assert "does not establish that the business has no website" in summary


def test_small_competitor_sample_is_reported_without_a_benchmark_score() -> None:
    business = _business()
    single_competitor = _discovery(
        _entity(
            "comp-only",
            "Fictional Solo HVAC",
            MarketEntityType.COMPETITOR,
            "HVAC",
            rating=4.4,
        )
    )
    own_rating = _evidence(
        "business:rating",
        subject=business.business_name,
        field="rating",
        value=4.8,
    )

    assessment = assess_business(business, single_competitor, evidence=(own_rating,))

    assert assessment.market_position.comparison_sample_size == 1
    assert assessment.market_position.metrics_compared == ()
    assert assessment.market_position.relative_strengths == ()
    assert any(
        "Fewer than two comparable" in item
        for item in assessment.market_position.limitations
    )


def test_identifies_partner_and_supplier_routes_without_claiming_a_relationship_or_savings() -> (
    None
):
    business = _business(
        business_name="Clear Day Cleaning (Fictional)", industry="House Cleaning"
    )
    discovery = _discovery(
        _entity(
            "partner-a",
            "Fictional Realty Group",
            MarketEntityType.PARTNER,
            "real estate agency",
        ),
        _entity(
            "supplier-a",
            "Fictional Janitorial Supply",
            MarketEntityType.SUPPLIER,
            "janitorial supply",
        ),
        _entity(
            "supplier-b",
            "Fictional Cleaning Distributor",
            MarketEntityType.SUPPLIER,
            "cleaning supply distributors",
        ),
    )

    assessment = assess_business(business, discovery)

    by_type = {item.opportunity_type: item for item in assessment.opportunities}
    assert OpportunityType.PARTNERSHIP in by_type
    assert OpportunityType.SUPPLIER in by_type
    assert "No referral arrangement" in by_type[OpportunityType.PARTNERSHIP].description
    assert "prices" in by_type[OpportunityType.SUPPLIER].description
    assert "savings" not in by_type[OpportunityType.SUPPLIER].description


def test_inferences_are_explicit_and_prospect_is_not_called_a_qualified_lead() -> None:
    business = _business(
        business_name="Clear Day Cleaning (Fictional)", industry="House Cleaning"
    )
    prospect = _entity(
        "prospect-a",
        "Fictional Property Managers",
        MarketEntityType.POTENTIAL_CUSTOMER,
        "property management company",
    )

    assessment = assess_business(business, _discovery(prospect))

    inference = next(
        item for item in assessment.evidence if item.kind is EvidenceKind.INFERRED
    )
    assert inference.owner_entity_id == "prospect-a"
    assert "No purchasing need" in " ".join(inference.assumptions)
    opportunity = next(
        item
        for item in assessment.opportunities
        if item.opportunity_type is OpportunityType.CUSTOMER_ACQUISITION
    )
    assert "potential fit only" in opportunity.description
    assert "buying intent are not verified" in opportunity.description


def test_evidence_ownership_and_best_next_move_references_are_consistent() -> None:
    business = _business(
        business_name="Clear Day Cleaning (Fictional)",
        industry="House Cleaning",
        has_structured_follow_up=False,
    )
    partner = _entity(
        "partner-a",
        "Fictional Moving Company",
        MarketEntityType.PARTNER,
        "moving company",
    )
    extra_owned = _evidence(
        "partner-a:phone",
        subject="Fictional Moving Company",
        field="phone",
        value="555-0100",
        owner_entity_id="partner-a",
    )

    assessment = assess_business(business, _discovery(partner), evidence=(extra_owned,))

    entity = next(
        item for item in assessment.market_entities if item.entity_id == "partner-a"
    )
    assert extra_owned.evidence_id in entity.evidence_ids
    _assert_traceability(assessment)


def test_identical_inputs_produce_identical_assessment_json() -> None:
    business = _business(has_structured_follow_up=False)
    discovery = _discovery(
        _entity("comp-a", "Fictional HVAC A", MarketEntityType.COMPETITOR, "HVAC"),
        _entity("comp-b", "Fictional HVAC B", MarketEntityType.COMPETITOR, "HVAC"),
    )

    first = assess_business(business, discovery)
    second = assess_business(business, discovery)

    assert assessment_to_json(first) == assessment_to_json(second)


def test_estimated_evidence_is_retained_without_creating_financial_claims() -> None:
    business = _business(
        business_name="Clear Day Cleaning (Fictional)",
        industry="House Cleaning",
        has_structured_follow_up=False,
    )
    estimated = _evidence(
        "owner-estimate",
        subject=business.business_name,
        field="average_job_value",
        value=250.0,
        kind=EvidenceKind.ESTIMATED,
        assumptions=("A fictional planning assumption, not a reported transaction.",),
    )

    assessment = assess_business(business, _discovery(), evidence=(estimated,))

    assert any(item.kind is EvidenceKind.REPORTED for item in assessment.evidence)
    assert any(item.kind is EvidenceKind.ESTIMATED for item in assessment.evidence)
    assert all("$" not in item.description for item in assessment.opportunities)
    assert all(
        "revenue" not in item.description.casefold()
        or "no lost sales or revenue can be calculated" in item.description.casefold()
        for item in assessment.opportunities
    )
    assert all("250.0" not in item.description for item in assessment.opportunities)
    assert assessment.best_next_move is not None
    assert "250.0" not in assessment.best_next_move.first_action
    assert "[ESTIMATED] owner-estimate" in render_assessment_summary(assessment)


def test_equal_priority_opportunities_use_stable_identifier_tie_break() -> None:
    def opportunity(identifier: str) -> Opportunity:
        return Opportunity(
            opportunity_id=identifier,
            opportunity_type=OpportunityType.FOLLOW_UP,
            title="Follow up",
            description="Fixture action.",
            evidence_ids=("e-1",),
            impact=3,
            confidence=3,
            evidence_strength=3,
            executability=3,
            effort=2,
            time_to_value="Unknown",
            recommended_action="Review the process.",
        )

    ranked = rank_opportunities(
        (opportunity("z-opportunity"), opportunity("a-opportunity"))
    )

    assert tuple(item.opportunity_id for item in ranked) == (
        "a-opportunity",
        "z-opportunity",
    )


def test_website_signal_must_match_its_observed_source_evidence() -> None:
    business = _business(website_url="https://sunrise-hvac.example")
    wrong_source = _evidence(
        "website:quote",
        subject=business.business_name,
        field="contact_information",
        value=False,
    )
    website = WebsiteInspectionResult(
        signals=(
            WebsiteSignal(
                field="quote_request_path",
                value=False,
                evidence_id="website:quote",
            ),
        ),
        evidence=(wrong_source,),
    )

    with pytest.raises(InvalidLiveContract, match="conflicts with its source"):
        assess_business(business, _discovery(), website_inspection=website)


def test_duplicate_evidence_ids_are_rejected_before_assessment() -> None:
    business = _business()
    competitor = _entity(
        "comp-a", "Fictional HVAC A", MarketEntityType.COMPETITOR, "HVAC"
    )
    duplicate = competitor[1][0]

    with pytest.raises(InvalidLiveContract, match="duplicate evidence identifier"):
        assess_business(business, _discovery(competitor), evidence=(duplicate,))


def test_unmatched_categories_and_locations_do_not_become_comparables() -> None:
    business = _business(service_radius_miles=10)
    unrelated = _entity(
        "comp-a",
        "Fictional Roofing Company",
        MarketEntityType.COMPETITOR,
        "Roofing",
        city="Miami",
        state="FL",
        rating=5.0,
    )

    assessment = assess_business(business, _discovery(unrelated))

    assert assessment.market_position.comparable_competitor_ids == ()
    assert assessment.market_position.comparison_sample_size == 0


def test_missing_google_profile_url_is_unknown_and_not_an_absence_claim() -> None:
    assessment = assess_business(_business(), _discovery())

    assert all(
        item.opportunity_type is not OpportunityType.LOCAL_VISIBILITY
        for item in assessment.opportunities
    )
    coverage = next(
        item
        for item in assessment.market_position.data_coverage
        if item.signal == "google_business_profile_status"
    )
    assert coverage.available is False
    assert "no absence is assumed" in (coverage.notes or "")


def test_observed_google_profile_absence_supports_a_verify_and_claim_action() -> None:
    business = _business()
    absent_profile = _evidence(
        "business:no-profile",
        subject=business.business_name,
        field="google_business_profile_present",
        value=False,
        kind=EvidenceKind.OBSERVED,
    )

    assessment = assess_business(business, _discovery(), evidence=(absent_profile,))

    visibility = next(
        item
        for item in assessment.opportunities
        if item.opportunity_type is OpportunityType.LOCAL_VISIBILITY
    )
    assert absent_profile.evidence_id in visibility.evidence_ids
    assert "create or claim" in visibility.recommended_action


def test_wrong_evidence_field_does_not_support_prospect_category() -> None:
    business = _business()
    prospect = _entity(
        "prospect-a",
        "Fictional Property Managers",
        MarketEntityType.POTENTIAL_CUSTOMER,
        "property managers",
    )
    mismatched = _replace_entity_evidence(
        prospect, "prospect-a:category", field="phone"
    )

    assessment = assess_business(business, _discovery(mismatched))

    assert all(
        item.opportunity_type is not OpportunityType.CUSTOMER_ACQUISITION
        for item in assessment.opportunities
    )
    assert any(
        "category fit" in item and "missing" in item for item in assessment.limitations
    )


def test_wrong_evidence_value_does_not_support_entity_attribute() -> None:
    business = _business()
    prospect = _entity(
        "prospect-a",
        "Fictional Property Managers",
        MarketEntityType.POTENTIAL_CUSTOMER,
        "property managers",
    )
    mismatched = _replace_entity_evidence(
        prospect, "prospect-a:category", value="roofing suppliers"
    )

    assessment = assess_business(business, _discovery(mismatched))

    assert all(
        item.opportunity_type is not OpportunityType.CUSTOMER_ACQUISITION
        for item in assessment.opportunities
    )
    assert any("value does not match" in item for item in assessment.limitations)


def test_wrong_evidence_subject_does_not_support_entity_attribute() -> None:
    business = _business()
    prospect = _entity(
        "prospect-a",
        "Fictional Property Managers",
        MarketEntityType.POTENTIAL_CUSTOMER,
        "property managers",
    )
    mismatched = _replace_entity_evidence(
        prospect, "prospect-a:category", subject="Different Fictional Company"
    )

    assessment = assess_business(business, _discovery(mismatched))

    assert all(
        item.opportunity_type is not OpportunityType.CUSTOMER_ACQUISITION
        for item in assessment.opportunities
    )
    assert any(
        "not associated with this entity name" in item
        for item in assessment.limitations
    )


def test_fit_evidence_owned_by_another_entity_does_not_promote_prospect() -> None:
    business = _business()
    prospect = _entity(
        "prospect-a",
        "Fictional General Business",
        MarketEntityType.POTENTIAL_CUSTOMER,
        "general business",
    )
    competitor = _entity(
        "competitor-a", "Fictional HVAC Co.", MarketEntityType.COMPETITOR, "HVAC"
    )
    wrong_owner_fit = _evidence(
        "wrong-owner-fit",
        subject="Fictional General Business",
        field="potential_customer_fit",
        value=True,
        owner_entity_id="competitor-a",
    )

    assessment = assess_business(
        business,
        _discovery(prospect, competitor),
        evidence=(wrong_owner_fit,),
    )

    assert all(
        item.opportunity_type is not OpportunityType.CUSTOMER_ACQUISITION
        for item in assessment.opportunities
    )
    prospect_result = next(
        item for item in assessment.market_entities if item.entity_id == "prospect-a"
    )
    assert wrong_owner_fit.evidence_id not in prospect_result.evidence_ids


def test_entity_outside_verified_service_radius_is_not_a_prospect() -> None:
    business = _business(service_radius_miles=25)
    prospect, records = _entity(
        "prospect-a",
        "Fictional Property Managers",
        MarketEntityType.POTENTIAL_CUSTOMER,
        "property managers",
        city="Miami",
    )
    distance = _evidence(
        "prospect-a:distance",
        subject=prospect.name,
        field="distance_miles",
        value=100.0,
        owner_entity_id=prospect.entity_id,
    )
    prospect = replace(
        prospect,
        distance_miles=100.0,
        evidence_ids=(*prospect.evidence_ids, distance.evidence_id),
    )

    assessment = assess_business(business, _discovery((prospect, (*records, distance))))

    assert all(
        item.opportunity_type is not OpportunityType.CUSTOMER_ACQUISITION
        for item in assessment.opportunities
    )
    assert any("distance exceeds" in item for item in assessment.limitations)


def test_website_evidence_from_another_business_is_rejected() -> None:
    business_a = _business(
        business_name="Business A (Fictional)",
        website_url="https://business-a.example",
    )
    business_b = _business(
        business_name="Business B (Fictional)",
        website_url="https://business-b.example",
    )
    signal = WebsiteSignal(
        field="quote_request_path", value=False, evidence_id="business-a:quote"
    )
    source = replace(
        _evidence(
            signal.evidence_id,
            subject=business_a.business_name,
            field=signal.field,
            value=signal.value,
        ),
        source_url=business_a.website_url,
    )
    inspection = WebsiteInspectionResult(signals=(signal,), evidence=(source,))

    with pytest.raises(InvalidLiveContract, match="subject must match"):
        assess_business(business_b, _discovery(), website_inspection=inspection)


def test_invalid_customer_category_is_discovered_but_not_promoted() -> None:
    business = _business()
    prospect = _entity(
        "prospect-a",
        "Fictional Contractor",
        MarketEntityType.POTENTIAL_CUSTOMER,
        "general contractors",
    )

    assessment = assess_business(business, _discovery(prospect))
    summary = render_assessment_summary(assessment)

    assert all(
        item.opportunity_type is not OpportunityType.CUSTOMER_ACQUISITION
        for item in assessment.opportunities
    )
    assert "Potential prospects (not qualified leads)" not in summary
    assert "Other discovered organizations (commercial fit not established)" in summary


def test_partner_missing_category_evidence_is_not_promoted() -> None:
    business = _business()
    partner = _entity(
        "partner-a",
        "Fictional General Contractor",
        MarketEntityType.PARTNER,
        "general contractors",
    )
    mismatched = _replace_entity_evidence(partner, "partner-a:category", field="phone")

    assessment = assess_business(business, _discovery(mismatched))
    summary = render_assessment_summary(assessment)

    assert all(
        item.opportunity_type is not OpportunityType.PARTNERSHIP
        for item in assessment.opportunities
    )
    assert "Possible referral partners (no relationship verified)" not in summary
    assert "Other discovered organizations (commercial fit not established)" in summary


def test_unknown_industry_does_not_infer_customer_partner_or_supplier_fit() -> None:
    business = _business(industry="Unclassified Specialty Service")
    prospect = _entity(
        "prospect-a",
        "Fictional Property Managers",
        MarketEntityType.POTENTIAL_CUSTOMER,
        "property managers",
    )
    partner = _entity(
        "partner-a",
        "Fictional General Contractor",
        MarketEntityType.PARTNER,
        "general contractors",
    )
    supplier = _entity(
        "supplier-a",
        "Fictional Equipment Distributor",
        MarketEntityType.SUPPLIER,
        "equipment distributors",
    )

    assessment = assess_business(business, _discovery(prospect, partner, supplier))

    assert assessment.opportunities == ()
    assert assessment.status is AssessmentStatus.INSUFFICIENT_DATA
    assert any(
        "no declared vertical profile" in item for item in assessment.limitations
    )


def test_single_competitor_requests_more_data_before_comparison() -> None:
    competitor = _entity(
        "comp-only", "Fictional Solo HVAC", MarketEntityType.COMPETITOR, "HVAC"
    )
    assessment = assess_business(_business(), _discovery(competitor))

    next_steps = render_assessment_summary(assessment).split(
        "Useful next information to collect:\n", maxsplit=1
    )[1]
    assert "at least one additional source-backed competitor" in next_steps


def test_empty_website_inspection_is_insufficient_data() -> None:
    business = _business(website_url="https://sunrise-hvac.example")
    assessment = assess_business(
        business,
        _discovery(),
        website_inspection=WebsiteInspectionResult(signals=(), evidence=()),
    )

    coverage = next(
        item
        for item in assessment.market_position.data_coverage
        if item.signal == "website_inspection"
    )
    assert coverage.available is False
    assert "without structured signals" in (coverage.notes or "")
    assert "structured signal-level results" in render_assessment_summary(assessment)


def test_conflicting_profile_presence_requests_reconciliation() -> None:
    business = _business()
    evidence = (
        _evidence(
            "profile-present",
            subject=business.business_name,
            field="google_business_profile_present",
            value=True,
        ),
        _evidence(
            "profile-absent",
            subject=business.business_name,
            field="google_business_profile_present",
            value=False,
        ),
    )
    assessment = assess_business(business, _discovery(), evidence=evidence)
    coverage = next(
        item
        for item in assessment.market_position.data_coverage
        if item.signal == "google_business_profile_status"
    )

    assert all(
        item.opportunity_type is not OpportunityType.LOCAL_VISIBILITY
        for item in assessment.opportunities
    )
    assert "Conflicting" in (coverage.notes or "")
    assert "Reconcile the conflicting source records" in render_assessment_summary(
        assessment
    )


@pytest.mark.parametrize(
    ("field", "values", "coverage_signal"),
    (
        ("rating", (4.1, 4.8), "business_rating"),
        ("review_count", (20, 45), "business_review_count"),
    ),
)
def test_conflicting_target_metrics_request_reconciliation(
    field: str, values: tuple[float | int, float | int], coverage_signal: str
) -> None:
    business = _business()
    evidence = tuple(
        _evidence(
            f"target:{field}:{index}",
            subject=business.business_name,
            field=field,
            value=value,
        )
        for index, value in enumerate(values)
    )

    assessment = assess_business(business, _discovery(), evidence=evidence)
    coverage = next(
        item
        for item in assessment.market_position.data_coverage
        if item.signal == coverage_signal
    )

    assert "Conflicting" in (coverage.notes or "")
    assert field not in assessment.market_position.metrics_compared
    assert "Reconcile the conflicting source records" in render_assessment_summary(
        assessment
    )


def test_conflicting_competitor_metric_is_not_used_in_benchmark() -> None:
    business = _business()
    first, first_records = _entity(
        "comp-a",
        "Fictional HVAC A",
        MarketEntityType.COMPETITOR,
        "HVAC",
        rating=4.2,
    )
    second = _entity(
        "comp-b",
        "Fictional HVAC B",
        MarketEntityType.COMPETITOR,
        "HVAC",
        rating=4.4,
    )
    conflicting_rating = _evidence(
        "comp-a:rating-conflict",
        subject=first.name,
        field="rating",
        value=4.9,
        owner_entity_id=first.entity_id,
    )
    first = replace(
        first,
        evidence_ids=(*first.evidence_ids, conflicting_rating.evidence_id),
    )
    discovery = _discovery((first, (*first_records, conflicting_rating)), second)
    target_rating = _evidence(
        "target:rating",
        subject=business.business_name,
        field="rating",
        value=4.5,
    )

    assessment = assess_business(business, discovery, evidence=(target_rating,))
    coverage = next(
        item
        for item in assessment.market_position.data_coverage
        if item.signal == "competitor_rating"
    )

    assert "Conflicting" in (coverage.notes or "")
    assert "rating" not in assessment.market_position.metrics_compared
    assert any(
        "Conflicting competitor rating" in item for item in assessment.limitations
    )
    assert "Reconcile the conflicting source records" in render_assessment_summary(
        assessment
    )


def test_assessment_with_no_supported_opportunity_is_insufficient_data() -> None:
    assessment = assess_business(_business(), _discovery())

    assert assessment.status is AssessmentStatus.INSUFFICIENT_DATA
    assert assessment.opportunities == ()
    assert assessment.best_next_move is None


def test_best_next_move_explains_score_and_decisive_difference() -> None:
    business = _business(has_structured_follow_up=False)
    website = _website_inspection(business)

    assessment = assess_business(business, _discovery(), website_inspection=website)

    assert assessment.best_next_move is not None
    explanation = assessment.best_next_move.why_this_one
    assert (
        assessment.best_next_move.selected_opportunity_id
        == "website-conversion-friction"
    )
    assert (
        "impact=4, evidence_strength=5, confidence=4, executability=3, effort=3"
        in explanation
    )
    assert "evidence strength is 5 versus 4" in explanation
    assert "not measured financial impact" in explanation


def test_full_assessment_tie_uses_stable_opportunity_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assessment_module = importlib.import_module("aeos.application.live.assess_business")
    action_scores = {
        **_ACTION_SCORES,
        OpportunityType.FOLLOW_UP: (3, 3, 2),
        OpportunityType.LOCAL_VISIBILITY: (3, 3, 2),
    }
    monkeypatch.setattr(assessment_module, "_ACTION_SCORES", action_scores)
    business = _business()
    evidence = (
        _evidence(
            "reported-no-follow-up",
            subject=business.business_name,
            field="has_structured_follow_up",
            value=False,
            kind=EvidenceKind.REPORTED,
        ),
        _evidence(
            "reported-no-profile",
            subject=business.business_name,
            field="google_business_profile_present",
            value=False,
            kind=EvidenceKind.REPORTED,
        ),
    )

    assessment = assess_business(business, _discovery(), evidence=evidence)

    assert tuple(item.opportunity_id for item in assessment.opportunities) == (
        "follow-up-process",
        "local-profile-presence",
    )
    assert assessment.best_next_move is not None
    assert assessment.best_next_move.selected_opportunity_id == "follow-up-process"
    assert "all score components tie" in assessment.best_next_move.why_this_one


def test_demo_json_output_contains_two_fictional_assessments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    demo_main(["--json"])

    payload = json.loads(capsys.readouterr().out)
    assessments = payload["assessments"]
    assert "FICTIONAL" in payload["notice"]
    assert len(assessments) == 2
    assert {item["business"]["industry"] for item in assessments} == {
        "HVAC",
        "House Cleaning",
    }
    assert assessments[0]["opportunities"] != assessments[1]["opportunities"]
