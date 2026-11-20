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


def _field_status(profile: BusinessProfile, field: str) -> str:
    status = profile.field_statuses.get(field)
    return status.value if status is not None else "UNKNOWN"


def _digital_presence_actions(
    profile: BusinessProfile, reported: list[SourceEvidence]
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    facebook_evidence = [
        item
        for item in reported
        if item.field == "social_media_urls"
        and "facebook.com" in str(item.value).casefold()
    ]
    for item in facebook_evidence:
        url = item.source_url or str(item.value)
        actions.append(
            {
                "action_id": f"review-reported-facebook-{item.evidence_id}",
                "title": "Revisar la página de Facebook reportada",
                "data_status": "REPORTED_NOT_INSPECTED",
                "evidence_ids": [item.evidence_id],
                "source_urls": [url],
                "recommended_action": (
                    "Revisar con el propietario si la página presenta de forma clara "
                    "los servicios, la cobertura, el contacto y el paso para solicitar "
                    "una cotización; actualizar únicamente datos confirmados."
                ),
                "validation_method": (
                    "Registrar la URL y fecha de revisión, y confirmar cada dato con "
                    "el propietario."
                ),
            }
        )

    if profile.instagram_presence is True and profile.instagram_url is None:
        evidence_ids = [
            item.evidence_id
            for item in reported
            if item.field == "instagram_presence" and item.value is True
        ]
        actions.append(
            {
                "action_id": "confirm-instagram-url",
                "title": "Confirmar la URL de Instagram",
                "data_status": "NEEDS_CONFIRMATION",
                "evidence_ids": evidence_ids,
                "source_urls": [],
                "recommended_action": (
                    "Solicitar al propietario la URL oficial de Instagram y asociarla "
                    "a la empresa solo después de confirmarla."
                ),
                "validation_method": (
                    "Confirmar la URL con el propietario y conservar la fuente y la fecha."
                ),
            }
        )

    if profile.website_url is None:
        evidence_ids = [
            item.evidence_id for item in reported if item.field == "website_presence"
        ]
        website_reported_present = profile.website_presence is True
        website_reported_absent = profile.website_presence is False
        actions.append(
            {
                "action_id": "confirm-website-url",
                "title": (
                    "Solicitar la URL del sitio web reportado"
                    if website_reported_present
                    else "Confirmar la presencia de un sitio web"
                ),
                "data_status": (
                    "REPORTED_PRESENT_URL_MISSING"
                    if website_reported_present
                    else "REPORTED_ABSENT_NEEDS_CONFIRMATION"
                    if website_reported_absent
                    else "PRESENCE_UNKNOWN"
                ),
                "evidence_ids": evidence_ids,
                "source_urls": [],
                "recommended_action": (
                    "Solicitar al propietario la URL pública del sitio que reportó y "
                    "asociarla al negocio solo después de confirmarla."
                    if website_reported_present
                    else "El propietario reportó que no existe un sitio. Confirmar ese "
                    "dato y, si se confirma, evaluar si conviene publicar una página "
                    "sencilla con servicios, cobertura, contacto y solicitud de cotización."
                    if website_reported_absent
                    else "Preguntar al propietario si existe un sitio público y pedir "
                    "la URL si la respuesta es sí. No asumir que el sitio no existe."
                ),
                "validation_method": (
                    "Registrar la respuesta y la URL confirmada, si existe; inspeccionar "
                    "el sitio en una evaluación posterior."
                ),
            }
        )

    if profile.google_business_profile_url is None:
        evidence_ids = [
            item.evidence_id
            for item in reported
            if item.field == "google_business_profile_present"
        ]
        google_profile_reported_present = (
            profile.google_business_profile_present is True
        )
        google_profile_reported_absent = (
            profile.google_business_profile_present is False
        )
        actions.append(
            {
                "action_id": "confirm-google-business-profile",
                "title": (
                    "Solicitar la URL del Perfil de Negocio de Google reportado"
                    if google_profile_reported_present
                    else "Confirmar la presencia del Perfil de Negocio de Google"
                ),
                "data_status": (
                    "REPORTED_PRESENT_URL_MISSING"
                    if google_profile_reported_present
                    else "REPORTED_ABSENT_NEEDS_CONFIRMATION"
                    if google_profile_reported_absent
                    else "PRESENCE_UNKNOWN"
                ),
                "evidence_ids": evidence_ids,
                "source_urls": [],
                "recommended_action": (
                    "Solicitar al propietario la URL pública del perfil reportado y "
                    "asociarla al negocio solo después de confirmarla."
                    if google_profile_reported_present
                    else "El propietario reportó que no existe un perfil. Confirmar ese "
                    "dato y revisar elegibilidad antes de considerar reclamarlo o crearlo."
                    if google_profile_reported_absent
                    else "Preguntar al propietario si existe un perfil público y pedir "
                    "la URL si la respuesta es sí. No asumir que el perfil no existe."
                ),
                "validation_method": (
                    "Registrar la respuesta y la URL, si se proporciona; cualquier "
                    "ausencia seguirá siendo reportada hasta verificarla."
                ),
            }
        )

    return actions


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

    search_status = provider.get("status")
    market_result_available = search_status in {
        "COMPLETED_WITH_RESULTS",
        "COMPLETED_NO_RESULTS",
    }
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
    if not market_result_available:
        limitations = [
            item
            for item in limitations
            if not any(
                phrase in item.casefold()
                for phrase in (
                    "fewer than two comparable competitors",
                    "competitor list is a discovery sample",
                    "no rating or review metric had matching observed evidence",
                )
            )
        ]
    if market_result_available and discovery.entities:
        limitations.append(
            "Directory inclusion does not confirm that an organization is a lead, has current demand, or intends to buy."
        )
    if profile.service_radius is not None:
        limitations.append(
            "The owner-declared service radius is preserved in the profile but cannot be applied as a distance filter without verified business coordinates."
        )
    if search_status not in {"NOT_RUN", "UNSUPPORTED"}:
        limitations.append(
            "The Overpass search uses named administrative areas, which may not match the owner's service boundary exactly."
        )
    limitations.append(
        "No underserved-market or revenue claim is inferred from the number of listings returned."
    )
    if provider_error:
        limitations.append(provider_error)
    if not market_result_available:
        limitations.append(
            "Market discovery did not produce a usable result; competitor counts and market demand are unknown."
        )

    observed = [
        item for item in assessment.evidence if item.kind is EvidenceKind.OBSERVED
    ]
    profile_reported_ids = {
        item.evidence_id
        for item in profile.reported_evidence()
        if item.kind is EvidenceKind.REPORTED
    }
    reported = [
        item
        for item in assessment.evidence
        if item.kind is EvidenceKind.REPORTED
        and item.evidence_id in profile_reported_ids
    ]
    digital_presence_actions = _digital_presence_actions(profile, reported)
    registry_fields = {
        "legal_name",
        "registration_id",
        "legal_entity_status",
        "registered_address",
        "registered_agent",
        "reinstatement_filed_date",
        "reported_prior_names",
    }
    operational_fields = {
        "business_name",
        "industry",
        "vertical",
        "description",
        "city",
        "state_region",
        "primary_services",
        "additional_service_areas",
        "website_url",
        "website_presence",
        "google_business_profile_url",
        "google_business_profile_present",
        "social_media_urls",
        "instagram_presence",
        "instagram_url",
    }
    registry_evidence = [
        _evidence_dict(item) for item in reported if item.field in registry_fields
    ]
    operational_evidence = [
        _evidence_dict(item) for item in reported if item.field in operational_fields
    ]
    assessment_report = assessment_to_dict(assessment)
    if not market_result_available:
        assessment_report["market_entities"] = None
        assessment_report["market_structure_observations"] = None
        market_position = cast(dict[str, object], assessment_report["market_position"])
        market_position["comparison_sample_size"] = None
        market_position["comparable_competitor_ids"] = None
        market_position["relative_strengths"] = None
        market_position["relative_weaknesses"] = None
        market_position["market_gaps"] = None
        market_position["limitations"] = [
            item
            for item in cast(list[str], market_position["limitations"])
            if not any(
                phrase in item.casefold()
                for phrase in (
                    "fewer than two comparable competitors",
                    "competitor list is a discovery sample",
                    "no rating or review metric had matching observed evidence",
                )
            )
        ] + [
            "Market discovery did not produce a usable result; competitor counts and market demand are unknown."
        ]
        assessment_report["limitations"] = [
            item
            for item in cast(list[str], assessment_report["limitations"])
            if not any(
                phrase in item.casefold()
                for phrase in (
                    "fewer than two comparable competitors",
                    "competitor list is a discovery sample",
                    "no rating or review metric had matching observed evidence",
                )
            )
        ] + [
            "Market discovery did not produce a usable result; competitor counts and market demand are unknown."
        ]
        coverage = cast(list[dict[str, object]], market_position["data_coverage"])
        for coverage_item in coverage:
            if coverage_item["signal"] in {
                "comparable_competitors",
                "competitor_rating",
                "competitor_review_count",
            }:
                coverage_item["sample_size"] = None
                coverage_item["available"] = False
                coverage_item["notes"] = (
                    "Market discovery was not available; this run cannot determine "
                    "competitor counts or comparison coverage."
                )
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
    if search_status == "FAILED":
        discovery_summary = "The market search failed; no entity count or market absence can be inferred from this run."
        listing_note = "The provider returned no usable market result."
    elif search_status == "UNSUPPORTED":
        discovery_summary = "This vertical is unsupported by the configured market mappings, so no provider search was sent."
        listing_note = "No market absence can be inferred from an unsupported search."
    elif search_status == "NOT_RUN":
        discovery_summary = "Market discovery was not run; no entity count or market absence can be inferred from this run."
        listing_note = "No provider result is available."
    elif market_result_available:
        discovery_summary = f"Discovery returned {len(discovery.entities)} named organizations across the mapped categories."
        listing_note = "These listings support research hypotheses only; they do not establish buying intent or commercial relationships."
    else:
        discovery_summary = "The market provider returned an unrecognized status; no entity count or market absence can be inferred from this run."
        listing_note = "No usable provider result is available."
    location_context = (
        f"with a registered address reported in {profile.city}, {profile.state_region}"
        if profile.registered_address is not None
        else f"with reported location context in {profile.city}, {profile.state_region}"
    )
    executive_summary = (
        f"The profile describes {profile.business_name} as a {profile.business_model.value} "
        f"{profile.vertical.replace('_', ' ').lower()} business {location_context}. "
        f"{discovery_summary} {listing_note} "
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
                else "Each profile field retains its own evidence status. REPORTED details were supplied by the owner or user and were not independently verified."
            ),
        },
        "executive_summary": executive_summary,
        "what_we_know": {
            "owner_reported": [_evidence_dict(item) for item in reported],
            "observed_in_discovery": [_evidence_dict(item) for item in observed],
            "inferred_hypotheses": [_evidence_dict(item) for item in inferred],
            "information_not_found": missing_benchmark_information,
        },
        "legal_registry": {
            "business_name": profile.legal_name,
            "status": profile.legal_entity_status,
            "registration_id": profile.registration_id,
            "registered_address": profile.registered_address,
            "registered_agent": profile.registered_agent,
            "reinstatement_filed_date": profile.reinstatement_filed_date,
            "reported_prior_names": [
                {"name": name, "status": "REPORTED", "continuity_confirmed": False}
                for name in profile.reported_prior_names or ()
            ],
            "data_status": "REPORTED" if registry_evidence else "NOT_PROVIDED",
            "field_statuses": {
                field: _field_status(profile, field)
                for field in (
                    "legal_name",
                    "legal_entity_status",
                    "registration_id",
                    "registered_address",
                    "registered_agent",
                    "reinstatement_filed_date",
                    "reported_prior_names",
                )
            },
            "verification_note": (
                "Registry details were supplied by the owner; the referenced page was "
                "not retrieved during this assessment."
                if registry_evidence
                and any(
                    "sunbiz.org" in str(item.get("source_url", "")).casefold()
                    for item in registry_evidence
                )
                else "Registry details were supplied by the owner but no Sunbiz source "
                "was supplied; these details were not independently verified."
                if registry_evidence
                else "No legal registry details were supplied; this assessment did not query a registry."
            ),
            "evidence": registry_evidence,
        },
        "operational_profile": {
            "business_name": profile.business_name,
            "industry": profile.industry,
            "vertical": profile.vertical,
            "primary_services": list(profile.primary_services),
            "reported_location": {
                "city": profile.city,
                "state_region": profile.state_region,
                "basis": (
                    "Registered address location; service coverage is recorded separately."
                    if profile.registered_address is not None
                    else "Profile location context; service coverage is recorded separately."
                ),
            },
            "reported_service_areas": list(profile.additional_service_areas or ()),
            "digital_presence": {
                "facebook_urls": [
                    str(item.value)
                    for item in reported
                    if item.field == "social_media_urls"
                    and "facebook.com" in str(item.value).casefold()
                ],
                "instagram_presence": profile.instagram_presence,
                "instagram_presence_status": _field_status(
                    profile, "instagram_presence"
                ),
                "instagram_url": profile.instagram_url,
                "instagram_url_status": _field_status(profile, "instagram_url"),
                "website_url": profile.website_url,
                "website_presence": profile.website_presence,
                "website_presence_status": _field_status(profile, "website_presence"),
                "website_inspection_status": "NOT_INSPECTED",
                "google_business_profile_url": profile.google_business_profile_url,
                "google_business_profile_present": (
                    profile.google_business_profile_present
                ),
                "google_business_profile_status": _field_status(
                    profile, "google_business_profile_present"
                ),
                "google_business_profile_inspection_status": "NOT_INSPECTED",
            },
            "data_status": "REPORTED",
            "evidence": operational_evidence,
        },
        "market_scope": {
            "country": profile.country,
            "state_region": profile.state_region,
            "city": profile.city,
            "search_status": search_status,
            "result_available": market_result_available,
            "declared_service_radius": profile.service_radius,
            "declared_service_radius_unit": (
                profile.service_radius_unit.value
                if profile.service_radius_unit is not None
                else None
            ),
            "additional_service_areas": list(profile.additional_service_areas or ()),
            "applied_spatial_method": (
                "Named OSM administrative areas; radius not applied without business coordinates."
                if market_result_available
                else "Not applied; no usable market result is available."
            ),
        },
        "competitive_environment": {
            "market_result_available": market_result_available,
            "result_status": search_status,
            "potential_competitors": (
                competitors["potential"] if market_result_available else None
            ),
            "verified_competitors": (
                competitors["verified"] if market_result_available else None
            ),
            "same_sector_unqualified": (
                competitors["sector_related_unqualified"]
                if market_result_available
                else None
            ),
            "counts": {
                "all_discovered_entities": (
                    len(discovery.entities) if market_result_available else None
                ),
                "potential_competitors": (
                    len(competitors["potential"]) if market_result_available else None
                ),
                "verified_competitors": (
                    len(competitors["verified"]) if market_result_available else None
                ),
                "same_sector_unqualified": len(
                    competitors["sector_related_unqualified"]
                )
                if market_result_available
                else None,
            },
        },
        "potential_customers": customers if market_result_available else None,
        "partners_and_channels": partners if market_result_available else None,
        "suppliers": suppliers if market_result_available else None,
        "benchmark": {
            "status": benchmark_status,
            "market_result_available": market_result_available,
            "comparable_competitor_ids": (
                [item["entity_id"] for item in comparable_records]
                if market_result_available
                else None
            ),
            "comparison_dimensions": benchmark_metrics
            if market_result_available
            else None,
            "metrics_compared": [] if market_result_available else None,
            "metric_note": "No rating or review metric is compared unless equivalent OBSERVED values are available for both the business and at least two verified competitors.",
            "comparison_rows": comparable_records if market_result_available else None,
            "missing_information": missing_benchmark_information,
            "rule": "A company is comparable only when the existing LIVE assessment accepts its supported industry category and matching OBSERVED evidence covers service, target segment, geographic coverage, and business model.",
        },
        "opportunities": {
            "business_assessment_actions": engine_opportunities,
            "entity_research_hypotheses": relationship_opportunities,
        },
        "digital_presence_actions": digital_presence_actions,
        "best_next_move": best_next_move,
        "limitations": list(dict.fromkeys(limitations)),
        "sources_and_research_date": {
            "consulted_at_utc": started_at.astimezone(timezone.utc).isoformat(),
            "provider": provider,
            "sources": source_urls,
        },
        "assessment": assessment_report,
    }

    return cast(dict[str, object], sanitize_report_data(report))


