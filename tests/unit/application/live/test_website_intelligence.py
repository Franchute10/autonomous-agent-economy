"""Owner market selection and website report behavior."""

from datetime import datetime, timezone
from dataclasses import replace
import json
from pathlib import Path
from typing import cast

import pytest

from aeos.application.live.resolve_business_locations import (
    MarketSelectionResolution,
    resolve_business_locations,
)
from aeos.application.live.website_report import (
    build_website_report,
    render_website_report_markdown,
)
from aeos.live.website_demo import run_website_market_command
from aeos.live.domain.evidence import EvidenceKind
from aeos.live.domain.location_candidate import (
    LocationCandidate,
    LocationType,
    ServiceCandidate,
    VerificationStatus,
)
from aeos.live.domain.website_inspection import (
    WebsiteInspectionDetails,
    WebsitePage,
)
from aeos.live.ports.website import WebsiteInspectionResult
from aeos.live import website_demo


def _candidate(
    city: str = "Sample City Two",
    state: str | None = "Example Region",
    *,
    location_type: LocationType = LocationType.EXPLICITLY_SERVED_CITY,
    evidence_id: str = "website:area:sample-city-two",
) -> LocationCandidate:
    state_text = f", {state}" if state else ""
    return LocationCandidate(
        city=city,
        state=state,
        postal_code=None,
        location_type=location_type,
        source_url="https://example.com/service-areas",
        supporting_text=f"We serve {city}{state_text}.",
        evidence_classification=EvidenceKind.REPORTED,
        confidence=0.88,
        verification_status=VerificationStatus.WEBSITE_REPORTED,
        evidence_id=evidence_id,
    )


def _service(name: str = "Deep cleaning") -> ServiceCandidate:
    return ServiceCandidate(
        service=name,
        source_url="https://example.com/services",
        supporting_text=f"We offer {name}.",
        evidence_classification=EvidenceKind.REPORTED,
        confidence=0.82,
        verification_status=VerificationStatus.WEBSITE_REPORTED,
        evidence_id="website:service:deep",
    )


def _inspection(
    locations: tuple[LocationCandidate, ...] = (_candidate(),),
    services: tuple[ServiceCandidate, ...] = (_service(),),
) -> WebsiteInspectionResult:
    return WebsiteInspectionResult(
        signals=(),
        evidence=(),
        details=WebsiteInspectionDetails(
            requested_url="https://example.com/",
            final_url="https://example.com/",
            inspected_at=datetime(2026, 11, 6, tzinfo=timezone.utc),
            business_name="Example Cleaning",
            phone="202-555-0100",
            email="hello@example.com",
            address=None,
        ),
        pages=(WebsitePage("https://example.com/", 200, title="Example Cleaning"),),
        locations=locations,
        services=services,
    )


def test_market_selection_creates_owner_confirmed_scope_and_keeps_source_candidate() -> (
    None
):
    original = _candidate()
    result = resolve_business_locations(
        _inspection(),
        selected_city="Sample City Two",
        use_detected_services=True,
        research_radius=15,
        radius_unit="miles",
        clock=lambda: datetime(2026, 11, 6, 12, tzinfo=timezone.utc),
    )

    assert result.scope.city == "Sample City Two"
    assert result.scope.state == "Example Region"
    assert result.scope.research_radius == 15
    assert result.scope.selected_services == ("Deep cleaning",)
    assert result.scope.owner_confirmed is True
    assert result.scope.source_evidence_id == original.evidence_id
    assert result.original_candidate == original
    assert result.location_was_corrected_or_added is False


def test_neighborhood_is_not_serialized_or_selected_as_a_city() -> None:
    neighborhood = _candidate(
        city="Los Rios",
        state="Texas",
        location_type=LocationType.NEIGHBORHOOD_MENTION,
    )
    regional_area = _candidate(
        city="DFW Metro Area",
        state=None,
        location_type=LocationType.REGIONAL_SERVICE_AREA,
        evidence_id="website:area:dfw",
    )
    inspection = _inspection(locations=(neighborhood, regional_area))
    result = resolve_business_locations(
        inspection,
        selected_city="Los Rios",
        selected_state="Texas",
        selected_services=("Kitchen remodeling",),
    )

    assert result.original_candidate is None
    assert result.location_was_corrected_or_added is True
    assert result.scope.source_evidence_id is None
    report = build_website_report(
        inspection,
        website_url="https://example.com/",
        status="succeeded",
    )
    section = cast(dict[str, object], report["website_inspection"])
    candidates = cast(list[dict[str, object]], section["candidatos_geograficos"])
    assert candidates[0]["city"] is None
    assert candidates[0]["neighborhood"] == "Los Rios"
    assert candidates[0]["place_name"] == "Los Rios"
    assert candidates[1]["city"] is None
    assert candidates[1]["region"] == "DFW Metro Area"
    assert "NEIGHBORHOOD_MENTION" in render_website_report_markdown(report)
    assert "REGIONAL_SERVICE_AREA" in render_website_report_markdown(report)


