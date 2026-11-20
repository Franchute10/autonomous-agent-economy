"""Single-tenant lead review pilot; not a production tenant interface.

This pilot does not crawl sites or log in to provider accounts. It reports the
configured state of reviewed sources and accepts manually captured, redacted
source evidence for preview through the existing Opportunity Inbox contract.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, unquote, urlsplit, urlunsplit

from aeos.application.live.opportunity_inbox import import_record
from aeos.live.adapters.opportunity_inbox import LocalOpportunityInbox
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.url_policy import (
    safe_text_for_report,
    safe_url_for_report,
    sanitize_report_data,
)
from aeos.live.domain.opportunity_inbox import (
    DemandType,
    DuplicateMatchType,
    OpportunityAssessment,
    OpportunityPreviewAssessment,
    OpportunityRecord,
    PermissionBasis,
    SourceProvenance,
    duplicate_match_evidence,
    is_reserved_example_source_url,
    possible_duplicate_candidate,
    score_opportunity_preview,
)
from aeos.live.domain.profile import BusinessProfile, parse_business_profile_document
from aeos.live.domain.vertical import vertical_profile_for


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FEASIBILITY = ROOT / "examples/live/real_lead_pilot/source_feasibility.json"
DEFAULT_PROFILE = (
    ROOT / "examples/live/business_profiles/fictional_cleaning_company.json"
)
MAX_CANDIDATE_FILE_BYTES = 1_000_000
MAX_CANDIDATES = 50
MAX_REPORT_TEXT = 600

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\w)"
)
_HANDLE_RE = re.compile(r"(?<![\w/])@[A-Za-z0-9_.-]{2,}")
_ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+[\w.#'-]+(?:\s+[\w.#'-]+){0,4}\s+"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|"
    r"Court|Ct|Highway|Hwy|Way)\b",
    re.IGNORECASE,
)
_PERSON_LABEL_RE = re.compile(
    r"\b(?:contact|posted by|author|buyer|requester|owner|poc)\s*[:=-]?\s+"
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}",
    re.IGNORECASE,
)
_ALLOWED_EVIDENCE_FIELDS = frozenset(
    {
        "city",
        "state",
        "service_requested",
        "explicit_intent",
        "open_status",
        "response_method",
        "publication_date",
        "procurement_status",
        "procurement_scope",
        "eligibility_reviewed",
        "expected_jobs_per_day",
        "solicitation_id",
        "issuing_organization",
        "contract_duration",
        "required_insurance",
    }
)
_ALLOWED_ACCESS_METHODS = frozenset(
    {
        "PUBLIC_PAGE_MANUAL",
        "OFFICIAL_NOTICE_MANUAL",
        "AUTHORIZED_ACCOUNT",
        "OFFICIAL_WEBHOOK",
        "OFFICIAL_API",
        "OWNER_PROVIDED",
    }
)


def redact_personal_data(value: str) -> str:
    """Remove common personal contact details before text enters a report."""

    redacted = _EMAIL_RE.sub("[redacted email]", value)
    redacted = _PHONE_RE.sub("[redacted phone]", redacted)
    redacted = _HANDLE_RE.sub("[redacted handle]", redacted)
    redacted = _ADDRESS_RE.sub("[redacted address]", redacted)
    redacted = _PERSON_LABEL_RE.sub("[redacted contact]", redacted)
    return redacted[:MAX_REPORT_TEXT]


def _contains_personal_data(value: str) -> bool:
    decoded = unquote(value)
    return any(
        pattern.search(decoded)
        for pattern in (_EMAIL_RE, _PHONE_RE, _HANDLE_RE, _ADDRESS_RE)
    )


def _safe_source_url(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidLiveContract("source_url must be text")
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise InvalidLiveContract("source_url must be an absolute HTTP(S) URL")
    if (
        parts.username
        or parts.password
        or is_reserved_example_source_url(value.strip())
        or _contains_personal_data(unquote(parts.path))
    ):
        raise InvalidLiveContract(
            "source_url must identify a non-reserved source and contain no credentials or personal contact data"
        )
    safe_query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not re.search(
            r"email|phone|mobile|token|auth|session|credential|handle|api.?key|secret|signature",
            key,
            re.I,
        )
        and not _contains_personal_data(item)
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(safe_query), "")
    )


def _safe_capture(
    payload: Mapping[str, object],
    *,
    captured_at: datetime,
    allowed_platforms: frozenset[str],
) -> dict[str, object]:
    """Keep only normalized contract fields; omit free-form source excerpts."""

    safe = dict(payload)
    if safe.get("template_only") is True:
        raise InvalidLiveContract(
            "template-only evidence cannot be reviewed or imported"
        )
    source_platform = _required_text(safe, "source_platform")
    if source_platform.casefold() not in allowed_platforms:
        raise InvalidLiveContract(
            "source_platform must match a reviewed source in the feasibility matrix"
        )
    service = _required_text(safe, "service_requested")
    city_value = safe.get("city")
    city = city_value.strip() if isinstance(city_value, str) else None
    state_value = safe.get("state")
    state = state_value.strip() if isinstance(state_value, str) else None
    for field_name, value in (("service_requested", service), ("city", city or "")):
        if _contains_personal_data(value):
            raise InvalidLiveContract(f"{field_name} contains personal contact data")

    public = safe.get("publicly_accessible") is True
    account_authorized = safe.get("account_holder_authorized") is True
    basis_value = safe.get("permission_basis")
    try:
        basis = PermissionBasis(str(basis_value))
    except ValueError as error:
        raise InvalidLiveContract("permission_basis is invalid") from error

    source_url = _safe_source_url(safe.get("source_url"))
    source_event_ref_value = safe.get("source_event_ref")
    source_event_ref = (
        source_event_ref_value.strip()
        if isinstance(source_event_ref_value, str) and source_event_ref_value.strip()
        else None
    )
    if source_event_ref and _contains_personal_data(source_event_ref):
        raise InvalidLiveContract(
            "source_event_ref must be an opaque non-contact reference"
        )
    try:
        demand_type = DemandType(str(safe.get("demand_type")))
    except ValueError as error:
        raise InvalidLiveContract("demand_type is invalid") from error
    solicitation_id_value = safe.get("solicitation_id")
    solicitation_id = (
        solicitation_id_value.strip()
        if isinstance(solicitation_id_value, str)
        else None
    )
    if solicitation_id and (
        demand_type is not DemandType.PUBLIC_PROCUREMENT
        or not public
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,79}", solicitation_id)
        or _contains_personal_data(solicitation_id)
    ):
        raise InvalidLiveContract(
            "solicitation_id is allowed only as an opaque public procurement identifier"
        )
    identity = (
        source_url or source_event_ref or f"{source_platform}|{captured_at.isoformat()}"
    )
    opportunity_id = (
        "pilot-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    )

    if safe.get("procurement_scope") is not None:
        safe["procurement_scope"] = redact_personal_data(str(safe["procurement_scope"]))
    requirements = safe.get("eligibility_requirements", [])
    if isinstance(requirements, list):
        safe["eligibility_requirements"] = [
            redact_personal_data(str(item)) for item in requirements
        ]

    raw_evidence = safe.get("evidence")
    if not isinstance(raw_evidence, list):
        raise InvalidLiveContract("evidence must be an array")
    safe_response = (
        "Ruta nativa de la fuente; datos de contacto no conservados."
        if public
        else "Responder dentro de la plataforma autorizada"
    )
    safe["response_method"] = safe_response
    expected_values: dict[str, object] = {
        "city": city,
        "state": state,
        "service_requested": service,
        "explicit_intent": safe.get("explicit_intent"),
        "open_status": safe.get("is_open"),
        "response_method": safe_response,
        "publication_date": safe.get("publication_date"),
        "procurement_status": safe.get("procurement_status"),
        "procurement_scope": safe.get("procurement_scope"),
        "eligibility_reviewed": safe.get("eligibility_reviewed"),
        "expected_jobs_per_day": safe.get("expected_jobs_per_day"),
        "solicitation_id": solicitation_id,
        "issuing_organization": safe.get("issuing_organization"),
        "contract_duration": safe.get("contract_duration"),
        "required_insurance": safe.get("required_insurance"),
    }
    for field in ("issuing_organization", "contract_duration", "required_insurance"):
        expected_value = expected_values[field]
        if isinstance(expected_value, str):
            expected_values[field] = redact_personal_data(expected_value)
    evidence: list[dict[str, object]] = []
    for item in raw_evidence:
        if not isinstance(item, dict):
            raise InvalidLiveContract("each evidence entry must be an object")
        evidence_field = item.get("field")
        if (
            not isinstance(evidence_field, str)
            or evidence_field not in _ALLOWED_EVIDENCE_FIELDS
        ):
            continue
        evidence_value = expected_values.get(evidence_field)
        if evidence_value is None:
            continue
        entry = dict(item)
        entry["evidence_id"] = f"{opportunity_id}-{evidence_field}"
        entry["source_name"] = source_platform
        entry["value"] = evidence_value
        entry["kind"] = "REPORTED"
        entry["excerpt"] = (
            f"Declaración manual de {evidence_field}; requiere verificación en la fuente."
        )
        entry.pop("assumptions", None)
        evidence.append(entry)

    safe["opportunity_id"] = opportunity_id
    safe["source_url"] = source_url
    safe["source_event_ref"] = source_event_ref
    safe["title"] = "Service request"
    safe["summary"] = "Public source evidence captured."
    access_method = str(safe.get("access_method", ""))
    if access_method not in _ALLOWED_ACCESS_METHODS:
        access_method = "OWNER_PROVIDED" if safe.get("owner_provided") is True else ""
    safe["source_terms_note"] = (
        f"Captura manual; método declarado: {access_method or 'no indicado'}; "
        f"base declarada: {basis.value}. Texto original omitido."
    )
    observation_value = safe.get("observed_at")
    if observation_value is None:
        observed_at = captured_at
    elif isinstance(observation_value, str):
        try:
            observed_at = datetime.fromisoformat(
                observation_value.replace("Z", "+00:00")
            )
        except ValueError as error:
            raise InvalidLiveContract("observed_at must be an ISO datetime") from error
        if observed_at.tzinfo is None:
            raise InvalidLiveContract("observed_at must include a timezone")
    else:
        raise InvalidLiveContract("observed_at must be an ISO datetime")
    safe["discovered_at"] = observed_at.isoformat()
    safe["limitations"] = [
        "El contenido original no se almacena; solo se conservan datos mínimos de la oportunidad."
    ]
    safe["stable_request_id"] = solicitation_id
    safe["evidence"] = evidence

    if public and source_url is None:
        raise InvalidLiveContract("public evidence requires source_url")
    if not public and (not account_authorized or source_event_ref is None):
        raise InvalidLiveContract(
            "private evidence requires account-holder authorization and an event reference"
        )
    if not safe.get("business_authorized"):
        safe["business_authorized"] = False
        safe["permission_basis"] = PermissionBasis.NOT_APPROVED.value
    elif basis is PermissionBasis.NOT_APPROVED:
        raise InvalidLiveContract("approved evidence cannot use NOT_APPROVED")
    return safe


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{key} is required")
    return value.strip()


def _load_candidate_file(
    path: Path,
    *,
    captured_at: datetime,
    allowed_platforms: frozenset[str],
) -> tuple[list[OpportunityRecord], list[dict[str, object]]]:
    if path.stat().st_size > MAX_CANDIDATE_FILE_BYTES:
        raise InvalidLiveContract("candidate file exceeds the 1 MB limit")
    data = json.loads(path.read_text(encoding="utf-8"))
    candidates = data.get("candidates") if isinstance(data, dict) else data
    if not isinstance(candidates, list):
        raise InvalidLiveContract("candidate file must contain a list")
    if len(candidates) > MAX_CANDIDATES:
        raise InvalidLiveContract(f"candidate file exceeds {MAX_CANDIDATES} candidates")

    records: list[OpportunityRecord] = []
    rejected: list[dict[str, object]] = []
    for index, candidate in enumerate(candidates, start=1):
        candidate_id = f"candidate-{index}"
        if not isinstance(candidate, dict):
            rejected.append(
                {
                    "candidate": candidate_id,
                    "reason": "El registro no es un objeto JSON.",
                }
            )
            continue
        if candidate.get("source_accessible") is False:
            rejected.append(
                {
                    "candidate": candidate_id,
                    "reason": "La fuente no estaba accesible; no se creó una oportunidad ni se contó como demanda vacía.",
                }
            )
            continue
        try:
            safe = _safe_capture(
                candidate,
                captured_at=captured_at,
                allowed_platforms=allowed_platforms,
            )
            record = import_record(safe, imported_at=captured_at)
        except (InvalidLiveContract, TypeError, ValueError) as error:
            rejected.append(
                {"candidate": candidate_id, "reason": redact_personal_data(str(error))}
            )
            continue
        records.append(record)
    return records, rejected


def _duplicate_preview(
    incoming: OpportunityRecord, existing: Sequence[OpportunityRecord]
) -> dict[str, str | None]:
    exact: list[str] = []
    strong: list[str] = []
    possible: list[str] = []
    for stored in existing:
        if stored.status.value == "DUPLICATE":
            continue
        match, _ = duplicate_match_evidence(incoming.opportunity, stored.opportunity)
        if match is DuplicateMatchType.EXACT:
            exact.append(stored.opportunity.opportunity_id)
        elif match is DuplicateMatchType.STRONG:
            strong.append(stored.opportunity.opportunity_id)
        elif possible_duplicate_candidate(incoming.opportunity, stored.opportunity):
            possible.append(stored.opportunity.opportunity_id)
    if len(exact) == 1:
        return {"result": "DUPLICATE", "matched_id": exact[0]}
    if len(exact) > 1 or len(strong) > 1 or possible or (strong and exact):
        matches = exact + strong + possible
        return {"result": "NEEDS_REVIEW", "matched_id": ",".join(matches)}
    if len(strong) == 1:
        return {"result": "DUPLICATE", "matched_id": strong[0]}
    return {"result": "NEW", "matched_id": None}


def _classify_records(
    records: Sequence[OpportunityRecord],
    stored_records: Sequence[OpportunityRecord],
    *,
    as_of: date,
    business_profile: BusinessProfile,
) -> list[dict[str, object]]:
    from aeos.live.domain.opportunity_inbox import classify_opportunity

    seen = list(stored_records)
    output: list[dict[str, object]] = []
    for record in records:
        synthetic_preview = (
            record.opportunity.source_provenance is SourceProvenance.SYNTHETIC
        )
        assessment: OpportunityAssessment | OpportunityPreviewAssessment
        if synthetic_preview:
            assessment = score_opportunity_preview(
                record.opportunity,
                as_of=as_of,
                organization_profile=business_profile,
            )
        else:
            assessment = classify_opportunity(
                record.opportunity,
                as_of=as_of,
                organization_profile=business_profile,
            )
        duplicate = _duplicate_preview(record, seen)
        opportunity = record.opportunity
        evidence_values = {item.field: item.value for item in opportunity.evidence}
        output.append(
            {
                "opportunity_id": opportunity.opportunity_id,
                "classification": assessment.classification.value,
                "source_provenance": opportunity.source_provenance.value,
                "evaluation_mode": (
                    "SYNTHETIC_PREVIEW" if synthetic_preview else "SOURCE_REVIEW"
                ),
                "demand_type": opportunity.demand_type.value,
                "source_platform": opportunity.source_platform,
                "publication_date": opportunity.publication_date.isoformat()
                if opportunity.publication_date
                else None,
                "official_deadline": opportunity.official_deadline.isoformat()
                if opportunity.official_deadline
                else None,
                "observed_at": opportunity.discovered_at.isoformat(),
                "retrieved_at": next(
                    (
                        item.retrieved_at.isoformat()
                        for item in opportunity.evidence
                        if item.retrieved_at is not None
                    ),
                    None,
                ),
                "city": opportunity.city,
                "state": opportunity.state,
                "service_requested": opportunity.service_requested,
                "current_request_status": (
                    opportunity.procurement_status.value
                    if opportunity.procurement_status
                    else "OPEN"
                    if opportunity.is_open is True
                    else "CLOSED"
                    if opportunity.is_open is False
                    else "UNKNOWN"
                ),
                "solicitation_id": opportunity.stable_request_id,
                "issuing_organization": evidence_values.get("issuing_organization"),
                "procurement_scope": opportunity.procurement_scope,
                "eligibility_requirements": list(opportunity.eligibility_requirements),
                "contract_duration": evidence_values.get("contract_duration"),
                "required_insurance": evidence_values.get("required_insurance"),
                "why_it_qualifies": assessment.priority_reason_es,
                "reason_codes": list(assessment.score_components),
                "capacity_fit": assessment.capacity_note_es,
                "capacity_review_required": assessment.capacity_review_required,
                "evidence_url": safe_url_for_report(opportunity.source_url),
                "permission_basis": opportunity.permission_basis.value,
                "limitations": list(opportunity.limitations),
                "duplicate_preview": duplicate,
            }
        )
        seen.append(record)
    return output


def _serializable_candidate(item: Mapping[str, object]) -> dict[str, object]:
    converted = dict(item)
    components = converted.get("reason_codes")
    if isinstance(components, list):
        converted["reason_codes"] = [
            {
                "key": component.key,
                "score": component.score,
                "maximum": component.maximum,
                "explanation_es": component.explanation_es,
            }
            for component in components
        ]
    return converted


def _provider_diagnostics(feasibility: Mapping[str, object]) -> dict[str, object]:
    sources = feasibility.get("sources", [])
    entries: list[dict[str, object]] = []
    for source in sources if isinstance(sources, list) else []:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id", "unknown"))
        status = str(source.get("pilot_status", "MANUAL_ONLY"))
        env_name = source.get("configuration_env")
        extra_env_names = source.get("additional_configuration_env", [])
        env_names = [str(env_name)] if env_name else []
        if isinstance(extra_env_names, list):
            env_names.extend(item for item in extra_env_names if isinstance(item, str))
        configured = bool(env_names) and all(os.environ.get(name) for name in env_names)
        if status == "REQUIRES_API_CREDENTIALS":
            status = (
                "CONNECTOR_NOT_IMPLEMENTED" if configured else "PROVIDER_NOT_CONFIGURED"
            )
        entries.append(
            {
                "source_id": source_id,
                "source_name": source.get("name"),
                "source_name_es": source.get("name_es", source.get("name")),
                "status": status,
                "configured": configured,
                "configuration_env": env_name,
                "configuration_envs": env_names,
                "request_attempted": False,
                "request_count": 0,
                "retry_count": 0,
                "last_result": source.get("pilot_note"),
                "last_result_es": source.get("pilot_note_es", source.get("pilot_note")),
                "market_checks": source.get("market_checks", []),
            }
        )
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read-only preview",
        "network_requests": 0,
        "retries": 0,
        "sources": entries,
    }


def _profile_markets(profile: BusinessProfile) -> tuple[str, ...]:
    configured = (
        profile.owner_confirmed_service_areas or profile.additional_service_areas
    )
    areas = configured or (profile.city,)
    return tuple(dict.fromkeys(item.strip() for item in areas if item.strip()))


def _profile_services(profile: BusinessProfile) -> tuple[str, ...]:
    services = (*profile.primary_services, *(profile.secondary_services or ()))
    return tuple(dict.fromkeys(item.strip() for item in services if item.strip()))


def _vertical_label(profile: BusinessProfile) -> str:
    vertical = vertical_profile_for(profile.vertical)
    return vertical.canonical_industry_name if vertical else profile.industry


def _profile_storage_directory(profile: BusinessProfile) -> Path:
    if profile.organization_id is not None:
        identity = profile.organization_id.value
    elif profile.is_fictional_example:
        identity = f"synthetic-{profile.business_name}"
    else:
        raise InvalidLiveContract(
            "organization_id is required when using default pilot storage paths"
        )
    slug = re.sub(r"[^a-z0-9]+", "-", identity.casefold()).strip("-")
    return ROOT / "artifacts/live/profiles" / (slug or "unidentified-profile")


def _query_plan(
    diagnostics: Mapping[str, object], business_profile: BusinessProfile
) -> list[dict[str, object]]:
    raw_sources = diagnostics.get("sources")
    sources = raw_sources if isinstance(raw_sources, list) else []
    statuses = {
        str(item.get("source_id")): str(item.get("status"))
        for item in sources
        if isinstance(item, dict)
    }
    source_ids = tuple(statuses)
    rows: list[dict[str, object]] = []
    for market in _profile_markets(business_profile):
        for service in _profile_services(business_profile):
            rows.append(
                {
                    "city": market,
                    "state": business_profile.state_region,
                    "vertical": business_profile.vertical,
                    "service": service,
                    "providers": [
                        {
                            "source_id": source,
                            "status": statuses.get(source, "NOT_CHECKED"),
                        }
                        for source in source_ids
                    ],
                    "search_status": "NOT_EXECUTED",
                    "reason": "No configured, permitted live discovery connector is available for this profile-scoped query.",
                }
            )
    return rows


def _render_report(
    candidates: Sequence[Mapping[str, object]],
    rejected: Sequence[Mapping[str, object]],
    diagnostics: Mapping[str, object],
    *,
    as_of: date,
    imported: bool,
    business_profile: BusinessProfile,
) -> str:
    counts = Counter(str(item.get("classification")) for item in candidates)
    mode = "importación confirmada" if imported else "vista previa; sin persistencia"
    status_labels = {
        "FIXTURE_ONLY": "solo pruebas",
        "MANUAL_ONLY": "solo manual",
        "PROVIDER_NOT_CONFIGURED": "proveedor sin configurar",
        "CONNECTOR_NOT_IMPLEMENTED": "conector pendiente",
        "PROVIDER_UNAVAILABLE": "proveedor no disponible",
        "NOT_SUPPORTED": "no admitido",
    }
    lines = [
        f"# Informe de oportunidades — {business_profile.business_name} ({_vertical_label(business_profile)})",
        "",
        f"Fecha de corte: {as_of.isoformat()} · Modo: {mode}. Mercados configurados: {', '.join(_profile_markets(business_profile)) or 'sin confirmar'}.",
        "",
        "## Resultado del piloto",
        "",
        "No se ejecutaron consultas de red: los proveedores permitidos no tienen un conector configurado en este repositorio. Esto **no** significa que el mercado carezca de demanda.",
        f"Candidatos recibidos para revisión: {len(candidates)}. Rechazados: {len(rejected)}.",
        f"Clasificación: oportunidades prioritarias {counts['HOT']}, prometedoras {counts['WARM']}, de baja prioridad {counts['COLD']}, vencidas {counts['EXPIRED']}, con evidencia insuficiente {counts['INSUFFICIENT_EVIDENCE']}.",
        "",
        "## Oportunidades directas",
        "",
    ]
    direct = [
        item
        for item in candidates
        if item.get("demand_type")
        in {DemandType.DIRECT_CUSTOMER_DEMAND.value, DemandType.MARKETPLACE_LEAD.value}
    ]
    if not direct:
        lines.append(
            "No se recibieron solicitudes directas verificables en esta ejecución."
        )
    for item in direct:
        lines.extend(
            [
                f"### {item.get('source_platform')} · {item.get('classification')}",
                f"- Procedencia de fuente: {item.get('source_provenance', 'UNKNOWN')}.",
                f"- Publicación: {item.get('publication_date') or 'sin fecha verificada'}; ubicación: {item.get('city') or 'desconocida'}, {item.get('state') or 'desconocido'}. ",
                f"- Servicio: {item.get('service_requested')}; estado: {item.get('current_request_status')}. ",
                f"- Evaluación: {item.get('why_it_qualifies')}",
                f"- Capacidad: {item.get('capacity_fit')}",
                f"- Evidencia: {item.get('evidence_url') or 'referencia privada autorizada'}",
                f"- Duplicados: {item.get('duplicate_preview')}",
                "",
            ]
        )
    potential = [
        item
        for item in candidates
        if item.get("demand_type") == DemandType.POTENTIAL_B2B_BUYER.value
    ]
    lines.extend(["## Organizaciones compradoras potenciales", ""])
    lines.append(f"Hallazgos separados de solicitudes directas: {len(potential)}.")
    for item in potential:
        lines.append(
            f"- {item.get('source_platform')} · {item.get('city') or 'ubicación desconocida'}: {item.get('service_requested')}; {item.get('classification')}. {item.get('why_it_qualifies')} Evidencia: {item.get('evidence_url') or 'referencia privada autorizada'}."
        )
    procurement = [
        item
        for item in candidates
        if item.get("demand_type") == DemandType.PUBLIC_PROCUREMENT.value
    ]
    lines.extend(
        [
            "",
            "## Contratación pública e histórica",
            "",
            f"Avisos de contratación pública capturados: {len(procurement)}.",
            "Los avisos abiertos con alcance o elegibilidad desconocidos conservan la clasificación del motor existente y requieren revisión; no se promueven automáticamente a prioridad alta.",
        ]
    )
    for item in procurement:
        lines.extend(
            [
                f"### {item.get('source_platform')} · {item.get('classification')}",
                f"- ID de solicitud: {item.get('solicitation_id') or 'no publicado'}; entidad emisora: {item.get('issuing_organization') or 'no verificada'}.",
                f"- Publicación: {item.get('publication_date') or 'sin fecha verificada'}; vence: {item.get('official_deadline') or 'sin fecha verificada'}; estado: {item.get('current_request_status')}.",
                f"- Ubicación: {item.get('city') or 'desconocida'}, {item.get('state') or 'desconocido'}; servicio: {item.get('service_requested')}.",
                f"- Alcance: {item.get('procurement_scope') or 'no verificado'}; duración: {item.get('contract_duration') or 'no publicada'}.",
                f"- Elegibilidad/seguro: {item.get('eligibility_requirements')}; {item.get('required_insurance') or 'requisitos de seguro no publicados'}.",
                f"- Capacidad: {item.get('capacity_fit')}; fuente: {item.get('evidence_url') or 'no disponible'}.",
                "",
            ]
        )
    historical_requests = [
        item
        for item in candidates
        if item.get("classification") == "EXPIRED"
        and item.get("demand_type") != DemandType.PUBLIC_PROCUREMENT.value
    ]
    unverified = [
        item
        for item in candidates
        if item.get("classification") == "INSUFFICIENT_EVIDENCE"
    ]
    lines.extend(
        [
            "",
            "## Solicitudes históricas",
            "",
            f"Solicitudes directas o de marketplace vencidas: {len(historical_requests)}.",
            "",
            "## Candidatos sin verificación suficiente",
            "",
            f"Candidatos que requieren evidencia o permiso adicional: {len(unverified)}.",
        ]
    )
    lines.extend(["", "## Fuentes inaccesibles y configuración", ""])
    source_items = diagnostics.get("sources", [])
    for item in source_items if isinstance(source_items, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('source_name_es', item.get('source_name'))}: "
                f"**{status_labels.get(str(item.get('status')), item.get('status'))}**; "
                f"{item.get('last_result_es', item.get('last_result'))}"
            )
    lines.extend(
        [
            "",
            "## Candidatos rechazados",
            "",
        ]
    )
    if not rejected:
        lines.append("Ninguno recibido.")
    else:
        for item in rejected:
            lines.append(f"- {item.get('candidate')}: {item.get('reason')}")
    lines.extend(
        [
            "",
            "## Capacidad operativa del perfil",
            "",
            f"Capacidad diaria base reportada: {business_profile.base_capacity_jobs_per_day if business_profile.base_capacity_jobs_per_day is not None else 'no configurada'}. Capacidad ampliada: {business_profile.expanded_capacity_jobs_per_day if business_profile.expanded_capacity_jobs_per_day is not None else 'no configurada'}. Dependencia declarada: {business_profile.capacity_expansion_dependency or 'no configurada'}. Los datos del perfil son declarados y no se trataron como verificación independiente.",
            "",
            "## Acciones sugeridas",
            "",
            "1. Revisar el informe de factibilidad de fuentes.",
            "2. Confirmar que cada proveedor permita el uso comercial previsto y que exista un canal autorizado antes de configurar una integración.",
            f"3. Revisar manualmente las fuentes pertinentes para {', '.join(_profile_markets(business_profile)) or 'los mercados confirmados'}; registrar una oportunidad solo después de revisar permiso, fecha, servicio y estado.",
            "",
            "AEOS no envió mensajes, pujas, formularios ni pagos.",
        ]
    )
    return safe_text_for_report("\n".join(lines) + "\n")


def _render_source_feasibility(
    feasibility: Mapping[str, object], business_profile: BusinessProfile
) -> str:
    feasibility_labels = {
        "REQUIRES_ACCOUNT_AUTHORIZATION": "requiere autorización de la cuenta",
        "REQUIRES_API_CREDENTIALS": "requiere credenciales de API",
        "MANUAL_ONLY": "solo revisión manual",
        "NOT_SUPPORTED": "no compatible con este piloto",
    }
    status_labels = {
        "FIXTURE_ONLY": "solo pruebas",
        "MANUAL_ONLY": "solo manual",
        "PROVIDER_NOT_CONFIGURED": "proveedor sin configurar",
        "CONNECTOR_NOT_IMPLEMENTED": "conector pendiente",
        "PROVIDER_UNAVAILABLE": "proveedor no disponible",
        "NOT_SUPPORTED": "no admitido",
    }
    lines = [
        "# Factibilidad de fuentes de adquisición",
        "",
        f"Fecha de revisión: {feasibility.get('as_of', 'sin fecha')}. Mercados del perfil: {', '.join(_profile_markets(business_profile)) or 'sin confirmar'}; región: {business_profile.state_region}.",
        "",
        "Las categorías separan acceso documentado de integración realmente disponible. La presencia de una API no implica que autorice el uso comercial o que haya credenciales configuradas.",
        "",
    ]
    sources = feasibility.get("sources", [])
    if not isinstance(sources, list):
        return safe_text_for_report("\n".join(lines) + "\n")
    for source in sources:
        if not isinstance(source, dict):
            continue
        refs = source.get("official_references", [])
        reference_links = (
            ", ".join(
                f"[fuente oficial {index + 1}]({url})"
                for index, url in enumerate(refs)
                if isinstance(url, str)
            )
            if isinstance(refs, list)
            else ""
        )
        lines.extend(
            [
                f"## {source.get('name_es', source.get('name'))} — {feasibility_labels.get(str(source.get('feasibility_class')), source.get('feasibility_class'))}",
                "",
                f"- Evaluación: {source.get('summary_es', 'Resumen no disponible en español.')}",
                f"- Clasificación: {feasibility_labels.get(str(source.get('feasibility_class')), source.get('feasibility_class'))}; estado: {status_labels.get(str(source.get('pilot_status')), source.get('pilot_status'))}",
                f"- Retención de datos: {source.get('data_retention_es', source.get('data_retention'))}",
                f"- Nota del piloto: {source.get('pilot_note_es', source.get('pilot_note'))}",
                f"- Integración real disponible ahora: {'sí' if source.get('integration_possible_now') else 'no'}.",
                f"- Referencias: {reference_links or 'sin referencia oficial registrada'}",
                "",
            ]
        )
    return safe_text_for_report("\n".join(lines) + "\n")


def run_pilot(
    *,
    candidate_file: Path | None,
    output_dir: Path | None = None,
    store_path: Path | None = None,
    feasibility_path: Path,
    profile_path: Path = DEFAULT_PROFILE,
    as_of: date,
    confirm_import: bool,
) -> dict[str, object]:
    profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(profile_payload, dict):
        raise InvalidLiveContract("business profile file must contain a JSON object")
    business_profile = parse_business_profile_document(profile_payload)
    feasibility = json.loads(feasibility_path.read_text(encoding="utf-8"))
    if not isinstance(feasibility, dict):
        raise InvalidLiveContract("source feasibility file must contain a JSON object")
    if output_dir is None or store_path is None:
        profile_directory = _profile_storage_directory(business_profile)
        output_dir = output_dir or profile_directory / "reports"
        store_path = store_path or profile_directory / "opportunities.json"
    if confirm_import and candidate_file is None:
        raise InvalidLiveContract("--confirm-import requires --candidate-file")

    captured_at = datetime.now(timezone.utc)
    sources = feasibility.get("sources")
    allowed_platforms = (
        frozenset(
            str(item.get("name", "")).casefold()
            for item in sources
            if isinstance(item, dict) and item.get("name")
        )
        if isinstance(sources, list)
        else frozenset()
    )
    new_records: list[OpportunityRecord] = []
    rejected: list[dict[str, object]] = []
    if candidate_file is not None:
        new_records, rejected = _load_candidate_file(
            candidate_file,
            captured_at=captured_at,
            allowed_platforms=allowed_platforms,
        )

    inbox = LocalOpportunityInbox(store_path)
    stored_records = inbox.list_records()
    candidates = [
        _serializable_candidate(item)
        for item in _classify_records(
            new_records,
            stored_records,
            as_of=as_of,
            business_profile=business_profile,
        )
    ]

    imported = False
    if confirm_import:
        for record, candidate in zip(new_records, candidates, strict=True):
            if not record.opportunity.business_authorized:
                rejected.append(
                    {
                        "candidate": record.opportunity.opportunity_id,
                        "reason": "La fuente no está autorizada para uso comercial; no se importó.",
                    }
                )
                continue
            try:
                saved, inserted = inbox.add(record)
            except InvalidLiveContract as error:
                rejected.append(
                    {
                        "candidate": record.opportunity.opportunity_id,
                        "reason": redact_personal_data(str(error)),
                    }
                )
                continue
            candidate["inbox_result"] = (
                "INSERTED" if inserted else "DUPLICATE_OR_LINKED"
            )
            candidate["inbox_record_id"] = saved.opportunity.opportunity_id
            imported = imported or inserted

    diagnostics = _provider_diagnostics(feasibility)
    report = _render_report(
        candidates,
        rejected,
        diagnostics,
        as_of=as_of,
        imported=imported,
        business_profile=business_profile,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "acquisition-report-es.md").write_text(report, encoding="utf-8")
    (output_dir / "source-feasibility-es.md").write_text(
        _render_source_feasibility(feasibility, business_profile), encoding="utf-8"
    )
    (output_dir / "source-feasibility.json").write_text(
        json.dumps(sanitize_report_data(feasibility), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "provider-diagnostics.json").write_text(
        json.dumps(sanitize_report_data(diagnostics), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "query-plan.json").write_text(
        json.dumps(
            sanitize_report_data(_query_plan(diagnostics, business_profile)),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "opportunities.json").write_text(
        json.dumps(sanitize_report_data(candidates), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "rejected-candidates.json").write_text(
        json.dumps(sanitize_report_data(rejected), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "candidate_count": len(candidates),
        "rejected_count": len(rejected),
        "imported": imported,
        "output_dir": str(output_dir),
        "diagnostics": diagnostics,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded business-profile opportunity preview using only configured, "
            "permitted sources and manually supplied source evidence."
        )
    )
    parser.add_argument("--candidate-file", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--feasibility", type=Path, default=DEFAULT_FEASIBILITY)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--as-of", type=_iso_date, default=date.today())
    parser.add_argument(
        "--confirm-import",
        action="store_true",
        help="Explicitly import authorized preview candidates into the Opportunity Inbox.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_pilot(
            candidate_file=args.candidate_file,
            output_dir=args.output_dir,
            store_path=args.store,
            feasibility_path=args.feasibility,
            profile_path=args.profile,
            as_of=args.as_of,
            confirm_import=args.confirm_import,
        )
    except (OSError, ValueError, InvalidLiveContract, json.JSONDecodeError) as error:
        print(f"real lead pilot error: {error}", file=sys.stderr)
        return 2
    print(
        f"Informe en español: {Path(str(result['output_dir'])) / 'acquisition-report-es.md'}"
    )
    print(
        f"Candidatos: {result['candidate_count']}; rechazados: {result['rejected_count']}; "
        f"importación persistente: {'sí' if result['imported'] else 'no'}."
    )
    print("Solicitudes de red: 0; mensajes, pujas y pagos: 0.")
    return 0


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error


if __name__ == "__main__":
    raise SystemExit(main())
