"""Single-tenant Orlando demo; not a production tenant interface."""

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from typing import cast
from urllib.parse import urlsplit

from aeos.application.live.assess_business import assess_business
from aeos.application.live.business_report import (
    build_business_report,
    render_business_report_markdown,
)
from aeos.application.live.profile_assessment import assess_business_profile
from aeos.live.website_demo import (
    run_website_inspection_command,
    run_website_market_command,
)
from aeos.live.url_diagnosis import run_business_url_diagnosis_command
from aeos.live.adapters.overpass import (
    APPLICATION_USER_AGENT,
    DEFAULT_ENDPOINT,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_RESPONSE_BYTES,
    ORLANDO_LATITUDE,
    ORLANDO_LONGITUDE,
    ORLANDO_RADIUS_MILES,
    PROFILE_APPLICATION_USER_AGENT,
    OverpassMarketDiscovery,
    OverpassRequestError,
    OverpassResponseError,
    profile_category_mappings,
)
from aeos.live.domain import (
    AssessmentStatus,
    BusinessAssessment,
    BusinessInput,
    MarketEntity,
    MarketEntityType,
    InvalidLiveContract,
    SourceEvidence,
    assessment_to_dict,
)
from aeos.live.domain.profile import parse_business_profile_document
from aeos.live.ports import MarketDiscoveryPort, MarketDiscoveryResult

