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
        provider={"name": "simulated Overpass"},
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
        provider={"request_count": adapter.request_count},
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
        ["--profile", str(_PROFILE_PATH), "--output-dir", str(tmp_path)]
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
