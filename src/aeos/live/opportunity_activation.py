"""Deterministic prospect qualification, outreach drafts, and pipeline rules."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from uuid import uuid4
from typing import cast

from aeos.live.domain.opportunity_activation import (
    ActivationOpportunityType,
    ActivationProspect,
    CapacityAssessment,
    CapacityState,
    OperationalCapacity,
    PipelineEvent,
    PipelineRecord,
    PipelineStatus,
    ProspectAssessment,
    ProspectClassification,
    ProspectEvidence,
    ScoreComponent,
    VendorOnboardingState,
)
from aeos.live.domain.profile import BusinessProfile
from aeos.tenancy.domain import TenantContext
from aeos.live.domain.url_policy import sanitize_report_data, safe_text_for_report


STALE_AFTER_DAYS = 90
BUYING_INTENT_FRESHNESS_DAYS = 30
QUALIFIED_SCORE_THRESHOLD = 70

SCORING_RUBRIC = (
    ("service_alignment", "Alineación de servicios", 20),
    ("geographic_alignment", "Alineación geográfica", 15),
    ("customer_segment_alignment", "Alineación del segmento", 15),
    ("recurring_demand", "Compatibilidad con demanda recurrente", 10),
    ("capacity_compatibility", "Compatibilidad de capacidad", 10),
    ("schedule_compatibility", "Compatibilidad de horario", 5),
    ("vendor_onboarding", "Acceso de incorporación de proveedores", 10),
    ("evidence_quality_freshness", "Calidad y vigencia de evidencia", 10),
    ("explicit_buying_intent", "Intención de compra explícita", 5),
)


def operational_capacity_from_profile(
    profile: BusinessProfile,
) -> OperationalCapacity:
    """Create pilot capacity facts with references to owner-reported evidence."""

    required = {
        "base_capacity_jobs_per_day": profile.base_capacity_jobs_per_day,
        "expanded_capacity_jobs_per_day": profile.expanded_capacity_jobs_per_day,
        "capacity_expansion_dependency": profile.capacity_expansion_dependency,
        "weekend_available": profile.weekend_available,
        "urgent_service_available": profile.urgent_service_available,
        "legal_business_established": profile.legal_business_established,
        "documentation_and_insurance_in_order": (
            profile.documentation_and_insurance_in_order
        ),
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(
            "owner-reported capacity fields are missing: " + ", ".join(missing)
        )
    evidence_by_field = {
        item.field: item.evidence_id for item in profile.reported_evidence()
    }
    ids = tuple(
        evidence_by_field[field] for field in required if field in evidence_by_field
    )
    return OperationalCapacity(
        base_capacity_jobs_per_day=profile.base_capacity_jobs_per_day or 0,
        expanded_capacity_jobs_per_day=profile.expanded_capacity_jobs_per_day or 0,
        expansion_dependency=profile.capacity_expansion_dependency or "",
        weekend_available=bool(profile.weekend_available),
        urgent_service_available=bool(profile.urgent_service_available),
        legal_business_established_reported=bool(profile.legal_business_established),
        documents_and_insurance_in_order_reported=bool(
            profile.documentation_and_insurance_in_order
        ),
        evidence_ids=ids,
    )


def assess_prospect(
    prospect: ActivationProspect,
    profile: BusinessProfile,
    capacity_facts: OperationalCapacity,
    *,
    as_of: date,
    stale_after_days: int = STALE_AFTER_DAYS,
    expected_jobs_per_day: int | None = None,
) -> ProspectAssessment:
    """Score fit and buying intent independently, retaining evidence per item."""

    if stale_after_days < 1:
        raise ValueError("stale_after_days must be positive")
    if expected_jobs_per_day is not None and (
        isinstance(expected_jobs_per_day, bool)
        or not isinstance(expected_jobs_per_day, int)
        or expected_jobs_per_day < 0
    ):
        raise ValueError("expected_jobs_per_day must be a non-negative integer or None")

    evidence = {item.evidence_id: item for item in prospect.evidence}
    stale_ids = tuple(
        sorted(
            item.evidence_id
            for item in prospect.evidence
            if item.classification.value == "OBSERVED"
            and not 0 <= (as_of - item.observed_on).days <= stale_after_days
        )
    )
    operating_evidence = _matching_evidence(
        prospect, ("cleaning_operations", "housekeeping_need")
    )
    coverage_evidence = _matching_evidence(prospect, ("market_coverage",))
    cleaning_terms = ("clean", "limpieza", "housekeep", "turnover", "huésped")
    segment_terms = ("vacation", "alquiler vacacional", "short-term", "estancia")
    clean_services = any(
        any(term in item.casefold() for term in cleaning_terms)
        for item in prospect.services
    )
    rental_segment = any(prospect.customer_segments) and any(
        any(term in item.casefold() for term in segment_terms)
        for item in (*prospect.services, *prospect.customer_segments)
    )
    service_areas = {item.casefold() for item in prospect.service_areas}
    profile_areas = {
        item.casefold()
        for item in (
            profile.owner_confirmed_service_areas
            or (profile.city, *(profile.additional_service_areas or ()))
        )
    }
    market_key = prospect.market.casefold()
    geographic_overlap = (
        {market_key}
        if market_key in service_areas and market_key in profile_areas
        else set()
    )
    explicit_cleaning_ids = tuple(
        item.evidence_id
        for item in operating_evidence
        if item.classification.value == "OBSERVED"
    )
    service_score = (
        20
        if clean_services and explicit_cleaning_ids
        else (10 if clean_services else 0)
    )
    geographic_score = 15 if geographic_overlap else 0
    recurring_score = (
        10 if explicit_cleaning_ids else (4 if prospect.recurring_options else 0)
    )
    capacity = assess_capacity(
        capacity_facts,
        expected_jobs_per_day=expected_jobs_per_day,
        evidence_ids=capacity_facts.evidence_ids,
    )
    if capacity.state is CapacityState.BASE_CAPACITY:
        capacity_score = 10
        capacity_explanation = "La carga comunicada cabe en la capacidad base reportada; aún se debe confirmar la agenda y ubicación."
    elif capacity.state is CapacityState.EXPANDED_CAPACITY:
        capacity_score = 5
        capacity_explanation = "La carga comunicada excede la capacidad base reportada y depende de colaboradores; confirme fecha, zona y disponibilidad antes de ofertar."
    elif capacity.state is CapacityState.OVER_CAPACITY:
        capacity_score = 0
        capacity_explanation = "La carga indicada supera el máximo condicional reportado; no se recomienda aceptar ese volumen."
    else:
        capacity_score = 5
        capacity_explanation = "No se publicó ni se proporcionó un volumen de trabajos/día. La capacidad queda sin dimensionar; no se estima a partir de propiedades administradas."
    schedule_score = (
        3
        if operating_evidence
        and capacity_facts.weekend_available
        and capacity_facts.urgent_service_available
        else 0
    )
    if prospect.vendor_onboarding is VendorOnboardingState.PUBLIC_VENDOR_ROUTE:
        vendor_score = 10
        vendor_explanation = "Hay una ruta pública para proveedores; no equivale a una vacante ni a intención de compra."
    elif prospect.external_cleaning_vendor_evidence_ids:
        vendor_score = 5
        vendor_explanation = "Hay una referencia a proveedores de limpieza a nivel de red, sin prueba del modelo local ni una ruta de alta local."
    else:
        vendor_score = 0
        vendor_explanation = (
            "No se encontró un proceso público de incorporación de proveedores."
        )
    current_observed = tuple(
        item
        for item in prospect.evidence
        if item.classification.value == "OBSERVED"
        and 0 <= (as_of - item.observed_on).days <= stale_after_days
    )
    freshness_score = (
        10 if current_observed and not stale_ids else (5 if current_observed else 0)
    )
    intent_ids = _current_buying_intent_ids(
        prospect,
        evidence,
        as_of=as_of,
        freshness_days=BUYING_INTENT_FRESHNESS_DAYS,
    )
    intent_score = 5 if intent_ids else 0
    components = (
        ScoreComponent(
            "service_alignment",
            "Alineación de servicios",
            service_score,
            20,
            explicit_cleaning_ids,
            "La organización anuncia operaciones de limpieza de rotación/alojamientos que corresponden a los servicios confirmados del perfil empresarial."
            if service_score
            else "No hay evidencia suficiente de servicios coincidentes.",
        ),
        ScoreComponent(
            "geographic_alignment",
            "Alineación geográfica",
            geographic_score,
            15,
            tuple(item.evidence_id for item in coverage_evidence),
            "La cobertura declarada del prospecto coincide con una ciudad confirmada por el propietario: "
            + (
                ", ".join(sorted(geographic_overlap))
                if geographic_overlap
                else "ninguna verificada"
            ),
        ),
        ScoreComponent(
            "customer_segment_alignment",
            "Alineación del segmento",
            15 if rental_segment else (7 if prospect.customer_segments else 0),
            15,
            explicit_cleaning_ids
            or tuple(item.evidence_id for item in coverage_evidence),
            "El prospecto administra o sirve alquileres vacacionales/de corta estancia."
            if rental_segment
            else "La evidencia del segmento de clientes es limitada.",
        ),
        ScoreComponent(
            "recurring_demand",
            "Compatibilidad con demanda recurrente",
            recurring_score,
            10,
            explicit_cleaning_ids,
            "La limpieza entre huéspedes ocurre como parte del flujo operativo; no se infiere una frecuencia semanal ni un volumen diario."
            if recurring_score
            else "No hay evidencia de una tarea recurrente de limpieza.",
        ),
        ScoreComponent(
            "capacity_compatibility",
            "Compatibilidad de capacidad",
            capacity_score,
            10,
            capacity.evidence_ids,
            capacity_explanation,
        ),
        ScoreComponent(
            "schedule_compatibility",
            "Compatibilidad de horario",
            schedule_score,
            5,
            (*explicit_cleaning_ids, *capacity_facts.evidence_ids),
            "La disponibilidad reportada de fin de semana y urgencias podría complementar los cambios entre estancias; no hay prueba de un pico o necesidad concreta del prospecto."
            if schedule_score
            else "La compatibilidad de horario no está demostrada.",
        ),
        ScoreComponent(
            "vendor_onboarding",
            "Acceso de incorporación de proveedores",
            vendor_score,
            10,
            (
                prospect.vendor_onboarding_evidence_ids
                or prospect.external_cleaning_vendor_evidence_ids
            ),
            vendor_explanation,
        ),
        ScoreComponent(
            "evidence_quality_freshness",
            "Calidad y vigencia de evidencia",
            freshness_score,
            10,
            tuple(item.evidence_id for item in current_observed),
            (
                "La evidencia pública observada está dentro de la ventana de vigencia de 90 días."
                if freshness_score == 10
                else "Se necesita evidencia pública más reciente antes de confiar en el perfil."
            ),
        ),
        ScoreComponent(
            "explicit_buying_intent",
            "Intención de compra explícita",
            intent_score,
            5,
            intent_ids,
            "Existe una solicitud pública, directa, observada y fechada dentro de 30 días."
            if intent_ids
            else "No se encontró una solicitud directa y fechada para contratar un proveedor de limpieza. El encaje no prueba intención.",
        ),
    )
    total = sum(item.score for item in components)
    fit_classification = _fit_classification(
        prospect,
        score=total,
        service_score=service_score,
        geographic_score=geographic_score,
        freshness_score=freshness_score,
        stale_ids=stale_ids,
    )
    classifications = [fit_classification]
    if intent_ids:
        classifications.append(ProspectClassification.ACTIVE_BUYING_INTENT)
    if prospect.source_role.value == "REFERRAL_PARTNER":
        classifications.append(ProspectClassification.REFERRAL_PARTNER)
    if prospect.overflow_partner_evidence_ids:
        classifications.append(ProspectClassification.OVERFLOW_PARTNER)
    overflow_hypothesis = "El equipo podría aportar capacidad de respaldo en fines de semana, cambios simultáneos, picos de temporada, avisos urgentes o nuevas zonas confirmadas. La hipótesis requiere validar fechas, ubicación, listas de tareas y disponibilidad de colaboradores."
    if capacity.state is CapacityState.OVER_CAPACITY:
        next_action = "No ofertar el volumen planteado; aclarar el alcance y buscar una opción de menor volumen."
    elif prospect.contact_revalidation_required:
        next_action = "Revalidar el teléfono o correo oficial y luego preguntar quién administra el alta de proveedores."
    elif stale_ids:
        next_action = "Revalidar las páginas y los datos del prospecto antes de confiar en el perfil o preparar contacto."
    elif fit_classification is ProspectClassification.QUALIFIED_PROSPECT:
        next_action = "Revisar el borrador y los requisitos de capacidad; después mover manualmente a READY_FOR_APPROVAL."
    else:
        next_action = prospect.recommended_action
    return ProspectAssessment(
        prospect=prospect,
        fit_score=total,
        fit_classification=fit_classification,
        classifications=tuple(classifications),
        score_components=components,
        buying_intent_evidence_ids=intent_ids,
        buying_intent_status=(
            "ACTIVE_BUYING_INTENT" if intent_ids else "NOT_ESTABLISHED"
        ),
        opportunity_type=ActivationOpportunityType.OVERFLOW_CLEANING_PARTNER,
        overflow_hypothesis=overflow_hypothesis,
        overflow_hypothesis_only=True,
        capacity=capacity,
        stale_evidence_ids=stale_ids,
        next_action=next_action,
    )


def assess_capacity(
    facts: OperationalCapacity,
    *,
    expected_jobs_per_day: int | None,
    evidence_ids: tuple[str, ...],
) -> CapacityAssessment:
    """Compare a stated daily workload to the 2/5 owner-reported limits."""

    if expected_jobs_per_day is None:
        state = CapacityState.CAPACITY_NOT_SCOPED
        recommendation = "Pregunte cuántos trabajos se requieren en cada fecha y ciudad antes de cotizar. La cantidad de propiedades administradas no establece los trabajos diarios de limpieza."
    elif expected_jobs_per_day > facts.expanded_capacity_jobs_per_day:
        state = CapacityState.OVER_CAPACITY
        recommendation = f"Los {expected_jobs_per_day} trabajos/día informados superan el máximo condicional de {facts.expanded_capacity_jobs_per_day}; no prometa cumplir ese volumen."
    elif expected_jobs_per_day > facts.base_capacity_jobs_per_day:
        state = CapacityState.EXPANDED_CAPACITY
        recommendation = "Confirme la disponibilidad de subcontratistas de confianza para cada fecha y ubicación antes de ofertar."
    else:
        state = CapacityState.BASE_CAPACITY
        recommendation = "El volumen diario informado cabe en la base normal, sujeto a confirmar la agenda y la ubicación."
    return CapacityAssessment(
        expected_jobs_per_day=expected_jobs_per_day,
        state=state,
        base_capacity_jobs_per_day=facts.base_capacity_jobs_per_day,
        expanded_capacity_jobs_per_day=facts.expanded_capacity_jobs_per_day,
        expansion_dependency=facts.expansion_dependency,
        recommendation=recommendation,
        evidence_ids=evidence_ids,
    )


def generate_outreach_materials(
    assessment: ProspectAssessment,
    profile: BusinessProfile,
) -> dict[str, dict[str, str]]:
    """Generate English drafts with Spanish internal-review translations."""

    if assessment.fit_classification is not ProspectClassification.QUALIFIED_PROSPECT:
        raise ValueError("outreach drafts are available only for qualified prospects")
    if assessment.prospect.contact_revalidation_required:
        raise ValueError("revalidate the public contact details before outreach")
    confirmed_areas = {
        item.casefold()
        for item in (profile.owner_confirmed_service_areas or (profile.city,))
    }
    if assessment.prospect.market.casefold() not in confirmed_areas:
        raise ValueError(
            "the prospect market is outside the owner's confirmed service areas"
        )
    business = profile.business_name
    prospect = assessment.prospect.organization
    city = assessment.prospect.market
    services = ", ".join(profile.primary_services) or "the services in our profile"
    service_areas = ", ".join(profile.owner_confirmed_service_areas or (profile.city,))
    capacity_en = (
        f"Our normal capacity is {profile.base_capacity_jobs_per_day} jobs per day. "
        f"We can expand to a conditional maximum of {profile.expanded_capacity_jobs_per_day} per day only when trusted subcontractors are available, and we confirm each date and location before committing."
    )
    capacity_es = (
        f"Nuestra capacidad normal es de {profile.base_capacity_jobs_per_day} trabajos al día. "
        f"Podemos ampliar hasta un máximo condicional de {profile.expanded_capacity_jobs_per_day} al día solo cuando haya subcontratistas de confianza disponibles; confirmamos cada fecha y ubicación antes de comprometernos."
    )
    materials = {
        "introductory_email": {
            "en": (
                f"Subject: Local turnover-cleaning backup for {city}\n\n"
                f"Hello {prospect} team,\n\n"
                f"I saw that {prospect} coordinates cleaning for vacation-rental turnovers in {city}. "
                f"{business} provides {services} in {service_areas}. {capacity_en}\n\n"
                "Would you be open to a short call about your vendor review process and whether a local backup provider is useful for specific dates?\n\n"
                f"Best,\n{business}"
            ),
            "es": (
                f"Asunto: Apoyo local de limpieza entre estancias en {city}\n\n"
                f"Hola, equipo de {prospect}:\n\n"
                f"Vi que {prospect} coordina limpiezas de rotación para alquileres vacacionales en {city}. "
                f"{business} ofrece {services} en {service_areas}. {capacity_es}\n\n"
                "¿Podríamos conversar brevemente sobre su proceso para evaluar proveedores y sobre si les resulta útil contar con un proveedor local de respaldo para fechas específicas?\n\n"
                f"Saludos,\n{business}"
            ),
        },
        "contact_form_message": {
            "en": (
                f"Hello, I saw that {prospect} coordinates vacation-rental cleaning in {city}. "
                f"{business} provides local turnover, residential, deep, and recurring cleaning. "
                "Could you direct me to the person who reviews independent cleaning vendors?"
            ),
            "es": (
                f"Hola. Vi que {prospect} coordina limpieza de alquileres vacacionales en {city}. "
                f"{business} ofrece limpieza local entre estancias, residencial, profunda y recurrente. "
                "¿Podrían indicarme quién evalúa proveedores independientes de limpieza?"
            ),
        },
        "telephone_opening": {
            "en": (
                f"Hello, this is {business}. I saw that {prospect} coordinates services in {city}. "
                "Could you point me to the person who handles cleaning vendors? I would like to ask how local providers are reviewed for specific turnover dates."
            ),
            "es": (
                f"Hola, llamo de {business}. Vi que {prospect} coordina servicios en {city}. "
                "¿Podrían indicarme quién atiende a los proveedores de limpieza? Quisiera consultar cómo evalúan proveedores locales para fechas específicas de rotación."
            ),
        },
        "follow_up_email": {
            "en": (
                f"Subject: Re: Local turnover-cleaning backup for {city}\n\n"
                f"Hello {prospect} team,\n\n"
                f"I am following up on my note about {prospect}'s vacation-rental cleaning in {city}. "
                "Would a 15-minute conversation next week be useful to learn whether you review local backup providers and what requirements you use?\n\n"
                f"Best,\n{business}"
            ),
            "es": (
                f"Asunto: Seguimiento: apoyo de limpieza entre estancias en {city}\n\n"
                f"Hola, equipo de {prospect}:\n\n"
                f"Doy seguimiento a mi mensaje sobre la limpieza de alquileres vacacionales de {prospect} en {city}. "
                "¿Les serviría una conversación de 15 minutos la próxima semana para saber si evalúan proveedores locales de respaldo y qué requisitos aplican?\n\n"
                f"Saludos,\n{business}"
            ),
        },
        "vendor_onboarding_inquiry": {
            "en": (
                f"Subject: Independent cleaning vendor inquiry — {city}\n\n"
                f"Hello {prospect} team,\n\n"
                f"I am contacting you through your public vendor inquiry channel on behalf of {business}. "
                f"Your site describes cleaning coordination for vacation-rental turnovers in {city}. "
                "Could you share whether you are reviewing independent cleaning providers and, if so, the onboarding steps, insurance requirements, checklists, service areas, and response-time expectations?\n\n"
                f"Thank you,\n{business}"
            ),
            "es": (
                f"Asunto: Consulta para proveedor independiente de limpieza — {city}\n\n"
                f"Hola, equipo de {prospect}:\n\n"
                f"Les escribo mediante su canal público para proveedores en nombre de {business}. "
                f"Su sitio describe coordinación de limpieza entre estancias de alquileres vacacionales en {city}. "
                "¿Podrían indicar si están evaluando proveedores independientes y, de ser así, cuáles son los pasos de incorporación, requisitos de seguro, listas de tareas, zonas y tiempos de respuesta?\n\n"
                f"Gracias,\n{business}"
            ),
        },
        "overflow_cleaning_partnership": {
            "en": (
                f"Subject: A local cleaning backup option for {prospect}\n\n"
                f"Hello {prospect} team,\n\n"
                f"Your public pages describe recurring vacation-rental turnover cleaning in {city}. "
                f"{business} could be an additional local option for a defined date when you want to evaluate backup coverage. "
                f"{capacity_en} We would first confirm the city, checklist, timing, and available capacity for each request. "
                "Would you be open to a short conversation about how you handle backup-provider onboarding?\n\n"
                f"Best,\n{business}"
            ),
            "es": (
                f"Asunto: Opción local de respaldo de limpieza para {prospect}\n\n"
                f"Hola, equipo de {prospect}:\n\n"
                f"Sus páginas públicas describen limpieza recurrente entre estancias de alquileres vacacionales en {city}. "
                f"{business} podría ser una opción local adicional para una fecha concreta en la que quieran evaluar cobertura de respaldo. "
                f"{capacity_es} Primero confirmaríamos la ciudad, lista de tareas, horario y capacidad disponible para cada solicitud. "
                "¿Podríamos conversar brevemente sobre cómo incorporan proveedores de respaldo?\n\n"
                f"Saludos,\n{business}"
            ),
        },
    }
    return {
        key: {
            **value,
            "approval_required": "true",
            "auto_send": "false",
            "external_document_claims": "none; owner approval is required before any such claim",
        }
        for key, value in materials.items()
    }


def new_pipeline_record(assessment: ProspectAssessment) -> PipelineRecord:
    """Start tracking at research-complete without auto-promoting qualification."""

    evidence_ids = tuple(
        dict.fromkeys(item.evidence_id for item in assessment.prospect.evidence)
    )
    created = datetime.now(timezone.utc)
    event = _pipeline_event(
        "research_recorded",
        "AEOS-LIVE-002C",
        "Created from reviewed public-source research; qualification and contact remain manual pipeline stages.",
        created,
        evidence_ids,
    )
    return PipelineRecord(
        prospect_id=assessment.prospect.prospect_id,
        organization=assessment.prospect.organization,
        market=assessment.prospect.market,
        status=PipelineStatus.RESEARCHED,
        source_evidence_ids=evidence_ids,
        next_action=assessment.next_action,
        events=(event,),
    )


def attach_research_evidence(
    record: PipelineRecord,
    assessment: ProspectAssessment,
    *,
    actor: str = "AEOS-LIVE-002C",
    occurred_at: datetime | None = None,
) -> PipelineRecord:
    """Append newly reviewed evidence references without changing pipeline status."""

    evidence_ids = tuple(
        dict.fromkeys(item.evidence_id for item in assessment.prospect.evidence)
    )
    additions = tuple(
        item for item in evidence_ids if item not in record.source_evidence_ids
    )
    if not additions:
        return record
    timestamp = occurred_at or datetime.now(timezone.utc)
    event = _pipeline_event(
        "research_evidence_added",
        actor,
        "Appended reviewed source references; pipeline qualification and contact status were not changed.",
        timestamp,
        additions,
    )
    return replace(
        record,
        source_evidence_ids=(*record.source_evidence_ids, *additions),
        events=(*record.events, event),
    )


_ALLOWED_TRANSITIONS: dict[PipelineStatus, frozenset[PipelineStatus]] = {
    PipelineStatus.DISCOVERED: frozenset({PipelineStatus.RESEARCH_PENDING}),
    PipelineStatus.RESEARCH_PENDING: frozenset({PipelineStatus.RESEARCHED}),
    PipelineStatus.RESEARCHED: frozenset(
        {PipelineStatus.QUALIFIED, PipelineStatus.DISQUALIFIED}
    ),
    PipelineStatus.QUALIFIED: frozenset(
        {
            PipelineStatus.READY_FOR_APPROVAL,
            PipelineStatus.LOST,
            PipelineStatus.DISQUALIFIED,
        }
    ),
    PipelineStatus.READY_FOR_APPROVAL: frozenset(
        {PipelineStatus.QUALIFIED, PipelineStatus.LOST, PipelineStatus.DISQUALIFIED}
    ),
    PipelineStatus.APPROVED_FOR_CONTACT: frozenset(
        {PipelineStatus.CONTACTED, PipelineStatus.QUALIFIED}
    ),
    PipelineStatus.CONTACTED: frozenset(
        {
            PipelineStatus.REPLIED,
            PipelineStatus.MEETING_SCHEDULED,
            PipelineStatus.LOST,
        }
    ),
    PipelineStatus.REPLIED: frozenset(
        {
            PipelineStatus.MEETING_SCHEDULED,
            PipelineStatus.LOST,
            PipelineStatus.DISQUALIFIED,
        }
    ),
    PipelineStatus.MEETING_SCHEDULED: frozenset(
        {PipelineStatus.QUOTE_REQUESTED, PipelineStatus.WON, PipelineStatus.LOST}
    ),
    PipelineStatus.QUOTE_REQUESTED: frozenset(
        {PipelineStatus.QUOTE_SENT, PipelineStatus.LOST, PipelineStatus.DISQUALIFIED}
    ),
    PipelineStatus.QUOTE_SENT: frozenset(
        {PipelineStatus.WON, PipelineStatus.LOST, PipelineStatus.REPLIED}
    ),
    PipelineStatus.WON: frozenset(),
    PipelineStatus.LOST: frozenset(),
    PipelineStatus.DISQUALIFIED: frozenset(),
}


def transition_pipeline(
    record: PipelineRecord,
    target: PipelineStatus,
    *,
    actor: str,
    details: str,
    occurred_at: datetime,
    source_evidence_ids: tuple[str, ...] = (),
) -> PipelineRecord:
    """Apply an allowed manual stage transition and append an event."""

    if target in {
        PipelineStatus.APPROVED_FOR_CONTACT,
        PipelineStatus.CONTACTED,
        PipelineStatus.REPLIED,
        PipelineStatus.MEETING_SCHEDULED,
        PipelineStatus.QUOTE_SENT,
        PipelineStatus.WON,
        PipelineStatus.LOST,
    }:
        raise ValueError(f"{target.value} requires its dedicated pipeline action")
    if target not in _ALLOWED_TRANSITIONS[record.status]:
        raise ValueError(
            f"invalid pipeline transition {record.status.value} -> {target.value}"
        )
    event = _pipeline_event(
        "status_update", actor, details, occurred_at, source_evidence_ids
    )
    return replace(
        record,
        status=target,
        last_action_date=occurred_at.date().isoformat(),
        next_action=(
            details
            if target is PipelineStatus.READY_FOR_APPROVAL
            else record.next_action
        ),
        owner_notes=details,
        events=(*record.events, event),
    )


def _trusted_approval_actor(approver: TenantContext) -> str:
    if not isinstance(approver, TenantContext):
        raise ValueError(
            "production approval requires an authenticated tenant manager context"
        )
    return approver.require_manager_actor()


def approve_contact(
    record: PipelineRecord,
    *,
    approver: TenantContext,
    note: str,
    occurred_at: datetime,
) -> PipelineRecord:
    """Record explicit human approval before a manual contact action."""

    approvable_statuses = {
        PipelineStatus.READY_FOR_APPROVAL,
        PipelineStatus.CONTACTED,
        PipelineStatus.REPLIED,
        PipelineStatus.MEETING_SCHEDULED,
        PipelineStatus.QUOTE_SENT,
    }
    if record.status not in approvable_statuses:
        raise ValueError("contact approval requires a reviewable pipeline status")
    actor = _trusted_approval_actor(approver)
    if not note.strip():
        raise ValueError("approval note is required")
    event = _pipeline_event("contact_approved", actor, note, occurred_at)
    return replace(
        record,
        status=PipelineStatus.APPROVED_FOR_CONTACT,
        last_action_date=occurred_at.date().isoformat(),
        owner_notes=note,
        events=(*record.events, event),
    )


def approve_quote(
    record: PipelineRecord,
    *,
    approver: TenantContext,
    note: str,
    occurred_at: datetime,
) -> PipelineRecord:
    """Record separate owner approval before a manual quote action."""

    if record.status is not PipelineStatus.QUOTE_REQUESTED:
        raise ValueError("quote approval requires QUOTE_REQUESTED status")
    actor = _trusted_approval_actor(approver)
    if not note.strip():
        raise ValueError("approval note is required")
    if record.events and record.events[-1].action == "quote_approved":
        raise ValueError("a quote approval is already pending")
    event = _pipeline_event("quote_approved", actor, note, occurred_at)
    return replace(
        record,
        status=record.status,
        last_action_date=occurred_at.date().isoformat(),
        owner_notes=note,
        events=(*record.events, event),
    )


def record_manual_contact(
    record: PipelineRecord,
    *,
    actor: str,
    channel: str,
    details: str,
    occurred_at: datetime,
    next_action: str,
    follow_up_date: date | None,
) -> PipelineRecord:
    """Record a completed human action; this function does not send messages."""

    if record.status is not PipelineStatus.APPROVED_FOR_CONTACT:
        raise ValueError("manual contact requires explicit APPROVED_FOR_CONTACT status")
    if not record.events or record.events[-1].action != "contact_approved":
        raise ValueError("this contact action needs its own approval event")
    if not channel.strip() or not details.strip() or not next_action.strip():
        raise ValueError("channel, action details, and next action are required")
    event = _pipeline_event("manual_contact_recorded", actor, details, occurred_at)
    return replace(
        record,
        status=PipelineStatus.CONTACTED,
        contact_channel=channel.strip(),
        last_action_date=occurred_at.date().isoformat(),
        next_action=next_action.strip(),
        follow_up_date=follow_up_date.isoformat() if follow_up_date else None,
        owner_notes=details.strip(),
        outcome=None,
        events=(*record.events, event),
    )


def record_quote_sent(
    record: PipelineRecord,
    *,
    actor: str,
    channel: str,
    details: str,
    occurred_at: datetime,
    next_action: str,
    follow_up_date: date | None,
) -> PipelineRecord:
    """Record a quote sent manually outside AEOS."""

    if (
        record.status is not PipelineStatus.QUOTE_REQUESTED
        or not record.events
        or record.events[-1].action != "quote_approved"
    ):
        raise ValueError(
            "a manual quote requires explicit approval after QUOTE_REQUESTED"
        )
    if not channel.strip() or not details.strip() or not next_action.strip():
        raise ValueError("channel, quote details, and next action are required")
    event = _pipeline_event("manual_quote_recorded", actor, details, occurred_at)
    return replace(
        record,
        status=PipelineStatus.QUOTE_SENT,
        contact_channel=channel.strip(),
        last_action_date=occurred_at.date().isoformat(),
        next_action=next_action.strip(),
        follow_up_date=follow_up_date.isoformat() if follow_up_date else None,
        owner_notes=details.strip(),
        events=(*record.events, event),
    )


def record_response(
    record: PipelineRecord,
    *,
    actor: str,
    outcome_status: PipelineStatus,
    outcome: str,
    occurred_at: datetime,
    next_action: str,
    follow_up_date: date | None,
    source_evidence_ids: tuple[str, ...] = (),
) -> PipelineRecord:
    """Record a manually received response, meeting, or quote request."""

    if record.status not in {
        PipelineStatus.CONTACTED,
        PipelineStatus.REPLIED,
        PipelineStatus.MEETING_SCHEDULED,
        PipelineStatus.QUOTE_SENT,
    }:
        raise ValueError("a response requires a contacted prospect")
    allowed = {
        PipelineStatus.REPLIED,
        PipelineStatus.MEETING_SCHEDULED,
        PipelineStatus.WON,
        PipelineStatus.LOST,
        PipelineStatus.DISQUALIFIED,
    }
    if (
        outcome_status not in allowed
        or outcome_status not in _ALLOWED_TRANSITIONS[record.status]
    ):
        raise ValueError(f"invalid response outcome {outcome_status.value}")
    if not outcome.strip() or not next_action.strip():
        raise ValueError("outcome and next action are required")
    event = _pipeline_event(
        "response_recorded", actor, outcome, occurred_at, source_evidence_ids
    )
    return replace(
        record,
        status=outcome_status,
        last_action_date=occurred_at.date().isoformat(),
        next_action=next_action.strip(),
        follow_up_date=follow_up_date.isoformat() if follow_up_date else None,
        owner_notes=outcome.strip(),
        outcome=outcome.strip(),
        events=(*record.events, event),
    )


def due_followups(
    records: tuple[PipelineRecord, ...], *, as_of: date
) -> tuple[PipelineRecord, ...]:
    """List records with a follow-up due on or before the requested date."""

    due = tuple(
        item
        for item in records
        if item.follow_up_date is not None
        and date.fromisoformat(item.follow_up_date) <= as_of
        and item.status
        not in {PipelineStatus.WON, PipelineStatus.LOST, PipelineStatus.DISQUALIFIED}
    )
    return tuple(
        sorted(due, key=lambda item: (item.follow_up_date or "", item.organization))
    )


def _pipeline_event(
    action: str,
    actor: str,
    details: str,
    occurred_at: datetime,
    evidence_ids: tuple[str, ...] = (),
) -> PipelineEvent:
    if not actor.strip() or not details.strip():
        raise ValueError("actor and event details are required")
    if occurred_at.tzinfo is None:
        raise ValueError("occurred_at must be timezone-aware")
    return PipelineEvent(
        event_id=f"event-{uuid4().hex}",
        action=action,
        occurred_at=occurred_at.astimezone(timezone.utc).isoformat(),
        actor=actor.strip(),
        details=details.strip(),
        source_evidence_ids=evidence_ids,
    )


def _fit_classification(
    prospect: ActivationProspect,
    *,
    score: int,
    service_score: int,
    geographic_score: int,
    freshness_score: int,
    stale_ids: tuple[str, ...],
) -> ProspectClassification:
    if not prospect.evidence or not prospect.services:
        return ProspectClassification.INSUFFICIENT_DATA
    if not prospect.public_contact_channels and not prospect.public_contact_details:
        return ProspectClassification.INSUFFICIENT_DATA
    if service_score == 0 or geographic_score == 0:
        return ProspectClassification.NOT_QUALIFIED
    if stale_ids or freshness_score == 0:
        return ProspectClassification.POTENTIAL_BUYER
    if prospect.source_role.value == "REFERRAL_PARTNER":
        return ProspectClassification.REFERRAL_PARTNER
    if (
        score >= QUALIFIED_SCORE_THRESHOLD
        and prospect.vendor_onboarding is VendorOnboardingState.PUBLIC_VENDOR_ROUTE
        and prospect.vendor_onboarding_evidence_ids
    ):
        return ProspectClassification.QUALIFIED_PROSPECT
    return ProspectClassification.POTENTIAL_BUYER


def _matching_evidence(
    prospect: ActivationProspect, fields: tuple[str, ...]
) -> tuple[ProspectEvidence, ...]:
    field_set = set(fields)
    return tuple(item for item in prospect.evidence if item.field in field_set)


def _current_buying_intent_ids(
    prospect: ActivationProspect,
    evidence: dict[str, ProspectEvidence],
    *,
    as_of: date,
    freshness_days: int,
) -> tuple[str, ...]:
    explicit_fields = {
        "public_vendor_solicitation",
        "buying_intent",
        "vendor_recruitment",
        "cleaning_supplier_request",
    }
    intent_terms = ("seeking", "looking for", "request", "recruit", "accepting vendors")
    result = []
    for evidence_id in prospect.buying_intent_evidence_ids:
        item = evidence.get(evidence_id)
        if (
            item is not None
            and item.classification.value == "OBSERVED"
            and item.published_on is not None
            and 0 <= (as_of - item.published_on).days <= freshness_days
            and item.field in explicit_fields
            and any(term in item.value.casefold() for term in intent_terms)
        ):
            result.append(evidence_id)
    return tuple(result)


def _assessment_dict(assessment: ProspectAssessment, rank: int) -> dict[str, object]:
    prospect = assessment.prospect
    report: dict[str, object] = {
        "rank": rank,
        "prospect_id": prospect.prospect_id,
        "organization": prospect.organization,
        "market": prospect.market,
        "source_classification": prospect.source_role.value,
        "fit_score": assessment.fit_score,
        "fit_classification": assessment.fit_classification.value,
        "classifications": [item.value for item in assessment.classifications],
        "score_components": [
            {
                "key": item.key,
                "label": item.label,
                "score": item.score,
                "maximum": item.maximum,
                "evidence_ids": list(item.evidence_ids),
                "explanation": item.explanation,
            }
            for item in assessment.score_components
        ],
        "profile": {
            "website_url": prospect.website_url,
            "service_areas": list(prospect.service_areas),
            "services": list(prospect.services),
            "customer_segments": list(prospect.customer_segments),
            "recurring_options": list(prospect.recurring_options),
            "cleaning_delivery_model": prospect.cleaning_delivery_model,
            "operational_scale": prospect.operational_scale,
            "relevant_public_contact_role": prospect.relevant_public_contact_role,
        },
        "contact": {
            "channels": list(prospect.public_contact_channels),
            "details": list(prospect.public_contact_details),
            "revalidation_required": prospect.contact_revalidation_required,
            "revalidation_note": prospect.contact_revalidation_note,
        },
        "vendor_onboarding": {
            "status": prospect.vendor_onboarding.value,
            "evidence_ids": list(prospect.vendor_onboarding_evidence_ids),
            "limitations": list(prospect.limitations),
        },
        "buying_intent": {
            "status": assessment.buying_intent_status,
            "evidence_ids": list(assessment.buying_intent_evidence_ids),
            "source_buying_intent_evidence_ids": list(
                prospect.buying_intent_evidence_ids
            ),
        },
        "capacity": {
            "expected_jobs_per_day": assessment.capacity.expected_jobs_per_day,
            "state": assessment.capacity.state.value,
            "base_capacity_jobs_per_day": (
                assessment.capacity.base_capacity_jobs_per_day
            ),
            "expanded_capacity_jobs_per_day": (
                assessment.capacity.expanded_capacity_jobs_per_day
            ),
            "expansion_dependency": assessment.capacity.expansion_dependency,
            "recommendation": assessment.capacity.recommendation,
            "evidence_ids": list(assessment.capacity.evidence_ids),
        },
        "overflow_opportunity": {
            "type": assessment.opportunity_type.value,
            "hypothesis": assessment.overflow_hypothesis,
            "confirmed_need": not assessment.overflow_hypothesis_only,
            "evidence_ids": [
                item.evidence_id
                for item in prospect.evidence
                if item.field in {"cleaning_operations", "housekeeping_need"}
            ],
        },
        "recommended_action": prospect.recommended_action,
        "validation_question": prospect.validation_question,
        "next_action": assessment.next_action,
        "stale_evidence_ids": list(assessment.stale_evidence_ids),
        "limitations": list(prospect.limitations),
        "evidence": [_evidence_dict(item) for item in prospect.evidence],
    }

    return cast(dict[str, object], sanitize_report_data(report))


def _evidence_dict(item: ProspectEvidence) -> dict[str, object]:
    return {
        "evidence_id": item.evidence_id,
        "entity_id": item.entity_id,
        "field": item.field,
        "value": item.value,
        "source_name": item.source_name,
        "source_url": item.source_url,
        "observed_on": item.observed_on.isoformat(),
        "published_on": item.published_on.isoformat() if item.published_on else None,
        "classification": item.classification.value,
        "confidence": item.confidence,
        "supporting_information": item.supporting_information,
        "limitations": list(item.limitations),
    }


def build_activation_report(
    profile: BusinessProfile,
    assessments: tuple[ProspectAssessment, ...],
    *,
    snapshot_at: date,
    pipeline_records: tuple[PipelineRecord, ...] = (),
) -> dict[str, object]:
    """Build combined report and evidence-complete individual prospect briefs."""

    market_order = {"sample-city-one": 0, "sample-city-two": 1}
    ranked_assessments = tuple(
        sorted(
            assessments,
            key=lambda item: (
                0
                if item.fit_classification is ProspectClassification.QUALIFIED_PROSPECT
                else 1,
                market_order.get(item.prospect.market.casefold(), 2),
                -item.fit_score,
                item.prospect.organization.casefold(),
            ),
        )
    )
    ranked = [
        _assessment_dict(item, index)
        for index, item in enumerate(ranked_assessments, start=1)
    ]
    outreach = {
        item.prospect.prospect_id: generate_outreach_materials(item, profile)
        for item in ranked_assessments
        if item.fit_classification is ProspectClassification.QUALIFIED_PROSPECT
    }
    records = {item.prospect_id: item for item in pipeline_records}
    pipeline = [
        {
            "prospect_id": item.prospect.prospect_id,
            "organization": item.prospect.organization,
            "market": item.prospect.market,
            "status": records[item.prospect.prospect_id].status.value
            if item.prospect.prospect_id in records
            else PipelineStatus.RESEARCHED.value,
            "source_evidence_ids": list(
                records[item.prospect.prospect_id].source_evidence_ids
            )
            if item.prospect.prospect_id in records
            else [evidence.evidence_id for evidence in item.prospect.evidence],
            "contact_channel": records[item.prospect.prospect_id].contact_channel
            if item.prospect.prospect_id in records
            else None,
            "last_action_date": records[item.prospect.prospect_id].last_action_date
            if item.prospect.prospect_id in records
            else None,
            "next_action": records[item.prospect.prospect_id].next_action
            if item.prospect.prospect_id in records
            else item.next_action,
            "follow_up_date": records[item.prospect.prospect_id].follow_up_date
            if item.prospect.prospect_id in records
            else None,
            "owner_notes": records[item.prospect.prospect_id].owner_notes
            if item.prospect.prospect_id in records
            else None,
            "outcome": records[item.prospect.prospect_id].outcome
            if item.prospect.prospect_id in records
            else None,
        }
        for item in ranked_assessments
    ]
    capacity_facts = operational_capacity_from_profile(profile)
    first = next(
        (
            item
            for item in ranked_assessments
            if item.fit_classification is ProspectClassification.QUALIFIED_PROSPECT
        ),
        ranked_assessments[0] if ranked_assessments else None,
    )
    report: dict[str, object] = {
        "project": "AEOS-LIVE-002C",
        "report_language": "es",
        "snapshot_date": snapshot_at.isoformat(),
        "business": {
            "name": profile.business_name,
            "website_url": profile.website_url,
            "service_areas": list(profile.owner_confirmed_service_areas or ()),
            "services": list(profile.primary_services),
            "customer_segments": list(profile.target_customer_segments),
            "operational_capacity": {
                "base_capacity_jobs_per_day": (
                    capacity_facts.base_capacity_jobs_per_day
                ),
                "expanded_capacity_jobs_per_day": (
                    capacity_facts.expanded_capacity_jobs_per_day
                ),
                "expansion_dependency": capacity_facts.expansion_dependency,
                "weekend_available": capacity_facts.weekend_available,
                "urgent_service_available": capacity_facts.urgent_service_available,
                "legal_business_established": {
                    "value": capacity_facts.legal_business_established_reported,
                    "classification": "REPORTED",
                    "evidence_id": "profile:legal_business_established:0",
                },
                "documentation_and_insurance_in_order": {
                    "value": capacity_facts.documents_and_insurance_in_order_reported,
                    "classification": "REPORTED",
                    "evidence_id": "profile:documentation_and_insurance_in_order:0",
                    "external_claim_requires_owner_approval": True,
                },
                "evidence_ids": list(capacity_facts.evidence_ids),
            },
        },
        "scoring_rubric": [
            {
                "component": key,
                "name": label,
                "maximum_points": maximum,
                "rule": _rubric_rule(key),
            }
            for key, label, maximum in SCORING_RUBRIC
        ],
        "qualification_rule": (
            f"QUALIFIED_PROSPECT requiere al menos {QUALIFIED_SCORE_THRESHOLD}/100, evidencia OBSERVED vigente, encaje de servicio y zona, y una ruta pública de proveedores con evidencia. Esta etiqueta indica encaje y acceso, no intención de compra."
        ),
        "prospect_ranking": [
            {
                "rank": item["rank"],
                "prospect_id": item["prospect_id"],
                "organization": item["organization"],
                "market": item["market"],
                "score": item["fit_score"],
                "classification": item["fit_classification"],
                "buying_intent": _as_dict(item["buying_intent"])["status"],
                "next_action": item["next_action"],
            }
            for item in ranked
        ],
        "recommended_first_contact": (
            {
                "prospect_id": first.prospect.prospect_id,
                "organization": first.prospect.organization,
                "reason": first.next_action,
                "offer": "Una conversación de validación sobre cobertura de respaldo para fechas y ubicaciones definidas, sujeta a confirmación de capacidad.",
                "ask": first.prospect.validation_question,
                "channel": first.prospect.public_contact_channels[0]
                if first.prospect.public_contact_channels
                else "Verificar un canal público de contacto.",
                "follow_up": "Registrar la respuesta manualmente; si no hay respuesta, programar un único seguimiento tras cinco días hábiles.",
            }
            if first is not None
            else None
        ),
        "prospects": ranked,
        "outreach_materials": outreach,
        "pipeline": pipeline,
        "limitations": [
            "La investigación es una muestra de páginas públicas y de la evidencia preexistente del LIVE-002B2, no un censo de empresas ni una medición del tamaño del mercado.",
            f"Los {len(assessments)} prospectos del ejemplo no establecen por sí solos una intención actual de compra.",
            "No se confirmó quién hace las limpiezas, el proceso de compras, los requisitos de proveedor, el número de inmuebles ni el volumen diario; no se calcula capacidad desde propiedades administradas.",
            f"La capacidad ampliada declarada ({capacity_facts.expanded_capacity_jobs_per_day} trabajos/día) es un máximo condicional, no una promesa.",
            f"La cobertura confirmada se limita a {', '.join(profile.owner_confirmed_service_areas or ())}; valida otras ubicaciones con el propietario.",
            "El propietario reporta que la empresa está legalmente establecida y que documentación y seguro están en orden. Estas declaraciones no se verificaron de forma independiente y requieren aprobación del propietario antes de afirmarlas externamente.",
            "Revalide cualquier canal de contacto antes de usarlo.",
            "Las clasificaciones de idoneidad no confirman compra, relación existente ni autoridad de compras.",
        ],
    }

    return cast(dict[str, object], sanitize_report_data(report))


def _rubric_rule(key: str) -> str:
    rules = {
        "service_alignment": "20 puntos con servicio de limpieza observado que coincide; 10 si solo está descrito en el perfil del candidato; 0 si no coincide.",
        "geographic_alignment": "15 puntos solo con intersección entre cobertura de servicio del prospecto y ciudades confirmadas por el propietario.",
        "customer_segment_alignment": "15 puntos para gestión/operación de alquiler vacacional o corta estancia; 7 con segmento incompleto; 0 sin evidencia.",
        "recurring_demand": "10 puntos si la página describe limpieza de rotación; no se infiere periodicidad ni cantidad de trabajos.",
        "capacity_compatibility": "10 si el volumen declarado cabe en la base; 5 si es desconocido o requiere expansión; 0 si supera el máximo condicional reportado.",
        "schedule_compatibility": "Hasta 5 puntos por posible coincidencia entre rotaciones y disponibilidad reportada en fin de semana/urgencias; no acredita demanda de horario.",
        "vendor_onboarding": "10 con ruta pública explícita para proveedores; 5 con indicio de red a nivel corporativo; 0 si no hay evidencia.",
        "evidence_quality_freshness": "10 si existe evidencia OBSERVED de fuente primaria dentro de 90 días y sin registros OBSERVED vencidos; 5 parcial; 0 sin evidencia vigente.",
        "explicit_buying_intent": "5 solo con evidencia OBSERVED, directa y publicada dentro de 30 días, enlazada como buying_intent_evidence; un formulario general no cuenta.",
    }
    return rules[key]


def render_activation_report_markdown(report: dict[str, object]) -> str:
    """Render the combined activation report in Spanish."""

    business = report["business"]
    if not isinstance(business, dict):
        raise TypeError("business report section is invalid")
    summary = report["recommended_first_contact"]
    prospects = report["prospects"]
    pipeline = report["pipeline"]
    if not isinstance(prospects, list) or not isinstance(pipeline, list):
        raise TypeError("prospect report sections are invalid")
    lines = [
        "# AEOS-LIVE-002C — Activación comercial",
        "",
        f"Fecha del informe: {report['snapshot_date']}",
        "",
        "## 1. Resumen ejecutivo",
        "",
        f"La revisión produjo {len(prospects)} candidatos para validación. Consulte sus fuentes y estados antes de decidir cualquier contacto.",
        "",
        "Confirme capacidad, cobertura y canales antes de asumir un compromiso o contactar una organización.",
        "",
        "## 2. Ranking de prospectos",
        "",
        "| # | Organización | Mercado | Encaje / 100 | Clasificación | Intención de compra | Siguiente paso |",
        "|---:|---|---|---:|---|---|---|",
    ]
    for item in prospects:
        prospect = _as_dict(item)
        intent = _as_dict(prospect["buying_intent"])
        lines.append(
            "| {rank} | {organization} | {market} | {score} | {classification} | {intent} | {action} |".format(
                rank=prospect["rank"],
                organization=prospect["organization"],
                market=prospect["market"],
                score=prospect["fit_score"],
                classification=prospect["fit_classification"],
                intent=intent["status"],
                action=str(prospect["next_action"]).replace("|", "\\|"),
            )
        )
    if isinstance(summary, dict):
        lines.extend(
            (
                "",
                "## 3. A quién contactar primero",
                "",
                f"**{summary['organization']} ({summary['prospect_id']}).** {summary['reason']}",
                "",
                f"- Oferta: {summary['offer']}",
                f"- Pregunta: {summary['ask']}",
                f"- Canal: {summary['channel']}",
                f"- Después: {summary['follow_up']}",
            )
        )
    lines.extend(
        (
            "",
            f"## 4. Perfil de {business['name']} y control de capacidad",
            "",
            f"Servicios: {', '.join(str(item) for item in business['services'])}.",
            f"Cobertura confirmada: {', '.join(str(item) for item in business['service_areas'])}.",
        )
    )
    capacity = _as_dict(business["operational_capacity"])
    lines.extend(
        (
            f"Capacidad base reportada: {capacity['base_capacity_jobs_per_day']} trabajos/día.",
            f"Máximo expandido condicional: {capacity['expanded_capacity_jobs_per_day']} trabajos/día; dependencia: {_period(capacity['expansion_dependency'])}",
            f"Disponibilidad reportada: fines de semana={capacity['weekend_available']}; urgencias={capacity['urgent_service_available']}.",
            f"Evidencia de capacidad del propietario: {', '.join(str(item) for item in _as_list(capacity['evidence_ids']))} (REPORTED).",
            "Confirme la capacidad disponible para cada fecha y ubicación. No infiera trabajos diarios a partir de propiedades administradas.",
            "El estado legal y los documentos/seguro disponibles son declaraciones REPORTED. No incluirlos en mensajes externos sin aprobación final del propietario.",
            "",
            "## 5. Cómo se calcula el encaje",
            "",
            str(report["qualification_rule"]),
            "La puntuación de encaje no mide intención de compra. Cada componente muestra su evidencia y explicación en el perfil individual.",
            "",
            "## 6–9. Perfiles, encaje comercial y señales",
            "",
        )
    )
    for item in prospects:
        _append_prospect_profile(lines, _as_dict(item))
    lines.extend(("## 10. Material de contacto personalizado", ""))
    outreach = _as_dict(report["outreach_materials"])
    if not outreach:
        lines.append("No se generaron borradores: no hay prospectos calificados.")
    for prospect_id, materials in outreach.items():
        lines.append(f"### {prospect_id}")
        lines.append("")
        lines.append(
            "Los borradores en inglés son primarios; la versión en español es para revisión interna. Todos requieren aprobación humana y ninguno se envía automáticamente."
        )
        lines.append("")
        for key, body in _as_dict(materials).items():
            if not isinstance(body, dict):
                continue
            lines.append(f"#### {key.replace('_', ' ').title()}")
            lines.append("")
            lines.extend(("**English**", "", "```text", str(body["en"]), "```", ""))
            lines.extend(
                (
                    "**Español — revisión interna**",
                    "",
                    "```text",
                    str(body["es"]),
                    "```",
                    "",
                )
            )
    lines.extend(("## 11–12. Próximos pasos y seguimiento", ""))
    for item in pipeline:
        record = _as_dict(item)
        lines.append(
            f"- {record['organization']} ({record['market']}): estado `{record['status']}`; siguiente paso: {record['next_action']}; último contacto: {record['last_action_date'] or 'sin contacto registrado'}; seguimiento: {record['follow_up_date'] or 'sin fecha'}."
        )
    lines.extend(
        (
            "",
            "El pipeline solo registra acciones manuales. El contacto requiere estado `APPROVED_FOR_CONTACT` después de una aprobación registrada. Las respuestas, reuniones y cotizaciones se registran manualmente.",
            "",
            "## 13. Límites de la investigación",
            "",
        )
    )
    limitations = report["limitations"]
    if isinstance(limitations, list):
        lines.extend(f"- {item}" for item in limitations)
    return safe_text_for_report("\n".join(lines) + "\n")


def render_prospect_brief_markdown(assessment: ProspectAssessment, *, rank: int) -> str:
    """Render an individual brief from one assessment, in Spanish."""

    report = _assessment_dict(assessment, rank)
    lines = [
        f"# Ficha comercial — {report['organization']}",
        "",
        f"Proyecto: AEOS-LIVE-002C · Mercado: {report['market']} · Puesto: {rank}",
        "",
    ]
    _append_prospect_profile(lines, report)
    return safe_text_for_report("\n".join(lines) + "\n")


def render_outreach_markdown(
    organization: str, materials: dict[str, dict[str, str]]
) -> str:
    """Render the dual-language review pack for a qualified prospect."""

    lines = [
        f"# Borradores para revisión — {organization}",
        "",
        "English is the primary outreach language. Spanish is an internal translation for owner review. Human approval is required before every contact. This file contains drafts only; it does not send or submit anything.",
        "",
    ]
    for key, body in materials.items():
        lines.extend(
            (
                f"## {key.replace('_', ' ').title()}",
                "",
                "### English",
                "",
                "```text",
                body["en"],
                "```",
                "",
                "### Español — revisión interna",
                "",
                "```text",
                body["es"],
                "```",
                "",
            )
        )
    return safe_text_for_report("\n".join(lines))


def _append_prospect_profile(lines: list[str], prospect: dict[str, object]) -> None:
    profile = _as_dict(prospect["profile"])
    contact = _as_dict(prospect["contact"])
    vendor = _as_dict(prospect["vendor_onboarding"])
    intent = _as_dict(prospect["buying_intent"])
    capacity = _as_dict(prospect["capacity"])
    overflow = _as_dict(prospect["overflow_opportunity"])
    lines.extend(
        (
            f"### {prospect['rank']}. {prospect['organization']} — {prospect['fit_classification']} ({prospect['fit_score']}/100)",
            "",
            f"- Mercado: {prospect['market']}.",
            f"- Sitio oficial: {profile['website_url'] or 'no documentado'}.",
            f"- Cobertura publicada: {', '.join(str(item) for item in _as_list(profile['service_areas'])) or 'no documentada'}.",
            f"- Actividad/servicios: {', '.join(str(item) for item in _as_list(profile['services'])) or 'no documentados'}.",
            f"- Segmentos: {', '.join(str(item) for item in _as_list(profile['customer_segments'])) or 'no documentados'}.",
            f"- Demanda recurrente: {', '.join(str(item) for item in _as_list(profile['recurring_options'])) or 'no establecida'}.",
            f"- Modelo de limpieza: {_period(profile['cleaning_delivery_model'])}",
            f"- Escala pública: {_period(profile['operational_scale'])}",
            f"- Contacto público: {_period('; '.join(str(item) for item in _as_list(contact['channels'])) or 'no disponible')}",
            f"- Rol público: {_period(profile['relevant_public_contact_role'] or 'no documentado')}",
            f"- Revalidación de contacto: {_period(('sí — ' + str(contact['revalidation_note'])) if contact['revalidation_required'] else 'no señalada por las fuentes revisadas')}",
            f"- Incorporación de proveedores: {vendor['status']}; evidencia: {', '.join(str(item) for item in _as_list(vendor['evidence_ids'])) or 'ninguna'}.",
            f"- Intención de compra: {intent['status']}; evidencia: {', '.join(str(item) for item in _as_list(intent['evidence_ids'])) or 'ninguna'}. El fit no se trata como intención.",
            f"- Capacidad para esta oportunidad: {capacity['state']}; {_period(capacity['recommendation'])}",
            f"- Oportunidad de overflow: `{overflow['type']}` — HIPÓTESIS; necesidad confirmada={overflow['confirmed_need']}. {overflow['hypothesis']}",
            f"- Enfoque: {_period(prospect['recommended_action'])}",
            f"- Pregunta de validación: {_period(prospect['validation_question'])}",
            f"- Próxima acción: {_period(prospect['next_action'])}",
            "",
            "#### Componentes del score",
            "",
            "| Componente | Puntos | Explicación | Evidencia |",
            "|---|---:|---|---|",
        )
    )
    components = prospect["score_components"]
    if isinstance(components, list):
        for raw in components:
            component = _as_dict(raw)
            refs = (
                ", ".join(str(item) for item in _as_list(component["evidence_ids"]))
                or "sin evidencia directa"
            )
            lines.append(
                f"| {component['label']} | {component['score']}/{component['maximum']} | {component['explanation']} | {refs} |"
            )
    lines.extend(("", "#### Fuentes y evidencia", ""))
    evidence_items = prospect["evidence"]
    if isinstance(evidence_items, list):
        for raw in evidence_items:
            item = _as_dict(raw)
            lines.append(
                f"- `{item['evidence_id']}` ({item['classification']}, observada {item['observed_on']}): {item['value']} — [{item['source_name']}]({item['source_url']})."
            )
            if item["limitations"]:
                lines.append(
                    "  Limitación: "
                    + "; ".join(str(value) for value in _as_list(item["limitations"]))
                )
    lines.extend(("", "#### Limitaciones", ""))
    limitations = prospect["limitations"]
    if isinstance(limitations, list):
        lines.extend(f"- {item}" for item in limitations)
    lines.append("")


def _as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("report value must be a dictionary")
    return value


def _as_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError("report value must be a list")
    return value


def _period(value: object) -> str:
    sentence = str(value).strip().rstrip(".").rstrip()
    if not sentence:
        return ""
    return sentence if sentence.endswith(("?", "!")) else sentence + "."