DEFAULT_OUTPUT_DIRECTORY = Path("artifacts/live")
OSM_LICENSE_URL = "https://www.openstreetmap.org/copyright"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run one bounded, live OpenStreetMap/Overpass market search. Profile mode "
            "supports documented cleaning, HVAC, and roofing mappings; no-profile "
            "mode remains the Orlando House Cleaning pilot. The command makes at "
            "most one provider request."
        )
    )
    parser.add_argument("--city", default="Orlando")
    parser.add_argument("--state", default="FL")
    parser.add_argument("--industry", default="HOUSE_CLEANING")
    parser.add_argument(
        "--overpass-endpoint",
        default=os.environ.get("AEOS_OVERPASS_ENDPOINT", DEFAULT_ENDPOINT),
        help=(
            "HTTPS Overpass interpreter endpoint (default: AEOS_OVERPASS_ENDPOINT "
            "or the documented public instance)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help=f"Local report directory (default: {DEFAULT_OUTPUT_DIRECTORY}).",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        help="JSON business profile for contextual market discovery.",
    )
    parser.add_argument(
        "--inspect-website",
        metavar="URL",
        help="Inspect a public business website and write JSON/Markdown reports only.",
    )
    parser.add_argument(
        "--diagnose-url",
        metavar="URL",
        help=(
            "Classify a business URL and produce an evidence-led report. "
            "This route never starts market discovery."
        ),
    )
    parser.add_argument(
        "--website-report",
        type=Path,
        help="Previously generated website inspection JSON for market selection.",
    )
    parser.add_argument(
        "--select-market",
        action="append",
        default=[],
        metavar="CITY",
        help="Select a detected city; repeat to select multiple markets.",
    )
    parser.add_argument(
        "--market-city", help="Correct or add the selected city (single market)."
    )
    parser.add_argument(
        "--market-state",
        help="Owner-supplied state for a corrected or incomplete location.",
    )
    parser.add_argument("--market-postal-code", help="Owner-supplied ZIP/postal code.")
    parser.add_argument(
        "--market-radius",
        type=float,
        help="Optional research radius to record in the scope.",
    )
    parser.add_argument(
        "--radius-unit", choices=("miles", "kilometers"), default="miles"
    )
    parser.add_argument(
        "--service",
        action="append",
        default=[],
        help="Owner-selected service for this scope; repeat for multiple services.",
    )
    parser.add_argument(
        "--use-detected-services",
        action="store_true",
        help="Confirm all website-detected services for the selected scope.",
    )
    parser.add_argument(
        "--confirm-market-discovery",
        action="store_true",
        help=(
            "Explicitly authorize Overpass discovery for a profile or selected "
            "market(s)."
        ),
    )
    return parser


def _run_profile(args: argparse.Namespace) -> int:
    profile_path = cast(Path, args.profile)
    try:
        profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
        profile = parse_business_profile_document(profile_payload)
    except (OSError, json.JSONDecodeError, InvalidLiveContract, ValueError) as error:
        _parser().error(f"could not load business profile: {error}")
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    business = profile.to_business_input()
    endpoint = cast(str, args.overpass_endpoint)
    category_mappings = profile_category_mappings(profile.vertical)
    supported_pilot = bool(category_mappings)
    provider_error: str | None = None
    provider_exception: OverpassRequestError | OverpassResponseError | None = None
    provider_diagnostic: dict[str, object] = {
        "name": "OpenStreetMap data via Overpass API",
        "endpoint": endpoint,
        "endpoint_hostname": urlsplit(endpoint).hostname,
        "application_user_agent": PROFILE_APPLICATION_USER_AGENT,
        "instance_usage_policy_reference": "https://wiki.openstreetmap.org/wiki/Overpass_API",
        "osm_attribution": "© OpenStreetMap contributors",
        "data_license": "Open Database License (ODbL) 1.0",
        "license_url": OSM_LICENSE_URL,
        "request_count": 0,
        "attempt_count": 0,
        "retry_count": 0,
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "response_size_limit_bytes": MAX_RESPONSE_BYTES,
        "api_cost_usd": None,
        "api_cost_note": "No per-request price was published for this listed public instance; actual charge is unknown.",
        "searched_categories": [mapping.label for mapping in category_mappings],
        "category_mapping_references": [
            {"tag": mapping.label, "url": mapping.reference_url}
            for mapping in category_mappings
        ],
    }
    if supported_pilot and args.confirm_market_discovery:
        adapter = OverpassMarketDiscovery(
            endpoint=endpoint,
            timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
            max_response_bytes=MAX_RESPONSE_BYTES,
            business=business,
            service_areas=profile.additional_service_areas or (),
            user_agent=PROFILE_APPLICATION_USER_AGENT,
        )
        try:
            discovery = _merge_port_results(adapter, business)
        except (OverpassRequestError, OverpassResponseError) as error:
            provider_exception = error
            provider_error = error.sanitized_error_message
            discovery = _empty_discovery(
                "No market entities were assessed because the live provider request failed."
            )
        provider_diagnostic.update(
            {
                "request_count": adapter.request_count,
                "attempt_count": adapter.request_count,
                "retry_count": 0,
                "request_elapsed_seconds": round(adapter.request_elapsed_seconds, 3),
                "http_status": (
                    provider_exception.http_status
                    if provider_exception is not None
                    else adapter.last_http_status
                ),
                "failure_category": (
                    provider_exception.category
                    if provider_exception is not None
                    else None
                ),
                "request_reached_http_server": adapter.request_reached_http_server,
                "search_areas": [
                    profile.city,
                    *(profile.additional_service_areas or ()),
                ],
                "area_scope": "Named administrative areas within the supplied state/region and country.",
                "status": (
                    "FAILED"
                    if provider_error
                    else "COMPLETED_WITH_RESULTS"
                    if discovery.entities
                    else "COMPLETED_NO_RESULTS"
                ),
                "result_count": None if provider_error else len(discovery.entities),
                "error": provider_error,
            }
        )
    elif supported_pilot:
        discovery = _empty_discovery(
            "Market discovery was not run because explicit confirmation was not provided."
        )
        provider_diagnostic.update(
            {
                "status": "NOT_RUN",
                "result_count": None,
                "not_run_reason": (
                    "Pass --confirm-market-discovery to authorize the Overpass request."
                ),
                "search_areas": [
                    profile.city,
                    *(profile.additional_service_areas or ()),
                ],
                "area_scope": "Named administrative areas within the supplied state/region and country.",
            }
        )
    else:
        normalized_vertical = profile.vertical.replace("_", " ").casefold()
        if normalized_vertical == "home remodeling":
            unsupported_reason = (
                "HOME_REMODELING is not a declared vertical in the vertical registry, "
                "and the broader CONSTRUCTION taxonomy does not identify residential "
                "remodeling providers or dedicated remodeling suppliers. No documented "
                "Overpass category mapping is available, so no provider request was sent."
            )
        else:
            unsupported_reason = (
                f"No documented Overpass category mapping is available for vertical "
                f"{profile.vertical!r}; no provider request was sent."
            )
        discovery = _empty_discovery(unsupported_reason)
        provider_diagnostic.update(
            {
                "status": "UNSUPPORTED",
                "result_count": None,
                "unsupported_reason": unsupported_reason,
            }
        )

    assessment = assess_business_profile(profile, discovery)
    elapsed = time.monotonic() - started
    provider_diagnostic["elapsed_seconds"] = round(elapsed, 3)
    report = build_business_report(
        profile=profile,
        discovery=discovery,
        assessment=assessment,
        started_at=started_at,
        provider=provider_diagnostic,
        provider_error=provider_error,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^a-z0-9]+", "-", profile.business_name.casefold()).strip("-")
    stem = f"{slug or 'business-profile'}-{stamp}"
    json_path = args.output_dir / f"{stem}.json"
    markdown_path = args.output_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_business_report_markdown(report), encoding="utf-8")
    competition = cast(dict[str, object], report["competitive_environment"])
    discovery_status = str(provider_diagnostic["status"])
    print(f"AEOS LIVE profile assessment: {assessment.status.value}")
    print(f"Business: {profile.business_name}")
    if discovery_status == "NOT_RUN":
        print("Discovery counts (NOT_RUN): unavailable; confirmation was not provided.")
    elif discovery_status == "FAILED":
        print("Discovery counts (FAILED): unavailable; market result is unknown.")
    elif discovery_status == "UNSUPPORTED":
        print(
            "Discovery counts (UNSUPPORTED): not searched; no provider request was sent."
        )
    else:
        result_count = provider_diagnostic["result_count"]
        print(
            f"Discovery counts ({discovery_status}): {result_count} organizations; "
            f"{len(cast(list[object], competition['potential_competitors']))} potential competitors, "
            f"{len(cast(list[object], competition['verified_competitors']))} verified competitors, "
            f"{len(cast(list[object], report['potential_customers']))} potential customers, "
            f"{len(cast(list[object], report['partners_and_channels']))} partners/channels, "
            f"{len(cast(list[object], report['suppliers']))} suppliers"
        )
    print(f"Benchmark: {cast(dict[str, object], report['benchmark'])['status']}")
    print(f"BestNextMove: {report['best_next_move']}")
    attempt_count = cast(int, provider_diagnostic["attempt_count"])
    if discovery_status in {"NOT_RUN", "UNSUPPORTED"}:
        search_detail = "no search sent (0 attempts)"
        provider_label = (
            f"provider: not contacted (configured: {provider_diagnostic['name']})"
        )
    else:
        search_detail = f"attempts: {attempt_count}"
        provider_label = f"provider: {provider_diagnostic['name']}"
    http_status = provider_diagnostic.get("http_status")
    print(
        f"Market discovery: {discovery_status} | {provider_label} | "
        f"{search_detail} | retries: {provider_diagnostic['retry_count']} | "
        f"HTTP status: {http_status if http_status is not None else 'unavailable'}"
    )
    print(f"JSON report: {json_path.resolve()}")
    print(f"Markdown report: {markdown_path.resolve()}")
    if not supported_pilot:
        return 1
    return (
        2
        if provider_error
        else (0 if assessment.status is AssessmentStatus.READY else 1)
    )