def test_owner_correction_does_not_overwrite_the_extracted_candidate() -> None:
    result = resolve_business_locations(
        _inspection(),
        selected_city="Sample City Two",
        corrected_city="Sample City Three",
        corrected_state="Example Region",
        selected_services=("Deep cleaning", "Office cleaning"),
    )

    assert result.scope.city == "Sample City Three"
    assert result.scope.state == "Example Region"
    assert result.original_candidate == _candidate()
    assert result.scope.source_evidence_id == _candidate().evidence_id
    assert result.location_was_corrected_or_added is True
    assert result.user_added_services == ("Office cleaning",)


def test_owner_can_add_a_new_market_and_service_without_fabricating_website_evidence() -> (
    None
):
    result = resolve_business_locations(
        _inspection(),
        selected_city="Sample City Five",
        corrected_state="Example Region",
        selected_services=("Post-construction cleaning",),
    )

    assert result.scope.city == "Sample City Five"
    assert result.scope.source_evidence_id is None
    assert result.original_candidate is None
    assert result.location_was_corrected_or_added is True
    assert result.user_added_services == ("Post-construction cleaning",)


def test_missing_state_requires_owner_supplied_state_and_unknown_services_are_not_defaulted() -> (
    None
):
    inspection = _inspection(locations=(_candidate(state=None),))
    with pytest.raises(ValueError, match="state is required"):
        resolve_business_locations(
            inspection,
            selected_city="Sample City Two",
            selected_services=("Deep cleaning",),
        )
    with pytest.raises(ValueError, match="at least one service"):
        resolve_business_locations(
            inspection, selected_city="Sample City Two", selected_state="Example Region"
        )


def test_market_radius_and_unit_must_be_supplied_together() -> None:
    with pytest.raises(ValueError, match="research_radius and radius_unit"):
        resolve_business_locations(
            _inspection(),
            selected_city="Sample City Two",
            selected_services=("Deep cleaning",),
            research_radius=10,
        )


def test_market_report_is_spanish_and_separates_original_evidence_from_corrections() -> (
    None
):
    inspection = _inspection()
    resolution = resolve_business_locations(
        inspection,
        selected_city="Sample City Two",
        corrected_city="Sample City Three",
        corrected_state="Example Region",
        selected_services=("Deep cleaning",),
    )
    report = build_website_report(
        inspection,
        website_url="https://example.com/",
        status="succeeded",
        selection=resolution,
    )
    markdown = render_website_report_markdown(report)

    assert "Identificación del negocio" in markdown
    assert "Deep cleaning" in markdown
    selection = cast(dict[str, object], report["seleccion_del_mercado"])
    original = cast(dict[str, object], selection["candidato_original"])
    preserved = cast(
        list[dict[str, object]], selection["evidencia_original_preservada"]
    )
    assert selection["ciudad"] == "Sample City Three"
    assert original["city"] == "Sample City Two"
    assert preserved[0]["city"] == "Sample City Two"


