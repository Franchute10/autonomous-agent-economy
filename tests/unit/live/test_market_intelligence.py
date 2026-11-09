from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, cast

import pytest

from aeos.application.live.market_intelligence import (
    build_market_report,
    prioritize_opportunities,
    render_combined_market_report_markdown,
    render_market_report_markdown,
)
from aeos.live.adapters.market_research import load_manual_market_research
from aeos.live.adapters.overpass import OverpassRequestError
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind
from aeos.live.domain.market_intelligence import (
    CityMarketResearch,
    CompetitorClassification,
    DemandStatus,
    MarketEvidence,
    MarketOrganization,
    OrganizationRole,
    PublicDemandSignal,
    ResearchStatus,
    SourceCoverage,
    resolve_organization_duplicates,
)
from aeos.live.domain.profile import BusinessProfile, parse_business_profile_document
from aeos.live.ports.discovery import MarketDiscoveryResult
from aeos.live.market_pilot import _add_live_overpass


ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / "examples/live/business_profiles/fictional_cleaning_company.json"
CORPUS_PATH = ROOT / "examples/live/market_research/fictional_cleaning_markets.json"
NOW = datetime(2026, 11, 7, 15, 0, tzinfo=timezone.utc)


def _profile() -> BusinessProfile:
    import json

    return parse_business_profile_document(
        json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    )


def _organization(
    *,
    entity_id: str = "entity-a",
    name: str = "Example Cleaning",
    role: OrganizationRole = OrganizationRole.COMPETITOR,
    website_url: str | None = "https://fixture.example/",
    city: str = "Sample City One",
    services: tuple[str, ...] = ("Residential cleaning",),
    service_areas: tuple[str, ...] = ("Sample City One",),
    buyer_fit_reason: str | None = None,
    referral_reason: str | None = None,
    evidence_ids: tuple[str, ...] = ("evidence-a",),
    buying_intent_evidence_ids: tuple[str, ...] = (),
    vertical: str = "CLEANING_SERVICES",
) -> MarketOrganization:
    return MarketOrganization(
        entity_id=entity_id,
        name=name,
        city=city,
        role=role,
        website_url=website_url,
        public_address=None,
        service_areas=service_areas,
        services=services,
        customer_segments=("Homeowners",),
        vacation_rental_specialization=False,
        recurring_options=(),
        pricing_model=None,
        public_listing_url=None,
        rating_claim=None,
        review_count_claim=None,
        booking_methods=(),
        conversion_channels=("Website",),
        public_contacts=("https://fixture.example/contact",),
        buyer_fit_reason=buyer_fit_reason,
        referral_reason=referral_reason,
        recommended_action="Review the public service fit.",
        validation_question="Do you need cleaning support?",
        evidence_ids=evidence_ids,
        buying_intent_evidence_ids=buying_intent_evidence_ids,
        vertical=vertical,
        synthetic_record=True,
    )


def _evidence(
    *,
    evidence_id: str = "evidence-a",
    entity_id: str = "entity-a",
    field: str = "services",
    source_url: str = "https://fixture.example/",
    retrieved_at: datetime = NOW,
    confidence: float = 0.9,
) -> MarketEvidence:
    return MarketEvidence(
        evidence_id=evidence_id,
        entity_id=entity_id,
        field=field,
        value="residential cleaning",
        source_name="Example official website",
        source_url=source_url,
        retrieved_at=retrieved_at,
        published_at=None,
        classification=EvidenceKind.REPORTED,
        confidence=confidence,
        supporting_information="The public page lists residential cleaning.",
    )


def _signal(
    *,
    signal_id: str = "signal-a",
    city: str = "Sample City One",
    publication_date: date | None = NOW.date(),
    excerpt: str = "Looking for a reliable house cleaner in Sample City One.",
    evidence_id: str = "signal-evidence-a",
) -> PublicDemandSignal:
    return PublicDemandSignal(
        signal_id=signal_id,
        city=city,
        platform="Public Reddit post",
        source_url="https://fixture.example/community/sample-city-one/example/",
        publication_date=publication_date,
        retrieved_at=NOW,
        service_requested="Residential house cleaning",
        supporting_excerpt=excerpt,
        evidence_id=evidence_id,
        synthetic_record=True,
    )


