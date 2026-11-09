"""Qualification and Spanish reporting for a bounded commercial research pilot."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import cast

from aeos.live.domain.evidence import SourceEvidence
from aeos.live.domain.opportunity_inbox import is_reserved_example_source_url
from aeos.live.domain.market_intelligence import (
    CityMarketResearch,
    CommercialOpportunity,
    CompetitorClassification,
    DemandStatus,
    MarketEvidence,
    MarketOrganization,
    OpportunityPriority,
    OrganizationRole,
    PublicDemandSignal,
    ResearchStatus,
    SourceCoverage,
)
from aeos.live.domain.profile import BusinessProfile
from aeos.live.domain.url_policy import safe_url_for_report
from aeos.live.domain.vertical import (
    canonical_service_for_vertical,
    verticals_match,
)


def build_market_report(
    profile: BusinessProfile,
    markets: tuple[CityMarketResearch, ...],
    *,
    owner_evidence: tuple[SourceEvidence, ...],
    snapshot_at: datetime,
    stale_after_days: int = 30,
    website_reported_location: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build independent city reports and a comparison from source-backed records."""

    if any(not verticals_match(profile.vertical, item.vertical) for item in markets):
        raise ValueError("market vertical must match the selected organization profile")
    if len({item.city.casefold() for item in markets}) != len(markets):
        raise ValueError("each city must have one independently collected market scope")
    as_of = snapshot_at.date()
    city_reports = tuple(
        _city_report(
            market,
            as_of=as_of,
            stale_after_days=stale_after_days,
            opportunities=prioritize_opportunities(
                market,
                as_of=as_of,
                stale_after_days=stale_after_days,
                business_profile=profile,
            ),
        )
        for market in markets
    )
    return {
        "project": "AEOS-LIVE-002B2",
        "business_profile": profile.to_dict(),
        "owner_confirmation_evidence": [
            _source_evidence_dict(item) for item in owner_evidence
        ],
        "website_reported_location": website_reported_location,
        "snapshot_at": snapshot_at.isoformat(),
        "demand_actionability_window_days": stale_after_days,
        "markets": list(city_reports),
        "combined_comparison": _combined_report(
            markets,
            city_reports,
            as_of=as_of,
            stale_after_days=stale_after_days,
            business_profile=profile,
        ),
    }


def prioritize_opportunities(
    market: CityMarketResearch,
    *,
    as_of: date,
    stale_after_days: int = 30,
    business_profile: BusinessProfile | None = None,
) -> tuple[CommercialOpportunity, ...]:
    """Put current explicit requests first, then buyer fit, then referral channels."""

    opportunities: list[CommercialOpportunity] = []
    evidence_by_id = {item.evidence_id: item for item in market.evidence}
    for signal in market.demand_signals:
        if business_profile is not None and not _service_in_profile(
            business_profile, signal.service_requested
        ):
            continue
        if not signal.is_actionable(as_of, stale_after_days=stale_after_days):
            continue
        evidence = next(
            item for item in market.evidence if item.evidence_id == signal.evidence_id
        )
        opportunities.append(
            CommercialOpportunity(
                opportunity_id=f"opportunity:{signal.signal_id}",
                city=market.city,
                priority=OpportunityPriority.HIGH,
                opportunity_type="PUBLIC_DEMAND_SIGNAL",
                target_id=signal.signal_id,
                target_name=f"Solicitud pública de {signal.service_requested}",
                why_it_matters=f"La solicitud pública es reciente y coincide con el servicio configurado para la vertical {market.vertical}.",
                recommended_next_action="Revise el hilo público y responda solo si sigue abierto y las reglas de la plataforma lo permiten.",
                validation_question="¿La persona aún necesita el servicio y qué frecuencia o fecha requiere?",
                public_contact_channel=signal.source_url,
                confidence=evidence.confidence,
                evidence_ids=(signal.evidence_id,),
                limitations=signal.limitations,
            )
        )
    for organization in market.organizations:
        if organization.role is OrganizationRole.POTENTIAL_BUYER:
            if not organization.buyer_fit_reason:
                continue
            intent_status = _organization_buying_intent_status(
                organization,
                evidence_by_id,
                as_of=as_of,
                stale_after_days=stale_after_days,
            )
            if intent_status is DemandStatus.BUYING_INTENT:
                intent_evidence_ids = organization.buying_intent_evidence_ids
                opportunities.append(
                    CommercialOpportunity(
                        opportunity_id=f"opportunity:buyer-intent:{organization.entity_id}:{market.city.casefold()}",
                        city=market.city,
                        priority=OpportunityPriority.HIGH,
                        opportunity_type="BUYER_BUYING_INTENT",
                        target_id=organization.entity_id,
                        target_name=organization.name,
                        why_it_matters=organization.buyer_fit_reason,
                        recommended_next_action=organization.recommended_action,
                        validation_question=organization.validation_question,
                        public_contact_channel=(
                            organization.public_contacts[0]
                            if organization.public_contacts
                            else organization.website_url
                        ),
                        confidence=min(
                            evidence_by_id[item].confidence
                            for item in intent_evidence_ids
                        ),
                        evidence_ids=intent_evidence_ids,
                        limitations=tuple(
                            dict.fromkeys(
                                (
                                    *organization.limitations,
                                    "La solicitud pública debe confirmarse antes de invertir tiempo en una cotización.",
                                )
                            )
                        ),
                    )
                )
                continue
            cleaning_coordination = (
                "coordination" in organization.buyer_fit_reason.casefold()
            )
            opportunities.append(
                CommercialOpportunity(
                    opportunity_id=f"opportunity:{organization.entity_id}:{market.city.casefold()}",
                    city=market.city,
                    priority=(
                        OpportunityPriority.MEDIUM
                        if cleaning_coordination
                        else OpportunityPriority.LOW
                    ),
                    opportunity_type="BUYER_FIT",
                    target_id=organization.entity_id,
                    target_name=organization.name,
                    why_it_matters=organization.buyer_fit_reason,
                    recommended_next_action=organization.recommended_action,
                    validation_question=organization.validation_question,
                    public_contact_channel=(
                        organization.public_contacts[0]
                        if organization.public_contacts
                        else organization.website_url
                    ),
                    confidence=_confidence_for(organization, market),
                    evidence_ids=organization.evidence_ids,
                    limitations=tuple(
                        dict.fromkeys(
                            (
                                *organization.limitations,
                                "BUYER_FIT no establece BUYING_INTENT ni una vacante actual para proveedores.",
                            )
                        )
                    ),
                )
            )
        elif organization.role is OrganizationRole.REFERRAL_PARTNER:
            opportunities.append(
                CommercialOpportunity(
                    opportunity_id=f"opportunity:{organization.entity_id}:{market.city.casefold()}",
                    city=market.city,
                    priority=OpportunityPriority.LOW,
                    opportunity_type="REFERRAL_PARTNER",
                    target_id=organization.entity_id,
                    target_name=organization.name,
                    why_it_matters=organization.referral_reason
                    or "Canal local potencial; la voluntad de referir no está confirmada.",
                    recommended_next_action=organization.recommended_action,
                    validation_question=organization.validation_question,
                    public_contact_channel=(
                        organization.public_contacts[0]
                        if organization.public_contacts
                        else organization.website_url
                    ),
                    confidence=_confidence_for(organization, market),
                    evidence_ids=organization.evidence_ids,
                    limitations=organization.limitations,
                )
            )
    order = {
        OpportunityPriority.HIGH: 0,
        OpportunityPriority.MEDIUM: 1,
        OpportunityPriority.LOW: 2,
    }
    return tuple(
        sorted(
            opportunities,
            key=lambda item: (
                order[item.priority],
                item.opportunity_type,
                item.target_name.casefold(),
            ),
        )
    )


