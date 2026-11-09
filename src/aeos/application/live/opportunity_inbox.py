"""Qualification, human approval, and Spanish reporting for the LIVE inbox."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Mapping, cast
from uuid import uuid4

from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.profile import BusinessProfile
from aeos.live.domain.url_policy import safe_text_for_report, safe_url_for_report
from aeos.live.domain.evidence import EvidenceKind, JsonScalar, SourceEvidence
from aeos.tenancy.domain import TenantContext
from aeos.live.domain.opportunity_inbox import (
    DemandType,
    LeadClassification,
    Opportunity,
    OpportunityAssessment,
    OpportunityEvent,
    OpportunityEventAction,
    OpportunityRecord,
    OpportunityStatus,
    PermissionBasis,
    ProcurementStatus,
    SourceProvenance,
    classify_opportunity,
    duplicate_key,
    make_initial_record,
    history_issues,
    DuplicateMatchType,
    unused_approval_event,
    validate_status_transition,
)


def _trusted_approval_actor(approver: TenantContext) -> str:
    if not isinstance(approver, TenantContext):
        raise InvalidLiveContract(
            "approval requires an authenticated tenant manager context"
        )
    return approver.require_manager_actor()


def opportunity_from_mapping(
    payload: Mapping[str, object], *, imported_at: datetime | None = None
) -> Opportunity:
    """Build one sanitized manual opportunity from a JSON-compatible mapping."""

    if payload.get("template_only") is True:
        raise InvalidLiveContract(
            "the sample template cannot be imported; replace its values and remove template_only"
        )
    discovered_at = (
        _datetime(payload.get("discovered_at"))
        or imported_at
        or datetime.now(timezone.utc)
    )
    public = _bool(payload, "publicly_accessible")
    account_authorized = bool(payload.get("account_holder_authorized", False))
    if not public and not account_authorized:
        raise InvalidLiveContract(
            "private marketplace information requires account-holder authorization"
        )
    try:
        demand_type = DemandType(str(payload["demand_type"]))
        permission_basis = PermissionBasis(str(payload["permission_basis"]))
        provenance_value = payload.get("source_provenance", "UNKNOWN")
        declared_provenance = SourceProvenance(
            "UNKNOWN" if provenance_value is None else str(provenance_value)
        )
        source_provenance = (
            SourceProvenance.SYNTHETIC
            if declared_provenance is SourceProvenance.SYNTHETIC
            else SourceProvenance.UNKNOWN
        )
        procurement_value = payload.get("procurement_status")
        procurement_status = (
            ProcurementStatus(str(procurement_value))
            if procurement_value not in (None, "")
            else None
        )
    except (KeyError, ValueError) as error:
        raise InvalidLiveContract(f"invalid opportunity category: {error}") from error

    opportunity_id = _text_value(payload, "opportunity_id")
    title = _text_value(payload, "title")
    source_platform = _text_value(payload, "source_platform")
    source_url = _optional_text(payload.get("source_url"))
    source_event_ref = _optional_text(payload.get("source_event_ref"))
    city = _optional_text(payload.get("city"))
    state = _optional_text(payload.get("state"))
    service = _text_value(payload, "service_requested")
    customer_segment = _optional_text(payload.get("customer_segment"))
    summary = _text_value(payload, "summary")
    response_method = _optional_text(payload.get("response_method"))
    source_terms_note = _text_value(payload, "source_terms_note")
    stable_request_id = _optional_text(payload.get("stable_request_id"))
    procurement_scope = _optional_text(payload.get("procurement_scope"))
    eligibility_reviewed = _bool(payload, "eligibility_reviewed", default=False)
    eligibility_requirements = _string_tuple(
        payload.get("eligibility_requirements", [])
    )
    limitations = _string_tuple(payload.get("limitations", []))
    if not public:
        # Private customer details stay in the source account. AEOS retains only
        # a generic label and a fixed summary; the mapped event adapter follows
        # the same allowlist.
        title = f"Lead privado de {source_platform}: {service}"
        summary = "Detalles del cliente conservados en la plataforma autorizada."
        response_method = "Responder dentro de la plataforma autorizada"
        source_terms_note = "Datos mínimos de una cuenta autorizada; los detalles permanecen en la plataforma."
        eligibility_requirements = ()
        limitations = ("No se conserva el contenido ni el contacto del cliente.",)

    publication = _date(payload.get("publication_date"))
    evidence_payload = payload.get("evidence")
    if not isinstance(evidence_payload, list) or not evidence_payload:
        raise InvalidLiveContract("evidence must be a non-empty array")
    evidence: list[SourceEvidence] = []
    allowed_private_fields = {
        "service_requested",
        "customer_segment",
        "city",
        "state",
        "explicit_intent",
        "response_method",
        "publication_date",
        "source_event_ref",
    }
    for index, raw in enumerate(evidence_payload):
        if not isinstance(raw, dict):
            raise InvalidLiveContract("each evidence entry must be an object")
        field = _text_value(raw, "field")
        if not public and field not in allowed_private_fields:
            raise InvalidLiveContract(
                f"private marketplace evidence field {field!r} is not allowed"
            )
        try:
            kind = EvidenceKind(str(raw.get("kind", "REPORTED")))
        except ValueError as error:
            raise InvalidLiveContract("evidence kind is invalid") from error
        value_raw = raw.get("value")
        if type(value_raw) not in (str, int, float, bool) and value_raw is not None:
            raise InvalidLiveContract("evidence values must be JSON scalars")
        value = cast(JsonScalar, value_raw)
        if not public:
            value = _safe_private_evidence_value(
                field,
                service=service,
                city=city,
                state=state,
                explicit_intent=bool(payload.get("explicit_intent", False)),
                response_method=response_method,
                publication_date=publication,
                event_ref=source_event_ref,
            )
        source_name = (
            source_platform
            if not public
            else _optional_text(raw.get("source_name")) or source_platform
        )
        evidence.append(
            SourceEvidence(
                evidence_id=_optional_text(raw.get("evidence_id"))
                or f"{opportunity_id}-evidence-{index + 1}",
                kind=kind,
                subject=opportunity_id,
                field=field,
                value=value,
                source_name=source_name,
                source_url=source_url if public else None,
                retrieved_at=None,
                excerpt=(_optional_text(raw.get("excerpt")) if public else None),
                confidence=_float_or_none(raw.get("confidence")),
                assumptions=()
                if not public
                else _string_tuple(raw.get("assumptions", [])),
                owner_entity_id=opportunity_id,
            )
        )
    try:
        opportunity = Opportunity(
            opportunity_id=opportunity_id,
            title=title,
            source_platform=source_platform,
            demand_type=demand_type,
            publication_date=publication,
            discovered_at=discovered_at,
            service_requested=service,
            summary=summary,
            source_url=source_url,
            source_event_ref=source_event_ref,
            city=city,
            state=state,
            explicit_intent=_bool(payload, "explicit_intent"),
            is_open=_optional_bool(payload.get("is_open"), "is_open"),
            response_method=response_method,
            publicly_accessible=public,
            business_authorized=_bool(payload, "business_authorized"),
            account_holder_authorized=account_authorized,
            permission_basis=permission_basis,
            source_terms_note=source_terms_note,
            procurement_status=procurement_status,
            official_deadline=_date(payload.get("official_deadline")),
            eligibility_requirements=eligibility_requirements,
            expected_jobs_per_day=_optional_int(
                payload.get("expected_jobs_per_day"), "expected_jobs_per_day"
            ),
            ongoing_need=_bool(payload, "ongoing_need", default=False),
            limitations=limitations,
            evidence=tuple(evidence),
            stable_request_id=stable_request_id if public else None,
            procurement_scope=procurement_scope,
            eligibility_reviewed=eligibility_reviewed,
            source_provenance=source_provenance,
            customer_segment=customer_segment,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidLiveContract(f"invalid opportunity: {error}") from error
    return opportunity


def import_record(
    payload: Mapping[str, object], *, imported_at: datetime | None = None
) -> OpportunityRecord:
    opportunity = opportunity_from_mapping(payload, imported_at=imported_at)
    return make_initial_record(opportunity, occurred_at=opportunity.discovered_at)


def update_status(
    record: OpportunityRecord,
    status: OpportunityStatus,
    *,
    actor: str,
    note: str,
    occurred_at: datetime,
) -> OpportunityRecord:
    event = _event(
        record,
        status,
        OpportunityEventAction.STATUS_UPDATED,
        actor,
        _private_action_note(record, note, "Estado manual actualizado"),
        occurred_at,
    )
    return OpportunityRecord(
        record.opportunity,
        status,
        (*record.events, event),
        record.next_action,
        record.follow_up_date,
    )


def approve_contact(
    record: OpportunityRecord,
    *,
    approver: TenantContext,
    note: str,
    occurred_at: datetime,
    business_profile: BusinessProfile | None = None,
) -> OpportunityRecord:
    _require_clean_history(record)
    actor = _trusted_approval_actor(approver)
    if not note.strip():
        raise InvalidLiveContract("approval note is required")
    assessment = classify_opportunity(
        record.opportunity,
        as_of=occurred_at.date(),
        organization_profile=business_profile,
    )
    if assessment.classification is not LeadClassification.HOT:
        raise InvalidLiveContract("contact approval requires a HOT opportunity")
    if record.possible_duplicate_ids:
        raise InvalidLiveContract(
            "possible duplicates must be resolved before contact approval"
        )
    if not _has_verified_review_path(record):
        raise InvalidLiveContract(
            "contact approval requires verified evidence followed by NEEDS_REVIEW"
        )
    event = _event(
        record,
        OpportunityStatus.APPROVED_FOR_CONTACT,
        OpportunityEventAction.CONTACT_APPROVED,
        actor,
        _private_action_note(record, note, "Aprobación de un contacto manual"),
        occurred_at,
    )
    return OpportunityRecord(
        record.opportunity,
        OpportunityStatus.APPROVED_FOR_CONTACT,
        (*record.events, event),
        record.next_action,
        record.follow_up_date,
    )


def record_manual_contact(
    record: OpportunityRecord,
    *,
    actor: str,
    channel: str,
    note: str,
    next_action: str,
    follow_up_date: date | None,
    occurred_at: datetime,
) -> OpportunityRecord:
    _require_clean_history(record)
    if not _has_verified_review_path(record):
        raise InvalidLiveContract("contact requires a verified review path")
    approval = unused_approval_event(
        record,
        OpportunityEventAction.CONTACT_APPROVED,
        OpportunityEventAction.MANUAL_CONTACT_RECORDED,
    )
    event = _event(
        record,
        OpportunityStatus.CONTACTED,
        OpportunityEventAction.MANUAL_CONTACT_RECORDED,
        actor,
        _private_action_note(
            record,
            f"Contacto manual por {channel}: {note}",
            "Contacto manual registrado",
        ),
        occurred_at,
        related_event_id=approval.event_id if approval is not None else None,
    )
    return OpportunityRecord(
        record.opportunity,
        OpportunityStatus.CONTACTED,
        (*record.events, event),
        _safe_next_action(record, next_action),
        follow_up_date,
    )


def approve_quote(
    record: OpportunityRecord,
    *,
    approver: TenantContext,
    note: str,
    occurred_at: datetime,
) -> OpportunityRecord:
    _require_clean_history(record)
    actor = _trusted_approval_actor(approver)
    if not note.strip():
        raise InvalidLiveContract("approval note is required")
    if record.status is not OpportunityStatus.QUOTE_REQUESTED:
        raise InvalidLiveContract("quote approval requires QUOTE_REQUESTED status")
    if not record.opportunity.business_authorized:
        raise InvalidLiveContract("quote approval requires authorized source use")
    if not _has_contact_reply_path(record):
        raise InvalidLiveContract("quote approval requires recorded contact and reply")
    if (
        unused_approval_event(
            record,
            OpportunityEventAction.QUOTE_APPROVED,
            OpportunityEventAction.QUOTE_RECORDED,
        )
        is not None
    ):
        raise InvalidLiveContract("a quote approval is already pending")
    event = _event(
        record,
        OpportunityStatus.QUOTE_REQUESTED,
        OpportunityEventAction.QUOTE_APPROVED,
        actor,
        _private_action_note(record, note, "Aprobación de una cotización manual"),
        occurred_at,
    )
    return OpportunityRecord(
        record.opportunity,
        record.status,
        (*record.events, event),
        record.next_action,
        record.follow_up_date,
    )


def record_quote(
    record: OpportunityRecord,
    *,
    actor: str,
    channel: str,
    note: str,
    next_action: str,
    follow_up_date: date | None,
    occurred_at: datetime,
) -> OpportunityRecord:
    _require_clean_history(record)
    if not _has_contact_reply_path(record):
        raise InvalidLiveContract("quote action requires recorded contact and reply")
    approval = unused_approval_event(
        record,
        OpportunityEventAction.QUOTE_APPROVED,
        OpportunityEventAction.QUOTE_RECORDED,
    )
    if not record.opportunity.business_authorized:
        raise InvalidLiveContract("quote action requires authorized source use")
    event = _event(
        record,
        OpportunityStatus.QUOTE_SENT,
        OpportunityEventAction.QUOTE_RECORDED,
        actor,
        _private_action_note(
            record,
            f"Cotización registrada manualmente por {channel}: {note}",
            "Cotización manual registrada",
        ),
        occurred_at,
        related_event_id=approval.event_id if approval is not None else None,
    )
    return OpportunityRecord(
        record.opportunity,
        OpportunityStatus.QUOTE_SENT,
        (*record.events, event),
        _safe_next_action(record, next_action),
        follow_up_date,
    )


def record_response(
    record: OpportunityRecord,
    *,
    status: OpportunityStatus,
    actor: str,
    note: str,
    next_action: str,
    follow_up_date: date | None,
    occurred_at: datetime,
) -> OpportunityRecord:
    _require_clean_history(record)
    if status is OpportunityStatus.WON and not _has_contact_reply_path(record):
        raise InvalidLiveContract("WON requires a documented contact and reply")
    event = _event(
        record,
        status,
        OpportunityEventAction.RESPONSE_RECORDED,
        actor,
        _private_action_note(record, note, "Respuesta manual registrada"),
        occurred_at,
    )
    return OpportunityRecord(
        record.opportunity,
        status,
        (*record.events, event),
        _safe_next_action(record, next_action),
        follow_up_date,
    )


def build_opportunity_report(
    records: tuple[OpportunityRecord, ...],
    *,
    as_of: date,
    business_profile: BusinessProfile | None = None,
) -> tuple[OpportunityAssessment, ...]:
    assessments = tuple(
        classify_opportunity(
            record.opportunity, as_of=as_of, organization_profile=business_profile
        )
        for record in records
    )
    priority = {
        LeadClassification.HOT: 0,
        LeadClassification.WARM: 1,
        LeadClassification.COLD: 2,
        LeadClassification.INSUFFICIENT_EVIDENCE: 3,
        LeadClassification.EXPIRED: 4,
    }
    return tuple(
        sorted(
            assessments,
            key=lambda item: (
                priority[item.classification],
                -item.commercial_fit_score,
                item.opportunity.opportunity_id,
                item.opportunity.title.casefold(),
            ),
        )
    )


def render_opportunity_report_markdown(
    records: tuple[OpportunityRecord, ...],
    *,
    as_of: date,
    business_profile: BusinessProfile | None = None,
) -> str:
    assessments = build_opportunity_report(
        records, as_of=as_of, business_profile=business_profile
    )
    organization_label = business_profile.business_name if business_profile else "AEOS"
    lines = [
        f"# Bandeja de oportunidades — {organization_label}",
        "",
        f"Fecha de revisión: {as_of.isoformat()}",
        "",
        "Este reporte diferencia solicitudes reales, leads de marketplace, compras públicas y señales indirectas. La puntuación mide ajuste comercial; no estima probabilidad de cierre, ingresos ni conversiones. No se envía contacto ni cotización desde AEOS.",
        "",
        "## Cola prioritaria",
        "",
    ]
    queue = [
        item
        for item in assessments
        if item.classification in {LeadClassification.HOT, LeadClassification.WARM}
        and _record_for(item.opportunity.opportunity_id, records).status
        in {
            OpportunityStatus.DISCOVERED,
            OpportunityStatus.VERIFIED,
            OpportunityStatus.NEEDS_REVIEW,
            OpportunityStatus.APPROVED_FOR_CONTACT,
        }
        and not _record_for(
            item.opportunity.opportunity_id, records
        ).possible_duplicate_ids
    ]
    if queue:
        for index, item in enumerate(queue, 1):
            linked_sources = _record_for(
                item.opportunity.opportunity_id, records
            ).duplicate_source_ids
            linked_note = (
                f"; {len(linked_sources)} fuente(s) exacta(s) o confirmada(s) vinculada(s)"
                if linked_sources
                else ""
            )
            lines.append(
                f"{index}. **{_report_title(item.opportunity)}** — {item.classification.value}, ajuste {item.commercial_fit_score}/100{linked_note}. {item.priority_reason_es}"
            )
    else:
        if any(record.possible_duplicate_ids for record in records):
            lines.append(
                "No hay oportunidades HOT o WARM liberadas para acción; los registros con posible duplicado esperan revisión humana."
            )
        else:
            lines.append("No hay oportunidades HOT o WARM calificadas en el registro.")
    lines.extend(("", "## Revisión de duplicados", ""))
    duplicate_rows: list[str] = []
    seen_pairs: set[tuple[str, str]] = set()
    by_id = {record.opportunity.opportunity_id: record for record in records}
    for record in records:
        opportunity_id = record.opportunity.opportunity_id
        if record.duplicate_of:
            duplicate_rows.append(
                f"- `{opportunity_id}` está vinculado como `{record.duplicate_match.value if record.duplicate_match else 'DUPLICATE'}` a `{record.duplicate_of}`. Su fuente y evidencia se conservan, pero no cuentan como demanda HOT independiente ni pueden recibir acciones."
            )
        for related_id in record.duplicate_source_ids:
            pair = (
                (opportunity_id, related_id)
                if opportunity_id < related_id
                else (related_id, opportunity_id)
            )
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                duplicate_rows.append(
                    f"- `{opportunity_id}` conserva fuente(s) duplicada(s) vinculada(s): `{related_id}`."
                )
        for related_id in record.possible_duplicate_ids:
            pair = (
                (opportunity_id, related_id)
                if opportunity_id < related_id
                else (related_id, opportunity_id)
            )
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                other = by_id.get(related_id)
                other_label = _report_title(other.opportunity) if other else related_id
                duplicate_rows.append(
                    f"- **POSSIBLE_DUPLICATE** `{opportunity_id}` ↔ `{related_id}` ({_report_title(record.opportunity)} / {other_label}). Requiere revisión humana; no se fusiona, no se aprueba para contacto y no se presenta como demanda única verificada."
                )
    lines.extend(duplicate_rows or ["No hay relaciones de duplicado registradas."])
    lines.append("")
    lines.extend(("", "## Hallazgos", ""))
    if not assessments:
        lines.append(
            "La bandeja está vacía. Importe una solicitud autorizada para comenzar."
        )
    for item in assessments:
        opportunity = item.opportunity
        evidence_notes = "; ".join(
            f"{e.field}={'[private reference redacted]' if e.field == 'source_event_ref' else e.value} "
            f"({e.kind.value}, confianza {e.confidence if e.confidence is not None else 'no indicada'})"
            for e in opportunity.evidence
        )
        source_ref = (
            f"[{opportunity.source_platform}]({safe_url_for_report(opportunity.source_url) or ''})"
            if opportunity.source_url
            else f"{opportunity.source_platform} — evento autorizado (referencia interna)"
        )
        publication = (
            opportunity.publication_date.isoformat()
            if opportunity.publication_date
            else "no indicada"
        )
        procurement = (
            opportunity.procurement_status.value
            if opportunity.procurement_status
            else "No aplica"
        )
        if opportunity.eligibility_requirements:
            eligibility_text = "; ".join(opportunity.eligibility_requirements)
        elif opportunity.eligibility_reviewed:
            eligibility_text = "revisada; no se identificaron requisitos adicionales"
        else:
            eligibility_text = "no revisada/no documentada"
        workload_text = (
            f"{opportunity.expected_jobs_per_day} trabajo(s)/día"
            if opportunity.expected_jobs_per_day is not None
            else "desconocida"
        )
        procurement_review = (
            f"- Demanda explícita: {_yes_no(opportunity.explicit_intent)}; evidencia observada: {_observed_evidence_count(opportunity)} campo(s) de calidad suficiente.\n"
            f"- Elegibilidad revisada: {_yes_no(opportunity.eligibility_reviewed)}; requisitos: {eligibility_text}.\n"
            f"- Ajuste operativo: alcance {opportunity.procurement_scope or 'desconocido'}; carga {workload_text}.\n"
            "- Autorización de respuesta o presentación: requiere aprobación humana específica; AEOS no contacta ni presenta bids."
            if opportunity.demand_type is DemandType.PUBLIC_PROCUREMENT
            else ""
        )
        lines.extend(
            (
                f"### {_report_title(opportunity)}",
                "",
                f"- Fuente: {source_ref}.",
                f"- Ciudad: {opportunity.city or 'no verificada'}{', ' + opportunity.state if opportunity.state else ''}.",
                f"- Servicio solicitado: {opportunity.service_requested}.",
                f"- Segmento de cliente: {opportunity.customer_segment or 'No especificado'}.",
                f"- Tipo de demanda: {opportunity.demand_type.value}.",
                f"- Procedencia de fuente: {opportunity.source_provenance.value}.",
                f"- Clasificación: **{item.classification.value}**; estado manual: `{_status_for(opportunity.opportunity_id, records)}`.",
                *[
                    f"- Motivo de clasificación: {reason}"
                    for reason in item.classification_reasons_es
                ],
                f"- Publicación: {publication}; descubrimiento: {opportunity.discovered_at.date().isoformat()}.",
                f"- Evidencia: {evidence_notes or 'sin evidencia'}.",
                f"- Estado de contratación: {procurement}; abierto confirmado: {_yes_no(opportunity.is_open)}.",
                f"- Canal de respuesta: {opportunity.response_method or 'no verificado'}.",
                f"- Condición de vigencia: {_expiration_condition(opportunity, as_of)}",
                f"- Restricciones: {opportunity.source_terms_note}; autorización de uso: {_yes_no(opportunity.business_authorized)}.",
                f"- Capacidad: {item.capacity_note_es}",
                f"- Oportunidad potencialmente sobredimensionada: {_yes_no(item.potentially_oversized)}. Disponibilidad de fin de semana y urgencias: confirmar con el dueño.",
                f"- Ajuste comercial: {item.commercial_fit_score}/100.",
                f"- Próxima acción recomendada: {item.recommended_action_es}",
            )
        )
        if procurement_review:
            lines.extend(procurement_review.splitlines())
        if record_has_possible_duplicate(opportunity.opportunity_id, records):
            lines.append(
                "- Revisión pendiente: POSSIBLE_DUPLICATE; no aprobar contacto hasta resolver la relación."
            )
        record = _record_for(opportunity.opportunity_id, records)
        if record.duplicate_of:
            lines.append(
                f"- Duplicado de `{record.duplicate_of}`; esta fuente se mantiene como procedencia auditable."
            )
        if opportunity.publicly_accessible and opportunity.summary:
            lines.append(f"- Resumen de evidencia: {opportunity.summary}")
        if opportunity.official_deadline:
            lines.append(
                f"- Plazo oficial: {opportunity.official_deadline.isoformat()}."
            )
        if opportunity.eligibility_requirements:
            lines.append(
                "- Elegibilidad documentada: "
                + "; ".join(opportunity.eligibility_requirements)
                + "."
            )
        if opportunity.limitations:
            lines.append("- Limitaciones: " + "; ".join(opportunity.limitations) + ".")
        lines.extend(("", "#### Componentes del ajuste", ""))
        lines.append("| Componente | Puntos | Explicación |")
        lines.append("|---|---:|---|")
        for component in item.score_components:
            lines.append(
                f"| {component.label_es} | {component.score}/{component.maximum} | {component.explanation_es} |"
            )
        lines.append("")
    lines.extend(
        (
            "## Alcance de las fuentes",
            "",
            "Thumbtack: `PROVIDER_NOT_CONFIGURED`; el contrato de ingesta solo se probó con eventos sintéticos (`FIXTURE_ONLY`), sin endpoint conectado. Turno: registro manual por el titular, sin extracción ni bids automatizados. OpenGov y otros portales públicos: envío y revisión manuales.",
            "",
            "Cada contacto y cada acción de cotización requiere aprobación explícita del dueño. AEOS solo registra el seguimiento; no envía mensajes, ofertas ni bids.",
            "",
        )
    )
    return safe_text_for_report("\n".join(lines))


def render_follow_up_report(
    records: tuple[OpportunityRecord, ...], *, as_of: date
) -> str:
    due = tuple(
        item
        for item in records
        if item.follow_up_date is not None
        and item.follow_up_date <= as_of
        and item.status
        not in {
            OpportunityStatus.WON,
            OpportunityStatus.LOST,
            OpportunityStatus.EXPIRED,
            OpportunityStatus.DISQUALIFIED,
            OpportunityStatus.DUPLICATE,
        }
    )
    lines = [
        "# Seguimientos pendientes — Sample Cleaning Company (Fictional)",
        "",
        f"Corte: {as_of.isoformat()}",
        "",
    ]
    if not due:
        lines.append("No hay seguimientos manuales pendientes.")
    for record in due:
        due_date = record.follow_up_date
        if due_date is None:
            continue
        lines.append(
            f"- **{_report_title(record.opportunity)}** — vencido {due_date.isoformat()}; acción: {record.next_action or 'revisar manualmente'}; estado `{record.status.value}`."
        )
    lines.extend(("", "Este reporte no ejecuta contactos.", ""))
    return safe_text_for_report("\n".join(lines))


def record_duplicate_key(record: OpportunityRecord) -> str:
    return duplicate_key(record.opportunity)


def flag_possible_duplicate(
    record: OpportunityRecord,
    related_opportunity_id: str,
    *,
    actor: str,
    note: str,
    occurred_at: datetime,
) -> OpportunityRecord:
    if related_opportunity_id == record.opportunity.opportunity_id:
        raise InvalidLiveContract(
            "an opportunity cannot be a possible duplicate of itself"
        )
    if related_opportunity_id in record.possible_duplicate_ids:
        return record
    target = record.status
    if record.status in {OpportunityStatus.DISCOVERED, OpportunityStatus.VERIFIED}:
        target = OpportunityStatus.NEEDS_REVIEW
    event = _event(
        record,
        target,
        OpportunityEventAction.POSSIBLE_DUPLICATE_FLAGGED,
        actor,
        _private_action_note(
            record,
            note,
            "Posible duplicado; revisión humana requerida",
        ),
        occurred_at,
        related_event_id=related_opportunity_id,
    )
    return replace(
        record,
        status=target,
        events=(*record.events, event),
        possible_duplicate_ids=tuple(
            sorted((*record.possible_duplicate_ids, related_opportunity_id))
        ),
    )


def link_duplicate_source(
    canonical: OpportunityRecord,
    source: OpportunityRecord,
    *,
    match_type: DuplicateMatchType,
    actor: str,
    note: str,
    occurred_at: datetime,
) -> tuple[OpportunityRecord, OpportunityRecord]:
    if source.status is not OpportunityStatus.DISCOVERED:
        raise InvalidLiveContract("only a newly discovered record can be auto-linked")
    if source.opportunity.opportunity_id == canonical.opportunity.opportunity_id:
        raise InvalidLiveContract("an opportunity cannot duplicate itself")
    source_event = _event(
        source,
        OpportunityStatus.DUPLICATE,
        OpportunityEventAction.DUPLICATE_MARKED,
        actor,
        note,
        occurred_at,
        related_event_id=canonical.opportunity.opportunity_id,
    )
    canonical_event = _event(
        canonical,
        canonical.status,
        OpportunityEventAction.DUPLICATE_SOURCE_LINKED,
        actor,
        note,
        occurred_at,
        related_event_id=source.opportunity.opportunity_id,
    )
    linked_source = replace(
        source,
        status=OpportunityStatus.DUPLICATE,
        events=(*source.events, source_event),
        duplicate_of=canonical.opportunity.opportunity_id,
        duplicate_match=match_type,
    )
    linked_canonical = replace(
        canonical,
        events=(*canonical.events, canonical_event),
        duplicate_source_ids=tuple(
            sorted((*canonical.duplicate_source_ids, source.opportunity.opportunity_id))
        ),
    )
    return linked_canonical, linked_source


def resolve_possible_duplicate_pair(
    left: OpportunityRecord,
    right: OpportunityRecord,
    *,
    is_same_request: bool,
    canonical_opportunity_id: str | None,
    actor: str,
    note: str,
    occurred_at: datetime,
) -> tuple[OpportunityRecord, OpportunityRecord]:
    left_id = left.opportunity.opportunity_id
    right_id = right.opportunity.opportunity_id
    if (
        right_id not in left.possible_duplicate_ids
        or left_id not in right.possible_duplicate_ids
    ):
        raise InvalidLiveContract(
            "the pair is not flagged for possible duplicate review"
        )
    if not is_same_request:
        updated_left = _resolve_one_possible_duplicate(
            left, right_id, actor=actor, note=note, occurred_at=occurred_at
        )
        updated_right = _resolve_one_possible_duplicate(
            right, left_id, actor=actor, note=note, occurred_at=occurred_at
        )
        return updated_left, updated_right
    if canonical_opportunity_id not in {left_id, right_id}:
        raise InvalidLiveContract("choose one of the pair as the canonical opportunity")
    canonical, duplicate = (
        (left, right) if canonical_opportunity_id == left_id else (right, left)
    )
    duplicate_event = _event(
        duplicate,
        OpportunityStatus.DUPLICATE,
        OpportunityEventAction.DUPLICATE_MARKED,
        actor,
        _private_action_note(
            duplicate,
            note,
            "Duplicado confirmado por revisión humana",
        ),
        occurred_at,
        related_event_id=canonical_opportunity_id,
    )
    canonical_event = _event(
        canonical,
        canonical.status,
        OpportunityEventAction.DUPLICATE_SOURCE_LINKED,
        actor,
        _private_action_note(
            canonical,
            note,
            "Fuente duplicada confirmada por revisión humana",
        ),
        occurred_at,
        related_event_id=duplicate.opportunity.opportunity_id,
    )
    linked_duplicate = replace(
        duplicate,
        status=OpportunityStatus.DUPLICATE,
        events=(*duplicate.events, duplicate_event),
        duplicate_of=canonical_opportunity_id,
        duplicate_match=DuplicateMatchType.HUMAN_CONFIRMED,
        possible_duplicate_ids=tuple(
            item
            for item in duplicate.possible_duplicate_ids
            if item != canonical_opportunity_id
        ),
    )
    linked_canonical = replace(
        canonical,
        events=(*canonical.events, canonical_event),
        duplicate_source_ids=tuple(
            sorted(
                (*canonical.duplicate_source_ids, duplicate.opportunity.opportunity_id)
            )
        ),
        possible_duplicate_ids=tuple(
            item
            for item in canonical.possible_duplicate_ids
            if item != duplicate.opportunity.opportunity_id
        ),
    )
    return (
        (linked_canonical, linked_duplicate)
        if canonical is left
        else (linked_duplicate, linked_canonical)
    )


def _resolve_one_possible_duplicate(
    record: OpportunityRecord,
    related_id: str,
    *,
    actor: str,
    note: str,
    occurred_at: datetime,
) -> OpportunityRecord:
    event = _event(
        record,
        record.status,
        OpportunityEventAction.POSSIBLE_DUPLICATE_RESOLVED,
        actor,
        _private_action_note(record, note, "Solicitudes revisadas como independientes"),
        occurred_at,
        related_event_id=related_id,
    )
    return replace(
        record,
        events=(*record.events, event),
        possible_duplicate_ids=tuple(
            item for item in record.possible_duplicate_ids if item != related_id
        ),
    )


def record_open_verification(
    record: OpportunityRecord,
    *,
    actor: str,
    note: str,
    occurred_at: datetime,
) -> OpportunityRecord:
    """Record that a person rechecked the source and confirmed it remains open."""

    _require_clean_history(record)
    if not record.opportunity.business_authorized:
        raise InvalidLiveContract(
            "open-state verification requires authorized source use"
        )
    evidence = SourceEvidence(
        evidence_id=f"{record.opportunity.opportunity_id}-open-{uuid4().hex[:12]}",
        kind=EvidenceKind.OBSERVED,
        subject=record.opportunity.opportunity_id,
        field="open_status",
        value=True,
        source_name=record.opportunity.source_platform,
        source_url=record.opportunity.source_url,
        retrieved_at=occurred_at,
        excerpt=None,
        confidence=1.0,
        assumptions=(),
        owner_entity_id=record.opportunity.opportunity_id,
    )
    opportunity = replace(
        record.opportunity,
        is_open=True,
        evidence=(*record.opportunity.evidence, evidence),
    )
    target = (
        OpportunityStatus.NEEDS_REVIEW
        if record.status is OpportunityStatus.NEEDS_REVIEW
        else OpportunityStatus.VERIFIED
    )
    event = _event(
        record,
        target,
        OpportunityEventAction.OPEN_STATUS_VERIFIED,
        actor,
        _private_action_note(
            record, note, "El estado abierto fue revalidado manualmente"
        ),
        occurred_at,
    )
    return OpportunityRecord(
        opportunity,
        target,
        (*record.events, event),
        record.next_action,
        record.follow_up_date,
    )


def _event(
    record: OpportunityRecord,
    target: OpportunityStatus,
    action: OpportunityEventAction,
    actor: str,
    note: str,
    occurred_at: datetime,
    *,
    related_event_id: str | None = None,
) -> OpportunityEvent:
    validate_status_transition(
        record,
        target,
        action,
        note=note,
        related_event_id=related_event_id,
    )
    return OpportunityEvent(
        event_id=uuid4().hex,
        action=action,
        actor=actor,
        note=note,
        occurred_at=occurred_at,
        scope_id=record.opportunity.opportunity_id,
        related_event_id=related_event_id,
        from_status=record.status,
        to_status=target,
    )


def _ensure_active(record: OpportunityRecord) -> None:
    if record.status in {
        OpportunityStatus.WON,
        OpportunityStatus.LOST,
        OpportunityStatus.EXPIRED,
        OpportunityStatus.DISQUALIFIED,
        OpportunityStatus.DUPLICATE,
    }:
        raise InvalidLiveContract("terminal opportunities cannot be advanced")


def _require_clean_history(record: OpportunityRecord) -> None:
    issues = history_issues(record)
    if issues:
        raise InvalidLiveContract(
            "historical record requires review: " + "; ".join(issues)
        )


def _has_verified_review_path(record: OpportunityRecord) -> bool:
    transitions = tuple(
        (event.from_status, event.to_status)
        for event in record.events
        if event.from_status is not None and event.to_status is not None
    )
    verified = any(
        after is OpportunityStatus.VERIFIED and before is OpportunityStatus.DISCOVERED
        for before, after in transitions
    )
    normal_review = verified and (
        (OpportunityStatus.VERIFIED, OpportunityStatus.NEEDS_REVIEW) in transitions
    )
    if normal_review:
        return True
    resolution_indexes = [
        index
        for index, event in enumerate(record.events)
        if event.action is OpportunityEventAction.POSSIBLE_DUPLICATE_RESOLVED
    ]
    last_resolution = max(resolution_indexes, default=-1)
    revalidated_after_resolution = any(
        event.action is OpportunityEventAction.OPEN_STATUS_VERIFIED
        and event.from_status is OpportunityStatus.NEEDS_REVIEW
        and event.to_status is OpportunityStatus.NEEDS_REVIEW
        and index > last_resolution
        for index, event in enumerate(record.events)
    )
    return (
        not record.possible_duplicate_ids
        and bool(resolution_indexes)
        and revalidated_after_resolution
    )


def _has_contact_reply_path(record: OpportunityRecord) -> bool:
    transitions = tuple(
        (event.from_status, event.to_status)
        for event in record.events
        if event.from_status is not None and event.to_status is not None
    )
    return (
        (OpportunityStatus.APPROVED_FOR_CONTACT, OpportunityStatus.CONTACTED)
        in transitions
        and (OpportunityStatus.CONTACTED, OpportunityStatus.REPLIED) in transitions
        and (OpportunityStatus.REPLIED, OpportunityStatus.QUOTE_REQUESTED)
        in transitions
    )


def _has_unused_approval(
    record: OpportunityRecord,
    approval_action: OpportunityEventAction,
    use_action: OpportunityEventAction,
) -> bool:
    return unused_approval_event(record, approval_action, use_action) is not None


def _private_action_note(
    record: OpportunityRecord, submitted_note: str, safe_note: str
) -> str:
    if not record.opportunity.publicly_accessible:
        return f"{safe_note}; los detalles del cliente permanecen en la plataforma."
    return submitted_note


def _safe_next_action(record: OpportunityRecord, submitted_action: str) -> str:
    if not record.opportunity.publicly_accessible:
        return "Revisar novedades dentro de la plataforma autorizada."
    return submitted_action


def _safe_private_evidence_value(
    field: str,
    *,
    service: str,
    city: str | None,
    state: str | None,
    explicit_intent: bool,
    response_method: str | None,
    publication_date: date | None,
    event_ref: str | None,
) -> JsonScalar:
    values: dict[str, JsonScalar] = {
        "service_requested": service,
        "city": city,
        "state": state,
        "explicit_intent": explicit_intent,
        "response_method": response_method,
        "publication_date": publication_date.isoformat() if publication_date else None,
        "source_event_ref": event_ref,
    }
    return values[field]


def _report_title(opportunity: Opportunity) -> str:
    if not opportunity.publicly_accessible:
        return f"Lead privado de {opportunity.source_platform}: {opportunity.service_requested}"
    return opportunity.title


def _status_for(opportunity_id: str, records: tuple[OpportunityRecord, ...]) -> str:
    return next(
        record.status.value
        for record in records
        if record.opportunity.opportunity_id == opportunity_id
    )


def _record_for(
    opportunity_id: str, records: tuple[OpportunityRecord, ...]
) -> OpportunityRecord:
    return next(
        record
        for record in records
        if record.opportunity.opportunity_id == opportunity_id
    )


def record_has_possible_duplicate(
    opportunity_id: str, records: tuple[OpportunityRecord, ...]
) -> bool:
    return bool(_record_for(opportunity_id, records).possible_duplicate_ids)


def _observed_evidence_count(opportunity: Opportunity) -> int:
    return sum(
        1
        for evidence in opportunity.evidence
        if evidence.kind is EvidenceKind.OBSERVED
        and evidence.confidence is not None
        and evidence.confidence >= 0.7
    )


def _yes_no(value: bool | None) -> str:
    return "sí" if value is True else "no" if value is False else "desconocido"


def _expiration_condition(opportunity: Opportunity, as_of: date) -> str:
    if opportunity.procurement_status in {
        ProcurementStatus.CLOSED_SOLICITATION,
        ProcurementStatus.AWARD_NOTICE,
    }:
        return "cerrada o adjudicada según el estado oficial"
    if opportunity.official_deadline is not None:
        return f"plazo oficial {opportunity.official_deadline.isoformat()}"
    if opportunity.is_open is False:
        return "la fuente indica que la solicitud está cerrada"
    if opportunity.publication_date is None:
        return "fecha de publicación desconocida; requiere revalidación"
    age_days = (as_of - opportunity.publication_date).days
    if age_days < 0:
        return "la fecha de publicación está en el futuro; requiere validación"
    maximum_days = 90 if opportunity.ongoing_need else 30
    return f"revalidar solicitud de {age_days} días; expira tras {maximum_days} días sin confirmación"


def _text_value(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{key} must be a non-blank string")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract("optional text must be a non-blank string or None")
    return value.strip()


def _bool(
    payload: Mapping[str, object], key: str, *, default: bool | None = None
) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise InvalidLiveContract(f"{key} must be boolean")
    return value


def _optional_bool(value: object, field: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise InvalidLiveContract(f"{field} must be boolean or None")
    return value


def _optional_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidLiveContract(f"{field} must be a non-negative integer or None")
    return value


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise InvalidLiveContract("confidence must be numeric or None")
    return float(value)


def _date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise InvalidLiveContract("date values must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise InvalidLiveContract("date values must use YYYY-MM-DD") from error


def _datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise InvalidLiveContract("datetime values must be ISO-8601 strings")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidLiveContract("datetime values must be ISO-8601 strings") from error
    if parsed.tzinfo is None:
        raise InvalidLiveContract("datetime values must include a timezone")
    return parsed.astimezone(timezone.utc)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) and not isinstance(value, tuple):
        raise InvalidLiveContract("expected an array of strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise InvalidLiveContract("expected non-blank strings")
    return tuple(item.strip() for item in value)
