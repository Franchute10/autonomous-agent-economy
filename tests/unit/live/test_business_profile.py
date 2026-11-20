from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import cast

import pytest

from aeos.application.live.business_report import (
    build_business_report,
    render_business_report_markdown,
)
from aeos.application.live.profile_assessment import assess_business_profile
from aeos.live.adapters.overpass import (
    OverpassMarketDiscovery,
    build_profile_area_query,
)
from aeos.live.domain import (
    BusinessProfile,
    EvidenceKind,
    InvalidLiveContract,
    MarketEntity,
    MarketEntityType,
    SourceEvidence,
)
from aeos.live.domain.profile import BusinessProfileFixture
from aeos.live.ports import MarketDiscoveryResult
from aeos.live.real_demo import main as real_demo_main

_ROOT = Path(__file__).parents[3]
_PROFILE_PATH = _ROOT / "examples/live/business_profiles/orlando_house_cleaning.json"
_STARTED_AT = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


def _profile(**overrides: object) -> BusinessProfile:
    values = cast(
        dict[str, object],
        json.loads(_PROFILE_PATH.read_text(encoding="utf-8")),
    )
    values.update(overrides)
    return BusinessProfile.from_dict(values)


def test_synthetic_profile_fixture_uses_strict_explicit_envelope() -> None:
    fixture_path = (
        _ROOT / "examples/live/business_profiles/fictional_cleaning_company.json"
    )
    fixture_document = cast(
        dict[str, object], json.loads(fixture_path.read_text(encoding="utf-8"))
    )
    fixture = BusinessProfileFixture.from_dict(fixture_document)

    assert fixture.synthetic_fixture is True
    assert fixture.synthetic_record is True
    assert fixture.business_profile.is_fictional_example is True
    with pytest.raises(InvalidLiveContract, match="unknown business profile field"):
        BusinessProfile.from_dict(fixture_document)

    invalid_profile: dict[str, object] = dict(fixture_document)
    invalid_profile["business_profile"] = {
        **cast(dict[str, object], fixture_document["business_profile"]),
        "unknown_profile_field": "must not be discarded",
    }
    with pytest.raises(InvalidLiveContract, match="unknown business profile field"):
        BusinessProfileFixture.from_dict(invalid_profile)


def _market_entity(
    entity_id: str,
    name: str,
    entity_type: MarketEntityType,
    category: str,
    *,
    fields: tuple[tuple[str, str | int | float | bool], ...] = (),
) -> tuple[MarketEntity, tuple[SourceEvidence, ...]]:
    values = (
        ("name", name),
        ("category", category),
        ("city", "Orlando"),
        ("state", "Example Region"),
        *fields,
    )
    evidence = tuple(
        SourceEvidence(
            evidence_id=f"{entity_id}:{field}:{index}",
            kind=EvidenceKind.OBSERVED,
            subject=name,
            field=field,
            value=value,
            source_name="Simulated OpenStreetMap listing",
            source_url=f"https://www.openstreetmap.org/node/{entity_id.split(':')[-1]}",
            retrieved_at=_STARTED_AT,
            excerpt=f"Simulated source field {field}={value}.",
            owner_entity_id=entity_id,
        )
        for index, (field, value) in enumerate(values)
    )
    services = tuple(
        str(value) for field, value in fields if field in {"services", "service"}
    )
    return (
        MarketEntity(
            entity_id=entity_id,
            name=name,
            entity_type=entity_type,
            category=category,
            city="Orlando",
            state="Example Region",
            services=services,
            evidence_ids=tuple(item.evidence_id for item in evidence),
        ),
        evidence,
    )


def _discovery(
    *entities: tuple[MarketEntity, tuple[SourceEvidence, ...]],
) -> MarketDiscoveryResult:
    return MarketDiscoveryResult(
        entities=tuple(item[0] for item in entities),
        evidence=tuple(evidence for _, records in entities for evidence in records),
        limitations=("Simulated profile-scoped provider response.",),
    )


def _report(
    profile: BusinessProfile, discovery: MarketDiscoveryResult
) -> dict[str, object]:
    assessment = assess_business_profile(profile, discovery)
    return build_business_report(
        profile=profile,
        discovery=discovery,
        assessment=assessment,
        started_at=_STARTED_AT,
        provider={
            "name": "simulated Overpass",
            "status": (
                "COMPLETED_WITH_RESULTS"
                if discovery.entities
                else "COMPLETED_NO_RESULTS"
            ),
        },
    )