def _service_in_profile(profile: BusinessProfile, service: str) -> bool:
    configured = tuple(profile.primary_services) + tuple(
        profile.secondary_services or ()
    )
    if not configured:
        return False
    requested = canonical_service_for_vertical(profile.vertical, service)
    return requested in {
        canonical_service_for_vertical(profile.vertical, item) for item in configured
    }


def _confidence_for(
    organization: MarketOrganization, market: CityMarketResearch
) -> float:
    evidence = {item.evidence_id: item for item in market.evidence}
    values = [evidence[item].confidence for item in organization.evidence_ids]
    return min(values) if values else 0.0


def _organization_buying_intent_status(
    organization: MarketOrganization,
    evidence_by_id: dict[str, MarketEvidence],
    *,
    as_of: date,
    stale_after_days: int,
) -> DemandStatus | None:
    """Classify a buyer's separately cited, public intent evidence by freshness."""

    if not organization.buying_intent_evidence_ids:
        return None
    if organization.synthetic_record:
        return DemandStatus.INSUFFICIENT_EVIDENCE
    statuses: list[DemandStatus] = []
    for evidence_id in organization.buying_intent_evidence_ids:
        published_at = evidence_by_id[evidence_id].published_at
        if published_at is None or published_at > as_of:
            statuses.append(DemandStatus.INSUFFICIENT_EVIDENCE)
            continue
        age_days = (as_of - published_at).days
        statuses.append(
            DemandStatus.HISTORICAL_BUYING_INTENT
            if age_days > stale_after_days
            else DemandStatus.BUYING_INTENT
        )
    if DemandStatus.BUYING_INTENT in statuses:
        return DemandStatus.BUYING_INTENT
    if DemandStatus.HISTORICAL_BUYING_INTENT in statuses:
        return DemandStatus.HISTORICAL_BUYING_INTENT
    return DemandStatus.INSUFFICIENT_EVIDENCE


