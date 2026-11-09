"""Business-friendly report assembly for the LIVE profile assessment."""

from datetime import datetime, timezone
from typing import cast

from aeos.live.domain import (
    BusinessAssessment,
    BusinessProfile,
    EvidenceKind,
    MarketEntity,
    MarketEntityType,
    SourceEvidence,
    assessment_to_dict,
)
from aeos.live.domain.url_policy import sanitize_report_data, safe_text_for_report
from aeos.live.ports import MarketDiscoveryResult


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


def _entity_evidence(
    entity: MarketEntity, evidence_by_id: dict[str, SourceEvidence]
) -> tuple[SourceEvidence, ...]:
    return tuple(
        evidence_by_id[item]
        for item in entity.evidence_ids
        if item in evidence_by_id
        and evidence_by_id[item].owner_entity_id == entity.entity_id
    )


def _observed_values(
    entity: MarketEntity,
    evidence: tuple[SourceEvidence, ...],
    *fields: str,
) -> tuple[str, ...]:
    return tuple(
        str(item.value)
        for item in evidence
        if item.field in fields
        and item.kind is EvidenceKind.OBSERVED
        and item.owner_entity_id == entity.entity_id
    )


def _same_text(left: str, right: str) -> bool:
    return " ".join(left.casefold().replace("_", " ").split()) == " ".join(
        right.casefold().replace("_", " ").split()
    )


def _competitor_requirements(
    profile: BusinessProfile,
    entity: MarketEntity,
    evidence: tuple[SourceEvidence, ...],
) -> dict[str, bool]:
    services = _observed_values(entity, evidence, "services", "service")
    service_match = any(
        _same_text(candidate_service, profile_service)
        for candidate_service in services
        for profile_service in profile.primary_services
    )
    segments = _observed_values(
        entity,
        evidence,
        "customer_segment",
        "customer_segments",
        "target_customer_segment",
        "target_customer_segments",
    )
    segment_match = any(
        _same_text(candidate, target)
        for candidate in segments
        for target in profile.target_customer_segments
    )
    models = _observed_values(entity, evidence, "business_model")
    model_values = {" ".join(value.casefold().split()) for value in models}
    model_match = len(model_values) == 1 and _same_text(
        models[0], profile.business_model.value
    )
    target_areas = (profile.city, *(profile.additional_service_areas or ()))
    entity_cities = _observed_values(entity, evidence, "city")
    entity_states = _observed_values(entity, evidence, "state", "state_region")
    city_values = {" ".join(value.casefold().split()) for value in entity_cities}
    state_values = {" ".join(value.casefold().split()) for value in entity_states}
    location_match = (
        len(city_values) == 1
        and len(state_values) == 1
        and any(
            _same_text(city, area) for city in entity_cities for area in target_areas
        )
        and any(_same_text(state, profile.state_region) for state in entity_states)
    )
    return {
        "service": service_match,
        "customer_segment": segment_match,
        "geography": location_match,
        "business_model": model_match,
    }


def _entity_record(
    entity: MarketEntity,
    evidence_by_id: dict[str, SourceEvidence],
    inference_ids: tuple[str, ...],
) -> dict[str, object]:
    evidence = _entity_evidence(entity, evidence_by_id)
    source_urls = list(
        dict.fromkeys(item.source_url for item in evidence if item.source_url)
    )
    return {
        "entity_id": entity.entity_id,
        "name": entity.name,
        "category": entity.category,
        "location": {
            "address": entity.address,
            "city": entity.city,
            "state_region": entity.state,
            "latitude": entity.latitude,
            "longitude": entity.longitude,
            "distance_miles": entity.distance_miles,
        },
        "presence": {
            "website": entity.website,
            "google_business_profile_url": next(
                (
                    str(item.value)
                    for item in evidence
                    if item.field == "google_business_profile_url"
                    and item.kind is EvidenceKind.OBSERVED
                ),
                None,
            ),
            "rating": entity.rating,
            "review_count": entity.review_count,
        },
        "observed_services": list(
            dict.fromkeys(
                (
                    *entity.services,
                    *_observed_values(entity, evidence, "services", "service"),
                )
            )
        ),
        "observed_customer_segments": list(
            _observed_values(
                entity,
                evidence,
                "customer_segment",
                "customer_segments",
                "target_customer_segment",
                "target_customer_segments",
            )
        ),
        "observed_business_models": list(
            _observed_values(entity, evidence, "business_model")
        ),
        "observed_differentiators": list(
            _observed_values(entity, evidence, "differentiators", "differentiator")
        ),
        "source_urls": source_urls,
        "evidence_ids": [item.evidence_id for item in evidence],
        "hypothesis_evidence_ids": list(inference_ids),
        "evidence": [_evidence_dict(item) for item in evidence],
        "unknowns": [
            label
            for value, label in (
                (entity.website, "website"),
                (
                    next(
                        (
                            item.value
                            for item in evidence
                            if item.field == "google_business_profile_url"
                            and item.kind is EvidenceKind.OBSERVED
                        ),
                        None,
                    ),
                    "Google Business Profile URL",
                ),
                (entity.rating, "rating"),
                (entity.review_count, "review count"),
            )
            if value is None
        ],
    }


