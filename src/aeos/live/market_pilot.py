"""Single-tenant market pilot; not a production tenant interface."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import cast

from aeos.application.live.market_intelligence import (
    build_market_report,
    render_combined_market_report_markdown,
    render_market_report_markdown,
)
from aeos.live.adapters.market_research import load_manual_market_research
from aeos.live.adapters.overpass import (
    DEFAULT_ENDPOINT,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_RESPONSE_BYTES,
    PROFILE_APPLICATION_USER_AGENT,
    OverpassMarketDiscovery,
    OverpassRequestError,
    OverpassResponseError,
)
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import SourceEvidence
from aeos.live.domain.market_intelligence import (
    CityMarketResearch,
    MarketEvidence,
    MarketOrganization,
    OrganizationRole,
    ResearchStatus,
    SourceCoverage,
    resolve_organization_duplicates,
)
from aeos.live.domain.market import MarketEntityType
from aeos.live.domain.profile import BusinessProfile
from aeos.live.ports.discovery import MarketDiscoveryResult


DEFAULT_PROFILE = Path(
    "examples/live/business_profiles/fictional_cleaning_company.json"
)
DEFAULT_CORPUS = Path("examples/live/market_research/fictional_cleaning_markets.json")
DEFAULT_PROSPECT_SOURCES = Path(
    "examples/live/opportunity_activation/fictional_cleaning_prospects.json"
)
DEFAULT_OUTPUT = Path("artifacts/live/fictional-cleaning-002b2")
OSM_ATTRIBUTION_URL = "https://www.openstreetmap.org/copyright"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate independent Sample City One and Sample City Two Spanish reports from a "
            "manually reviewed evidence corpus. --live makes exactly one bounded "
            "Overpass request per city, with no retries."
        )
    )
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--research", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument(
        "--prospect-sources", type=Path, default=DEFAULT_PROSPECT_SOURCES
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one bounded OpenStreetMap/Overpass query independently for each city.",
    )
    parser.add_argument(
        "--activation-report",
        action="store_true",
        help=(
            "Generate AEOS-LIVE-002C activation reports from the reviewed local corpus; "
            "this mode does not make provider requests."
        ),
    )
    parser.add_argument(
        "--stale-after-days",
        type=int,
        default=30,
        help="Treat a public request as stale after this many days (default: 30).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.stale_after_days < 1:
        _parser().error("--stale-after-days must be at least 1")
    if args.activation_report:
        if args.live:
            _parser().error(
                "--activation-report uses reviewed local evidence; omit --live"
            )
        from aeos.live.activation_pilot import main as activation_main

        activation_output = args.output_dir / "activation"
        return activation_main(
            [
                "report",
                "--profile",
                str(args.profile),
                "--market-research",
                str(args.research),
                "--prospect-sources",
                str(args.prospect_sources),
                "--output-dir",
                str(activation_output),
                "--pipeline",
                str(activation_output / "pipeline.json"),
                "--stale-after-days",
                str(args.stale_after_days),
            ]
        )
    try:
        profile_payload = json.loads(args.profile.read_text(encoding="utf-8"))
        profile = BusinessProfile.from_dict(profile_payload)
        source_snapshot_at, markets = load_manual_market_research(args.research)
    except (OSError, json.JSONDecodeError, InvalidLiveContract, ValueError) as error:
        _parser().error(f"could not load pilot inputs: {error}")

    snapshot_at = datetime.now(timezone.utc) if args.live else source_snapshot_at
    if args.live:
        markets = tuple(
            _add_live_overpass(profile, market, snapshot_at) for market in markets
        )
    owner_evidence = profile.reported_evidence()
    report = build_market_report(
        profile,
        markets,
        owner_evidence=owner_evidence,
        snapshot_at=snapshot_at,
        stale_after_days=args.stale_after_days,
        website_reported_location={
            "evidence_id": "fictional-cleaning-website-address-reported",
            "entity_id": "fictional-cleaning-cleaning-llc",
            "value": "Sample City Two, Example Region",
            "status": "WEBSITE_REPORTED",
            "classification": "REPORTED",
            "source_name": "User-provided brief reporting an earlier website inspection",
            "source_url": profile.website_url,
            "retrieved_at": snapshot_at.isoformat(),
            "published_at": None,
            "confidence": 0.65,
            "supporting_information": "The pilot brief says the previous website inspection detected Sample City Two as the business address; the underlying inspection date was not available.",
            "limitations": [
                "Not independently verified as a registered or operating address.",
                "Not used as the center of either market or as proof of every service area.",
            ],
        },
    )
    _write_reports(report, args.output_dir)
    print("AEOS-LIVE-002B2 market research report created")
    print(f"Business: {profile.business_name}")
    for item in cast(list[dict[str, object]], report["markets"]):
        counts = cast(dict[str, object], item["counts"])
        city = item["city"]
        print(
            f"{city}: {counts['direct_competitors']} direct competitors, "
            f"{counts['potential_buyers']} buyer-fit organizations, "
            f"{counts['current_buying_intent_signals']} current intent signals, "
            f"{counts['historical_explicit_demand_signals']} historical demand signals, "
            f"{counts['referral_partners']} referral partners"
        )
        overpass = next(
            (
                cast(dict[str, object], coverage)
                for coverage in cast(list[object], item["source_coverage"])
                if cast(dict[str, object], coverage)["source_name"]
                == "OpenStreetMap / Overpass"
            ),
            None,
        )
        if overpass is not None:
            print(
                f"  Overpass: {overpass['status']} "
                f"({overpass['request_count']} request(s), no retries)"
            )
    print(f"JSON report: {(args.output_dir / 'market-report.json').resolve()}")
    print(f"Markdown reports: {args.output_dir.resolve()}")
    return 0


def _add_live_overpass(
    profile: BusinessProfile,
    market: CityMarketResearch,
    retrieved_at: datetime,
) -> CityMarketResearch:
    """Run exactly one city-scoped Overpass request and preserve failure state."""

    business = replace(
        profile.to_business_input(), city=market.city, state=market.state
    )
    adapter = OverpassMarketDiscovery(
        endpoint=DEFAULT_ENDPOINT,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes=MAX_RESPONSE_BYTES,
        business=business,
        service_areas=(),
        user_agent=PROFILE_APPLICATION_USER_AGENT,
    )
    try:
        result = adapter.discover_all()
    except (OverpassRequestError, OverpassResponseError) as error:
        coverage = SourceCoverage(
            source_name="OpenStreetMap / Overpass",
            status=ResearchStatus.PROVIDER_UNAVAILABLE,
            retrieved_at=retrieved_at,
            result_count=None,
            request_count=adapter.request_count,
            note=(
                f"La solicitud acotada falló en {error.phase or 'provider'} "
                f"({error.category}); no se reintentó. Un fallo no equivale a un mercado vacío."
            ),
        )
        return replace(
            market,
            source_coverage=_replace_overpass_coverage(
                market.source_coverage, coverage
            ),
            limitations=tuple(
                dict.fromkeys(
                    (
                        *market.limitations,
                        "Overpass no estuvo disponible; la cobertura de directorios es incompleta y esto no significa que no haya negocios locales.",
                    )
                )
            ),
        )
    coverage = SourceCoverage(
        source_name="OpenStreetMap / Overpass",
        status=(
            ResearchStatus.SUCCEEDED
            if result.entities
            else ResearchStatus.NO_RESULTS_FOUND
        ),
        retrieved_at=retrieved_at,
        result_count=len(result.entities),
        request_count=adapter.request_count,
        note=(
            "Se completó una solicitud independiente para el área nombrada de esta ciudad. "
            "OSM es una muestra de búsqueda, no un directorio completo ni una fuente de intención de compra. "
            f"Atribución: © OpenStreetMap contributors ({OSM_ATTRIBUTION_URL})."
        ),
    )
    added_organizations, added_evidence = _overpass_records(
        result, city=market.city, retrieved_at=retrieved_at
    )
    organizations, evidence = resolve_organization_duplicates(
        (*market.organizations, *added_organizations),
        (*market.evidence, *added_evidence),
    )
    return replace(
        market,
        organizations=organizations,
        evidence=evidence,
        source_coverage=_replace_overpass_coverage(market.source_coverage, coverage),
        limitations=tuple(
            dict.fromkeys(
                (
                    *market.limitations,
                    *result.limitations,
                    "Las etiquetas de categoría de OSM no prueban alcance residencial, necesidad de limpieza de un comprador ni intención de compra actual.",
                )
            )
        ),
    )


def _replace_overpass_coverage(
    existing: tuple[SourceCoverage, ...], replacement: SourceCoverage
) -> tuple[SourceCoverage, ...]:
    result = tuple(
        item for item in existing if item.source_name != replacement.source_name
    )
    return (*result, replacement)


def _overpass_records(
    result: MarketDiscoveryResult,
    *,
    city: str,
    retrieved_at: datetime,
) -> tuple[tuple[MarketOrganization, ...], tuple[MarketEvidence, ...]]:
    organizations: list[MarketOrganization] = []
    evidence: list[MarketEvidence] = []
    evidence_by_owner: dict[str, list[SourceEvidence]] = {}
    for item in result.evidence:
        if item.owner_entity_id:
            evidence_by_owner.setdefault(item.owner_entity_id, []).append(item)
    for entity in result.entities:
        sources = evidence_by_owner.get(entity.entity_id, [])
        if not sources:
            continue
        role = (
            OrganizationRole.COMPETITOR
            if entity.entity_type is MarketEntityType.COMPETITOR
            else OrganizationRole.DIRECTORY_CANDIDATE
        )
        evidence_ids = tuple(item.evidence_id for item in sources)
        for source in sources:
            evidence.append(
                MarketEvidence(
                    evidence_id=source.evidence_id,
                    entity_id=entity.entity_id,
                    field=source.field,
                    value=str(source.value),
                    source_name=source.source_name,
                    source_url=source.source_url or "https://www.openstreetmap.org/",
                    retrieved_at=source.retrieved_at or retrieved_at,
                    published_at=None,
                    classification=source.kind,
                    confidence=source.confidence or 0.72,
                    supporting_information=source.excerpt
                    or f"OSM provider field {source.field}.",
                    limitations=(
                        "La comunidad mantiene las categorías y direcciones de OSM; esos datos no confirman por sí solos el alcance del servicio ni la actividad actual del negocio.",
                    ),
                )
            )
        organizations.append(
            MarketOrganization(
                entity_id=entity.entity_id,
                name=entity.name,
                city=city,
                role=role,
                website_url=entity.website,
                public_address=entity.address,
                service_areas=(city,),
                services=(),
                customer_segments=(),
                vacation_rental_specialization=False,
                recurring_options=(),
                pricing_model=None,
                public_listing_url=next(
                    (
                        str(item.value)
                        for item in sources
                        if item.field == "listing_url"
                    ),
                    None,
                ),
                rating_claim=None,
                review_count_claim=None,
                booking_methods=(),
                conversion_channels=tuple(
                    value
                    for value in (entity.website, entity.phone)
                    if value is not None
                ),
                public_contacts=tuple(
                    value
                    for value in (entity.phone, entity.website)
                    if value is not None
                ),
                buyer_fit_reason=None,
                referral_reason=None,
                recommended_action="Open the OSM source record and verify the organization's active website, service scope, and market before qualification.",
                validation_question="Does this organization provide or purchase a service relevant to Sample Cleaning Company in this city?",
                evidence_ids=evidence_ids,
                limitations=(
                    "Se encontró dentro del área administrativa seleccionada; puede faltar una dirección pública o la ciudad exacta donde presta servicio.",
                    "Una etiqueta de limpieza de OSM por sí sola se mantiene como UNVERIFIED_CLEANING_BUSINESS.",
                ),
            )
        )
    return tuple(organizations), tuple(evidence)


def _write_reports(report: dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "market-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for item in cast(list[dict[str, object]], report["markets"]):
        city = str(item["city"])
        slug = re.sub(r"[^a-z0-9]+", "-", city.casefold()).strip("-")
        single_report = {
            "project": report["project"],
            "snapshot_at": report["snapshot_at"],
            "business_profile": report["business_profile"],
            "owner_confirmation_evidence": report["owner_confirmation_evidence"],
            "website_reported_location": report["website_reported_location"],
            "market": item,
        }
        (output_dir / f"fictional-cleaning-{slug}.md").write_text(
            render_market_report_markdown(single_report), encoding="utf-8"
        )
    (output_dir / "market-comparison.md").write_text(
        render_combined_market_report_markdown(report), encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
