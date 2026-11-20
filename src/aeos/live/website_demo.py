"""Single-tenant website demo; its file paths are not tenant authorization."""

import json
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import cast
from urllib.parse import urlsplit

from aeos.application.live.assess_business import assess_business
from aeos.application.live.inspect_business_website import inspect_business_website
from aeos.application.live.resolve_business_locations import (
    MarketSelectionResolution,
    resolve_business_locations,
)
from aeos.application.live.website_report import (
    build_website_report,
    render_website_report_markdown,
)
from aeos.live.adapters.overpass import (
    DEFAULT_ENDPOINT,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_RESPONSE_BYTES,
    PROFILE_APPLICATION_USER_AGENT,
    OverpassMarketDiscovery,
    OverpassRequestError,
    OverpassResponseError,
)
from aeos.live.adapters.website_inspector import (
    WebsiteInspectionError,
    WebsiteInspector,
)
from aeos.live.domain.business import BusinessInput
from aeos.live.domain.evidence import EvidenceKind, SourceEvidence
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


def run_website_inspection_command(website_url: str, *, output_directory: Path) -> int:
    """Inspect a URL and write JSON/Markdown without starting market discovery."""

    started_at = datetime.now(timezone.utc)
    inspection: WebsiteInspectionResult | None = None
    failure_category: str | None = None
    failure_stage: str | None = None
    try:
        inspection = inspect_business_website(WebsiteInspector(), website_url)
        status = "succeeded"
    except WebsiteInspectionError as error:
        status = "failed"
        failure_category = error.category
        failure_stage = error.stage
    report = build_website_report(
        inspection,
        website_url=website_url,
        status=status,
        failure_category=failure_category,
        failure_stage=failure_stage,
    )
    json_path, markdown_path = _write_reports(
        report,
        output_directory,
        started_at,
        _website_slug(website_url),
    )
    print(f"AEOS LIVE website inspection: {status}")
    if failure_category:
        print(f"Failure category: {failure_category}")
    if inspection is not None:
        details = inspection.details
        print(f"Business: {details.business_name if details else 'not identified'}")
        print(f"Pages inspected: {len(inspection.pages)}")
        print(f"Services detected: {len(inspection.services)}")
        print("Detected markets:")
        if inspection.locations:
            for index, candidate in enumerate(inspection.locations, start=1):
                state = f", {candidate.state}" if candidate.state else ""
                print(
                    f"  {index}. {candidate.city}{state} — {candidate.location_type.value}; "
                    f"{candidate.verification_status.value}; owner review required"
                )
        else:
            print("  No geographic candidates found")
        print("Overpass discovery: not started")
        print("Use --website-report with --select-market for a later selection.")
    print(f"JSON report: {json_path.resolve()}")
    print(f"Markdown report: {markdown_path.resolve()}")
    return 0 if inspection is not None else 2


def run_website_market_command(
    website_report_path: Path,
    *,
    selected_markets: list[str],
    corrected_city: str | None,
    corrected_state: str | None,
    postal_code: str | None,
    research_radius: float | None,
    radius_unit: str | None,
    selected_services: tuple[str, ...],
    use_detected_services: bool,
    confirm_discovery: bool,
    output_directory: Path,
) -> int:
    """Save one or more owner selections and optionally run confirmed discovery."""

    if not selected_markets:
        raise ValueError("select at least one market with --select-market")
    if len(selected_markets) > 1 and corrected_city is not None:
        raise ValueError(
            "location corrections must be applied one selected market at a time"
        )
    original_report = json.loads(website_report_path.read_text(encoding="utf-8"))
    if not isinstance(original_report, dict):
        raise ValueError("website report must contain a JSON object")
    report_section = original_report.get("website_inspection")
    if not isinstance(report_section, dict):
        raise ValueError("website report does not contain website_inspection")
    inspection = _inspection_from_report(report_section)
    website_url = str(report_section.get("requested_url") or "")
    resolutions: list[MarketSelectionResolution] = []
    for index, selector in enumerate(selected_markets):
        resolution = resolve_business_locations(
            inspection,
            selected_city=selector,
            corrected_city=corrected_city if index == 0 else None,
            corrected_state=corrected_state if index == 0 else None,
            postal_code=postal_code,
            research_radius=research_radius,
            radius_unit=radius_unit,
            selected_services=selected_services,
            use_detected_services=use_detected_services,
        )
        resolutions.append(resolution)

    status = str(report_section.get("status") or "succeeded")
    report = build_website_report(
        inspection,
        website_url=website_url,
        status=status,
        failure_category=cast(str | None, report_section.get("failure_category")),
        failure_stage=cast(str | None, report_section.get("failure_stage")),
        selection=resolutions[0],
    )
    report["seleccion_del_mercado"] = [
        {
            **_selection_dict(item),
            "discovery_requires_explicit_confirmation": not confirm_discovery,
        }
        for item in resolutions
    ]
    discovery_reports: list[dict[str, object]] = []
    if confirm_discovery:
        for resolution in resolutions:
            discovery_reports.append(
                _discover_selected_market(resolution, inspection, website_url)
            )
        report["investigacion_de_mercado"] = discovery_reports
    started_at = datetime.now(timezone.utc)
    json_path, markdown_path = _write_reports(
        report,
        output_directory,
        started_at,
        _website_slug(website_url) + "-market-selection",
    )
    print(f"AEOS LIVE selected markets: {len(resolutions)}")
    for resolution in resolutions:
        scope = resolution.scope
        print(f"  {scope.city}, {scope.state}: {', '.join(scope.selected_services)}")
        if scope.research_radius is not None:
            print(
                f"  Requested radius: {scope.research_radius:g} {scope.radius_unit}; "
                "Overpass uses named administrative areas and does not enforce it."
            )
    if confirm_discovery:
        print(f"Overpass discovery requests: {len(discovery_reports)}")
    else:
        print(
            "Overpass discovery: not started; pass --confirm-market-discovery to start."
        )
    print(f"JSON report: {json_path.resolve()}")
    print(f"Markdown report: {markdown_path.resolve()}")
    return 0