def _section(report: dict[str, object], field: str) -> dict[str, object]:
    return cast(dict[str, object], report[field])


def _records(report: dict[str, object], field: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], report[field])


def _complete_competitor(
    entity_id: str, name: str
) -> tuple[MarketEntity, tuple[SourceEvidence, ...]]:
    return _market_entity(
        entity_id,
        name,
        MarketEntityType.COMPETITOR,
        "House Cleaning",
        fields=(
            ("services", "Recurring residential cleaning"),
            ("customer_segment", "Homeowners"),
            ("business_model", "B2C"),
        ),
    )


def test_profile_loads_optional_fields_and_marks_owner_values_reported() -> None:
    profile = _profile()
    evidence = profile.reported_evidence()

    assert profile.website_url is None
    assert profile.google_business_profile_url is None
    assert profile.phone is None
    assert profile.business_email is None
    assert profile.to_business_input().service_radius_miles == 15
    assert evidence
    assert all(item.kind is EvidenceKind.REPORTED for item in evidence)
    assert any(item.field == "primary_services" for item in evidence)
    assert any(item.field == "products" and item.value == "[]" for item in evidence)
    assert any(
        item.field == "business_model" and item.value == "B2C" for item in evidence
    )


def test_business_report_separates_explicit_reported_and_inferred_profile_evidence() -> (
    None
):
    profile_values = cast(
        dict[str, object],
        json.loads(_PROFILE_PATH.read_text(encoding="utf-8")),
    )
    profile_values["field_statuses"] = {
        "business_name": "REPORTED",
        "country": "INFERRED",
    }
    profile_values["field_evidence"] = [
        {
            "evidence_id": "owner-input:business_name:0",
            "kind": "REPORTED",
            "subject": profile_values["business_name"],
            "field": "business_name",
            "value": profile_values["business_name"],
            "source_name": "Owner-reported test input",
            "source_url": None,
            "retrieved_at": None,
            "excerpt": "Owner-provided value; not independently verified.",
            "confidence": None,
            "assumptions": [],
            "owner_entity_id": None,
        },
        {
            "evidence_id": "geo-input:country:0",
            "kind": "INFERRED",
            "subject": profile_values["business_name"],
            "field": "country",
            "value": profile_values["country"],
            "source_name": "Geographic normalization",
            "source_url": None,
            "retrieved_at": None,
            "excerpt": "Country normalized from the supplied state.",
            "confidence": None,
            "assumptions": ["State normalized to country for the test profile."],
            "owner_entity_id": None,
        },
    ]
    profile = BusinessProfile.from_dict(profile_values)
    report = _report(
        profile,
        MarketDiscoveryResult(
            entities=(), evidence=(), limitations=("No market discovery.",)
        ),
    )
    what_we_know = _section(report, "what_we_know")
    owner_reported = _records(report=what_we_know, field="owner_reported")
    inferred = _records(report=what_we_know, field="inferred_hypotheses")
    profile_evidence = profile.reported_evidence()
    expected_reported = [
        item for item in profile_evidence if item.kind is EvidenceKind.REPORTED
    ]
    markdown = render_business_report_markdown(report)

    assert len(owner_reported) == len(expected_reported)
    assert any(
        item["evidence_id"] == "owner-input:business_name:0" for item in owner_reported
    )
    assert any(item["evidence_id"] == "geo-input:country:0" for item in inferred)
    assert not any(item["kind"] == "INFERRED" for item in owner_reported)
    assert (
        f"El JSON adjunto conserva {len(expected_reported)} datos REPORTED" in markdown
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("business_name", "  "),
        ("city", ""),
        ("service_radius", 0),
        ("primary_services", []),
        ("target_customer_segments", []),
        ("business_model", "C2C"),
        ("service_radius_unit", "yards"),
        ("approximate_employees", -1),
    ),
)
def test_profile_rejects_invalid_essential_and_optional_values(
    field: str, value: object
) -> None:
    with pytest.raises(InvalidLiveContract):
        _profile(**{field: value})


