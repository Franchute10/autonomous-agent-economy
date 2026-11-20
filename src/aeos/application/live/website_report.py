"""Spanish-language website intelligence report serialization and rendering."""

from datetime import datetime
from collections.abc import Mapping
from typing import cast

from aeos.application.live.resolve_business_locations import MarketSelectionResolution
from aeos.live.domain.url_policy import safe_text_for_report, safe_url_for_report
from aeos.live.domain.evidence import SourceEvidence
from aeos.live.domain.location_candidate import (
    LocationCandidate,
    LocationType,
    ServiceCandidate,
)
from aeos.live.ports.website import WebsiteInspectionResult


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
        "source_url": safe_url_for_report(item.source_url),
        "supporting_text": safe_text_for_report(item.supporting_text),
        "evidence_classification": item.evidence_classification.value,
        "confidence": item.confidence,
        "verification_status": item.verification_status.value,
        "evidence_id": item.evidence_id,
    }


def _service_dict(item: ServiceCandidate) -> dict[str, object]:
    return {
        "service": item.service,
        "source_url": safe_url_for_report(item.source_url),
        "supporting_text": safe_text_for_report(item.supporting_text),
        "evidence_classification": item.evidence_classification.value,
        "confidence": item.confidence,
        "verification_status": item.verification_status.value,
        "evidence_id": item.evidence_id,
    }


def _evidence_dict(item: SourceEvidence) -> dict[str, object]:
    return {
        "evidence_id": item.evidence_id,
        "classification": item.kind.value,
        "subject": item.subject,
        "field": item.field,
        "value": safe_text_for_report(item.value)
        if isinstance(item.value, str)
        else item.value,
        "source_url": safe_url_for_report(item.source_url),
        "retrieved_at": item.retrieved_at.isoformat() if item.retrieved_at else None,
        "supporting_text": safe_text_for_report(item.excerpt) if item.excerpt else None,
        "confidence": item.confidence,
    }