def _city_report(
    market: CityMarketResearch,
    *,
    as_of: date,
    stale_after_days: int,
    opportunities: tuple[CommercialOpportunity, ...],
) -> dict[str, object]:
    evidence_by_id = {item.evidence_id: item for item in market.evidence}
    direct = tuple(
        item
        for item in market.organizations
        if item.competitor_classification is CompetitorClassification.DIRECT_COMPETITOR
    )
    indirect = tuple(
        item
        for item in market.organizations
        if item.competitor_classification
        is CompetitorClassification.INDIRECT_COMPETITOR
    )
    unverified = tuple(
        item
        for item in market.organizations
        if item.competitor_classification
        in {
            CompetitorClassification.UNVERIFIED_CLEANING_BUSINESS,
            CompetitorClassification.UNVERIFIED_BUSINESS,
        }
    )
    buyers = tuple(
        item
        for item in market.organizations
        if item.role is OrganizationRole.POTENTIAL_BUYER
    )
    partners = tuple(
        item
        for item in market.organizations
        if item.role is OrganizationRole.REFERRAL_PARTNER
    )
    suppliers = tuple(
        item for item in market.organizations if item.role is OrganizationRole.SUPPLIER
    )
    directory_candidates = tuple(
        item
        for item in market.organizations
        if item.role is OrganizationRole.DIRECTORY_CANDIDATE
    )
    actionable = tuple(
        item
        for item in market.demand_signals
        if item.is_actionable(as_of, stale_after_days=stale_after_days)
    )
    historical = tuple(
        item
        for item in market.demand_signals
        if item.status_at(as_of, stale_after_days=stale_after_days)
        is DemandStatus.HISTORICAL_BUYING_INTENT
    )
    buyer_intent_statuses = {
        item.entity_id: _organization_buying_intent_status(
            item,
            evidence_by_id,
            as_of=as_of,
            stale_after_days=stale_after_days,
        )
        for item in buyers
    }

    def organization_dicts(
        items: tuple[MarketOrganization, ...],
    ) -> list[dict[str, object]]:
        return [
            _organization_dict(
                item,
                buying_intent_status=buyer_intent_statuses.get(item.entity_id),
            )
            for item in items
        ]

    return {
        "city": market.city,
        "state": market.state,
        "vertical": market.vertical,
        "status": _market_status(market),
        "counts": {
            "direct_competitors": len(direct),
            "indirect_competitors": len(indirect),
            "unverified_businesses": len(unverified),
            "unverified_cleaning_businesses": len(unverified),  # Legacy report key.
            "potential_buyers": len(buyers),
            "current_b2b_buying_intent_organizations": sum(
                status is DemandStatus.BUYING_INTENT
                for status in buyer_intent_statuses.values()
            ),
            "historical_b2b_buying_intent_organizations": sum(
                status is DemandStatus.HISTORICAL_BUYING_INTENT
                for status in buyer_intent_statuses.values()
            ),
            "current_buying_intent_signals": len(actionable),
            "historical_explicit_demand_signals": len(historical),
            "referral_partners": len(partners),
            "suppliers": len(suppliers),
            "unqualified_directory_candidates": len(directory_candidates),
        },
        "competitors": organization_dicts((*direct, *indirect, *unverified)),
        "potential_buyers": organization_dicts(buyers),
        "demand_signals": [
            _demand_dict(item, as_of=as_of, stale_after_days=stale_after_days)
            for item in market.demand_signals
        ],
        "referral_partners": organization_dicts(partners),
        "suppliers": organization_dicts(suppliers),
        "unqualified_directory_candidates": organization_dicts(directory_candidates),
        "source_coverage": [_coverage_dict(item) for item in market.source_coverage],
        "opportunity_queue": [_opportunity_dict(item) for item in opportunities],
        "service_specialization": sorted(
            {service for entity in direct for service in entity.services},
            key=str.casefold,
        ),
        "service_specialization_sources": [
            {
                "organization": item.name,
                "services": list(item.services),
                "evidence_ids": list(item.evidence_ids),
            }
            for item in direct
        ],
        "published_pricing": [
            {
                "organization": item.name,
                "pricing_model": item.pricing_model,
                "evidence_ids": list(item.evidence_ids),
            }
            for item in direct
            if item.pricing_model
        ],
        "main_gaps_and_limitations": list(
            dict.fromkeys(
                (
                    *market.limitations,
                    "No se recopilaron calificaciones ni cantidades de reseñas de Google Business Profile mediante una API autorizada.",
                    "No se calificó ningún proveedor con las fuentes manuales seleccionadas; la búsqueda de proveedores es secundaria.",
                    "Las operaciones descritas en fuentes públicas muestran encaje operativo, no disposición a incorporar otro proveedor.",
                )
            )
        ),
        "evidence": [_evidence_dict(item) for item in market.evidence],
    }


def _market_status(market: CityMarketResearch) -> str:
    relevant = tuple(
        item
        for item in market.source_coverage
        if item.status
        not in {ResearchStatus.NOT_REQUESTED, ResearchStatus.PROVIDER_NOT_CONFIGURED}
    )
    if any(item.status.value == "PROVIDER_UNAVAILABLE" for item in relevant):
        return "PARTIAL_PROVIDER_UNAVAILABLE"
    if not market.organizations and not market.demand_signals:
        if relevant and all(
            item.status.value == "NO_RESULTS_FOUND" for item in relevant
        ):
            return "NO_RESULTS_FOUND"
        return "INSUFFICIENT_EVIDENCE"
    return "SUCCEEDED_WITH_LIMITATIONS"


def _organization_dict(
    item: MarketOrganization,
    *,
    buying_intent_status: DemandStatus | None = None,
) -> dict[str, object]:
    competitor = item.competitor_classification
    return {
        "entity_id": item.entity_id,
        "name": item.name,
        "vertical": item.vertical,
        "city": item.city,
        "role": item.role.value,
        "synthetic_record": item.synthetic_record,
        "competitor_classification": competitor.value if competitor else None,
        "website": item.website_url,
        "public_address_or_service_area": item.public_address
        or ", ".join(item.service_areas)
        or None,
        "services": list(item.services),
        "customer_segments": list(item.customer_segments),
        "vacation_rental_specialization": item.vacation_rental_specialization,
        "recurring_options": list(item.recurring_options),
        "pricing_model": item.pricing_model,
        "public_listing": item.public_listing_url,
        "rating_claim": item.rating_claim,
        "review_count_claim": item.review_count_claim,
        "booking_methods": list(item.booking_methods),
        "conversion_channels": list(item.conversion_channels),
        "public_contacts": list(item.public_contacts),
        "buyer_fit": "BUYER_FIT"
        if item.role is OrganizationRole.POTENTIAL_BUYER
        else None,
        "buying_intent": (
            buying_intent_status.value if buying_intent_status else "NOT_ESTABLISHED"
        )
        if item.role is OrganizationRole.POTENTIAL_BUYER
        else None,
        "buyer_fit_reason": item.buyer_fit_reason,
        "referral_reason": item.referral_reason,
        "recommended_next_action": item.recommended_action,
        "suggested_validation_question": item.validation_question,
        "evidence_ids": list(item.evidence_ids),
        "buying_intent_evidence_ids": list(item.buying_intent_evidence_ids),
        "limitations": list(item.limitations),
    }