def _business_profile() -> BusinessInput:
    return BusinessInput(
        business_name="Unidentified Orlando house-cleaning business (assessment profile only)",
        industry="HOUSE_CLEANING",
        city="Orlando",
        state="Florida",
        country="US",
    )


def _merge_port_results(
    port: MarketDiscoveryPort, business: BusinessInput
) -> MarketDiscoveryResult:
    """Call the four established discovery methods and validate their union."""

    results = (
        port.discover_competitors(business),
        port.discover_potential_customers(business),
        port.discover_partners(business),
        port.discover_suppliers(business),
    )
    entities: dict[str, MarketEntity] = {}
    evidence: dict[str, SourceEvidence] = {}
    limitations: list[str] = []
    for result in results:
        for entity in result.entities:
            existing = entities.get(entity.entity_id)
            if existing is not None and existing != entity:
                raise ValueError(
                    f"Discovery methods returned conflicting data for {entity.entity_id}"
                )
            entities[entity.entity_id] = entity
        for item in result.evidence:
            existing_evidence = evidence.get(item.evidence_id)
            if existing_evidence is not None and existing_evidence != item:
                raise ValueError(
                    f"Discovery methods returned conflicting evidence for {item.evidence_id}"
                )
            evidence[item.evidence_id] = item
        limitations.extend(result.limitations)
    return MarketDiscoveryResult(
        entities=tuple(entities.values()),
        evidence=tuple(evidence.values()),
        limitations=tuple(dict.fromkeys(limitations)),
    )


def _evidence_dict(item: SourceEvidence) -> dict[str, object]:
    return {
        "evidence_id": item.evidence_id,
        "kind": item.kind.value,
        "subject": item.subject,
        "field": item.field,
        "value": item.value,
        "source_name": item.source_name,
        "source_url": item.source_url,
        "retrieved_at": item.retrieved_at.isoformat() if item.retrieved_at else None,
        "excerpt": item.excerpt,
        "assumptions": list(item.assumptions),
        "owner_entity_id": item.owner_entity_id,
    }