def build_website_report(
    inspection: WebsiteInspectionResult | None,
    *,
    website_url: str,
    status: str,
    failure_category: str | None = None,
    failure_stage: str | None = None,
    selection: MarketSelectionResolution | None = None,
    market_discovery: dict[str, object] | None = None,
    selected_at: datetime | None = None,
) -> dict[str, object]:
    """Create a report that keeps extracted evidence and owner input distinct."""

    details = inspection.details if inspection is not None else None
    pages = inspection.pages if inspection is not None else ()
    evidence = inspection.evidence if inspection is not None else ()
    address_candidate = (
        next(
            (
                item
                for item in inspection.locations
                if item.location_type is LocationType.BUSINESS_ADDRESS
            ),
            None,
        )
        if inspection is not None
        else None
    )
    city_candidates = (
        [
            item
            for item in inspection.locations
            if item.location_type
            not in {
                LocationType.NEIGHBORHOOD_MENTION,
                LocationType.REGIONAL_SERVICE_AREA,
            }
        ]
        if inspection
        else []
    )
    missing: list[str] = []
    if inspection is None:
        missing.append("No evaluada: la inspección falló antes de recuperar páginas.")
    else:
        if not details or not details.business_name:
            missing.append("Nombre comercial estructurado o inequívoco")
        if not details or not details.phone:
            missing.append("Teléfono público del negocio")
        if not details or not details.email:
            missing.append("Correo electrónico público")
        if not details or not details.address:
            missing.append(
                "Dirección empresarial verificable y su función (registrada u operativa)"
            )
        if not city_candidates:
            missing.append("Ciudades o áreas de servicio identificables en el sitio")
        if not inspection.services:
            missing.append("Servicios detallados en el sitio")
    limitations = list(details.limitations) if details else []
    if failure_category:
        stage_description = f" en {failure_stage}" if failure_stage else ""
        limitations.append(
            f"No se pudieron recuperar páginas por la categoría {failure_category}{stage_description}."
        )
    candidate_dict = (
        [_location_dict(item) for item in inspection.locations] if inspection else []
    )
    service_dict = (
        [_service_dict(item) for item in inspection.services] if inspection else []
    )
    report: dict[str, object] = {
        "project": "AEOS-LIVE-002B1",
        "report_language": "es",
        "website_inspection": {
            "status": status,
            "failure_category": failure_category,
            "failure_stage": failure_stage,
            "requested_url": safe_url_for_report(website_url) or "[URL omitted]",
            "final_url": safe_url_for_report(details.final_url) if details else None,
            "inspected_at": details.inspected_at.isoformat() if details else None,
            "identificacion_del_negocio": {
                "nombre_comercial": details.business_name if details else None,
                "clasificacion": "OBSERVED"
                if details and details.business_name
                else None,
            },
            "paginas_revisadas": [
                {
                    "url": safe_url_for_report(page.url) or "[URL omitted]",
                    "http_status": page.status_code,
                    "title": safe_text_for_report(page.title) if page.title else None,
                    "meta_description": safe_text_for_report(page.meta_description)
                    if page.meta_description
                    else None,
                    "h1": [safe_text_for_report(item) for item in page.h1_headings],
                    "h2": [safe_text_for_report(item) for item in page.h2_headings],
                    "main_text": safe_text_for_report(page.main_text),
                    "link_texts": [
                        safe_text_for_report(item) for item in page.link_texts
                    ],
                    "link_urls": [
                        safe_url_for_report(item) or "[URL omitted]"
                        for item in page.link_urls
                    ],
                    "metodo_inspeccion": page.inspection_method,
                    "title_html": safe_text_for_report(page.title)
                    if page.title
                    else None,
                    "meta_description_html": (
                        safe_text_for_report(page.meta_description)
                        if page.meta_description
                        else None
                    ),
                    "h1_html": [
                        safe_text_for_report(item) for item in page.h1_headings
                    ],
                    "dom_renderizado": (
                        {
                            "status": page.rendered_dom_status,
                            "fields_observed": list(page.rendered_dom_fields_observed),
                            "error_category": page.rendered_dom_error,
                            "error_message": safe_text_for_report(
                                page.rendered_dom_error_message
                            )
                            if page.rendered_dom_error_message
                            else None,
                            "title": safe_text_for_report(page.rendered_title)
                            if page.rendered_title
                            else None,
                            "meta_description": safe_text_for_report(
                                page.rendered_meta_description
                            )
                            if page.rendered_meta_description
                            else None,
                            "h1": [
                                safe_text_for_report(item)
                                for item in page.rendered_h1_headings
                            ],
                            "h2": [
                                safe_text_for_report(item)
                                for item in page.rendered_h2_headings
                            ],
                            "link_texts": [
                                safe_text_for_report(item)
                                for item in page.rendered_link_texts
                            ],
                            "link_urls": [
                                safe_url_for_report(item) or "[URL omitted]"
                                for item in page.rendered_link_urls
                            ],
                        }
                        if page.inspection_method == "HTTP_AND_RENDERED_DOM"
                        else {
                            "status": "HTML_ONLY",
                            "fields_observed": [],
                            "error_category": page.rendered_dom_error,
                            "error_message": safe_text_for_report(
                                page.rendered_dom_error_message
                            )
                            if page.rendered_dom_error_message
                            else None,
                        }
                    ),
                    "dom_renderizado_error": page.rendered_dom_error,
                    "dom_renderizado_error_mensaje": safe_text_for_report(
                        page.rendered_dom_error_message
                    )
                    if page.rendered_dom_error_message
                    else None,
                }
                for page in pages
            ],
            "contacto": {
                "telefono": details.phone if details else None,
                "correo": details.email if details else None,
                "clasificacion": "OBSERVED"
                if details and (details.phone or details.email)
                else None,
            },
            "direccion_empresarial": {
                "direccion": details.address if details else None,
                "tipo": address_candidate.location_type.value
                if address_candidate
                else None,
                "clasificacion": address_candidate.evidence_classification.value
                if address_candidate
                else None,
                "nota": "Si el sitio publica una dirección, eso no confirma si está registrada o si es un punto operativo.",
            },
            "coordenadas_declaradas_en_datos_estructurados": {
                "latitud": details.latitude if details else None,
                "longitud": details.longitude if details else None,
                "nota": "Solo se muestran si el sitio las publica; no se calculan ni se usan como centro de búsqueda.",
            },
            "otros_datos_estructurados": {
                "tipos_schema": (
                    list(details.structured_data_types) if details else []
                ),
                "horario_publicado": list(details.opening_hours) if details else [],
                "perfiles_mencionados": [
                    safe_url_for_report(item) or "[URL omitted]"
                    for item in details.same_as
                ]
                if details
                else [],
            },
            "candidatos_geograficos": candidate_dict,
            "servicios_detectados": service_dict,
            "robots_txt": {
                "status": details.robots_status if details else "not_checked",
                "sitemaps": list(details.robots_sitemaps) if details else [],
                "crawl_restrictions": list(details.robots_restrictions)
                if details
                else [],
            },
            "sitemaps": [
                safe_url_for_report(item) or "[URL omitted]"
                for item in details.sitemap_urls
            ]
            if details
            else [],
            "evidencia_y_fuentes": [_evidence_dict(item) for item in evidence],
            "informacion_faltante": missing,
            "limitaciones": [
                safe_text_for_report(item) for item in dict.fromkeys(limitations)
            ],
            "siguiente_paso_recomendado": (
                "Revise los servicios y candidatos geográficos, corrija o agregue una ubicación y seleccione el mercado antes de iniciar la investigación."
                if status == "succeeded"
                else "La inspección no se completó; revise la categoría de fallo y vuelva a intentar cuando el sitio sea accesible."
            ),
        },
    }
    if selection is not None:
        scope = selection.scope
        report["seleccion_del_mercado"] = {
            "ciudad": scope.city,
            "estado": scope.state,
            "codigo_postal": scope.postal_code,
            "radio_solicitado": scope.research_radius,
            "unidad_radio": scope.radius_unit,
            "servicios_seleccionados": list(scope.selected_services),
            "seleccionado_en": scope.selected_at.isoformat(),
            "confirmado_por_propietario": scope.owner_confirmed,
            "candidato_original": _location_dict(selection.original_candidate)
            if selection.original_candidate
            else None,
            "ubicacion_agregada_o_corregida_por_usuario": selection.location_was_corrected_or_added,
            "servicios_agregados_por_usuario": list(selection.user_added_services),
            "evidencia_original_preservada": candidate_dict,
            "discovery_requires_explicit_confirmation": market_discovery is None,
        }
    if market_discovery is not None:
        report["investigacion_de_mercado"] = _sanitize_report_value(market_discovery)
    return report