def _demand_dict(
    item: object, *, as_of: date, stale_after_days: int
) -> dict[str, object]:
    signal = cast(PublicDemandSignal, item)
    status = signal.status_at(as_of, stale_after_days=stale_after_days)
    return {
        "signal_id": signal.signal_id,
        "city": signal.city,
        "platform": signal.platform,
        "source_url": signal.source_url,
        "publication_date": signal.publication_date.isoformat()
        if signal.publication_date
        else None,
        "service_requested": signal.service_requested,
        "vertical": signal.vertical,
        "supporting_excerpt": signal.supporting_excerpt,
        "supporting_excerpt_es": signal.supporting_excerpt_es,
        "evidence_classification": "SYNTHETIC"
        if signal.synthetic_record
        else "OBSERVED",
        "synthetic_record": signal.synthetic_record,
        "intent_classification": status.value,
        "still_actionable": status is DemandStatus.BUYING_INTENT,
        "evidence_id": signal.evidence_id,
        "limitations": list(signal.limitations),
    }


def _evidence_dict(item: object) -> dict[str, object]:
    evidence = cast(MarketEvidence, item)
    return {
        "evidence_id": evidence.evidence_id,
        "entity_id": evidence.entity_id,
        "field": evidence.field,
        "value": evidence.value,
        "source_name": evidence.source_name,
        "source_url": evidence.source_url,
        "retrieved_at": evidence.retrieved_at.isoformat(),
        "published_at": evidence.published_at.isoformat()
        if evidence.published_at
        else None,
        "classification": evidence.classification.value,
        "confidence": evidence.confidence,
        "supporting_information": evidence.supporting_information,
        "limitations": list(evidence.limitations),
    }


def _coverage_dict(item: object) -> dict[str, object]:
    coverage = cast(SourceCoverage, item)
    return {
        "source_name": coverage.source_name,
        "status": coverage.status.value,
        "retrieved_at": coverage.retrieved_at.isoformat(),
        "result_count": coverage.result_count,
        "request_count": coverage.request_count,
        "note": coverage.note,
    }


def _opportunity_dict(item: CommercialOpportunity) -> dict[str, object]:
    return {
        "opportunity_id": item.opportunity_id,
        "city": item.city,
        "priority": item.priority.value,
        "opportunity_type": item.opportunity_type,
        "target_id": item.target_id,
        "target": item.target_name,
        "why_it_matters": item.why_it_matters,
        "recommended_next_action": item.recommended_next_action,
        "suggested_validation_question": item.validation_question,
        "public_contact_channel": item.public_contact_channel,
        "confidence": item.confidence,
        "evidence_ids": list(item.evidence_ids),
        "limitations": list(item.limitations),
    }


def _source_evidence_dict(item: SourceEvidence) -> dict[str, object]:
    return {
        "evidence_id": item.evidence_id,
        "entity_id": item.owner_entity_id or item.subject,
        "field": item.field,
        "value": item.value,
        "source_name": item.source_name,
        "source_url": item.source_url,
        "retrieved_at": item.retrieved_at.isoformat() if item.retrieved_at else None,
        "classification": item.kind.value,
        "supporting_information": item.excerpt,
        "confidence": item.confidence,
    }