def _market(
    *,
    city: str = "Sample City One",
    organizations: tuple[MarketOrganization, ...] | None = None,
    signals: tuple[PublicDemandSignal, ...] = (),
    evidence: tuple[MarketEvidence, ...] | None = None,
    coverage: tuple[SourceCoverage, ...] | None = None,
) -> CityMarketResearch:
    orgs = organizations or (_organization(city=city),)
    records = evidence or (_evidence(),)
    return CityMarketResearch(
        city=city,
        state="Example Region",
        organizations=orgs,
        demand_signals=signals,
        evidence=records,
        source_coverage=coverage
        or (
            SourceCoverage(
                source_name="Official websites",
                status=ResearchStatus.SUCCEEDED,
                retrieved_at=NOW,
                result_count=len(orgs),
                request_count=0,
                note="Manually reviewed public pages.",
            ),
        ),
        limitations=("Limited manual source sample.",),
    )


def test_fictional_profile_records_owner_facts_with_source_and_confirmation_date() -> (
    None
):
    profile = _profile()

    assert profile.service_radius is None
    assert profile.owner_confirmed_service_areas == (
        "Sample City One",
        "Sample City Two",
    )
    evidence = profile.reported_evidence()
    service_facts = [item for item in evidence if item.field == "primary_services"]
    assert len(service_facts) == 5
    assert all(item.kind is EvidenceKind.REPORTED for item in evidence)
    assert all(
        item.source_name == profile.owner_confirmation_source for item in evidence
    )
    assert all(
        item.retrieved_at == datetime(2026, 11, 7, tzinfo=timezone.utc)
        for item in evidence
    )
    assert all("2026-11-07" in (item.excerpt or "") for item in evidence)
    assert not any(item.field == "city" for item in evidence)


def test_manual_corpus_keeps_sample_markets_independent() -> None:
    snapshot_at, markets = load_manual_market_research(CORPUS_PATH)

    assert snapshot_at == NOW.replace(hour=14, minute=51, second=45)
    assert [market.city for market in markets] == ["Sample City One", "Sample City Two"]
    assert all(
        market.city.casefold()
        not in {"sample city one sample city two", "sample city two sample city one"}
        for market in markets
    )
    assert len(markets[0].demand_signals) == 1
    assert len(markets[1].demand_signals) == 1


def test_live_overpass_runs_one_independent_request_per_city_and_preserves_empty_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_cities: list[str] = []

    class EmptyAdapter:
        request_count = 0

        def __init__(self, *, business: object, **kwargs: object) -> None:
            requested_cities.append(getattr(business, "city"))

        def discover_all(self) -> MarketDiscoveryResult:
            self.request_count += 1
            return MarketDiscoveryResult(entities=(), evidence=())

    monkeypatch.setattr("aeos.live.market_pilot.OverpassMarketDiscovery", EmptyAdapter)
    _, markets = load_manual_market_research(CORPUS_PATH)
    updated = tuple(_add_live_overpass(_profile(), market, NOW) for market in markets)

    assert requested_cities == ["Sample City One", "Sample City Two"]
    for market in updated:
        coverage = next(
            item
            for item in market.source_coverage
            if item.source_name == "OpenStreetMap / Overpass"
        )
        assert coverage.status is ResearchStatus.NO_RESULTS_FOUND
        assert coverage.result_count == 0
        assert coverage.request_count == 1