def _entity_dict(
    entity: MarketEntity, evidence_by_id: dict[str, SourceEvidence]
) -> dict[str, object]:
    own_evidence = [
        evidence_by_id[evidence_id]
        for evidence_id in entity.evidence_ids
        if evidence_id in evidence_by_id
    ]
    source_urls = list(
        dict.fromkeys(
            item.source_url for item in own_evidence if item.source_url is not None
        )
    )
    return {
        "entity_id": entity.entity_id,
        "provider_identifier": entity.entity_id.removeprefix("osm:"),
        "name": entity.name,
        "entity_type": entity.entity_type.value,
        "category": entity.category,
        "address": entity.address,
        "city": entity.city,
        "state": entity.state,
        "latitude": entity.latitude,
        "longitude": entity.longitude,
        "distance_miles_from_pilot_center": entity.distance_miles,
        "website": entity.website,
        "public_business_phone": entity.phone,
        "services_explicitly_identified": list(entity.services),
        "source_urls": source_urls,
        "evidence": [_evidence_dict(item) for item in own_evidence],
        "classification_limit": _classification_limit(entity),
        "commercial_fit_explanation": _commercial_fit_explanation(entity),
        "confidence_or_qualification": _classification_limit(entity),
        "suggested_first_research_step": _suggested_research_step(entity),
    }


def _classification_limit(entity: MarketEntity) -> str:
    if entity.entity_type is MarketEntityType.COMPETITOR:
        return (
            "Possible cleaning-services competitor; the source tag does not establish "
            "residential house-cleaning service."
        )
    if entity.entity_type is MarketEntityType.POTENTIAL_CUSTOMER:
        return (
            "Potential customer category only; cleaning need, outsourcing, contact "
            "authority, and buying intent are unknown."
        )
    if entity.entity_type is MarketEntityType.PARTNER:
        return (
            "Possible referral/channel fit only; no relationship or mutual customer "
            "overlap is established."
        )
    return "Supplier listing only; product range, availability, prices, and terms are unknown."


def _commercial_fit_explanation(entity: MarketEntity) -> str:
    if entity.entity_type is MarketEntityType.COMPETITOR:
        return (
            "The OSM craft=cleaning tag supports a cleaning-services listing. "
            "Residential house-cleaning scope is unverified, so this is only a "
            "possible competitor."
        )
    if entity.entity_type is MarketEntityType.POTENTIAL_CUSTOMER:
        return (
            "Inference from the OSM property-management category: the organization "
            "may coordinate property cleaning. Service need, outsourcing, decision "
            "authority, and buying intent are unknown."
        )
    if entity.entity_type is MarketEntityType.PARTNER:
        return (
            "Inference from the OSM real-estate category: a referral route may be "
            "worth researching. No relationship or shared customer need is verified."
        )
    return (
        "The OSM cleaning-supplies category establishes a relevant supplier listing. "
        "The actual products and commercial terms are unknown."
    )


def _suggested_research_step(entity: MarketEntity) -> str:
    if entity.entity_type is MarketEntityType.COMPETITOR:
        return "Verify whether residential house cleaning is explicitly offered before benchmarking."
    if entity.entity_type is MarketEntityType.POTENTIAL_CUSTOMER:
        return (
            "Research whether the organization outsources move-out or turnover "
            "cleaning and identify the appropriate commercial contact."
        )
    if entity.entity_type is MarketEntityType.PARTNER:
        return (
            "Research whether the organization coordinates cleaning referrals and "
            "whether a referral discussion would be appropriate."
        )
    return (
        "Compare current product availability, delivery, and terms for the same "
        "frequently purchased items."
    )


def _grouped_entities(
    discovery: MarketDiscoveryResult,
    evidence_by_id: dict[str, SourceEvidence],
) -> dict[str, list[dict[str, object]]]:
    groups = {
        "possible_competitors": MarketEntityType.COMPETITOR,
        "potential_customers": MarketEntityType.POTENTIAL_CUSTOMER,
        "possible_partners": MarketEntityType.PARTNER,
        "suppliers": MarketEntityType.SUPPLIER,
    }
    return {
        group: [
            _entity_dict(entity, evidence_by_id)
            for entity in discovery.entities
            if entity.entity_type is entity_type
        ]
        for group, entity_type in groups.items()
    }