def _combined_report(
    markets: tuple[CityMarketResearch, ...],
    city_reports: tuple[dict[str, object], ...],
    *,
    as_of: date,
    stale_after_days: int,
    business_profile: BusinessProfile,
) -> dict[str, object]:
    entity_by_id: dict[str, MarketOrganization] = {}
    for market in markets:
        for entity in market.organizations:
            entity_by_id.setdefault(entity.entity_id, entity)
    category_counts = Counter(item.role for item in entity_by_id.values())
    direct_ids = {
        item.entity_id
        for item in entity_by_id.values()
        if item.competitor_classification is CompetitorClassification.DIRECT_COMPETITOR
    }
    indirect_ids = {
        item.entity_id
        for item in entity_by_id.values()
        if item.competitor_classification
        is CompetitorClassification.INDIRECT_COMPETITOR
    }
    unverified_ids = {
        item.entity_id
        for item in entity_by_id.values()
        if item.competitor_classification
        in {
            CompetitorClassification.UNVERIFIED_CLEANING_BUSINESS,
            CompetitorClassification.UNVERIFIED_BUSINESS,
        }
    }
    current_signals = [
        signal
        for market in markets
        for signal in market.demand_signals
        if signal.is_actionable(as_of, stale_after_days=stale_after_days)
    ]
    historical_signals = [
        signal
        for market in markets
        for signal in market.demand_signals
        if signal.status_at(as_of, stale_after_days=stale_after_days)
        is DemandStatus.HISTORICAL_BUYING_INTENT
    ]
    current_b2b_intent_ids: set[str] = set()
    historical_b2b_intent_ids: set[str] = set()
    for market in markets:
        evidence_by_id = {item.evidence_id: item for item in market.evidence}
        for organization in market.organizations:
            if organization.role is not OrganizationRole.POTENTIAL_BUYER:
                continue
            status = _organization_buying_intent_status(
                organization,
                evidence_by_id,
                as_of=as_of,
                stale_after_days=stale_after_days,
            )
            if status is DemandStatus.BUYING_INTENT:
                current_b2b_intent_ids.add(organization.entity_id)
            elif status is DemandStatus.HISTORICAL_BUYING_INTENT:
                historical_b2b_intent_ids.add(organization.entity_id)
    rows: list[dict[str, object]] = []
    for report in city_reports:
        counts = cast(dict[str, object], report["counts"])
        rows.append(
            {
                "city": report["city"],
                "direct_competitors": counts["direct_competitors"],
                "potential_buyers": counts["potential_buyers"],
                "current_b2b_buying_intent_organizations": counts[
                    "current_b2b_buying_intent_organizations"
                ],
                "historical_b2b_buying_intent_organizations": counts[
                    "historical_b2b_buying_intent_organizations"
                ],
                "current_buying_intent_signals": counts[
                    "current_buying_intent_signals"
                ],
                "historical_explicit_demand_signals": counts[
                    "historical_explicit_demand_signals"
                ],
                "referral_partners": counts["referral_partners"],
                "service_specialization": report["service_specialization"],
                "service_specialization_sources": report[
                    "service_specialization_sources"
                ],
                "published_pricing": report["published_pricing"],
                "source_coverage": report["source_coverage"],
                "main_gaps_and_limitations": report["main_gaps_and_limitations"],
            }
        )
    return {
        "counts_unique_organizations": {
            "direct_competitors": len(direct_ids),
            "indirect_competitors": len(indirect_ids),
            "unverified_businesses": len(unverified_ids),
            "unverified_cleaning_businesses": len(unverified_ids),  # Legacy report key.
            "potential_buyers": category_counts[OrganizationRole.POTENTIAL_BUYER],
            "current_b2b_buying_intent_organizations": len(current_b2b_intent_ids),
            "historical_b2b_buying_intent_organizations": len(
                historical_b2b_intent_ids
            ),
            "current_buying_intent_signals": len(current_signals),
            "historical_explicit_demand_signals": len(
                {item.signal_id for item in historical_signals}
            ),
            "referral_partners": category_counts[OrganizationRole.REFERRAL_PARTNER],
            "suppliers": category_counts[OrganizationRole.SUPPLIER],
            "unqualified_directory_candidates": category_counts[
                OrganizationRole.DIRECTORY_CANDIDATE
            ],
        },
        "city_comparison": rows,
        "focus_recommendation_evidence_ids": list(
            dict.fromkeys(
                signal.evidence_id
                for market in markets
                for signal in market.demand_signals
            )
        ),
        "recommended_first_contacts": _recommended_first_buyer_contacts(
            markets, as_of=as_of, stale_after_days=stale_after_days
        ),
        "focus_recommendation": (
            "Compare los mercados con las mismas fuentes y criterios; la muestra disponible no establece tamaño de mercado ni intención actual."
            if len(markets) >= 2
            else "La comparación requiere dos mercados independientes."
        ),
        "recommended_customer_segments": list(
            business_profile.target_customer_segments
        ),
        "recommended_first_contact_types": [
            "Compradores potenciales con evidencia pública de afinidad; validar si aceptan proveedores externos.",
            "Organizaciones asociadas potenciales; no existe evidencia de acuerdos o voluntad de referir.",
        ],
        "public_demand_channels": [
            "Fuentes públicas registradas en la cobertura de cada mercado: revisar solicitudes recientes y confirmar que siguen abiertas antes de responder.",
            "Directorios y tablones públicos: distinguir solicitudes de compradores de anuncios publicados por proveedores.",
            "Las redes sociales no fueron automatizadas; se admite captura manual de URL pública y evidencia.",
        ],
        "ranking_note": "No se declara un mercado ganador por cantidad de directorio. Los conteos son una muestra de fuentes identificadas, no tamaño de mercado ni cuota.",
    }


def _recommended_first_buyer_contacts(
    markets: tuple[CityMarketResearch, ...],
    *,
    as_of: date,
    stale_after_days: int,
) -> list[dict[str, object]]:
    """Suggest buyer validation order from public vendor paths and profile fit."""

    candidates: dict[
        str, tuple[tuple[int, int, int], MarketOrganization, DemandStatus | None]
    ] = {}
    sequence = 0
    for market_index, market in enumerate(markets):
        evidence_by_id = {item.evidence_id: item for item in market.evidence}
        for organization in market.organizations:
            if (
                organization.role is not OrganizationRole.POTENTIAL_BUYER
                or not organization.buyer_fit_reason
            ):
                continue
            public_vendor_path = any(
                any(term in channel.casefold() for term in ("vendor", "proveedor"))
                for channel in organization.conversion_channels
            )
            score = (0 if public_vendor_path else 1, market_index, sequence)
            intent_status = _organization_buying_intent_status(
                organization,
                evidence_by_id,
                as_of=as_of,
                stale_after_days=stale_after_days,
            )
            current = candidates.get(organization.entity_id)
            if current is None or score < current[0]:
                candidates[organization.entity_id] = (
                    score,
                    organization,
                    intent_status,
                )
            sequence += 1
    return [
        {
            "city": organization.city,
            "name": organization.name,
            "qualification": "BUYER_FIT",
            "buying_intent": intent_status.value
            if intent_status
            else "NOT_ESTABLISHED",
            "why_it_matters": organization.buyer_fit_reason,
            "recommended_next_action": organization.recommended_action,
            "validation_question": organization.validation_question,
            "public_contact_channels": list(
                dict.fromkeys(
                    (*organization.conversion_channels, *organization.public_contacts)
                )
            ),
            "evidence_ids": list(organization.evidence_ids),
        }
        for _, organization, intent_status in sorted(
            candidates.values(), key=lambda item: item[0]
        )
    ]