def test_profile_rejects_unknown_fields_and_converts_kilometers() -> None:
    with pytest.raises(InvalidLiveContract, match="unknown business profile field"):
        BusinessProfile.from_dict({"business_name": "Sample", "webiste": "typo"})

    profile = _profile(service_radius=15, service_radius_unit="kilometers")
    assert profile.to_business_input().service_radius_miles == pytest.approx(9.320565)


def test_profile_assessment_preserves_reported_observed_and_inferred_evidence() -> None:
    profile = _profile()
    property_manager = _market_entity(
        "osm:node:20",
        "Orlando Property Group",
        MarketEntityType.POTENTIAL_CUSTOMER,
        "property management",
    )
    assessment = assess_business_profile(profile, _discovery(property_manager))
    kinds_by_field = {(item.field, item.kind) for item in assessment.evidence}

    assert ("business_model", EvidenceKind.REPORTED) in kinds_by_field
    assert ("category", EvidenceKind.OBSERVED) in kinds_by_field
    assert (
        "commercial_relationship_hypothesis",
        EvidenceKind.INFERRED,
    ) in kinds_by_field
    assert all(
        item.kind is not EvidenceKind.OBSERVED for item in profile.reported_evidence()
    )


def test_relationship_groups_keep_customers_partners_suppliers_and_sector_candidates_distinct() -> (
    None
):
    profile = _profile()
    discovery = _discovery(
        _market_entity(
            "osm:node:10",
            "Broad Cleaning Listing",
            MarketEntityType.COMPETITOR,
            "cleaning services",
        ),
        _market_entity(
            "osm:node:20",
            "Property Manager",
            MarketEntityType.POTENTIAL_CUSTOMER,
            "property management",
        ),
        _market_entity(
            "osm:node:30",
            "Real Estate Agency",
            MarketEntityType.PARTNER,
            "real estate agencies",
        ),
        _market_entity(
            "osm:node:40",
            "Cleaning Supply Shop",
            MarketEntityType.SUPPLIER,
            "cleaning supplies",
        ),
    )
    report = _report(profile, discovery)
    competition = _section(report, "competitive_environment")
    benchmark = _section(report, "benchmark")
    opportunities = _section(report, "opportunities")

    assert competition["potential_competitors"] == []
    assert competition["verified_competitors"] == []
    assert len(cast(list[object], competition["same_sector_unqualified"])) == 1
    assert len(_records(report, "potential_customers")) == 1
    assert len(_records(report, "partners_and_channels")) == 2
    assert len(_records(report, "suppliers")) == 1
    assert benchmark["status"] == "INSUFFICIENT_COMPARABLE_DATA"
    assert benchmark["comparison_rows"] == []
    hypotheses = cast(
        list[dict[str, object]], opportunities["entity_research_hypotheses"]
    )
    assert any("buying intent" in str(item["hypothesis"]) for item in hypotheses)
    customer_hypothesis = next(
        item
        for item in hypotheses
        if item["opportunity_type"] == "CUSTOMER_ACQUISITION"
    )
    assert customer_hypothesis["related_entity_id"] == "osm:node:20"
    assert customer_hypothesis["pending_information"]
    assert customer_hypothesis["recommended_action"]
    assert customer_hypothesis["validation_method"]
    assert report["best_next_move"] is not None


def test_competitor_requires_each_observed_fit_dimension_and_rejects_conflicts() -> (
    None
):
    profile = _profile()
    complete = _complete_competitor("osm:node:101", "Comparable Cleaner")
    conflict = _market_entity(
        "osm:node:102",
        "Conflicting Cleaner",
        MarketEntityType.COMPETITOR,
        "House Cleaning",
        fields=(
            ("services", "Recurring residential cleaning"),
            ("customer_segment", "Homeowners"),
            ("business_model", "B2C"),
            ("business_model", "B2B"),
        ),
    )
    report = _report(profile, _discovery(complete, conflict))
    competition = _section(report, "competitive_environment")

    verified = cast(list[dict[str, object]], competition["verified_competitors"])
    potential = cast(list[dict[str, object]], competition["potential_competitors"])
    assert [item["name"] for item in verified] == ["Comparable Cleaner"]
    assert [item["name"] for item in potential] == ["Conflicting Cleaner"]
    assert _section(report, "benchmark")["status"] == "INSUFFICIENT_COMPARABLE_DATA"