def _target_identification(
    discovery: MarketDiscoveryResult,
    provider_error: str | None = None,
) -> dict[str, object]:
    cleaning_entities = tuple(
        entity
        for entity in discovery.entities
        if entity.entity_type is MarketEntityType.COMPETITOR
    )
    reason = (
        "No source records were returned because the provider request failed; target "
        "identification was not possible. Even if returned, OSM craft=cleaning alone "
        "does not verify residential scope, business independence, or size."
        if provider_error
        else "The searched OSM craft=cleaning tag describes cleaning services broadly "
        "and does not verify house-cleaning scope, business independence, or size. "
        "No target was selected from that evidence."
    )
    return {
        "target_business": None,
        "status": "unavailable",
        "reason": reason,
        "cleaning_service_listings_returned": len(cleaning_entities),
        "target_specific_benchmarking_available": False,
    }


def _provider_diagnostic(
    adapter: OverpassMarketDiscovery,
    error: OverpassRequestError | OverpassResponseError | None,
) -> dict[str, object]:
    return {
        "endpoint_hostname": urlsplit(adapter.endpoint).hostname,
        "attempt_count": adapter.request_count,
        "retry_count": 0,
        "failure_category": error.category if error is not None else None,
        "exception_type": error.exception_type if error is not None else None,
        "sanitized_error_message": (
            error.sanitized_error_message if error is not None else None
        ),
        "http_status": (
            error.http_status
            if error is not None and error.http_status is not None
            else adapter.last_http_status
        ),
        "request_reached_http_server": (
            error.request_reached_http_server
            if error is not None
            else adapter.request_reached_http_server
        ),
        "phase": error.phase if error is not None else None,
        "elapsed_seconds": round(adapter.request_elapsed_seconds, 3),
    }


def _make_report(
    *,
    discovery: MarketDiscoveryResult,
    assessment: BusinessAssessment,
    adapter: OverpassMarketDiscovery,
    started_at: datetime,
    elapsed_seconds: float,
    provider_error: str | None,
    provider_diagnostic: dict[str, object],
) -> dict[str, object]:
    evidence_by_id = {item.evidence_id: item for item in discovery.evidence}
    grouped = _grouped_entities(discovery, evidence_by_id)
    comparable_ids = set(assessment.market_position.comparable_competitor_ids)
    comparable_entities = [
        _entity_dict(entity, evidence_by_id)
        for entity in discovery.entities
        if entity.entity_id in comparable_ids
    ]
    limitations = list(discovery.limitations)
    limitations.extend(assessment.limitations)
    target = _target_identification(discovery, provider_error)
    limitations.append(str(target["reason"]))
    if provider_error:
        limitations.append(provider_error)
    counts = {
        "possible_competitors": len(grouped["possible_competitors"]),
        "exact_comparable_competitors": len(comparable_entities),
        "potential_customers": len(grouped["potential_customers"]),
        "possible_partners": len(grouped["possible_partners"]),
        "suppliers": len(grouped["suppliers"]),
    }
    assessment_dict = assessment_to_dict(assessment)
    return {
        "report_id": "AEOS-LIVE-001C",
        "research": {
            "industry": "HOUSE_CLEANING",
            "market": {
                "city": "Orlando",
                "state": "Florida",
                "state_code": "FL",
                "country": "US",
                "radius_miles": ORLANDO_RADIUS_MILES,
                "center": {
                    "latitude": ORLANDO_LATITUDE,
                    "longitude": ORLANDO_LONGITUDE,
                    "description": "Approximate Downtown Orlando reference coordinate",
                },
            },
            "research_started_at_utc": started_at.isoformat(),
            "research_date_utc": started_at.date().isoformat(),
        },
        "provider": {
            "name": "OpenStreetMap data via Overpass API",
            "status": (
                "FAILED"
                if provider_error
                else "COMPLETED_WITH_RESULTS"
                if discovery.entities
                else "COMPLETED_NO_RESULTS"
            ),
            "endpoint": adapter.endpoint,
            "endpoint_hostname": provider_diagnostic["endpoint_hostname"],
            "instance_usage_policy_reference": "https://wiki.openstreetmap.org/wiki/Overpass_API",
            "application_user_agent": APPLICATION_USER_AGENT,
            "request_count": adapter.request_count,
            "attempt_count": adapter.request_count,
            "retry_count": 0,
            "timeout_seconds": adapter.timeout_seconds,
            "request_elapsed_seconds": provider_diagnostic["elapsed_seconds"],
            "response_size_limit_bytes": adapter.max_response_bytes,
            "maximum_entities_per_category": 5,
            "osm_attribution": "© OpenStreetMap contributors",
            "data_license": "Open Database License (ODbL) 1.0",
            "license_url": OSM_LICENSE_URL,
            "api_cost_usd": None,
            "api_cost_note": "No per-request price was published for this listed public instance; actual charge is unknown.",
            "future_production_use": "This public pilot endpoint is not approved as a paid SaaS dependency; evaluate self-hosted or contracted capacity before production use.",
        },
        "target_identification": target,
        "query_mapping": [
            {
                "osm_tag": "craft=cleaning",
                "market_category": "possible competitor",
                "qualification": "Cleaning scope is broad; house-cleaning comparability is unverified.",
                "reference": "https://wiki.openstreetmap.org/wiki/Tag:craft%3Dcleaning",
            },
            {
                "osm_tag": "office=property_management",
                "market_category": "potential customer",
                "qualification": "Category fit only; buying intent is unknown.",
                "reference": "https://wiki.openstreetmap.org/wiki/Tag:office%3Dproperty_management",
            },
            {
                "osm_tag": "office=estate_agent or shop=estate_agent",
                "market_category": "possible partner",
                "qualification": "Potential referral route only; no relationship is established.",
                "reference": "https://wiki.openstreetmap.org/wiki/Tag:office%3Destate_agent",
            },
            {
                "osm_tag": "shop=cleaning_supplies",
                "market_category": "supplier",
                "qualification": "Product range and supplier terms are unknown.",
                "reference": "https://wiki.openstreetmap.org/wiki/Tag:shop%3Dcleaning_supplies",
            },
        ],
        "entities_by_category": grouped,
        "exact_comparable_competitors": comparable_entities,
        "counts": counts,
        "assessment": assessment_dict,
        "assessment_summary": {
            "status": assessment.status.value,
            "best_next_move": (
                assessment.best_next_move.first_action
                if assessment.best_next_move is not None
                else None
            ),
            "opportunity_ids": [
                item.opportunity_id for item in assessment.opportunities
            ],
        },
        "provider_error": provider_error,
        "provider_diagnostic": provider_diagnostic,
        "limitations": list(dict.fromkeys(limitations)),
        "execution": {
            "provider_requests": adapter.request_count,
            "provider_request_elapsed_seconds": provider_diagnostic["elapsed_seconds"],
            "elapsed_seconds": round(elapsed_seconds, 3),
            "estimated_api_cost_usd": None,
            "actual_api_cost_usd": None,
        },
    }