def render_market_report_markdown(report: dict[str, object]) -> str:
    """Render a single-city report as Spanish Markdown with linked evidence."""

    market = cast(dict[str, object], report["market"])
    counts = cast(dict[str, object], market["counts"])
    evidence_rows = cast(list[dict[str, object]], market["evidence"])
    evidence_urls = _reportable_evidence_urls(evidence_rows)
    lines = [
        f"# AEOS-LIVE-002B2 — Inteligencia comercial: {market['city']}, {market['state']}",
        "",
        f"Corte de datos: {report['snapshot_at']}",
        f"Estado: **{market['status']}**",
        "",
    ]
    profile = report.get("business_profile")
    if isinstance(profile, dict):
        services = cast(list[str], profile.get("primary_services", []))
        areas = cast(list[str], profile.get("owner_confirmed_service_areas", []))
        lines.extend(
            (
                "## Perfil de la organización seleccionada",
                "",
                f"- Servicios confirmados: {', '.join(services)}",
                f"- Cobertura confirmada por el propietario: {', '.join(areas)}",
                "- Los mercados de este informe se investigan por separado; el radio no se ha establecido.",
            )
        )
    location = report.get("website_reported_location")
    if isinstance(location, dict):
        source_url = _reportable_market_url(location.get("source_url"))
        source_link = f" ([fuente]({source_url}))" if source_url else ""
        lines.extend(
            (
                f"- Ubicación previa del sitio: **{location.get('value')} · {location.get('status')}**{source_link}.",
                "  - Se conserva como ubicación reportada por el sitio; no se usa como centro geográfico ni como ubicación verificada.",
                "",
            )
        )
    lines.extend(
        (
            "## Conteos",
            "",
            f"- Competidores directos: {counts['direct_competitors']}",
            f"- Competidores indirectos: {counts['indirect_competitors']}",
            f"- Negocios sin verificar: {counts.get('unverified_businesses', counts.get('unverified_cleaning_businesses', 0))}",
            f"- Compradores potenciales (BUYER_FIT): {counts['potential_buyers']}",
            f"- Señales actuales de BUYING_INTENT: {counts['current_buying_intent_signals']}",
            f"- Solicitudes explícitas históricas: {counts['historical_explicit_demand_signals']}",
            f"- Socios potenciales de referencia: {counts['referral_partners']}",
            f"- Proveedores calificados: {counts['suppliers']}",
            f"- Candidatos de directorio sin calificar: {counts['unqualified_directory_candidates']}",
            "",
            "## Competidores",
            "",
        )
    )
    competitors = cast(list[dict[str, object]], market["competitors"])
    if competitors:
        for item in competitors:
            lines.extend(_organization_markdown(item, evidence_urls))
    else:
        lines.append("No se calificó ningún competidor con la evidencia disponible.")
    lines.extend(("", "## Compradores potenciales", ""))
    buyers = cast(list[dict[str, object]], market["potential_buyers"])
    if buyers:
        for item in buyers:
            lines.extend(_organization_markdown(item, evidence_urls))
    else:
        lines.append(
            "No se calificó ningún comprador potencial con la evidencia disponible."
        )
    lines.extend(
        (
            "",
            f"## Solicitudes públicas de {market.get('vertical', 'la vertical configurada')}",
            "",
        )
    )
    signals = cast(list[dict[str, object]], market["demand_signals"])
    if signals:
        for item in signals:
            source_url = _reportable_market_url(item.get("source_url"))
            source_link = f" ([fuente]({source_url}))" if source_url else ""
            lines.extend(
                (
                    f"- **{item['intent_classification']} · {item['service_requested']} · {item['publication_date'] or 'fecha no disponible'}**",
                    f"  - Fragmento original (inglés): {item['supporting_excerpt']}{source_link}",
                    f"  - Traducción al español: {item['supporting_excerpt_es'] or 'no disponible'}",
                    f"  - Accionable hoy: {'sí' if item['still_actionable'] else 'no'}",
                    f"  - Limitaciones: {'; '.join(cast(list[str], item['limitations'])) or 'ninguna registrada'}",
                )
            )
    else:
        lines.append(
            "No se encontró una solicitud pública explícita en las fuentes revisadas."
        )
    lines.extend(("", "## Socios de referencia", ""))
    partners = cast(list[dict[str, object]], market["referral_partners"])
    if partners:
        for item in partners:
            lines.extend(_organization_markdown(item, evidence_urls))
    else:
        lines.append("No se calificó un socio de referencia.")
    lines.extend(("", "## Candidatos de directorio sin calificar", ""))
    candidates = cast(
        list[dict[str, object]], market["unqualified_directory_candidates"]
    )
    if candidates:
        for item in candidates:
            lines.extend(_organization_markdown(item, evidence_urls))
    else:
        lines.append(
            "No se incorporaron candidatos de directorio sin evidencia suficiente."
        )
    lines.extend(("", "## Oportunidades priorizadas", ""))
    opportunities = cast(list[dict[str, object]], market["opportunity_queue"])
    if opportunities:
        for item in opportunities:
            lines.extend(
                (
                    f"- **{item['priority']} · {item['opportunity_type']} · {item['target']}**",
                    f"  - Por qué importa: {item['why_it_matters']}",
                    f"  - Próxima acción: {item['recommended_next_action']}",
                    f"  - Pregunta de validación: {item['suggested_validation_question']}",
                    f"  - Canal público: {item['public_contact_channel'] or 'no publicado'}",
                    f"  - Evidencia: {', '.join(cast(list[str], item['evidence_ids']))}",
                    "  - Fuentes: "
                    + ", ".join(
                        f"[{evidence_id}]({evidence_urls[evidence_id]})"
                        for evidence_id in cast(list[str], item["evidence_ids"])
                        if evidence_id in evidence_urls
                    ),
                    f"  - Límites: {'; '.join(cast(list[str], item['limitations'])) or 'ninguno registrado'}",
                )
            )
    else:
        lines.append(
            "No hay oportunidades basadas en intención actual; valide los candidatos BUYER_FIT manualmente."
        )
    lines.extend(("", "## Fuentes y cobertura", ""))
    for item in cast(list[dict[str, object]], market["source_coverage"]):
        lines.append(f"- **{item['source_name']} — {item['status']}**: {item['note']}")
    lines.extend(("", "## Vacíos y limitaciones", ""))
    lines.extend(
        f"- {item}" for item in cast(list[str], market["main_gaps_and_limitations"])
    )
    owner_evidence = cast(
        list[dict[str, object]], report.get("owner_confirmation_evidence", [])
    )
    if owner_evidence:
        lines.extend(
            ("", "## Proveniencia de datos confirmados por el propietario", "")
        )
        for item in owner_evidence:
            lines.append(
                f"- **{item['field']}**: {item['value']} — {item['classification']}; "
                f"{item['source_name']}; fecha {item['retrieved_at'] or 'no disponible'}."
            )
    return "\n".join(lines) + "\n"