def test_two_full_comparables_enable_benchmark_without_invented_metrics() -> None:
    profile = _profile()
    report = _report(
        profile,
        _discovery(
            _complete_competitor("osm:node:201", "First Cleaner"),
            _complete_competitor("osm:node:202", "Second Cleaner"),
        ),
    )

    benchmark = _section(report, "benchmark")
    assert benchmark["status"] == "COMPARABLE_SAMPLE_AVAILABLE"
    assert benchmark["comparison_dimensions"]
    assert benchmark["metrics_compared"] == []
    comparison_rows = cast(list[dict[str, object]], benchmark["comparison_rows"])
    assert len(comparison_rows) == 2
    assert not any("score" in item for item in comparison_rows)


def test_empty_discovery_serializes_truthfully_and_renders_markdown() -> None:
    profile = _profile()
    report = _report(
        profile,
        MarketDiscoveryResult(
            entities=(), evidence=(), limitations=("No simulated results.",)
        ),
    )
    encoded = cast(
        dict[str, object], json.loads(json.dumps(report, ensure_ascii=False))
    )
    markdown = render_business_report_markdown(encoded)

    assert _section(encoded, "profile")["data_status"] == "FICTIONAL_EXAMPLE"
    assert _section(encoded, "benchmark")["status"] == "INSUFFICIENT_COMPARABLE_DATA"
    assert encoded["best_next_move"] is None
    assert "Fictional demonstration profile" in markdown
    assert "INSUFFICIENT_COMPARABLE_DATA" in markdown
    assert "No se encontraron organizaciones" in markdown