def render_markdown_report(report: dict[str, object]) -> str:
    """Render the machine report with explicit attribution and uncertainty."""

    research = cast(dict[str, object], report["research"])
    market = cast(dict[str, object], research["market"])
    counts = cast(dict[str, object], report["counts"])
    target = cast(dict[str, object], report["target_identification"])
    summary = cast(dict[str, object], report["assessment_summary"])
    provider = cast(dict[str, object], report["provider"])
    groups = cast(dict[str, list[dict[str, object]]], report["entities_by_category"])
    discovery_status = str(provider["status"])
    lines = [
        "# AEOS LIVE — Orlando House-Cleaning Discovery Pilot",
        "",
        f"Research date (UTC): {research['research_date_utc']}",
        f"Area: {market['city']}, {market['state']} · {market['radius_miles']} miles from approximate Downtown Orlando center",
        "Provider: OpenStreetMap data via the listed public Overpass instance",
        "",
        "## Target business",
        "",
        "No target selected. " + str(target["reason"]),
        "",
        "## Discovery counts",
        "",
        *(
            (
                "- Counts unavailable; the market result is unknown because discovery failed.",
            )
            if discovery_status == "FAILED"
            else (
                f"- Possible cleaning-service competitors: {counts['possible_competitors']}",
                f"- Exact comparable competitors: {counts['exact_comparable_competitors']}",
                f"- Potential customers: {counts['potential_customers']}",
                f"- Possible partners: {counts['possible_partners']}",
                f"- Suppliers: {counts['suppliers']}",
            )
        ),
        "",
        "These are directory observations, not confirmed leads, buyer need, or existing commercial relationships.",
        "",
    ]
    for key, title in (
        ("possible_competitors", "Possible competitors"),
        ("potential_customers", "Potential customers"),
        ("possible_partners", "Possible partners"),
        ("suppliers", "Suppliers"),
    ):
        lines.extend((f"## {title}", ""))
        items = groups[key]
        if not items:
            empty_note = (
                "No category result is available because the provider request did not return data."
                if report["provider_error"]
                else "No supported listings returned."
            )
            lines.extend((empty_note, ""))
            continue
        lines.extend(
            (
                "| Name | Category | Location | Distance | Public contact | Source |",
                "|---|---|---|---:|---|---|",
            )
        )
        for item in items:
            name = str(item["name"]).replace("|", "\\|")
            category = str(item["category"] or "unknown").replace("|", "\\|")
            location = (
                ", ".join(
                    str(value)
                    for value in (item["address"], item["city"], item["state"])
                    if value
                )
                or "unknown"
            )
            distance = (
                f"{item['distance_miles_from_pilot_center']} mi"
                if item["distance_miles_from_pilot_center"] is not None
                else "unknown"
            )
            contact = (
                " · ".join(
                    str(value)
                    for value in (item["website"], item["public_business_phone"])
                    if value
                )
                or "unknown"
            )
            source_urls = cast(list[str], item["source_urls"])
            source = source_urls[0] if source_urls else "unknown"
            lines.append(
                f"| {name} | {category} | {location} | {distance} | {contact} | [OSM]({source}) |"
            )
            lines.append(
                f"\nCommercial fit: {item['commercial_fit_explanation']}\n"
                f"Qualification: {item['confidence_or_qualification']}\n"
                f"First research step: {item['suggested_first_research_step']}\n"
            )
        lines.append("")
    lines.extend(
        (
            "## Assessment engine",
            "",
            f"Status: **{summary['status']}**",
            f"BestNextMove: {summary['best_next_move'] or 'None supported by current evidence.'}",
            "",
            "The assessment subject is an explicitly unidentified Orlando house-cleaning profile; it is not a named or verified business.",
            "",
            "## Limitations",
            "",
        )
    )
    for limitation in cast(list[str], report["limitations"]):
        lines.append(f"- {limitation}")
    execution = cast(dict[str, object], report["execution"])
    diagnostic = cast(dict[str, object], report["provider_diagnostic"])
    lines.extend(
        (
            "",
            "## Execution and source terms",
            "",
            f"- Final discovery status: {discovery_status}",
            f"- Provider attempts: {provider['attempt_count']} (retries: {provider['retry_count']})",
            f"- Endpoint hostname: `{provider['endpoint_hostname']}`",
            f"- HTTP status: {diagnostic['http_status'] if diagnostic['http_status'] is not None else 'unavailable'}",
            f"- Request reached HTTP server: {diagnostic['request_reached_http_server'] if diagnostic['request_reached_http_server'] is not None else 'unknown'}",
            f"- Failure category / exception: {diagnostic['failure_category'] or 'none'} / {diagnostic['exception_type'] or 'none'}",
            f"- Sanitized provider message: {diagnostic['sanitized_error_message'] or 'none'}",
            f"- Provider request elapsed time: {diagnostic['elapsed_seconds']} seconds",
            f"- Elapsed time: {execution['elapsed_seconds']} seconds",
            f"- API cost: unknown ({provider['api_cost_note']})",
            f"- User-Agent: `{provider['application_user_agent']}`",
            "- Data: © OpenStreetMap contributors, licensed under [ODbL 1.0](https://www.openstreetmap.org/copyright).",
            "- The selected public instance's usage notice permits use in projects; its availability is not a production SLA. Re-evaluate provider terms and capacity before recurring or paid SaaS use.",
            "",
        )
    )
    if target["target_business"] is not None:
        lines.append("A target business was selected from source evidence.")
    return "\n".join(lines)