def _hypothesis(
    *,
    record: dict[str, object],
    opportunity_type: str,
    title: str,
    hypothesis: str,
    evidence_ids: list[str],
    pending: list[str],
    action: str,
    validation: str,
) -> dict[str, object]:
    return {
        "opportunity_type": opportunity_type,
        "title": title,
        "related_entity_id": record["entity_id"],
        "related_entity_name": record["name"],
        "hypothesis": hypothesis,
        "confidence_level": "LOW",
        "confidence_basis": "A directory category supports research only; it does not establish need, intent, or a relationship.",
        "evidence_ids": evidence_ids,
        "pending_information": pending,
        "recommended_action": action,
        "validation_method": validation,
    }


def _relationship_opportunities(
    groups: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    opportunities: list[dict[str, object]] = []
    for record in groups["sector_related_unqualified"]:
        opportunities.append(
            _hypothesis(
                record=record,
                opportunity_type="COMPETITOR_RESEARCH",
                title=f"Verify service fit at {record['name']}",
                hypothesis="This cleaning-services listing may overlap with the business's offer, but its residential scope is not identified.",
                evidence_ids=cast(list[str], record["evidence_ids"])
                + cast(list[str], record["hypothesis_evidence_ids"]),
                pending=[
                    "Residential service scope",
                    "Target segment",
                    "Business model",
                    "Actual service coverage",
                ],
                action="Check the organization's own service description and record whether it explicitly offers the same residential services.",
                validation="Confirm service, customer segment, coverage, and business model from a direct public source or a verified conversation.",
            )
        )
    for record in groups["potential_customers"]:
        opportunities.append(
            _hypothesis(
                record=record,
                opportunity_type="CUSTOMER_ACQUISITION",
                title=f"Research possible service fit at {record['name']}",
                hypothesis="This organization category could coordinate properties that need cleaning; the listing does not show outsourcing, current need, authority, or buying intent.",
                evidence_ids=cast(list[str], record["evidence_ids"])
                + cast(list[str], record["hypothesis_evidence_ids"]),
                pending=[
                    "Whether cleaning is outsourced",
                    "Service frequency and scope",
                    "Relevant decision-maker",
                    "Current need and timing",
                ],
                action="Verify that the organization manages relevant properties and identify the appropriate operations contact before deciding whether to approach it.",
                validation="Confirm its service requirements and purchasing process directly; record the source and date of confirmation.",
            )
        )
    for record in groups["partners"]:
        opportunities.append(
            _hypothesis(
                record=record,
                opportunity_type="PARTNERSHIP",
                title=f"Check referral fit with {record['name']}",
                hypothesis="This category may connect the business with relevant customers; customer overlap and willingness to refer are not established.",
                evidence_ids=cast(list[str], record["evidence_ids"])
                + cast(list[str], record["hypothesis_evidence_ids"]),
                pending=[
                    "Customer overlap",
                    "Existing referral process",
                    "Partner interest and terms",
                ],
                action="Review the organization's public services and decide whether a referral conversation would be relevant.",
                validation="Confirm the referral route and any terms with an authorized representative; do not assume an agreement exists.",
            )
        )
    for record in groups["suppliers"]:
        opportunities.append(
            _hypothesis(
                record=record,
                opportunity_type="SUPPLIER",
                title=f"Compare product fit at {record['name']}",
                hypothesis="This listing may supply cleaning products or equipment; products, availability, prices, delivery, and terms are unknown.",
                evidence_ids=cast(list[str], record["evidence_ids"])
                + cast(list[str], record["hypothesis_evidence_ids"]),
                pending=[
                    "Exact product assortment",
                    "Availability and delivery area",
                    "Current prices and purchase terms",
                ],
                action="List frequently used products and request comparable current quotes from relevant suppliers.",
                validation="Compare the same products, quantities, delivery fees, and payment terms using dated supplier quotes.",
            )
        )
    return opportunities


def _engine_opportunity_dict(
    opportunity: object, evidence_by_id: dict[str, SourceEvidence]
) -> dict[str, object]:
    item = opportunity
    opportunity_id = getattr(item, "opportunity_id")
    evidence_ids = list(getattr(item, "evidence_ids"))
    related_ids = list(
        dict.fromkeys(
            evidence_by_id[evidence_id].owner_entity_id
            for evidence_id in evidence_ids
            if evidence_id in evidence_by_id
            and evidence_by_id[evidence_id].owner_entity_id is not None
        )
    )
    return {
        "opportunity_id": opportunity_id,
        "opportunity_type": getattr(item, "opportunity_type").value,
        "title": getattr(item, "title"),
        "related_entity_ids": related_ids,
        "description": getattr(item, "description"),
        "hypothesis": getattr(item, "description"),
        "confidence_score": getattr(item, "confidence"),
        "evidence_ids": evidence_ids,
        "evidence": [
            _evidence_dict(evidence_by_id[evidence_id])
            for evidence_id in evidence_ids
            if evidence_id in evidence_by_id
        ],
        "pending_information": [],
        "recommended_action": getattr(item, "recommended_action"),
        "validation_method": "Record the result of the recommended action and the source evidence collected.",
    }


def build_business_report(
    *,
    profile: BusinessProfile,
    discovery: MarketDiscoveryResult,
    assessment: BusinessAssessment,
    started_at: datetime,
    provider: dict[str, object],
    provider_error: str | None = None,
) -> dict[str, object]:
    """Build the auditable JSON report from profile, provider, and assessment."""

    evidence_by_id = {item.evidence_id: item for item in assessment.evidence}
    inference_by_entity: dict[str, list[str]] = {}
    for entity in discovery.entities:
        prefix = f"inference:{entity.entity_id}:"
        for item in assessment.evidence:
            if item.kind is EvidenceKind.INFERRED and item.evidence_id.startswith(
                prefix
            ):
                inference_by_entity.setdefault(entity.entity_id, []).append(
                    item.evidence_id
                )

    competitors: dict[str, list[dict[str, object]]] = {
        "potential": [],
        "verified": [],
        "sector_related_unqualified": [],
    }
    customers: list[dict[str, object]] = []
    partners: list[dict[str, object]] = []
    suppliers: list[dict[str, object]] = []
    for entity in discovery.entities:
        record = _entity_record(
            entity,
            evidence_by_id,
            tuple(inference_by_entity.get(entity.entity_id, ())),
        )
        if entity.entity_type is MarketEntityType.COMPETITOR:
            requirements = _competitor_requirements(
                profile, entity, _entity_evidence(entity, evidence_by_id)
            )
            record["comparability_requirements"] = requirements
            if all(requirements.values()):
                competitors["verified"].append(record)
            elif requirements["service"]:
                competitors["potential"].append(record)
            else:
                competitors["sector_related_unqualified"].append(record)
        elif entity.entity_type is MarketEntityType.POTENTIAL_CUSTOMER:
            customers.append(record)
            if entity.category == "property management":
                partners.append(record)
        elif entity.entity_type is MarketEntityType.PARTNER:
            partners.append(record)
        elif entity.entity_type is MarketEntityType.SUPPLIER:
            suppliers.append(record)

    engine_comparable_ids = set(assessment.market_position.comparable_competitor_ids)
    comparable_records = [
        item
        for item in competitors["verified"]
        if item["entity_id"] in engine_comparable_ids
    ]
    benchmark_status = (
        "INSUFFICIENT_COMPARABLE_DATA"
        if len(comparable_records) < 2
        else "COMPARABLE_SAMPLE_AVAILABLE"
    )
    benchmark_metrics = (
        [
            "primary services",
            "target customer segments",
            "geographic coverage",
            "business model",
            "website",
            "Google Business Profile URL",
            "ratings and review counts",
            "commercial differentiators",
        ]
        if len(comparable_records) >= 2
        else []
    )
    missing_benchmark_information = (
        [
            "Observed, equivalent rating and review-count values for the business and competitors",
            "Observed commercial differentiators for comparable competitors",
            "Google Business Profile data when a source exposes it",
        ]
        if len(comparable_records) >= 2
        else [
            "At least two companies with matching service evidence",
            "Observed target-segment evidence for each company",
            "Observed geographic coverage evidence for each company",
            "Observed business-model evidence for each company",
            "Comparable, dated digital-presence and reputation data",
        ]
    )

    groups: dict[str, list[dict[str, object]]] = {
        "sector_related_unqualified": competitors["sector_related_unqualified"],
        "potential_customers": customers,
        "partners": partners,
        "suppliers": suppliers,
    }
    relationship_opportunities = _relationship_opportunities(groups)
    engine_opportunities = [
        _engine_opportunity_dict(item, evidence_by_id)
        for item in assessment.opportunities
    ]
    best_next_move = (
        {
            "selected_opportunity_id": assessment.best_next_move.selected_opportunity_id,
            "first_action": assessment.best_next_move.first_action,
            "why_this_one": assessment.best_next_move.why_this_one,
            "measurement_kpi": assessment.best_next_move.measurement_kpi,
        }
        if assessment.best_next_move is not None
        else None
    )

    limitations = list(discovery.limitations) + list(assessment.limitations)
    limitations.extend(
        (
            "Directory inclusion does not confirm that an organization is a lead, has current demand, or intends to buy.",
            "The owner-declared service radius is preserved in the profile but cannot be applied as a distance filter without verified business coordinates.",
            "The Overpass search uses named administrative areas, which may not match the owner's service boundary exactly.",
            "No underserved-market or revenue claim is inferred from the number of listings returned.",
        )
    )
    if provider_error:
        limitations.append(provider_error)

    observed = [
        item for item in assessment.evidence if item.kind is EvidenceKind.OBSERVED
    ]
    reported = [
        item
        for item in assessment.evidence
        if item.kind is EvidenceKind.REPORTED
        and item.evidence_id.startswith("profile:")
    ]
    inferred = [
        item for item in assessment.evidence if item.kind is EvidenceKind.INFERRED
    ]
    provider_mapping_references = cast(
        list[dict[str, object]], provider.get("category_mapping_references", [])
    )
    source_urls = list(
        dict.fromkeys(
            [
                item.source_url
                for item in assessment.evidence
                if item.source_url is not None
            ]
            + [
                str(item["url"])
                for item in provider_mapping_references
                if item.get("url") is not None
            ]
        )
    )
    executive_summary = (
        f"The profile describes {profile.business_name} as a {profile.business_model.value} "
        f"{profile.vertical.replace('_', ' ').lower()} business serving {profile.city}, "
        f"{profile.state_region}. Discovery returned {len(discovery.entities)} named "
        "organizations across the mapped categories. These listings support research "
        "hypotheses only; they do not establish buying intent or commercial relationships. "
        + (
            "There is not enough verified comparable data for a competitor benchmark."
            if benchmark_status == "INSUFFICIENT_COMPARABLE_DATA"
            else "A comparable competitor sample is available for review."
        )
    )
    report: dict[str, object] = {
        "report_id": "AEOS-LIVE-002A",
        "generated_at_utc": started_at.astimezone(timezone.utc).isoformat(),
        "profile": {
            **profile.to_dict(),
            "data_status": (
                "FICTIONAL_EXAMPLE"
                if profile.is_fictional_example
                else "OWNER_SUPPLIED_REPORTED_DATA"
            ),
            "data_notice": (
                "Fictional demonstration profile. These details do not describe a real business."
                if profile.is_fictional_example
                else "Business details in this profile were supplied by the owner and are classified as REPORTED."
            ),
        },
        "executive_summary": executive_summary,
        "what_we_know": {
            "owner_reported": [_evidence_dict(item) for item in reported],
            "observed_in_discovery": [_evidence_dict(item) for item in observed],
            "inferred_hypotheses": [_evidence_dict(item) for item in inferred],
            "information_not_found": missing_benchmark_information,
        },
        "market_scope": {
            "country": profile.country,
            "state_region": profile.state_region,
            "city": profile.city,
            "declared_service_radius": profile.service_radius,
            "declared_service_radius_unit": (
                profile.service_radius_unit.value
                if profile.service_radius_unit is not None
                else None
            ),
            "additional_service_areas": list(profile.additional_service_areas or ()),
            "applied_spatial_method": "Named OSM administrative areas; radius not applied without business coordinates.",
        },
        "competitive_environment": {
            "potential_competitors": competitors["potential"],
            "verified_competitors": competitors["verified"],
            "same_sector_unqualified": competitors["sector_related_unqualified"],
            "counts": {
                "all_discovered_entities": len(discovery.entities),
                "potential_competitors": len(competitors["potential"]),
                "verified_competitors": len(competitors["verified"]),
                "same_sector_unqualified": len(
                    competitors["sector_related_unqualified"]
                ),
            },
        },
        "potential_customers": customers,
        "partners_and_channels": partners,
        "suppliers": suppliers,
        "benchmark": {
            "status": benchmark_status,
            "comparable_competitor_ids": [
                item["entity_id"] for item in comparable_records
            ],
            "comparison_dimensions": benchmark_metrics,
            "metrics_compared": [],
            "metric_note": "No rating or review metric is compared unless equivalent OBSERVED values are available for both the business and at least two verified competitors.",
            "comparison_rows": comparable_records,
            "missing_information": missing_benchmark_information,
            "rule": "A company is comparable only when the existing LIVE assessment accepts its supported industry category and matching OBSERVED evidence covers service, target segment, geographic coverage, and business model.",
        },
        "opportunities": {
            "business_assessment_actions": engine_opportunities,
            "entity_research_hypotheses": relationship_opportunities,
        },
        "best_next_move": best_next_move,
        "limitations": list(dict.fromkeys(limitations)),
        "sources_and_research_date": {
            "consulted_at_utc": started_at.astimezone(timezone.utc).isoformat(),
            "provider": provider,
            "sources": source_urls,
        },
        "assessment": assessment_to_dict(assessment),
    }

    return cast(dict[str, object], sanitize_report_data(report))


def render_business_report_markdown(report: dict[str, object]) -> str:
    """Render an accessible Markdown version of the profile report."""

    profile = cast(dict[str, object], report["profile"])
    competition = cast(dict[str, object], report["competitive_environment"])
    benchmark = cast(dict[str, object], report["benchmark"])
    opportunities = cast(dict[str, list[dict[str, object]]], report["opportunities"])
    lines = [
        "# AEOS LIVE — Informe de inteligencia comercial",
        "",
        f"Fecha de consulta (UTC): {report['generated_at_utc']}",
        f"Perfil: **{profile['business_name']}** · {profile['vertical']} · {profile['city']}, {profile['state_region']}",
        f"Estado de los datos: **{profile['data_status']}**",
        str(profile["data_notice"]),
        "",
        "## Resumen ejecutivo",
        "",
        str(report["executive_summary"]),
        "",
        "## Perfil declarado por el propietario",
        "",
        f"- Oferta principal: {', '.join(cast(list[str], profile['primary_services']))}",
        f"- Segmentos objetivo: {', '.join(cast(list[str], profile['target_customer_segments']))}",
        f"- Modelo comercial: {profile['business_model']}",
        f"- Cobertura declarada: {profile['service_radius']} {profile['service_radius_unit']} desde {profile['city']}",
        f"- Zonas adicionales: {', '.join(cast(list[str], profile['additional_service_areas'] or [])) or 'No declaradas'}",
        "Todos estos datos son REPORTED; no se verificaron de manera independiente.",
        "",
        "## Entorno competitivo",
        "",
        f"- Competidores verificados: {len(cast(list[object], competition['verified_competitors']))}",
        f"- Competidores potenciales: {len(cast(list[object], competition['potential_competitors']))}",
        f"- Empresas del sector aún sin evidencia de competencia directa: {len(cast(list[object], competition['same_sector_unqualified']))}",
        "",
        "Los listados de directorio no demuestran por sí solos que una organización compita directamente.",
        "",
        "## Benchmark",
        "",
        f"Estado: **{benchmark['status']}**",
        "",
    ]
    missing = cast(list[str], benchmark["missing_information"])
    if missing:
        lines.append(
            "Falta la siguiente información para comparar empresas de forma válida:"
        )
        lines.extend(f"- {item}" for item in missing)
    else:
        lines.append(
            "El informe contiene una muestra comparable; revise los datos y sus fuentes en el JSON."
        )

    for key, heading in (
        ("potential_customers", "Clientes potenciales"),
        ("partners_and_channels", "Partners y canales"),
        ("suppliers", "Proveedores"),
    ):
        records = cast(list[dict[str, object]], report[key])
        lines.extend(("", f"## {heading}", ""))
        if not records:
            lines.append(
                "No se encontraron organizaciones con una categoría documentada."
            )
            continue
        for record in records:
            lines.extend(
                (
                    f"### {record['name']}",
                    "",
                    f"Categoría: {record['category'] or 'Desconocida'}",
                    f"Evidencia: {', '.join(cast(list[str], record['source_urls'])) or 'sin URL de origen disponible'}",
                    "La categoría apoya una hipótesis de investigación; no confirma necesidad, intención ni relación comercial.",
                    "",
                )
            )

    lines.extend(("## Oportunidades comerciales", ""))
    all_opportunities = [
        *opportunities["business_assessment_actions"],
        *opportunities["entity_research_hypotheses"],
    ]
    if not all_opportunities:
        lines.append(
            "La evidencia disponible no respalda una acción comercial específica."
        )
    for item in all_opportunities:
        lines.extend(
            (
                f"### {item.get('title', item.get('opportunity_type'))}",
                "",
                f"Hipótesis: {item.get('hypothesis', item.get('description', ''))}",
                f"Confianza: {item.get('confidence_level', item.get('confidence_score', 'no asignada'))}",
                f"Evidencia: {', '.join(cast(list[str], item.get('evidence_ids', []))) or 'sin evidencia vinculada'}",
                f"Acción recomendada: {item.get('recommended_action', '')}",
                f"Validación: {item.get('validation_method', '')}",
                "",
            )
        )

    move = cast(dict[str, object] | None, report["best_next_move"])
    lines.extend(("## BestNextMove", ""))
    if move is None:
        lines.append(
            "No hay suficiente evidencia para priorizar una acción mediante el motor de evaluación."
        )
    else:
        lines.extend(
            (
                f"- Acción: {move['first_action']}",
                f"- Motivo: {move['why_this_one']}",
                f"- Medición: {move['measurement_kpi']}",
            )
        )

    lines.extend(("", "## Fuentes, datos pendientes y limitaciones", ""))
    for limitation in cast(list[str], report["limitations"]):
        lines.append(f"- {limitation}")
    lines.extend(
        (
            "",
            "## Evidencia",
            "",
            f"El JSON adjunto conserva {len(cast(list[object], cast(dict[str, object], report['what_we_know'])['owner_reported']))} datos REPORTED, {len(cast(list[object], cast(dict[str, object], report['what_we_know'])['observed_in_discovery']))} datos OBSERVED y {len(cast(list[object], cast(dict[str, object], report['what_we_know'])['inferred_hypotheses']))} inferencias con sus fuentes.",
        )
    )
    return safe_text_for_report("\n".join(lines) + "\n")


__all__ = ["build_business_report", "render_business_report_markdown"]