def test_report_keeps_reported_hvac_presence_and_failed_market_unknown() -> None:
    business_name = "Sample Climate Systems LLC"
    facebook_url = "https://www.facebook.com/sample-climate-systems"
    sunbiz_url = "https://registry.example/entities/sample-123"
    prior_name_url = "https://registry.example/entities/sample-123/history"
    profile_values: dict[str, object] = {
        "business_name": business_name,
        "legal_name": business_name,
        "registration_id": "SAMPLE-123",
        "legal_entity_status": "ACTIVE",
        "registered_address": "100 Example Way, Sample City, FL 00000",
        "registered_agent": "Example Registered Agent",
        "reinstatement_filed_date": "2026-02-09",
        "reported_prior_names": ["Sample Climate Corp."],
        "industry": "HVAC",
        "vertical": "HVAC",
        "description": "Air conditioning and heating services; operational details are reported and not independently verified.",
        "business_model": "UNKNOWN",
        "country": "United States",
        "city": "Kissimmee",
        "state_region": "Florida",
        "additional_service_areas": ["Central Florida", "Orlando"],
        "primary_services": [
            "Air conditioning installation",
            "Air conditioning maintenance",
            "Air conditioning repair",
            "Heating installation",
            "Heating maintenance",
            "Heating repair",
        ],
        "target_customer_segments": [],
        "service_radius": None,
        "service_radius_unit": None,
        "website_url": None,
        "website_presence": False,
        "google_business_profile_url": None,
        "google_business_profile_present": False,
        "social_media_urls": [facebook_url],
        "instagram_presence": True,
        "instagram_url": None,
        "is_fictional_example": False,
        "field_statuses": {
            "business_name": "REPORTED",
            "legal_name": "REPORTED",
            "registration_id": "REPORTED",
            "legal_entity_status": "REPORTED",
            "registered_address": "REPORTED",
            "registered_agent": "REPORTED",
            "reinstatement_filed_date": "REPORTED",
            "reported_prior_names": "REPORTED",
            "industry": "REPORTED",
            "vertical": "REPORTED",
            "description": "REPORTED",
            "business_model": "UNKNOWN",
            "country": "REPORTED",
            "city": "REPORTED",
            "state_region": "REPORTED",
            "additional_service_areas": "REPORTED",
            "primary_services": "REPORTED",
            "target_customer_segments": "UNKNOWN",
            "website_url": "NOT_PROVIDED",
            "website_presence": "REPORTED",
            "google_business_profile_url": "NOT_PROVIDED",
            "google_business_profile_present": "REPORTED",
            "social_media_urls": "REPORTED",
            "instagram_presence": "REPORTED",
            "instagram_url": "NEEDS_CONFIRMATION",
        },
        "field_evidence": [
            {
                "evidence_id": "owner-facebook-url",
                "kind": "REPORTED",
                "subject": business_name,
                "field": "social_media_urls",
                "value": facebook_url,
                "source_name": "Owner-provided Facebook reference",
                "source_url": facebook_url,
                "retrieved_at": None,
                "excerpt": "URL supplied by the owner; page content was not inspected.",
                "confidence": None,
                "assumptions": [],
                "owner_entity_id": None,
            },
            {
                "evidence_id": "synthetic-registry-id",
                "kind": "REPORTED",
                "subject": business_name,
                "field": "registration_id",
                "value": "SAMPLE-123",
                "source_name": "Registry reference supplied by the user; not retrieved",
                "source_url": sunbiz_url,
                "retrieved_at": None,
                "excerpt": "User-supplied summary of the official registry record.",
                "confidence": None,
                "assumptions": [],
                "owner_entity_id": None,
            },
            {
                "evidence_id": "reported-prior-name",
                "kind": "REPORTED",
                "subject": business_name,
                "field": "reported_prior_names",
                "value": "Sample Climate Corp.",
                "source_name": "Registry search reference supplied by the user; not retrieved",
                "source_url": prior_name_url,
                "retrieved_at": None,
                "excerpt": "Reported as a former name; continuity with this LLC is unconfirmed.",
                "confidence": None,
                "assumptions": [],
                "owner_entity_id": None,
            },
        ],
    }
    profile = BusinessProfile.from_dict(profile_values)
    discovery = MarketDiscoveryResult(
        entities=(),
        evidence=(),
        limitations=("Simulated Overpass failure; no network request was made.",),
    )
    assessment = assess_business_profile(profile, discovery)
    report = build_business_report(
        profile=profile,
        discovery=discovery,
        assessment=assessment,
        started_at=_STARTED_AT,
        provider={
            "name": "OpenStreetMap data via Overpass API",
            "status": "FAILED",
            "attempt_count": 1,
            "retry_count": 0,
            "result_count": None,
        },
    )
    markdown = render_business_report_markdown(report)
    reported = cast(dict[str, list[dict[str, object]]], report["what_we_know"])[
        "owner_reported"
    ]
    facebook = next(item for item in reported if item["field"] == "social_media_urls")
    registry = cast(dict[str, object], report["legal_registry"])
    operations = cast(dict[str, object], report["operational_profile"])
    digital = cast(dict[str, object], operations["digital_presence"])
    counts = cast(
        dict[str, object],
        cast(dict[str, object], report["competitive_environment"])["counts"],
    )
    actions = cast(list[dict[str, object]], report["digital_presence_actions"])

    assert facebook["kind"] == "REPORTED"
    assert facebook["source_url"] == facebook_url
    assert registry["status"] == "ACTIVE"
    assert registry["data_status"] == "REPORTED"
    assert (
        cast(list[dict[str, object]], registry["reported_prior_names"])[0][
            "continuity_confirmed"
        ]
        is False
    )
    assert "synthetic-registry-id" in {
        item["evidence_id"]
        for item in cast(list[dict[str, object]], registry["evidence"])
    }
    registration_evidence = next(
        item
        for item in cast(list[dict[str, object]], registry["evidence"])
        if item["evidence_id"] == "synthetic-registry-id"
    )
    assert registration_evidence["source_url"] == sunbiz_url
    assert "owner-facebook-url" in {
        item["evidence_id"]
        for item in cast(list[dict[str, object]], operations["evidence"])
    }
    assert digital["website_presence"] is False
    assert digital["website_presence_status"] == "REPORTED"
    assert digital["website_inspection_status"] == "NOT_INSPECTED"
    assert digital["google_business_profile_present"] is False
    assert digital["google_business_profile_status"] == "REPORTED"
    assert digital["google_business_profile_inspection_status"] == "NOT_INSPECTED"
    assert digital["instagram_url_status"] == "NEEDS_CONFIRMATION"
    assert all(value is None for value in counts.values())
    assert report["potential_customers"] is None
    assert (
        cast(dict[str, object], report["competitive_environment"])[
            "potential_competitors"
        ]
        is None
    )
    assert cast(dict[str, object], report["market_scope"])["result_available"] is False
    assessment_report = cast(dict[str, object], report["assessment"])
    assessment_position = cast(dict[str, object], assessment_report["market_position"])
    assert assessment_position["comparison_sample_size"] is None
    assert assessment_position["comparable_competitor_ids"] is None
    assert assessment_report["market_entities"] is None
    assert (
        cast(dict[str, object], report["benchmark"])["comparable_competitor_ids"]
        is None
    )
    assert "Revisar la página de Facebook reportada" in {
        str(item["title"]) for item in actions
    }
    assert "Confirmar la URL de Instagram" in {str(item["title"]) for item in actions}
    assert "Confirmar la presencia de un sitio web" in {
        str(item["title"]) for item in actions
    }
    assert "Confirmar la presencia del Perfil de Negocio de Google" in {
        str(item["title"]) for item in actions
    }
    assert "no inspeccionado" in markdown
    assert "la ausencia no está verificada" in markdown.casefold()
    assert "no se pueden determinar los conteos de competidores" in markdown.casefold()
    assert "Competidores potenciales: 0" not in markdown
    assert "continuidad con la LLC no confirmada" in markdown
    assert "Los datos operativos son REPORTED y no se atribuyen a Sunbiz." in markdown
    assert any("market demand are unknown" in item for item in report["limitations"])