def render_business_report_markdown(report: dict[str, object]) -> str:
    """Render an accessible Markdown version of the profile report."""

    profile = cast(dict[str, object], report["profile"])
    competition = cast(dict[str, object], report["competitive_environment"])
    benchmark = cast(dict[str, object], report["benchmark"])
    opportunities = cast(dict[str, list[dict[str, object]]], report["opportunities"])
    research = cast(dict[str, object], report["sources_and_research_date"])
    provider = cast(dict[str, object], research["provider"])
    search_status = provider.get("status")
    competition_counts: tuple[str, ...]
    if search_status == "FAILED":
        competition_counts = (
            "No se pueden determinar los conteos de competidores porque el proveedor no completó la búsqueda.",
        )
    elif search_status == "UNSUPPORTED":
        competition_counts = (
            "No hubo búsqueda para este vertical; los conteos de competidores no están disponibles.",
        )
    elif search_status == "NOT_RUN":
        competition_counts = (
            "No se ejecutó la búsqueda; los conteos de competidores no están disponibles.",
        )
    elif search_status in {"COMPLETED_WITH_RESULTS", "COMPLETED_NO_RESULTS"}:
        competition_counts = (
            f"- Competidores verificados: {len(cast(list[object], competition['verified_competitors']))}",
            f"- Competidores potenciales: {len(cast(list[object], competition['potential_competitors']))}",
            f"- Empresas del sector aún sin evidencia de competencia directa: {len(cast(list[object], competition['same_sector_unqualified']))}",
        )
    else:
        competition_counts = (
            "El estado de la búsqueda no es reconocido; los conteos de competidores no están disponibles.",
        )
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
    ]
    legal_registry = cast(dict[str, object], report["legal_registry"])
    registry_evidence = cast(list[dict[str, object]], legal_registry["evidence"])
    registry_sources = list(
        dict.fromkeys(
            str(item["source_url"])
            for item in registry_evidence
            if item.get("source_url") is not None
        )
    )
    lines.extend(
        (
            "## Datos registrales",
            "",
            f"- Nombre legal: {legal_registry['business_name'] or 'No proporcionado'} ({cast(dict[str, str], legal_registry['field_statuses'])['legal_name']})",
            f"- Estado registral: {legal_registry['status'] or 'No proporcionado'} ({cast(dict[str, str], legal_registry['field_statuses'])['legal_entity_status']})",
            f"- Número de registro: {legal_registry['registration_id'] or 'No proporcionado'} ({cast(dict[str, str], legal_registry['field_statuses'])['registration_id']})",
            f"- Dirección principal registral: {legal_registry['registered_address'] or 'No proporcionada'} ({cast(dict[str, str], legal_registry['field_statuses'])['registered_address']})",
            f"- Agente registrado: {legal_registry['registered_agent'] or 'No proporcionado'} ({cast(dict[str, str], legal_registry['field_statuses'])['registered_agent']})",
            f"- Reinstalación presentada: {legal_registry['reinstatement_filed_date'] or 'No proporcionada'} ({cast(dict[str, str], legal_registry['field_statuses'])['reinstatement_filed_date']})",
            f"- Fuentes registrales: {', '.join(registry_sources) or 'No proporcionadas'}",
            str(legal_registry["verification_note"]),
        )
    )
    for prior_name in cast(
        list[dict[str, object]], legal_registry["reported_prior_names"]
    ):
        lines.append(
            f"- Nombre anterior reportado: {prior_name['name']} (continuidad con la LLC no confirmada)"
        )

    operations = cast(dict[str, object], report["operational_profile"])
    digital = cast(dict[str, object], operations["digital_presence"])
    facebook_urls = cast(list[str], digital["facebook_urls"])
    services = cast(list[str], operations["primary_services"])
    service_areas = cast(list[str], operations["reported_service_areas"])
    lines.extend(
        (
            "",
            "## Información operativa reportada",
            "",
            f"- Servicios reportados: {', '.join(services) or 'No proporcionados'}",
            f"- Cobertura reportada: {', '.join(service_areas) or 'No proporcionada'}",
            f"- Facebook: {', '.join(facebook_urls) or 'URL no proporcionada'} (REPORTED; no inspeccionado)",
            (
                "- Instagram: presencia REPORTED; URL NEEDS_CONFIRMATION."
                if digital["instagram_presence"] is True
                and digital["instagram_url"] is None
                else f"- Instagram: presencia {digital['instagram_presence']}; URL {digital['instagram_url'] or 'no proporcionada'}."
            ),
            (
                "- Sitio web: el propietario reporta que no existe; URL no proporcionada y sitio no inspeccionado. La ausencia no está verificada."
                if digital["website_presence"] is False
                else "- Sitio web: URL no proporcionada/no inspeccionado; no se infiere que no exista."
            ),
            (
                "- Google Business Profile: el propietario reporta que no existe; URL no proporcionada y perfil no inspeccionado. La ausencia no está verificada."
                if digital["google_business_profile_present"] is False
                else "- Google Business Profile: URL no proporcionada/no inspeccionado; no se infiere que no exista."
            ),
            "Los datos operativos son REPORTED y no se atribuyen a Sunbiz.",
        )
    )

    digital_actions = cast(list[dict[str, object]], report["digital_presence_actions"])
    lines.extend(("", "## Acciones de presencia digital", ""))
    if not digital_actions:
        lines.append(
            "No hay acciones de presencia digital derivadas de los datos actuales."
        )
    for action in digital_actions:
        lines.extend(
            (
                f"### {action['title']}",
                "",
                f"Estado de los datos: {action['data_status']}",
                f"Acción sugerida: {action['recommended_action']}",
                f"Cómo validarla: {action['validation_method']}",
                f"Evidencia: {', '.join(cast(list[str], action['source_urls'])) or 'sin URL de origen'}",
                "",
            )
        )
    if isinstance(search_status, str):
        lines.extend(
            (
                "## Búsqueda de mercado",
                "",
                f"- Estado: **{search_status}**",
                f"- Intentos al proveedor: {provider.get('attempt_count', provider.get('request_count', 'desconocido'))}",
                f"- Reintentos: {provider.get('retry_count', 0)}",
            )
        )
        result_count = provider.get("result_count")
        if isinstance(result_count, int):
            lines.append(f"- Organizaciones devueltas: {result_count}")
        if search_status == "COMPLETED_NO_RESULTS":
            lines.append(
                "La búsqueda terminó correctamente y no devolvió organizaciones con las categorías consultadas."
            )
        elif search_status == "FAILED":
            lines.append(
                "El proveedor no completó la búsqueda; el resultado del mercado es desconocido."
            )
            if provider.get("error"):
                lines.append(f"- Error del proveedor: {provider['error']}")
        elif search_status == "UNSUPPORTED" and provider.get("unsupported_reason"):
            lines.append(str(provider["unsupported_reason"]))
        elif search_status == "NOT_RUN":
            lines.append(
                "No se ejecutó una búsqueda de mercado; los competidores y la demanda son desconocidos."
            )
        elif search_status not in {
            "COMPLETED_WITH_RESULTS",
            "COMPLETED_NO_RESULTS",
        }:
            lines.append(
                "El proveedor devolvió un estado no reconocido; los resultados de mercado son desconocidos."
            )
        lines.append("")
    lines.extend(
        (
            "## Perfil declarado por el propietario",
            "",
            f"- Oferta principal: {', '.join(cast(list[str], profile['primary_services'])) or 'No proporcionada'}",
            f"- Segmentos objetivo: {', '.join(cast(list[str], profile['target_customer_segments'])) or 'No proporcionados'}",
            f"- Modelo comercial: {profile['business_model']}",
            f"- Radio de servicio declarado: {profile['service_radius']} {profile['service_radius_unit']}"
            if profile["service_radius"] is not None
            else "- Radio de servicio declarado: No proporcionado",
            f"- Zonas adicionales: {', '.join(cast(list[str], profile['additional_service_areas'] or [])) or 'No declaradas'}",
            "Los campos marcados REPORTED proceden del propietario; UNKNOWN y NOT_PROVIDED indican información pendiente. No se verificaron de manera independiente.",
            "",
            "## Entorno competitivo",
            "",
            *competition_counts,
            "",
            "Los listados de directorio no demuestran por sí solos que una organización compita directamente.",
            "",
            "## Benchmark",
            "",
            f"Estado: **{benchmark['status']}**",
            "",
        )
    )
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
            if search_status == "FAILED":
                lines.append(
                    "No se puede determinar si hay organizaciones con esta categoría porque el proveedor no completó la búsqueda."
                )
            elif search_status == "UNSUPPORTED":
                lines.append(
                    "No se buscó este vertical porque no tiene una correspondencia de fuente habilitada."
                )
            elif search_status == "NOT_RUN":
                lines.append(
                    "No se ejecutó la búsqueda; no se puede determinar si hay organizaciones con esta categoría."
                )
            elif search_status not in {
                "COMPLETED_WITH_RESULTS",
                "COMPLETED_NO_RESULTS",
            }:
                lines.append(
                    "El estado de la búsqueda no es reconocido; no se puede determinar si hay organizaciones con esta categoría."
                )
            else:
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