def _discover_selected_market(
    resolution: MarketSelectionResolution,
    inspection: WebsiteInspectionResult,
    website_url: str,
) -> dict[str, object]:
    scope = resolution.scope
    if not any("clean" in service.casefold() for service in scope.selected_services):
        return {
            "status": "not_searched_unsupported_service",
            "scope": _selection_dict(resolution),
            "limitations": [
                "The current Overpass adapter only supports the House Cleaning pilot mapping; no provider request was sent."
            ],
            "entities": [],
        }
    business_name = (
        inspection.details.business_name
        if inspection.details and inspection.details.business_name
        else "Unidentified business from inspected website"
    )
    radius_miles = scope.research_radius if scope.radius_unit == "miles" else None
    business = BusinessInput(
        business_name=business_name,
        industry="HOUSE_CLEANING",
        city=scope.city,
        state=scope.state,
        country="US",
        service_radius_miles=radius_miles,
        website_url=website_url,
    )
    adapter = OverpassMarketDiscovery(
        endpoint=DEFAULT_ENDPOINT,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes=MAX_RESPONSE_BYTES,
        business=business,
        user_agent=PROFILE_APPLICATION_USER_AGENT,
    )
    limitations = [
        "Overpass searches the selected named administrative area; it does not apply a radius or exact geospatial circle.",
        "The selected service list is retained in the scope, but the current Overpass cleaning tags do not filter each service type.",
    ]
    try:
        discovery = adapter.discover_all()
        status = "succeeded"
        error = None
        limitations.extend(discovery.limitations)
    except (OverpassRequestError, OverpassResponseError) as failure:
        discovery = None
        status = "failed"
        error = {
            "category": failure.category,
            "exception_type": failure.exception_type,
            "message": failure.sanitized_error_message,
            "http_status": failure.http_status,
            "phase": failure.phase,
        }
        limitations.append(
            "No market entities were assessed because the provider request failed."
        )
    if discovery is None:
        return {
            "status": status,
            "scope": _selection_dict(resolution),
            "provider": {
                "name": "OpenStreetMap data via Overpass API",
                "endpoint": DEFAULT_ENDPOINT,
                "request_count": adapter.request_count,
                "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
                "response_size_limit_bytes": MAX_RESPONSE_BYTES,
            },
            "provider_error": error,
            "limitations": list(dict.fromkeys(limitations)),
            "entities": [],
            "evidence": [],
            "assessment": None,
        }
    assessment = assess_business(business, discovery)
    evidence_by_id = {item.evidence_id: item for item in discovery.evidence}
    entities = []
    for entity in discovery.entities:
        entities.append(
            {
                "name": entity.name,
                "entity_type": entity.entity_type.value,
                "category": entity.category,
                "address": entity.address,
                "city": entity.city,
                "state": entity.state,
                "latitude": entity.latitude,
                "longitude": entity.longitude,
                "distance_miles": entity.distance_miles,
                "website": entity.website,
                "phone": entity.phone,
                "evidence": [
                    {
                        "classification": evidence_by_id[item].kind.value,
                        "field": evidence_by_id[item].field,
                        "value": evidence_by_id[item].value,
                        "source_url": evidence_by_id[item].source_url,
                        "excerpt": evidence_by_id[item].excerpt,
                    }
                    for item in entity.evidence_ids
                    if item in evidence_by_id
                ],
            }
        )
    return {
        "status": status,
        "scope": _selection_dict(resolution),
        "provider": {
            "name": "OpenStreetMap data via Overpass API",
            "endpoint": DEFAULT_ENDPOINT,
            "request_count": adapter.request_count,
            "retry_count": 0,
        },
        "limitations": list(dict.fromkeys(limitations)),
        "entities": entities,
        "evidence": [
            {
                "classification": item.kind.value,
                "field": item.field,
                "value": item.value,
                "source_url": item.source_url,
                "excerpt": item.excerpt,
            }
            for item in discovery.evidence
        ],
        "assessment": {
            "status": assessment.status.value,
            "best_next_move": (
                {
                    "selected_opportunity_id": assessment.best_next_move.selected_opportunity_id,
                    "why_this_one": assessment.best_next_move.why_this_one,
                    "first_action": assessment.best_next_move.first_action,
                    "measurement_kpi": assessment.best_next_move.measurement_kpi,
                }
                if assessment.best_next_move
                else None
            ),
        },
    }