def _write_reports(
    report: dict[str, object], output_directory: Path, started_at: datetime
) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    json_path = output_directory / f"orlando-house-cleaning-{stamp}.json"
    markdown_path = output_directory / f"orlando-house-cleaning-{stamp}.md"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def _empty_discovery(reason: str) -> MarketDiscoveryResult:
    return MarketDiscoveryResult(entities=(), evidence=(), limitations=(reason,))


def main(argv: Sequence[str] | None = None) -> int:
    """Run one real request, then the actual deterministic LIVE assessment."""

    args = _parser().parse_args(argv)
    if args.diagnose_url is not None:
        if (
            args.inspect_website is not None
            or args.website_report is not None
            or args.select_market
            or args.market_city
            or args.market_state
            or args.market_postal_code
            or args.market_radius is not None
            or args.service
            or args.use_detected_services
            or args.confirm_market_discovery
        ):
            _parser().error(
                "--diagnose-url cannot be combined with website market selection or market discovery"
            )
        return run_business_url_diagnosis_command(
            args.diagnose_url,
            output_directory=args.output_dir,
            profile_path=args.profile,
        )
    if args.inspect_website is not None:
        if (
            args.profile is not None
            or args.website_report is not None
            or args.select_market
        ):
            _parser().error(
                "--inspect-website cannot be combined with profile or market selection options"
            )
        return run_website_inspection_command(
            args.inspect_website,
            output_directory=args.output_dir,
        )
    if args.website_report is not None or args.select_market:
        if args.profile is not None:
            _parser().error(
                "--profile cannot be combined with website market selection"
            )
        if args.website_report is None:
            _parser().error("--select-market requires --website-report")
        if not args.select_market:
            _parser().error(
                "--website-report market selection requires --select-market"
            )
        try:
            return run_website_market_command(
                args.website_report,
                selected_markets=args.select_market,
                corrected_city=args.market_city,
                corrected_state=args.market_state,
                postal_code=args.market_postal_code,
                research_radius=args.market_radius,
                radius_unit=args.radius_unit
                if args.market_radius is not None
                else None,
                selected_services=tuple(args.service),
                use_detected_services=args.use_detected_services,
                confirm_discovery=args.confirm_market_discovery,
                output_directory=args.output_dir,
            )
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            _parser().error(f"could not create selected market scope: {error}")
    if any(
        (
            args.market_city,
            args.market_state,
            args.market_postal_code,
            args.market_radius is not None,
            args.service,
            args.use_detected_services,
            args.confirm_market_discovery and args.profile is None,
        )
    ):
        _parser().error(
            "market selection options require --website-report and --select-market"
        )
    if args.profile is not None:
        return _run_profile(args)
    if (
        args.city.casefold() != "orlando"
        or args.state.casefold() not in {"fl", "florida"}
        or args.industry.casefold() not in {"house_cleaning", "house cleaning"}
    ):
        _parser().error(
            "this pilot is scoped to --city Orlando --state FL --industry HOUSE_CLEANING"
        )
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    adapter = OverpassMarketDiscovery(
        endpoint=cast(str, args.overpass_endpoint),
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes=MAX_RESPONSE_BYTES,
    )
    provider_error: str | None = None
    provider_exception: OverpassRequestError | OverpassResponseError | None = None
    try:
        discovery = _merge_port_results(adapter, _business_profile())
    except (OverpassRequestError, OverpassResponseError) as error:
        provider_exception = error
        provider_error = error.sanitized_error_message
        discovery = _empty_discovery(
            "No market entities were assessed because the live provider request failed."
        )
    assessment = assess_business(_business_profile(), discovery)
    elapsed = time.monotonic() - started
    report = _make_report(
        discovery=discovery,
        assessment=assessment,
        adapter=adapter,
        started_at=started_at,
        elapsed_seconds=elapsed,
        provider_error=provider_error,
        provider_diagnostic=_provider_diagnostic(adapter, provider_exception),
    )
    json_path, markdown_path = _write_reports(report, args.output_dir, started_at)
    target_report = cast(dict[str, object], report["target_identification"])
    counts = cast(dict[str, object], report["counts"])
    summary = cast(dict[str, object], report["assessment_summary"])
    provider = cast(dict[str, object], report["provider"])
    discovery_status = str(provider["status"])
    print(f"AEOS LIVE assessment: {assessment.status.value}")
    print(f"Target business: {target_report['target_business']}")
    if discovery_status == "FAILED":
        print("Counts: unavailable (FAILED; market result is unknown)")
    else:
        print(f"Counts ({discovery_status}): {counts}")
    print(f"BestNextMove: {summary['best_next_move']}")
    diagnostic = cast(dict[str, object], report["provider_diagnostic"])
    print(
        f"Market discovery: {discovery_status} | provider: {provider['name']} | "
        f"attempts: {provider['attempt_count']} | retries: {provider['retry_count']} | "
        f"HTTP status: {diagnostic['http_status'] if diagnostic['http_status'] is not None else 'unavailable'}"
    )
    print(
        "Provider diagnostic: "
        f"{diagnostic['failure_category'] or 'success'} "
        f"({diagnostic['exception_type'] or 'no exception'}); "
        f"HTTP status {diagnostic['http_status']}; "
        f"server reached={diagnostic['request_reached_http_server']}"
    )
    if assessment.best_next_move is None:
        print(
            "Assessment result: available source evidence does not support a "
            "specific commercial action."
        )
    else:
        print(f"Why this action: {assessment.best_next_move.why_this_one}")
        print(f"First action: {assessment.best_next_move.first_action}")
        print(f"Measurement: {assessment.best_next_move.measurement_kpi}")
    print(f"JSON report: {json_path.resolve()}")
    print(f"Markdown report: {markdown_path.resolve()}")
    return (
        2
        if provider_error
        else (0 if assessment.status is AssessmentStatus.READY else 1)
    )


if __name__ == "__main__":
    raise SystemExit(main())