def test_report_json_and_markdown_redact_sensitive_source_urls() -> None:
    profile = _profile()
    entity, evidence = _market_entity(
        "osm:node:sensitive",
        "Synthetic Example Cleaner",
        MarketEntityType.SUPPLIER,
        "cleaning",
    )
    secret_evidence = tuple(
        replace(
            item,
            source_url=(item.source_url or "https://fixture.example/synthetic-source")
            + "?access_token=synthetic-test-secret",
        )
        for item in evidence
    )
    report = _report(
        profile,
        MarketDiscoveryResult(
            entities=(entity,),
            evidence=secret_evidence,
            limitations=("Synthetic URL sanitization fixture.",),
        ),
    )
    json_output = json.dumps(report, ensure_ascii=False)
    markdown = render_business_report_markdown(report)

    assert "synthetic-test-secret" not in json_output
    assert "access_token" not in json_output
    assert "synthetic-test-secret" not in markdown


def test_missing_registry_and_unknown_market_status_remain_unknown() -> None:
    profile = _profile(
        legal_name=None,
        legal_entity_status=None,
        registration_id=None,
        registered_address=None,
        registered_agent=None,
        reinstatement_filed_date=None,
        reported_prior_names=[],
        field_statuses={
            "legal_name": "NOT_PROVIDED",
            "legal_entity_status": "NOT_PROVIDED",
            "registration_id": "NOT_PROVIDED",
            "registered_address": "NOT_PROVIDED",
            "registered_agent": "NOT_PROVIDED",
            "reinstatement_filed_date": "NOT_PROVIDED",
            "reported_prior_names": "NOT_PROVIDED",
        },
    )
    discovery = MarketDiscoveryResult(
        entities=(), evidence=(), limitations=("No provider result was supplied.",)
    )
    assessment = assess_business_profile(profile, discovery)
    report = build_business_report(
        profile=profile,
        discovery=discovery,
        assessment=assessment,
        started_at=_STARTED_AT,
        provider={"name": "simulated provider", "status": "UNKNOWN_STATUS"},
    )
    markdown = render_business_report_markdown(report)
    registry = cast(dict[str, object], report["legal_registry"])
    counts = cast(
        dict[str, object],
        cast(dict[str, object], report["competitive_environment"])["counts"],
    )

    assert registry["business_name"] is None
    assert registry["data_status"] == "NOT_PROVIDED"
    assert registry["evidence"] == []
    assert "No legal registry details were supplied" in registry["verification_note"]
    assert all(value is None for value in counts.values())
    assert "conteos de competidores no están disponibles" in markdown.casefold()
    assert "No se encontraron organizaciones" not in markdown
    assert "access_token" not in markdown