def _selection_dict(resolution: MarketSelectionResolution) -> dict[str, object]:
    scope = resolution.scope
    original = resolution.original_candidate
    return {
        "city": scope.city,
        "state": scope.state,
        "postal_code": scope.postal_code,
        "research_radius": scope.research_radius,
        "radius_unit": scope.radius_unit,
        "selected_services": list(scope.selected_services),
        "selected_at": scope.selected_at.isoformat(),
        "owner_confirmed": scope.owner_confirmed,
        "source_evidence_id": scope.source_evidence_id,
        "original_extracted_candidate": _location_dict(original) if original else None,
        "user_corrected_or_added_location": resolution.location_was_corrected_or_added,
        "user_added_services": list(resolution.user_added_services),
    }


def _location_dict(item: LocationCandidate) -> dict[str, object]:
    is_neighborhood = item.location_type is LocationType.NEIGHBORHOOD_MENTION
    is_region = item.location_type is LocationType.REGIONAL_SERVICE_AREA
    return {
        "city": None if is_neighborhood or is_region else item.city,
        "neighborhood": item.city if is_neighborhood else None,
        "region": item.city if is_region else None,
        "place_name": item.city,
        "state": item.state,
        "postal_code": item.postal_code,
        "location_type": item.location_type.value,
        "source_url": item.source_url,
        "supporting_text": item.supporting_text,
        "evidence_classification": item.evidence_classification.value,
        "confidence": item.confidence,
        "verification_status": item.verification_status.value,
        "evidence_id": item.evidence_id,
    }