def render_website_report_markdown(report: dict[str, object]) -> str:
    inspection = cast(dict[str, object], report["website_inspection"])
    identification = cast(dict[str, object], inspection["identificacion_del_negocio"])
    contact = cast(dict[str, object], inspection["contacto"])
    address = cast(dict[str, object], inspection["direccion_empresarial"])
    structured_data = cast(dict[str, object], inspection["otros_datos_estructurados"])
    failed = inspection["status"] != "succeeded"
    unknown = "No evaluado (la inspección no recuperó páginas)" if failed else None
    lines = [
        "# AEOS LIVE — Inteligencia del sitio web",
        "",
        f"Sitio: {inspection['requested_url']}",
        f"Estado de inspección: **{inspection['status']}**",
        f"Categoría de fallo: {inspection['failure_category'] or 'ninguna'}",
        f"Etapa de fallo: {inspection.get('failure_stage') or 'ninguna'}",
        "",
        "## A. Identificación del negocio",
        "",
        f"Nombre observado: {identification['nombre_comercial'] or unknown or 'No identificado'}",
        "",
        "## B. Estado de inspección",
        "",
        f"Páginas revisadas: {len(cast(list[object], inspection['paginas_revisadas']))}",
        "",
        "## C. Contacto extraído",
        "",
        f"- Teléfono: {contact['telefono'] or unknown or 'No encontrado'}",
        f"- Correo: {contact['correo'] or unknown or 'No encontrado'}",
        "",
        "## D. Dirección empresarial",
        "",
        f"- Dirección: {address['direccion'] or unknown or 'No encontrada'}",
        f"- Tipo: {address['tipo'] or unknown or 'Desconocido'}",
        f"- Nota: {address['nota']}",
        f"- Horario publicado: {', '.join(cast(list[str], structured_data['horario_publicado'])) or unknown or 'No encontrado'}",
        f"- Perfiles enlazados: {', '.join(cast(list[str], structured_data['perfiles_mencionados'])) or unknown or 'No encontrados'}",
        "",
        "## E. Áreas y referencias geográficas detectadas",
        "",
    ]
    locations = cast(list[dict[str, object]], inspection["candidatos_geograficos"])
    city_candidates = [
        item
        for item in locations
        if item.get("location_type")
        not in {"NEIGHBORHOOD_MENTION", "REGIONAL_SERVICE_AREA"}
    ]
    if locations:
        lines.extend(
            (
                "| Lugar | Estado | Tipo | Clasificación | Verificación | Fuente |",
                "|---|---|---|---|---|---|",
            )
        )
        for item in locations:
            lines.append(
                f"| {item.get('place_name', item.get('city'))} | {item['state'] or 'No indicado'} | {item['location_type']} | {item['evidence_classification']} | {item['verification_status']} | [sitio]({item['source_url']}) |"
            )
            lines.append(f"  - Evidencia: {item['supporting_text']}")
    else:
        lines.append(
            "No evaluable: la inspección no recuperó páginas."
            if failed
            else "No se identificaron ciudades candidatas en las páginas revisadas."
        )
    lines.extend(("", "## F. Servicios detectados", ""))
    services = cast(list[dict[str, object]], inspection["servicios_detectados"])
    if services:
        for item in services:
            lines.extend(
                (
                    f"- **{item['service']}** — {item['evidence_classification']} ({item['verification_status']})",
                    f"  - Evidencia: {item['supporting_text']}",
                    f"  - Fuente: {item['source_url']}",
                )
            )
    else:
        lines.append(
            "No evaluable: la inspección no recuperó páginas."
            if failed
            else "No se identificaron servicios específicos."
        )
    lines.extend(("", "## G. Mercados potenciales", ""))
    if city_candidates:
        lines.append(
            "Los candidatos requieren revisión y selección del propietario antes de iniciar investigación comercial."
        )
    else:
        lines.append(
            "No evaluable: la inspección no recuperó páginas."
            if failed
            else "Faltan ubicaciones para proponer mercados."
        )
    if "seleccion_del_mercado" in report:
        raw_selection = report["seleccion_del_mercado"]
        selections = (
            cast(list[dict[str, object]], raw_selection)
            if isinstance(raw_selection, list)
            else [cast(dict[str, object], raw_selection)]
        )
        for selected in selections:
            city = selected.get("city", selected.get("ciudad"))
            state = selected.get("state", selected.get("estado"))
            lines.extend(("", f"Mercado seleccionado: **{city}, {state}**."))
            if selected.get("discovery_requires_explicit_confirmation", False):
                lines.append(
                    "No se inició la búsqueda en Overpass; falta la confirmación explícita de investigación."
                )
            if (
                selected.get("research_radius", selected.get("radio_solicitado"))
                is not None
            ):
                lines.append(
                    "El radio queda registrado en el alcance, pero Overpass busca por área administrativa y no aplica este radio."
                )
    lines.extend(("", "## H. Evidencia y fuentes", ""))
    evidence = cast(list[dict[str, object]], inspection["evidencia_y_fuentes"])
    for item in evidence:
        lines.append(
            f"- **{item['classification']} · {item['field']}**: {item['supporting_text']} ([fuente]({item['source_url']}))"
        )
    lines.extend(("", "## I. Información faltante", ""))
    missing = cast(list[str], inspection["informacion_faltante"])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append(
        "No se detectaron campos faltantes de la lista básica."
    )
    lines.extend(
        (
            "",
            "## J. Limitaciones",
            "",
            "- Los datos del sitio son observaciones o declaraciones publicadas; no son confirmación del propietario.",
            "- No se infieren coordenadas ni centros geográficos.",
            "- Una mención de ciudad no confirma que el negocio atienda esa ciudad.",
        )
    )
    limitations = cast(list[str], inspection["limitaciones"])
    lines.extend(f"- {item}" for item in limitations)
    lines.extend(
        (
            "",
            "## K. Siguiente paso recomendado",
            "",
            str(inspection["siguiente_paso_recomendado"]),
        )
    )
    discovery = report.get("investigacion_de_mercado")
    if isinstance(discovery, dict | list):
        discoveries = discovery if isinstance(discovery, list) else [discovery]
        lines.extend(("", "## Investigación de mercado", ""))
        for item in cast(list[dict[str, object]], discoveries):
            lines.append(f"Estado: **{item.get('status', 'desconocido')}**")
            for limitation in cast(list[str], item.get("limitations", [])):
                lines.append(f"- {limitation}")
    return "\n".join(lines) + "\n"


def _sanitize_report_value(value: object) -> object:
    if isinstance(value, str):
        return safe_text_for_report(value)
    if isinstance(value, Mapping):
        return {str(key): _sanitize_report_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_sanitize_report_value(item) for item in value]
    return value