def test_profile_query_uses_named_areas_and_does_not_invent_radius_center() -> None:
    query = build_profile_area_query(
        country="United States",
        state_region="Example Region",
        city="Sample City Nine",
        additional_areas=("Clearwater",),
    )

    assert '"name"="United States"' in query
    assert '"name"="Example Region"' in query
    assert '"name"="Sample City Nine"' in query
    assert '"name"="Clearwater"' in query
    assert "around:" not in query
    assert query.count("out center 5;") == 10

    us_alias_query = build_profile_area_query(
        country="US", state_region="FL", city="Orlando"
    )
    assert '"name"="United States"' in us_alias_query
    assert '"name"="Florida"' in us_alias_query
    assert '"name"="Florida"' in build_profile_area_query(
        country="United States", state_region="FL", city="Orlando"
    )


def test_profile_scoped_overpass_integration_uses_one_simulated_request() -> None:
    profile = _profile(
        city="Sample City Nine",
        additional_service_areas=["Clearwater"],
        state_region="Example Region",
    )
    cleaning = {
        "type": "node",
        "id": 301,
        "lat": 27.95,
        "lon": -82.46,
        "tags": {
            "name": "Sample City Nine Cleaning Listing",
            "craft": "cleaning",
            "addr:city": "Sample City Nine",
            "addr:state": "Example Region",
        },
    }
    queries: list[str] = []

    def simulated_transport(
        query: str, endpoint: str, timeout: int, max_bytes: int
    ) -> bytes:
        queries.append(query)
        return json.dumps({"elements": [cleaning]}).encode("utf-8")

    business = profile.to_business_input()
    adapter = OverpassMarketDiscovery(
        transport=simulated_transport,
        business=business,
        service_areas=profile.additional_service_areas or (),
    )
    discovery = adapter.discover_competitors(business)
    assessment = assess_business_profile(profile, discovery)
    report = build_business_report(
        profile=profile,
        discovery=discovery,
        assessment=assessment,
        started_at=_STARTED_AT,
        provider={
            "request_count": adapter.request_count,
            "status": "COMPLETED_WITH_RESULTS",
        },
    )

    assert adapter.request_count == 1
    assert len(queries) == 1
    assert '"name"="Sample City Nine"' in queries[0]
    assert '"name"="Clearwater"' in queries[0]
    assert _section(report, "market_scope")["city"] == "Sample City Nine"
    assert _section(report, "competitive_environment")["same_sector_unqualified"]


def test_profile_cli_writes_json_and_markdown_from_simulated_overpass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {
        "elements": [
            {
                "type": "node",
                "id": 401,
                "lat": 28.54,
                "lon": -81.38,
                "tags": {
                    "name": "Orlando Cleaning Listing",
                    "craft": "cleaning",
                    "addr:city": "Orlando",
                    "addr:state": "Example Region",
                },
            }
        ]
    }
    calls = 0

    def simulated_http(
        query: str, endpoint: str, timeout: int, max_bytes: int
    ) -> bytes:
        nonlocal calls
        calls += 1
        assert '"name"="Orlando"' in query
        return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr("aeos.live.adapters.overpass._http_post", simulated_http)
    exit_code = real_demo_main(
        [
            "--profile",
            str(_PROFILE_PATH),
            "--output-dir",
            str(tmp_path),
            "--confirm-market-discovery",
        ]
    )
    capsys.readouterr()
    report = cast(
        dict[str, object],
        json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8")),
    )
    markdown = next(tmp_path.glob("*.md")).read_text(encoding="utf-8")

    assert exit_code == 1
    assert calls == 1
    assert report["report_id"] == "AEOS-LIVE-002A"
    assert _section(report, "profile")["data_status"] == "FICTIONAL_EXAMPLE"
    assert "INSUFFICIENT_COMPARABLE_DATA" in markdown


def test_unsupported_vertical_is_not_sent_to_overpass() -> None:
    profile = _profile(vertical="HVAC")
    report = _report(
        profile,
        MarketDiscoveryResult(
            entities=(),
            evidence=(),
            limitations=("No documented OSM mapping for HVAC.",),
        ),
    )

    assert _section(report, "competitive_environment")["verified_competitors"] == []
    assert _section(report, "benchmark")["status"] == "INSUFFICIENT_COMPARABLE_DATA"