def test_cli_market_selection_round_trip_does_not_start_discovery_without_confirmation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    inspection = _inspection()
    website_report = build_website_report(
        inspection,
        website_url="https://example.com/",
        status="succeeded",
    )
    source_path = tmp_path / "inspection.json"
    source_path.write_text(json.dumps(website_report), encoding="utf-8")

    assert (
        run_website_market_command(
            source_path,
            selected_markets=["Sample City Two"],
            corrected_city=None,
            corrected_state=None,
            postal_code=None,
            research_radius=None,
            radius_unit=None,
            selected_services=(),
            use_detected_services=True,
            confirm_discovery=False,
            output_directory=tmp_path / "output",
        )
        == 0
    )
    assert "Overpass discovery: not started" in capsys.readouterr().out
    result_path = next((tmp_path / "output").glob("*.json"))
    report = cast(
        dict[str, object], json.loads(result_path.read_text(encoding="utf-8"))
    )
    assert "investigacion_de_mercado" not in report
    selected = cast(list[dict[str, object]], report["seleccion_del_mercado"])[0]
    assert selected["city"] == "Sample City Two"
    assert selected["discovery_requires_explicit_confirmation"] is True
    original = cast(dict[str, object], selected["original_extracted_candidate"])
    assert original["evidence_id"] == "website:area:sample-city-two"


def test_cli_starts_only_confirmed_selected_market_discovery(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspection = _inspection()
    source_path = tmp_path / "inspection.json"
    source_path.write_text(
        json.dumps(
            build_website_report(
                inspection,
                website_url="https://example.com/",
                status="succeeded",
            )
        ),
        encoding="utf-8",
    )
    called: list[str] = []

    def fake_discovery(
        resolution: MarketSelectionResolution,
        loaded_inspection: WebsiteInspectionResult,
        website_url: str,
    ) -> dict[str, object]:
        called.append(resolution.scope.city)
        assert loaded_inspection.locations
        assert website_url == "https://example.com/"
        return {"status": "succeeded", "limitations": [], "entities": []}

    monkeypatch.setattr(website_demo, "_discover_selected_market", fake_discovery)
    assert (
        run_website_market_command(
            source_path,
            selected_markets=["Sample City Two"],
            corrected_city=None,
            corrected_state=None,
            postal_code=None,
            research_radius=None,
            radius_unit=None,
            selected_services=("House cleaning",),
            use_detected_services=False,
            confirm_discovery=True,
            output_directory=tmp_path / "confirmed",
        )
        == 0
    )
    assert called == ["Sample City Two"]
    assert "Overpass discovery requests: 1" in capsys.readouterr().out


def test_failed_website_inspection_does_not_claim_unobserved_fields() -> None:
    report = build_website_report(
        None,
        website_url="https://example.com/",
        status="failed",
        failure_category="dns_error",
    )
    inspection = cast(dict[str, object], report["website_inspection"])
    contact = cast(dict[str, object], inspection["contacto"])
    assert contact["clasificacion"] is None
    assert cast(list[str], inspection["informacion_faltante"]) == [
        "No evaluada: la inspección falló antes de recuperar páginas."
    ]
    assert "dns_error" in cast(list[str], inspection["limitaciones"])[0]


def test_failed_inspection_report_omits_sensitive_url_parameters() -> None:
    secret = "report-only-test-secret"
    report = build_website_report(
        None,
        website_url=f"https://fixture.example/?token={secret}#fragment",
        status="failed",
        failure_category="sensitive_url",
    )
    rendered = render_website_report_markdown(report)
    serialized = json.dumps(report, ensure_ascii=False) + rendered
    assert secret not in serialized
    assert "#fragment" not in serialized
    inspection = cast(dict[str, object], report["website_inspection"])
    assert inspection["requested_url"] == "https://fixture.example/"


def test_partial_rendered_dom_report_lists_only_observed_dom_fields() -> None:
    inspection = _inspection(locations=(), services=())
    partial_page = WebsitePage(
        url="https://example.com/",
        status_code=200,
        inspection_method="HTTP_AND_RENDERED_DOM",
        rendered_title="Rendered title",
        rendered_h1_headings=("Observed H1",),
        rendered_dom_error="render_timeout",
        rendered_dom_error_message="Partial DOM after navigation timeout.",
    )
    inspection = replace(inspection, pages=(partial_page,))

    report = build_website_report(
        inspection,
        website_url="https://example.com/",
        status="succeeded",
    )
    website = cast(dict[str, object], report["website_inspection"])
    page = cast(dict[str, object], cast(list[object], website["paginas_revisadas"])[0])
    rendered_dom = cast(dict[str, object], page["dom_renderizado"])

    assert rendered_dom["status"] == "PARTIAL"
    assert rendered_dom["fields_observed"] == ["title", "h1"]
    assert rendered_dom["title"] == "Rendered title"
    assert rendered_dom["h1"] == ["Observed H1"]