def render_combined_market_report_markdown(report: dict[str, object]) -> str:
    comparison = cast(dict[str, object], report["combined_comparison"])
    city_rows = cast(list[dict[str, object]], comparison["city_comparison"])
    markets = cast(list[dict[str, object]], report["markets"])
    evidence_urls = _reportable_evidence_urls(
        [
            item
            for market in markets
            for item in cast(list[dict[str, object]], market["evidence"])
        ]
    )
    profile_value = report.get("business_profile")
    profile = (
        cast(dict[str, object], profile_value)
        if isinstance(profile_value, dict)
        else {}
    )
    lines = [
        f"# AEOS-LIVE-002B2 — Comparación comercial {profile.get('business_name', 'AEOS')}",
        "",
        f"Corte de datos: {report['snapshot_at']}",
        "",
        "## Comparación por ciudad",
        "",
        "| Ciudad | Competidores directos | BUYER_FIT | BUYING_INTENT B2B actual | Solicitudes actuales | Solicitudes históricas | Referidores |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in city_rows:
        lines.append(
            "| {city} | {direct_competitors} | {potential_buyers} | "
            "{current_b2b_buying_intent_organizations} | "
            "{current_buying_intent_signals} | "
            "{historical_explicit_demand_signals} | {referral_partners} |".format(**row)
        )
    lines.extend(
        (
            "",
            "El BUYER_FIT describe ajuste del perfil. BUYING_INTENT requiere evidencia pública, observada y fechada. Las solicitudes de servicio y la intención de compra de una organización se cuentan por separado.",
            "",
            "## Recomendación de foco",
            "",
            str(comparison["focus_recommendation"]),
        )
    )
    focus_evidence_ids = cast(
        list[str], comparison.get("focus_recommendation_evidence_ids", [])
    )
    focus_sources = ", ".join(
        f"[{evidence_id}]({evidence_urls[evidence_id]})"
        for evidence_id in focus_evidence_ids
        if evidence_id in evidence_urls
    )
    if focus_sources:
        lines.extend((f"Fuentes de las solicitudes comparadas: {focus_sources}", ""))
    elif focus_evidence_ids:
        lines.extend(
            (
                "Fuentes de las solicitudes comparadas: "
                + ", ".join(focus_evidence_ids)
                + " (URL sintética omitida).",
                "",
            )
        )
    lines.extend(("", "## Segmentos recomendados", ""))
    lines.extend(
        f"- {item}"
        for item in cast(list[str], comparison["recommended_customer_segments"])
    )
    lines.extend(("", "## Especialización de servicios por ciudad", ""))
    for row in city_rows:
        source_rows = cast(
            list[dict[str, object]], row["service_specialization_sources"]
        )
        if source_rows:
            for item in source_rows:
                refs = cast(list[str], item["evidence_ids"])
                links = ", ".join(
                    f"[{evidence_id}]({evidence_urls[evidence_id]})"
                    for evidence_id in refs
                    if evidence_id in evidence_urls
                )
                services = cast(list[str], item["services"])
                lines.append(
                    f"- **{row['city']} · {item['organization']}**: "
                    f"{', '.join(services)} (fuentes: {links or ', '.join(refs)})."
                )
        else:
            lines.append(
                f"- **{row['city']}**: sin especialización directa confirmada en la muestra."
            )
    lines.extend(("", "## Precios y modelos publicados", ""))
    found_pricing = False
    for row in city_rows:
        pricing_items = cast(list[dict[str, object]], row["published_pricing"])
        for item in pricing_items:
            found_pricing = True
            refs = cast(list[str], item["evidence_ids"])
            links = ", ".join(
                f"[{evidence_id}]({evidence_urls[evidence_id]})"
                for evidence_id in refs
                if evidence_id in evidence_urls
            )
            lines.append(
                f"- **{row['city']} · {item['organization']}**: {item['pricing_model']} (fuente: {links or ', '.join(refs)})."
            )
    if not found_pricing:
        lines.append(
            "No se encontró un precio ni modelo de cotización publicado en las páginas revisadas."
        )
    lines.extend(("", "## Organizaciones a validar primero", ""))
    lines.append(
        "Orden sugerido por presencia de un canal público para proveedores y evidencia operacional. Todos los casos siguen siendo BUYER_FIT; ninguna aparece como solicitud actual de un proveedor adicional."
    )
    lines.append("")
    for index, item in enumerate(
        cast(list[dict[str, object]], comparison["recommended_first_contacts"]),
        start=1,
    ):
        refs = cast(list[str], item["evidence_ids"])
        links = ", ".join(
            f"[{evidence_id}]({evidence_urls[evidence_id]})"
            for evidence_id in refs
            if evidence_id in evidence_urls
        )
        lines.extend(
            (
                f"{index}. **{item['name']} — {item['city']}** ({item['qualification']}; intención: {item['buying_intent']}).",
                f"   - Ajuste: {item['why_it_matters']}",
                f"   - Próximo paso: {item['recommended_next_action']}",
                f"   - Validar: {item['validation_question']}",
                f"   - Canales públicos: {', '.join(cast(list[str], item['public_contact_channels'])) or 'no publicados'}",
                f"   - Fuentes: {links or 'sin enlace'}",
            )
        )
    lines.extend(("", "## Cobertura y confiabilidad de fuentes", ""))
    for row in city_rows:
        lines.append(f"### {row['city']}")
        lines.append("")
        for source in cast(list[dict[str, object]], row["source_coverage"]):
            lines.append(
                f"- **{source['source_name']} — {source['status']}**: {source['note']}"
            )
        lines.append("")
    lines.append("## Vacíos y limitaciones por ciudad")
    lines.append("")
    for row in city_rows:
        lines.append(f"### {row['city']}")
        lines.append("")
        lines.extend(
            f"- {gap_item}"
            for gap_item in cast(list[str], row["main_gaps_and_limitations"])
        )
        lines.append("")
    lines.extend(("## Organizaciones a contactar por categoría", ""))
    for contact_type in cast(list[str], comparison["recommended_first_contact_types"]):
        lines.append(f"- {contact_type}")
    lines.extend(("", "## Canales públicos para solicitudes", ""))
    for channel in cast(list[str], comparison["public_demand_channels"]):
        lines.append(f"- {channel}")
    lines.extend(
        (
            "",
            "## Lectura de la muestra",
            "",
            str(comparison["ranking_note"]),
        )
    )
    return "\n".join(lines) + "\n"


def _organization_markdown(
    item: dict[str, object], evidence_urls: dict[str, str]
) -> list[str]:
    links = cast(list[str], item["evidence_ids"])
    source_links = ", ".join(
        f"[{evidence_id}]({evidence_urls[evidence_id]})"
        for evidence_id in links
        if evidence_id in evidence_urls
    )
    return [
        f"- **{item['name']}** — {item.get('competitor_classification') or item['role']}",
        f"  - Web: {_reportable_market_url(item.get('website')) or 'no disponible'}",
        f"  - Servicios: {', '.join(cast(list[str], item['services'])) or 'sin confirmar'}",
        f"  - Especialización STR: {'sí' if item['vacation_rental_specialization'] else 'no documentada'}",
        f"  - Recurrencia: {', '.join(cast(list[str], item['recurring_options'])) or 'no publicada'}",
        f"  - Precio: {item.get('pricing_model') or 'no publicado'}",
        f"  - Calificación/reseñas: {item.get('rating_claim') or 'no publicada'} / {item.get('review_count_claim') or 'sin conteo disponible'}",
        f"  - Anuncio público: {_reportable_market_url(item.get('public_listing')) or 'no verificado en esta revisión'}",
        f"  - Reserva/cotización: {', '.join(cast(list[str], item['booking_methods'])) or 'no publicada'}",
        f"  - Contactos/canales: {', '.join(cast(list[str], item['public_contacts'])) or 'no publicado'}",
        f"  - Evidencia: {', '.join(links)}",
        f"  - Fuentes: {source_links or 'sin enlace'}",
        f"  - Limitaciones: {'; '.join(cast(list[str], item['limitations'])) or 'ninguna registrada'}",
    ]


def _reportable_market_url(value: object) -> str | None:
    if not isinstance(value, str) or is_reserved_example_source_url(value):
        return None
    return safe_url_for_report(value)


def _reportable_evidence_urls(
    evidence_rows: list[dict[str, object]],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in evidence_rows:
        evidence_id = item.get("evidence_id")
        source_url = _reportable_market_url(item.get("source_url"))
        if isinstance(evidence_id, str) and source_url:
            result[evidence_id] = source_url
    return result


__all__ = [
    "build_market_report",
    "prioritize_opportunities",
    "render_combined_market_report_markdown",
    "render_market_report_markdown",
]