def test_live_overpass_failure_is_unavailable_and_never_an_empty_market(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TimeoutAdapter:
        request_count = 0

        def __init__(self, **kwargs: object) -> None:
            pass

        def discover_all(self) -> MarketDiscoveryResult:
            self.request_count += 1
            raise OverpassRequestError(
                "bounded provider timeout", category="timeout", phase="request"
            )

    monkeypatch.setattr(
        "aeos.live.market_pilot.OverpassMarketDiscovery", TimeoutAdapter
    )
    _, markets = load_manual_market_research(CORPUS_PATH)
    updated = _add_live_overpass(_profile(), markets[0], NOW)
    coverage = next(
        item
        for item in updated.source_coverage
        if item.source_name == "OpenStreetMap / Overpass"
    )

    assert coverage.status is ResearchStatus.PROVIDER_UNAVAILABLE
    assert coverage.result_count is None
    assert coverage.request_count == 1
    assert any(
        "no significa que no haya negocios locales" in item
        for item in updated.limitations
    )
    assert len(updated.organizations) == len(markets[0].organizations)


def test_duplicate_organizations_merge_by_city_and_website_while_preserving_owners() -> (
    None
):
    first = _organization(entity_id="canonical", evidence_ids=("e1",))
    duplicate = _organization(
        entity_id="duplicate",
        name="EXAMPLE CLEANING LLC",
        website_url="https://www.fixture.example/about",
        services=("Deep cleaning",),
        evidence_ids=("e2",),
    )
    evidence = (
        _evidence(evidence_id="e1", entity_id="canonical"),
        _evidence(evidence_id="e2", entity_id="duplicate", field="pricing"),
    )

    resolved, resolved_evidence = resolve_organization_duplicates(
        (first, duplicate), evidence
    )

    assert len(resolved) == 1
    assert resolved[0].entity_id == "canonical"
    assert resolved[0].services == ("Residential cleaning", "Deep cleaning")
    assert resolved[0].evidence_ids == ("e1", "e2")
    assert {item.entity_id for item in resolved_evidence} == {"canonical"}


def test_competitor_classification_requires_service_and_market_evidence() -> None:
    direct = _organization(
        services=("Residential cleaning", "Vacation rental turnover cleaning")
    )
    indirect = _organization(services=("Commercial office cleaning",))
    generic_category = _organization(services=("Cleaning services",))
    category_only = _organization(services=(), service_areas=("Sample City One",))

    assert (
        direct.competitor_classification is CompetitorClassification.DIRECT_COMPETITOR
    )
    assert (
        indirect.competitor_classification
        is CompetitorClassification.INDIRECT_COMPETITOR
    )
    assert (
        generic_category.competitor_classification
        is CompetitorClassification.UNVERIFIED_CLEANING_BUSINESS
    )
    assert (
        category_only.competitor_classification
        is CompetitorClassification.UNVERIFIED_CLEANING_BUSINESS
    )


@pytest.mark.parametrize(
    ("vertical", "service", "other_vertical"),
    [
        ("HVAC", "air conditioning repair", "CONSTRUCTION"),
        ("CONSTRUCTION", "commercial construction", "HVAC"),
    ],
)
def test_competitor_taxonomy_is_vertical_scoped(
    vertical: str, service: str, other_vertical: str
) -> None:
    competitor = _organization(
        entity_id=f"{vertical.casefold()}-competitor",
        name="Synthetic vertical competitor",
        services=(service,),
        vertical=vertical,
    )
    cross_vertical = replace(competitor, vertical=other_vertical)

    assert (
        competitor.competitor_classification
        is CompetitorClassification.DIRECT_COMPETITOR
    )
    assert (
        cross_vertical.competitor_classification
        is CompetitorClassification.UNVERIFIED_BUSINESS
    )


def test_buyer_fit_does_not_become_buying_intent_and_current_demand_ranks_first() -> (
    None
):
    buyer = _organization(
        entity_id="buyer-1",
        name="Local STR Manager",
        role=OrganizationRole.POTENTIAL_BUYER,
        buyer_fit_reason="Manages vacation properties and coordinates cleaning.",
        evidence_ids=("buyer-evidence",),
    )
    fresh_signal = replace(
        _signal(),
        service_requested="Recurring residential cleaning",
        supporting_excerpt="Looking for recurring residential cleaning in Sample City One.",
    )
    market = _market(
        organizations=(buyer,),
        signals=(fresh_signal,),
        evidence=(
            _evidence(evidence_id="buyer-evidence", entity_id="buyer-1"),
            _evidence(
                evidence_id=fresh_signal.evidence_id,
                entity_id=fresh_signal.signal_id,
                field="demand",
            ),
        ),
    )
    report = cast(
        dict[str, Any],
        build_market_report(_profile(), (market,), owner_evidence=(), snapshot_at=NOW),
    )
    city = report["markets"][0]
    buyer_row = city["potential_buyers"][0]

    assert buyer_row["buyer_fit"] == "BUYER_FIT"
    assert buyer_row["buying_intent"] == "NOT_ESTABLISHED"
    assert city["counts"]["current_buying_intent_signals"] == 0
    assert city["opportunity_queue"][0]["opportunity_type"] == "BUYER_FIT"
    assert prioritize_opportunities(market, as_of=NOW.date())[0].priority.value == "LOW"


def test_explicit_dated_b2b_intent_is_separate_from_buyer_fit_and_expires() -> None:
    buyer = _organization(
        entity_id="buyer-intent-1",
        name="Vacation Manager with an active request",
        role=OrganizationRole.POTENTIAL_BUYER,
        buyer_fit_reason="Manages vacation properties and coordinates cleaning.",
        evidence_ids=("buyer-fit-evidence", "buyer-intent-evidence"),
        buying_intent_evidence_ids=("buyer-intent-evidence",),
    )
    evidence = (
        _evidence(evidence_id="buyer-fit-evidence", entity_id="buyer-intent-1"),
        MarketEvidence(
            evidence_id="buyer-intent-evidence",
            entity_id="buyer-intent-1",
            field="buying_intent",
            value="Publicly requested bids for recurring vacation-rental cleaning.",
            source_name="Public vendor request",
            source_url="https://fixture.example/vendor-request",
            retrieved_at=NOW,
            published_at=NOW.date(),
            classification=EvidenceKind.REPORTED,
            confidence=0.95,
            supporting_information="A dated public post asks providers to submit a cleaning proposal.",
        ),
    )
    market = _market(
        organizations=(buyer,),
        evidence=evidence,
    )
    current_report = cast(
        dict[str, Any],
        build_market_report(_profile(), (market,), owner_evidence=(), snapshot_at=NOW),
    )
    current = current_report["markets"][0]

    assert current["potential_buyers"][0]["buyer_fit"] == "BUYER_FIT"
    assert current["potential_buyers"][0]["buying_intent"] == "INSUFFICIENT_EVIDENCE"
    assert current["counts"]["current_b2b_buying_intent_organizations"] == 0
    assert current["opportunity_queue"][0]["opportunity_type"] == "BUYER_FIT"

    stale_evidence = tuple(
        replace(item, published_at=date(2026, 8, 24))
        if item.evidence_id == "buyer-intent-evidence"
        else item
        for item in evidence
    )
    stale_market = _market(organizations=(buyer,), evidence=stale_evidence)
    stale_report = cast(
        dict[str, Any],
        build_market_report(
            _profile(), (stale_market,), owner_evidence=(), snapshot_at=NOW
        ),
    )
    stale = stale_report["markets"][0]
    assert stale["potential_buyers"][0]["buying_intent"] == "INSUFFICIENT_EVIDENCE"
    assert stale["counts"]["current_b2b_buying_intent_organizations"] == 0
    assert stale["counts"]["historical_b2b_buying_intent_organizations"] == 0


def test_demand_signals_require_an_explicit_request_and_old_requests_are_stale() -> (
    None
):
    with pytest.raises(InvalidLiveContract, match="explicitly request"):
        _signal(excerpt="People talk about cleaning their homes in this forum.")

    stale = _signal(publication_date=date(2026, 8, 24))
    assert stale.status_at(NOW.date()) is DemandStatus.INSUFFICIENT_EVIDENCE
    assert stale.is_actionable(NOW.date()) is False
    assert stale.status_at(date(2026, 9, 10)) is DemandStatus.INSUFFICIENT_EVIDENCE


def test_source_urls_dates_and_evidence_ownership_are_mandatory() -> None:
    with pytest.raises(InvalidLiveContract, match="absolute HTTP"):
        _evidence(source_url="file:///tmp/private")

    with pytest.raises(InvalidLiveContract, match="wrong owner"):
        _market(
            organizations=(_organization(entity_id="different-owner"),),
            evidence=(_evidence(entity_id="entity-a"),),
        )

    with pytest.raises(InvalidLiveContract, match="timezone-aware"):
        _evidence(retrieved_at=datetime(2026, 11, 7))


def test_provider_failure_is_not_an_empty_result_or_market() -> None:
    failure = SourceCoverage(
        source_name="Overpass",
        status=ResearchStatus.PROVIDER_UNAVAILABLE,
        retrieved_at=NOW,
        result_count=None,
        request_count=1,
        note="Request timed out; no retry.",
    )
    empty = SourceCoverage(
        source_name="Overpass",
        status=ResearchStatus.NO_RESULTS_FOUND,
        retrieved_at=NOW,
        result_count=0,
        request_count=1,
        note="Request completed successfully and returned no mapped elements.",
    )
    not_configured = SourceCoverage(
        source_name="Google Places API",
        status=ResearchStatus.PROVIDER_NOT_CONFIGURED,
        retrieved_at=NOW,
        result_count=None,
        request_count=0,
        note="Credential and approved adapter are unavailable.",
    )

    assert failure.result_count is None
    assert empty.result_count == 0
    assert not_configured.status is ResearchStatus.PROVIDER_NOT_CONFIGURED


def test_report_markdown_contains_city_sources_and_honest_counts() -> None:
    snapshot_at, markets = load_manual_market_research(CORPUS_PATH)
    profile = _profile()
    location: dict[str, object] = {
        "value": "Sample City Two, Example Region",
        "status": "WEBSITE_REPORTED",
        "source_url": profile.website_url,
    }
    report = cast(
        dict[str, Any],
        build_market_report(
            profile,
            markets,
            owner_evidence=profile.reported_evidence(),
            snapshot_at=snapshot_at,
            website_reported_location=location,
        ),
    )
    first = report["markets"][0]
    city_markdown = render_market_report_markdown(
        {
            "market": first,
            "snapshot_at": report["snapshot_at"],
            "business_profile": report["business_profile"],
            "owner_confirmation_evidence": report["owner_confirmation_evidence"],
            "website_reported_location": report["website_reported_location"],
        }
    )
    combined_markdown = render_combined_market_report_markdown(report)

    assert "Sample City One, Example Region" in city_markdown
    assert "WEBSITE_REPORTED" in city_markdown
    assert "sample-evidence-" in city_markdown
    assert "sources.example" not in city_markdown
    assert "BUYER_FIT" in city_markdown
    assert "INSUFFICIENT_EVIDENCE" in city_markdown
    assert "Accionable hoy: no" in city_markdown
    assert "No se declara un mercado ganador" in combined_markdown
    assert "Especialización de servicios por ciudad" in combined_markdown
    assert "Precios y modelos publicados" in combined_markdown
    assert "Cobertura y confiabilidad de fuentes" in combined_markdown
    assert "Synthetic Example Organization 11" in combined_markdown
    assert "Synthetic Example Organization 10" in combined_markdown
    assert "Fuentes de las solicitudes comparadas" in combined_markdown
    assert "ninguna aparece como solicitud actual" in combined_markdown
    assert "Sample City Two" in combined_markdown


def test_corpus_keeps_explicit_buying_intent_separate_from_buyer_fit() -> None:
    _, markets = load_manual_market_research(CORPUS_PATH)
    report = cast(
        dict[str, Any],
        build_market_report(_profile(), markets, owner_evidence=(), snapshot_at=NOW),
    )

    assert report["markets"][0]["counts"]["potential_buyers"] == 3
    assert report["markets"][0]["counts"]["current_buying_intent_signals"] == 0
    assert (
        report["markets"][0]["counts"]["current_b2b_buying_intent_organizations"] == 0
    )
    assert report["markets"][0]["counts"]["historical_explicit_demand_signals"] == 0
    assert all(
        organization.synthetic_record
        for market in markets
        for organization in market.organizations
    )
    assert all(
        signal["evidence_classification"] == "SYNTHETIC"
        and signal["still_actionable"] is False
        for market in report["markets"]
        for signal in market["demand_signals"]
    )
    assert report["markets"][1]["counts"]["current_buying_intent_signals"] == 0
    assert (
        report["combined_comparison"]["counts_unique_organizations"]["potential_buyers"]
        == 4
    )
    assert (
        report["combined_comparison"]["counts_unique_organizations"][
            "current_buying_intent_signals"
        ]
        == 0
    )