def _inspection_from_report(report: dict[str, object]) -> WebsiteInspectionResult:
    evidence_raw = cast(list[dict[str, object]], report.get("evidencia_y_fuentes", []))
    evidence: list[SourceEvidence] = []
    for item in evidence_raw:
        timestamp = item.get("retrieved_at")
        evidence.append(
            SourceEvidence(
                evidence_id=str(item["evidence_id"]),
                kind=EvidenceKind(str(item["classification"])),
                subject=str(item["subject"]),
                field=str(item["field"]),
                value=cast(str | int | float | bool | None, item.get("value")),
                source_name="Public business website",
                source_url=cast(str | None, item.get("source_url")),
                retrieved_at=datetime.fromisoformat(str(timestamp))
                if timestamp
                else None,
                excerpt=cast(str | None, item.get("supporting_text")),
                confidence=cast(float | None, item.get("confidence")),
            )
        )
    pages_raw = cast(list[dict[str, object]], report.get("paginas_revisadas", []))
    pages = tuple(_website_page_from_report(item) for item in pages_raw)
    locations_raw = cast(
        list[dict[str, object]], report.get("candidatos_geograficos", [])
    )
    locations = tuple(
        LocationCandidate(
            city=str(
                item.get("place_name")
                or item.get("city")
                or item.get("neighborhood")
                or ""
            ),
            state=cast(str | None, item.get("state")),
            postal_code=cast(str | None, item.get("postal_code")),
            location_type=LocationType(str(item["location_type"])),
            source_url=str(item["source_url"]),
            supporting_text=str(item["supporting_text"]),
            evidence_classification=EvidenceKind(str(item["evidence_classification"])),
            confidence=cast(float, item["confidence"]),
            verification_status=VerificationStatus(str(item["verification_status"])),
            evidence_id=str(item["evidence_id"]),
        )
        for item in locations_raw
    )
    services_raw = cast(list[dict[str, object]], report.get("servicios_detectados", []))
    services = tuple(
        ServiceCandidate(
            service=str(item["service"]),
            source_url=str(item["source_url"]),
            supporting_text=str(item["supporting_text"]),
            evidence_classification=EvidenceKind(str(item["evidence_classification"])),
            confidence=cast(float, item["confidence"]),
            verification_status=VerificationStatus(str(item["verification_status"])),
            evidence_id=str(item["evidence_id"]),
        )
        for item in services_raw
    )
    details: WebsiteInspectionDetails | None = None
    inspected_at = report.get("inspected_at")
    if inspected_at and report.get("final_url"):
        identification = cast(
            dict[str, object], report.get("identificacion_del_negocio", {})
        )
        contact = cast(dict[str, object], report.get("contacto", {}))
        address = cast(dict[str, object], report.get("direccion_empresarial", {}))
        robots = cast(dict[str, object], report.get("robots_txt", {}))
        details = WebsiteInspectionDetails(
            requested_url=str(report.get("requested_url")),
            final_url=str(report.get("final_url")),
            inspected_at=datetime.fromisoformat(str(inspected_at)),
            business_name=cast(str | None, identification.get("nombre_comercial")),
            phone=cast(str | None, contact.get("telefono")),
            email=cast(str | None, contact.get("correo")),
            address=cast(str | None, address.get("direccion")),
            latitude=cast(
                float | None,
                cast(
                    dict[str, object],
                    report.get("coordenadas_declaradas_en_datos_estructurados", {}),
                ).get("latitud"),
            ),
            longitude=cast(
                float | None,
                cast(
                    dict[str, object],
                    report.get("coordenadas_declaradas_en_datos_estructurados", {}),
                ).get("longitud"),
            ),
            opening_hours=tuple(
                cast(
                    list[str],
                    cast(
                        dict[str, object],
                        report.get("otros_datos_estructurados", {}),
                    ).get("horario_publicado", []),
                )
            ),
            same_as=tuple(
                cast(
                    list[str],
                    cast(
                        dict[str, object],
                        report.get("otros_datos_estructurados", {}),
                    ).get("perfiles_mencionados", []),
                )
            ),
            structured_data_types=tuple(
                cast(
                    list[str],
                    cast(
                        dict[str, object],
                        report.get("otros_datos_estructurados", {}),
                    ).get("tipos_schema", []),
                )
            ),
            robots_status=str(robots.get("status", "unknown")),
            robots_sitemaps=tuple(cast(list[str], robots.get("sitemaps", []))),
            robots_restrictions=tuple(
                cast(list[str], robots.get("crawl_restrictions", []))
            ),
            sitemap_urls=tuple(cast(list[str], report.get("sitemaps", []))),
            limitations=tuple(cast(list[str], report.get("limitaciones", []))),
        )
    return WebsiteInspectionResult(
        signals=(),
        evidence=tuple(evidence),
        details=details,
        pages=pages,
        locations=locations,
        services=services,
    )


def _website_page_from_report(item: dict[str, object]) -> WebsitePage:
    rendered = item.get("dom_renderizado")
    rendered_dom = rendered if isinstance(rendered, dict) else {}
    method = str(item.get("metodo_inspeccion", "HTML_ONLY"))
    return WebsitePage(
        url=str(item["url"]),
        status_code=cast(int, item["http_status"]),
        title=cast(str | None, item.get("title_html", item.get("title"))),
        meta_description=cast(
            str | None, item.get("meta_description_html", item.get("meta_description"))
        ),
        h1_headings=tuple(cast(list[str], item.get("h1_html", item.get("h1", [])))),
        h2_headings=tuple(cast(list[str], item.get("html_h2", item.get("h2", [])))),
        main_text=str(item.get("main_text", "")),
        link_texts=tuple(cast(list[str], item.get("link_texts", []))),
        link_urls=tuple(
            cast(list[str], item.get("html_link_urls", item.get("link_urls", [])))
        ),
        inspection_method=method,
        rendered_title=cast(str | None, rendered_dom.get("title")),
        rendered_meta_description=cast(
            str | None, rendered_dom.get("meta_description")
        ),
        rendered_h1_headings=tuple(cast(list[str], rendered_dom.get("h1", []))),
        rendered_h2_headings=tuple(cast(list[str], rendered_dom.get("h2", []))),
        rendered_link_texts=tuple(cast(list[str], rendered_dom.get("link_texts", []))),
        rendered_link_urls=tuple(cast(list[str], rendered_dom.get("link_urls", []))),
        rendered_dom_error=cast(str | None, item.get("dom_renderizado_error")),
        rendered_dom_error_message=cast(
            str | None, item.get("dom_renderizado_error_mensaje")
        ),
    )


def _write_reports(
    report: dict[str, object],
    output_directory: Path,
    started_at: datetime,
    slug: str,
) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    stem = f"{slug}-{stamp}"
    json_path = output_directory / f"{stem}.json"
    markdown_path = output_directory / f"{stem}.md"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_website_report_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _website_slug(url: str) -> str:
    host = urlsplit(url).hostname or "website"
    return re.sub(r"[^a-z0-9]+", "-", host.casefold()).strip("-") or "website"
