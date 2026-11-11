"""Evidence-led diagnostics for a user-supplied business URL."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from aeos.application.live.website_report import build_website_report
from aeos.live.domain.evidence import EvidenceKind
from aeos.live.domain.profile import BusinessProfile, ProfileFieldStatus
from aeos.live.domain.url_policy import (
    has_sensitive_query_parameter,
    safe_text_for_report,
    safe_url_for_report,
)
from aeos.live.domain.location_candidate import LocationType
from aeos.live.domain.website_inspection import WebsitePage
from aeos.live.ports.website import WebsiteInspectionResult


class BusinessURLPlatform(StrEnum):
    WEBSITE = "WEBSITE"
    GOOGLE_BUSINESS_PROFILE = "GOOGLE_BUSINESS_PROFILE"
    FACEBOOK = "FACEBOOK"
    INSTAGRAM = "INSTAGRAM"
    LINKEDIN = "LINKEDIN"


@dataclass(frozen=True, slots=True)
class ClassifiedBusinessURL:
    url: str
    platform: BusinessURLPlatform


def classify_business_url(value: str) -> ClassifiedBusinessURL:
    """Normalize and classify the host without fetching the submitted URL."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("URL must not be blank")
    raw = value.strip()
    try:
        parts = urlsplit(raw)
        host = parts.hostname
        # Accessing .port validates malformed port syntax as well.
        _ = parts.port
    except ValueError as error:
        raise ValueError("URL is malformed") from error
    if (
        parts.scheme.casefold() not in {"http", "https"}
        or not host
        or parts.username
        or parts.password
    ):
        raise ValueError("URL must be an absolute HTTP(S) URL without credentials")
    if has_sensitive_query_parameter(raw):
        raise ValueError("URL contains a sensitive query parameter")
    normalized = safe_url_for_report(raw)
    if normalized in {None, "[URL omitted]"}:
        raise ValueError("URL could not be normalized safely")

    hostname = host.casefold().rstrip(".")
    path = parts.path.casefold()
    if _host_is(hostname, "facebook.com") or _host_is(hostname, "fb.com"):
        platform = BusinessURLPlatform.FACEBOOK
    elif _host_is(hostname, "instagram.com") or _host_is(hostname, "instagr.am"):
        platform = BusinessURLPlatform.INSTAGRAM
    elif _host_is(hostname, "linkedin.com") or _host_is(hostname, "lnkd.in"):
        platform = BusinessURLPlatform.LINKEDIN
    elif (
        hostname == "g.page"
        or hostname == "maps.app.goo.gl"
        or (hostname == "goo.gl" and path.startswith("/maps"))
        or _host_is(hostname, "share.google")
        or _host_is(hostname, "business.google.com")
        or hostname.startswith("maps.google.")
        or (
            _host_is(hostname, "google.com") and path.startswith(("/maps", "/business"))
        )
    ):
        platform = BusinessURLPlatform.GOOGLE_BUSINESS_PROFILE
    else:
        platform = BusinessURLPlatform.WEBSITE
    return ClassifiedBusinessURL(normalized, platform)


def build_business_url_diagnosis_report(
    url: str,
    *,
    profile: BusinessProfile | None = None,
    inspection: WebsiteInspectionResult | None = None,
    inspection_status: str | None = None,
    failure_category: str | None = None,
    failure_stage: str | None = None,
    inspected_at: str | None = None,
) -> dict[str, object]:
    classified = classify_business_url(url)
    report: dict[str, object] = {
        "project": "AEOS-LIVE-003C",
        "report_language": "es",
        "url_diagnosis": {
            "submitted_url": classified.url,
            "platform": classified.platform.value,
            "classification_status": "OBSERVED_FROM_SUBMITTED_URL",
            "inspection_status": "NOT_STARTED",
            "inspected_at": inspected_at,
            "business_context": _business_context(profile, classified),
            "observed_signals": {},
            "findings": [],
            "pending_verifications": [],
            "not_reviewed": [],
            "limitations": [],
        },
    }
    diagnosis = report["url_diagnosis"]
    assert isinstance(diagnosis, dict)

    if classified.platform is BusinessURLPlatform.WEBSITE:
        diagnosis["inspection_status"] = inspection_status or "NOT_COMPLETED"
        website_report = build_website_report(
            inspection,
            website_url=classified.url,
            status="succeeded" if inspection_status == "SUCCEEDED" else "failed",
            failure_category=failure_category,
            failure_stage=failure_stage,
        )
        report["website_inspection"] = website_report["website_inspection"]
        diagnosis["observed_signals"] = _website_signals(inspection)
        findings, pending_verifications = _website_findings(inspection, profile)
        diagnosis["findings"] = findings
        diagnosis["pending_verifications"] = pending_verifications
        html_only_urls = (
            [
                safe_url_for_report(page.url)
                for page in inspection.pages
                if getattr(page, "inspection_method", "HTML_ONLY") == "HTML_ONLY"
            ]
            if inspection
            else []
        )
        diagnosis["not_reviewed"] = [
            *(
                [
                    "DOM renderizado no disponible (HTML_ONLY) para: "
                    + ", ".join(str(item) for item in html_only_urls)
                    + ". Las ausencias en el HTML de esas URLs no se confirman como ausencias renderizadas."
                ]
                if html_only_urls
                else []
            ),
            "Posiciones, impresiones, clics y consultas de Search Console: requieren acceso autorizado a la propiedad.",
            "Rendimiento y conversiones del negocio: no se proporcionaron datos autorizados del propietario.",
            "Causalidad entre señales técnicas y posicionamiento: no se puede demostrar con esta inspección pública.",
        ]
        diagnosis["limitations"] = [
            "Se comparan los campos del HTML recibido con el DOM renderizado cuando Playwright está disponible; el estado por URL indica el método y no confirma indexación en buscadores.",
            "El HTML recibido puede ser solo el contenedor inicial de una aplicación; JavaScript puede agregar contenido después. HTML_ONLY deja esas diferencias sin confirmar.",
            "Los contenidos publicados por el sitio son OBSERVED como contenido web; las afirmaciones empresariales dentro de ellos siguen siendo REPORTED por el sitio.",
            "Las explicaciones sobre posible impacto son INFERRED y no demuestran una causa de posicionamiento ni pérdida de clientes.",
            *(
                cast_list(website_report["website_inspection"].get("limitaciones"))
                if isinstance(website_report.get("website_inspection"), Mapping)
                else []
            ),
        ]
    else:
        diagnosis["inspection_status"] = "OWNER_EVIDENCE_REQUIRED"
        diagnosis["not_reviewed"] = [
            "Contenido del perfil y campos visibles: no inspeccionados automáticamente.",
            "Datos privados, rendimiento, estadísticas y cambios del perfil.",
            "Existencia o estado actual del perfil: no se deduce de que el enlace no se haya abierto.",
        ]
        diagnosis["access_request"] = (
            "Solicitar al propietario una captura o exportación de los campos que quiera analizar, "
            "o acceso autorizado mediante el mecanismo oficial disponible. No enviar contraseñas."
        )
        diagnosis["limitations"] = [
            "No se hizo scraping, inicio de sesión, ni solicitud al servicio de la plataforma.",
            "La URL proporcionada no prueba por sí sola que el perfil esté activo o exista actualmente.",
            "Sin datos autorizados no se afirman posiciones, tráfico, pérdida de clientes ni causas de posicionamiento.",
        ]
    return report


def render_business_url_diagnosis_markdown(report: Mapping[str, object]) -> str:
    diagnosis = cast_mapping(report.get("url_diagnosis"))
    lines = [
        "# AEOS — Diagnóstico del negocio por URL",
        "",
        f"- URL recibida: {diagnosis.get('submitted_url')}",
        f"- Tipo clasificado: **{diagnosis.get('platform')}** ({diagnosis.get('classification_status')})",
        f"- Estado de inspección: **{diagnosis.get('inspection_status')}**",
        f"- Evaluado en: {diagnosis.get('inspected_at') or 'No disponible'}",
        "",
        "## Contexto del perfil",
        "",
    ]
    context = cast_mapping(diagnosis.get("business_context"))
    for key in ("reported", "observed", "inferred"):
        entries = cast_list(context.get(key))
        lines.append(f"### {key.upper()}")
        if not entries:
            lines.append("Sin datos de perfil en esta clasificación.")
        for raw in entries:
            item = cast_mapping(raw)
            source = item.get("source_url") or item.get("source_name") or "sin fuente"
            lines.append(f"- **{item.get('field')}**: {item.get('value')} — {source}")
            if item.get("excerpt"):
                lines.append(f"  - Evidencia: {item.get('excerpt')}")
        lines.append("")
    digital = cast_mapping(context.get("digital_presence"))
    if digital:
        lines.append("### Estado de presencia digital")
        for field, raw in digital.items():
            if isinstance(raw, Mapping):
                item = raw
                presence = cast_mapping(item.get("reported_presence"))
                reported = (
                    f"; presencia reportada={presence.get('value')} "
                    f"({presence.get('classification')})"
                    if presence
                    else ""
                )
                lines.append(
                    f"- {field}: {item.get('url_status')} — URL: "
                    f"{item.get('url') or 'no proporcionada'}{reported}"
                )
            elif isinstance(raw, list):
                lines.append(
                    f"- {field}: "
                    + (", ".join(str(item) for item in raw) or "sin URLs reportadas")
                )
            else:
                lines.append(f"- {field}: {raw}")
        lines.append("")

    failure = cast_mapping(diagnosis.get("failure"))
    if failure:
        lines.extend(
            (
                "## Bloqueo de inspección",
                "",
                f"- Categoría: {failure.get('category')}",
                f"- Etapa: {failure.get('stage') or 'no indicada'}",
                "",
            )
        )

    signals = cast_mapping(diagnosis.get("observed_signals"))
    if signals:
        lines.extend(("## Alcance y cobertura de inspección", ""))
        scope = cast_mapping(signals.get("inspection_scope"))
        lines.extend(
            (
                "Se comparan el HTML recibido y el DOM renderizado cuando está disponible; "
                "consulta el método indicado para cada URL.",
                f"- Páginas recibidas: {scope.get('pages_received', 0)}; candidatas potencialmente indexables según la respuesta observada: {scope.get('potentially_indexable_pages', 0)}.",
                f"- Cobertura de comprobaciones: {', '.join(cast_list(scope.get('checks_completed'))) or 'ninguna; no se recibieron páginas HTML'}.",
                f"- Páginas excluidas por estado HTTP distinto de 200: {scope.get('excluded_non_200', 0)}; excluidas por directiva noindex: {scope.get('excluded_noindex', 0)}.",
                "",
                "## Señales observadas en el sitio",
                "",
            )
        )
        for raw in cast_list(signals.get("pages")):
            page = cast_mapping(raw)
            page_noindex = page.get("potentially_indexable") is False
            lines.extend(
                (
                    f"### {page.get('url')}",
                    f"- HTTP: {page.get('http_status')}",
                    f"- Método: {page.get('inspection_method')}",
                    f"- Title HTML: {page.get('title') or 'no encontrado en el HTML recibido'}",
                    f"- Title DOM: {_rendered_value(page, 'title')}",
                    f"- Meta description HTML: {page.get('meta_description') or 'no encontrada en el HTML recibido'}",
                    f"- Meta description DOM: {_rendered_value(page, 'meta_description')}",
                    f"- H1 HTML: {', '.join(cast_list(page.get('h1'))) or 'no encontrado en el HTML recibido'}",
                    f"- H1 DOM: {_rendered_value(page, 'h1')}",
                    f"- Indexabilidad potencial: {'no (directiva noindex observada)' if page_noindex else page.get('potential_indexability_basis')}",
                    f"- H2 ({'DOM' if page.get('inspection_method') == 'HTTP_AND_RENDERED_DOM' else 'HTML'}): {', '.join(cast_list(page.get('h2'))) or 'No encontrados'}",
                    f"- Enlaces observados ({'DOM' if page.get('inspection_method') == 'HTTP_AND_RENDERED_DOM' else 'HTML'}): {len(cast_list(page.get('link_urls')))}",
                )
            )
        lines.extend(
            (
                f"- Tipos de datos estructurados: {', '.join(cast_list(signals.get('structured_data_types'))) or 'No identificados en el HTML inspeccionado'}",
                f"- robots.txt: {signals.get('robots_status')}",
                f"- Sitemaps encontrados: {', '.join(cast_list(signals.get('sitemaps'))) or 'No encontrados'}",
                f"- Teléfono/correo/dirección visibles o estructurados: {signals.get('contact')}",
                f"- Referencias de ubicación encontradas: {len(cast_list(signals.get('locations')))}",
                "",
            )
        )
        claims = cast_list(signals.get("website_claims"))
        if claims:
            lines.extend(("### Afirmaciones extraídas del sitio", ""))
            for raw in claims:
                claim = cast_mapping(raw)
                lines.append(
                    f"- **WEBSITE_REPORTED — {claim.get('field')}**: {claim.get('value')} — "
                    f"evidencia: {claim.get('evidence')} ([fuente]({claim.get('source_url')}))"
                )
            lines.append("")

    findings = cast_list(diagnosis.get("findings"))
    pending = cast_list(diagnosis.get("pending_verifications"))
    lines.extend(("## Hallazgos confirmados", ""))
    if findings:
        _append_finding_items(lines, findings, prompt_label="Prompt de corrección")
    elif pending:
        lines.append(
            "No se confirmaron problemas que justifiquen una corrección; hay verificaciones pendientes abajo."
        )
    else:
        scope = cast_mapping(signals.get("inspection_scope"))
        pages_received = int(scope.get("pages_received", 0) or 0)
        eligible_pages = int(scope.get("potentially_indexable_pages", 0) or 0)
        checks = ", ".join(cast_list(scope.get("checks_completed"))) or "ninguna"
        if pages_received == 0:
            lines.extend(
                (
                    "No se generaron hallazgos porque no se recibió HTML; no se completaron comprobaciones de página.",
                    "- Cobertura: 0 páginas recibidas; comprobaciones completadas: ninguna.",
                )
            )
        elif eligible_pages == 0:
            lines.extend(
                (
                    "No se evaluaron omisiones de metadatos o H1 porque ninguna página quedó como candidata potencialmente indexable según la respuesta observada.",
                    f"- Comprobaciones completadas: {checks}; {pages_received} páginas recibidas, 0 candidatas potencialmente indexables; {scope.get('excluded_non_200', 0)} con HTTP distinto de 200 y {scope.get('excluded_noindex', 0)} con noindex.",
                )
            )
        else:
            methods = cast_mapping(scope.get("inspection_methods"))
            html_only_count_raw = methods.get("HTML_ONLY", 0)
            html_only_count = (
                html_only_count_raw if isinstance(html_only_count_raw, int) else 0
            )
            html_only_note = (
                f" El DOM no estuvo disponible para {html_only_count} URLs HTML_ONLY."
                if html_only_count
                else ""
            )
            lines.extend(
                (
                    "No se detectaron problemas en las comprobaciones completadas; esto no demuestra indexación, posiciones ni rendimiento en buscadores."
                    + html_only_note,
                    f"- Comprobaciones y cobertura: {checks}; páginas recibidas: {pages_received}; candidatas potencialmente indexables: {eligible_pages}.",
                )
            )
    lines.extend(("## Verificaciones pendientes (INCONCLUSIVE)", ""))
    if pending:
        _append_finding_items(lines, pending, prompt_label="Prompt de verificación")
    else:
        lines.append("No hay verificaciones pendientes de campos de página.")
    lines.extend(("## Qué quedó sin revisar", ""))
    lines.extend(f"- {item}" for item in cast_list(diagnosis.get("not_reviewed")))
    lines.extend(("", "## Límites", ""))
    lines.extend(f"- {item}" for item in cast_list(diagnosis.get("limitations")))
    lines.extend(
        ("", "No se contactó a ninguna persona ni se inició búsqueda de mercado.", "")
    )
    return "\n".join(lines)


def _append_finding_items(
    lines: list[str], items: list[object], *, prompt_label: str
) -> None:
    for raw in items:
        item = cast_mapping(raw)
        evidence = cast_mapping(item.get("evidence"))
        why = cast_mapping(item.get("why_it_may_matter"))
        lines.extend(
            (
                f"### {item.get('priority')}. {item.get('title')}",
                f"- Observación: **{item.get('observation_status')}** — {item.get('observation')}",
                f"- Evidencia: {evidence.get('excerpt')}",
                f"- Por qué podría importar (**{why.get('classification')}**): {why.get('text')}",
                f"- Acción concreta: {item.get('action')}",
                f"- {prompt_label}:",
                "```text",
                str(item.get("copyable_prompt")),
                "```",
                "",
            )
        )
        for source in cast_list(evidence.get("sources")):
            source_item = cast_mapping(source)
            lines.append(
                f"  - URL y detalle: {source_item.get('excerpt')} "
                f"([fuente]({source_item.get('source_url')}))"
            )
        lines.append("")


def _website_signals(
    inspection: WebsiteInspectionResult | None,
) -> dict[str, object]:
    if inspection is None:
        return {}
    details = inspection.details
    pages = [
        {
            "url": safe_url_for_report(page.url),
            "http_status": page.status_code,
            "inspection_method": getattr(page, "inspection_method", "HTML_ONLY"),
            "html_received": {
                "title": safe_text_for_report(page.title) if page.title else None,
                "meta_description": safe_text_for_report(page.meta_description)
                if page.meta_description
                else None,
                "h1": [safe_text_for_report(item) for item in page.h1_headings],
            },
            "title": safe_text_for_report(page.title) if page.title else None,
            "meta_description": safe_text_for_report(page.meta_description)
            if page.meta_description
            else None,
            "h1": [safe_text_for_report(item) for item in page.h1_headings],
            "rendered_dom": (
                {
                    "status": getattr(page, "rendered_dom_status", "HTML_ONLY"),
                    "fields_observed": list(
                        getattr(page, "rendered_dom_fields_observed", ())
                    ),
                    "error_category": getattr(page, "rendered_dom_error", None),
                    "error_message": safe_text_for_report(
                        getattr(page, "rendered_dom_error_message", None)
                    )
                    if getattr(page, "rendered_dom_error_message", None)
                    else None,
                    "title": safe_text_for_report(getattr(page, "rendered_title", None))
                    if getattr(page, "rendered_title", None)
                    else None,
                    "meta_description": safe_text_for_report(
                        getattr(page, "rendered_meta_description", None)
                    )
                    if getattr(page, "rendered_meta_description", None)
                    else None,
                    "h1": [
                        safe_text_for_report(item)
                        for item in getattr(page, "rendered_h1_headings", ())
                    ],
                    "h2": [
                        safe_text_for_report(item)
                        for item in getattr(page, "rendered_h2_headings", ())
                    ],
                    "link_texts": [
                        safe_text_for_report(item)
                        for item in getattr(page, "rendered_link_texts", ())
                    ],
                    "link_urls": [
                        safe_url_for_report(item) or "[URL omitted]"
                        for item in getattr(page, "rendered_link_urls", ())
                    ],
                }
                if getattr(page, "inspection_method", "HTML_ONLY")
                == "HTTP_AND_RENDERED_DOM"
                else {
                    "status": "HTML_ONLY",
                    "fields_observed": [],
                    "error_category": getattr(page, "rendered_dom_error", None),
                    "error_message": safe_text_for_report(
                        getattr(page, "rendered_dom_error_message", None)
                    )
                    if getattr(page, "rendered_dom_error_message", None)
                    else None,
                }
            ),
            "h2": [
                safe_text_for_report(item)
                for item in (
                    getattr(page, "rendered_h2_headings", ())
                    if getattr(page, "inspection_method", "HTML_ONLY")
                    == "HTTP_AND_RENDERED_DOM"
                    else page.h2_headings
                )
            ],
            "html_h2": [safe_text_for_report(item) for item in page.h2_headings],
            "link_texts": [
                safe_text_for_report(item)
                for item in (
                    getattr(page, "rendered_link_texts", ())
                    if getattr(page, "inspection_method", "HTML_ONLY")
                    == "HTTP_AND_RENDERED_DOM"
                    else getattr(page, "link_texts", ())
                )
            ],
            "link_urls": [
                safe_url_for_report(item) or "[URL omitted]"
                for item in (
                    getattr(page, "rendered_link_urls", ())
                    if getattr(page, "inspection_method", "HTML_ONLY")
                    == "HTTP_AND_RENDERED_DOM"
                    else getattr(page, "link_urls", ())
                )
            ],
            "html_link_urls": [
                safe_url_for_report(item) or "[URL omitted]"
                for item in getattr(page, "link_urls", ())
            ],
            "robots_directives": list(getattr(page, "robots_directives", ())),
            "x_robots_tag": safe_text_for_report(getattr(page, "x_robots_tag", None))
            if getattr(page, "x_robots_tag", None)
            else None,
            "potentially_indexable": _page_is_potentially_indexable(page),
            "potential_indexability_basis": _page_indexability_basis(page),
        }
        for page in inspection.pages
    ]
    eligible_pages = [
        page for page in inspection.pages if _page_is_potentially_indexable(page)
    ]
    rendered_pages = [
        page
        for page in inspection.pages
        if getattr(page, "inspection_method", "HTML_ONLY") == "HTTP_AND_RENDERED_DOM"
    ]
    return {
        "inspection_scope": {
            "source": "HTML recibido y DOM renderizado local cuando estuvo disponible",
            "javascript_executed": bool(rendered_pages),
            "rendered_dom_inspected": bool(rendered_pages),
            "inspection_methods": {
                "HTTP_AND_RENDERED_DOM": len(rendered_pages),
                "HTML_ONLY": len(inspection.pages) - len(rendered_pages),
            },
            "pages_received": len(inspection.pages),
            "potentially_indexable_pages": len(eligible_pages),
            "excluded_non_200": sum(
                page.status_code != 200 for page in inspection.pages
            ),
            "excluded_noindex": sum(
                page.status_code == 200 and _page_has_noindex(page)
                for page in inspection.pages
            ),
            "checks_completed": [
                "title HTML",
                "meta description HTML",
                "H1 HTML",
                *(
                    [
                        "title, meta description y H1 del DOM renderizado",
                        "H2 y enlaces del DOM renderizado",
                    ]
                    if rendered_pages
                    else [
                        "estado HTML_ONLY por URL cuando Playwright no estuvo disponible"
                    ]
                ),
                "duplicados de títulos y meta descripciones",
                "directivas meta robots y X-Robots-Tag recibidas",
                "enlaces presentes en el HTML",
                "datos estructurados JSON-LD",
                "contacto y ubicación presentes en HTML/JSON-LD",
                "robots.txt y sitemap según disponibilidad del inspector",
            ]
            if inspection.pages
            else [],
        },
        "pages": pages,
        "structured_data_types": list(getattr(details, "structured_data_types", ()))
        if details
        else [],
        "robots_status": details.robots_status if details else "not_checked",
        "robots_sitemaps": list(details.robots_sitemaps) if details else [],
        "robots_restrictions": list(details.robots_restrictions) if details else [],
        "sitemaps": list(details.sitemap_urls) if details else [],
        "contact": {
            "phone": details.phone if details else None,
            "email": details.email if details else None,
            "address": details.address if details else None,
        },
        "locations": [
            {
                "value": item.city,
                "state": item.state,
                "classification": item.evidence_classification.value,
                "source_url": safe_url_for_report(item.source_url),
                "evidence": safe_text_for_report(item.supporting_text),
            }
            for item in inspection.locations
        ],
        "website_claims": _website_claims(inspection),
    }


def _website_findings(
    inspection: WebsiteInspectionResult | None,
    profile: BusinessProfile | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if inspection is None or not inspection.pages:
        return [], []
    findings: list[dict[str, object]] = []
    pending: list[dict[str, object]] = []
    eligible = [
        page for page in inspection.pages if _page_is_potentially_indexable(page)
    ]
    if not eligible:
        return [], []
    context = _website_prompt_context(profile, inspection)

    confirmed_metadata: list[tuple[WebsitePage, str, str]] = []
    pending_metadata: list[tuple[WebsitePage, str, str]] = []
    for page in eligible:
        for field in ("title", "meta_description"):
            state = _field_observation_status(page, field)
            if state == "CONFIRMED_ABSENT":
                confirmed_metadata.append(
                    (page, field, _missing_field_evidence(page, field))
                )
            elif state == "PENDING":
                pending_metadata.append(
                    (page, field, _missing_field_evidence(page, field))
                )
    if confirmed_metadata:
        findings.append(
            _missing_fields_finding(
                confirmed_metadata,
                priority=1,
                title="Metadatos ausentes en DOM renderizado",
                pending=False,
            )
        )
    if pending_metadata:
        pending.append(
            _missing_fields_finding(
                pending_metadata,
                priority=1,
                title="Verificación pendiente de títulos o meta descripciones",
                pending=True,
            )
        )

    confirmed_h1 = [
        (page, "h1", _missing_field_evidence(page, "h1"))
        for page in eligible
        if _field_observation_status(page, "h1") == "CONFIRMED_ABSENT"
    ]
    pending_h1 = [
        (page, "h1", _missing_field_evidence(page, "h1"))
        for page in eligible
        if _field_observation_status(page, "h1") == "PENDING"
    ]
    if confirmed_h1:
        findings.append(
            _missing_fields_finding(
                confirmed_h1,
                priority=2,
                title="H1 ausente en DOM renderizado",
                pending=False,
            )
        )
    if pending_h1:
        pending.append(
            _missing_fields_finding(
                pending_h1,
                priority=2,
                title="Verificación pendiente de H1",
                pending=True,
            )
        )

    duplicate_groups = _duplicate_metadata(eligible)
    if duplicate_groups:
        excerpt = "; ".join(
            f"{field} ({'DOM renderizado' if method == 'HTTP_AND_RENDERED_DOM' else 'HTML_ONLY'}): {value!r} en {', '.join(page.url for page in pages)}"
            for field, value, pages, method in duplicate_groups
        )
        involved = tuple(
            dict.fromkeys(page for _, _, pages, _ in duplicate_groups for page in pages)
        )
        findings.append(
            _finding(
                priority=3,
                title="Posibles mejoras: títulos o meta descripciones duplicados",
                page=involved[0],
                source_pages=tuple(
                    (
                        page,
                        "Metadato duplicado: "
                        + "; ".join(
                            f"{field}={value!r}"
                            for field, value, pages, _ in duplicate_groups
                            if page in pages
                        ),
                    )
                    for page in involved
                ),
                observation="Se repite el mismo texto de título o meta description en varias páginas potencialmente indexables.",
                excerpt=excerpt,
                why="Metadatos únicos pueden distinguir el contenido de cada URL. La duplicación observada no demuestra pérdida de posiciones ni una consecuencia específica en buscadores.",
                action="Comparar las páginas enlazadas y redactar metadatos únicos solo cuando su contenido lo justifique.",
                observation_status="OBSERVED",
                prompt=(
                    f"Revisa title y meta description en estas URLs: {', '.join(_report_page_url(page) for page in involved)}. Repetido: {_duplicate_values_for_prompt(duplicate_groups)}. Ajusta según cada página; no inventes datos ni afirmes pérdida de posiciones."
                ),
            )
        )

    if not findings and not pending:
        details = inspection.details
        structured_data_types = (
            getattr(details, "structured_data_types", None)
            if details is not None
            else None
        )
        if (
            details is not None
            and structured_data_types is not None
            and not any(
                item.casefold()
                in {
                    "localbusiness",
                    "homeandconstructionbusiness",
                    "cleaningservice",
                    "hvacbusiness",
                    "generalcontractor",
                    "organization",
                }
                for item in structured_data_types
            )
        ):
            page = eligible[0]
            findings.append(
                _finding(
                    priority=3,
                    title="Posible mejora: no se identificó schema de negocio u organización",
                    page=page,
                    observation="No se identificó un tipo JSON-LD de negocio u organización en las páginas revisadas.",
                    excerpt="No se identificó en el HTML inspeccionado un tipo LocalBusiness, HomeAndConstructionBusiness u Organization.",
                    why="El marcado estructurado puede describir información empresarial a sistemas compatibles; su ausencia no demuestra una causa de posicionamiento ni garantiza resultados enriquecidos.",
                    action="Evaluar JSON-LD solo con información confirmada y validar el marcado antes de publicarlo.",
                    prompt=(
                        f"Revisa si conviene añadir JSON-LD a {page.url}. Los datos del sitio enumerados como WEBSITE_REPORTED requieren confirmación del propietario antes de reutilizarse: {context}. "
                        "No inventes tipo legal, dirección, teléfono, horarios ni áreas."
                    ),
                )
            )
    return findings[:3], pending[:3]


def _missing_fields_finding(
    fields: list[tuple[WebsitePage, str, str]],
    *,
    priority: int,
    title: str,
    pending: bool,
) -> dict[str, object]:
    pages_by_url: dict[str, list[str]] = {}
    for page, _, evidence in fields:
        pages_by_url.setdefault(page.url, []).append(evidence)
    sources = tuple(
        (page, "; ".join(evidence))
        for page in dict.fromkeys(page for page, _, _ in fields)
        if (evidence := pages_by_url.get(page.url))
    )
    urls_and_fields = "; ".join(
        f"{_report_page_url(page)}: "
        + ", ".join(
            dict.fromkeys(
                _field_label(field)
                for source_page, field, _ in fields
                if source_page.url == page.url
            )
        )
        for page, _ in sources
    )
    if pending:
        observation = (
            "La falta en el HTML recibido no confirma ausencia en la página renderizada; "
            "el DOM está incompleto o no disponible para estas URLs."
        )
        action = "Completar la verificación del DOM antes de decidir si hace falta cambiar estos campos."
        prompt = (
            f"Verifica en un DOM completo estos campos y URLs: {urls_and_fields}. "
            "No agregues ni cambies contenido hasta confirmar que falta en la página renderizada."
        )
        why = "La respuesta HTML no permite confirmar si el campo falta en el DOM final; hay que completar la observación antes de decidir una corrección."
    else:
        observation = "El DOM renderizado completo no contiene estos campos con texto en las URLs indicadas."
        action = (
            "Revisar cada página y añadir solo los campos confirmados como ausentes, "
            "según su contenido real."
        )
        prompt = (
            f"Revisa y corrige solo estos campos confirmados como ausentes: {urls_and_fields}. "
            "Usa el contenido de cada página; no inventes servicios, ubicaciones ni promesas."
        )
        why = "Un título, descripción o encabezado claro puede describir la página; la ausencia observada no demuestra pérdida de posiciones ni una causa comprobada de posicionamiento."
    return _finding(
        priority=priority,
        title=title,
        page=sources[0][0],
        source_pages=sources,
        observation=observation,
        excerpt="; ".join(f"{page.url}: {detail}" for page, detail in sources),
        why=why,
        action=action,
        prompt=prompt,
        observation_status="INCONCLUSIVE" if pending else "OBSERVED",
    )


def _finding(
    *,
    priority: int,
    title: str,
    page: WebsitePage,
    source_pages: tuple[tuple[WebsitePage, str], ...] = (),
    observation: str,
    excerpt: str,
    why: str,
    action: str,
    prompt: str,
    observation_status: str = "OBSERVED",
) -> dict[str, object]:
    return {
        "priority": priority,
        "title": title,
        "observation_status": observation_status,
        "observation": observation,
        "evidence": {
            "classification": "OBSERVED",
            "source_url": safe_url_for_report(page.url),
            "excerpt": safe_text_for_report(excerpt),
            "sources": [
                {
                    "source_url": safe_url_for_report(source_page.url),
                    "excerpt": safe_text_for_report(source_excerpt),
                }
                for source_page, source_excerpt in source_pages
            ],
        },
        "why_it_may_matter": {"classification": "INFERRED", "text": why},
        "action": action,
        "copyable_prompt": prompt,
    }


def _page_has_noindex(page: WebsitePage) -> bool:
    directives = [*getattr(page, "robots_directives", ())]
    x_robots_tag = getattr(page, "x_robots_tag", None)
    if x_robots_tag:
        directives.extend(x_robots_tag.split(","))
    for raw in directives:
        directive = raw.casefold().strip().split(":", 1)[-1].strip()
        if directive in {"noindex", "none"}:
            return True
    return False


def _page_inspection_value(
    page: WebsitePage, field: str
) -> str | tuple[str, ...] | None:
    html_value = _normalized_page_field_value(page, field, rendered=False)
    rendered_value = _normalized_page_field_value(page, field, rendered=True)
    dom_status = getattr(page, "rendered_dom_status", "HTML_ONLY")
    if dom_status == "RENDERED":
        return rendered_value
    if dom_status == "PARTIAL" and rendered_value:
        return rendered_value
    return html_value


def _normalized_page_field_value(
    page: WebsitePage, field: str, *, rendered: bool
) -> str | tuple[str, ...] | None:
    if field not in {"title", "meta_description", "h1"}:
        raise ValueError(f"Unsupported page field: {field}")
    value = (
        getattr(
            page,
            f"rendered_{field}_headings" if field == "h1" else f"rendered_{field}",
            () if field == "h1" else None,
        )
        if rendered
        else getattr(page, "h1_headings" if field == "h1" else field)
    )
    if field == "h1":
        normalized = tuple(item.strip() for item in value if item.strip())
        return normalized or None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _field_observation_status(page: WebsitePage, field: str) -> str:
    html_value = _normalized_page_field_value(page, field, rendered=False)
    rendered_value = _normalized_page_field_value(page, field, rendered=True)
    dom_status = getattr(page, "rendered_dom_status", "HTML_ONLY")
    if dom_status == "RENDERED":
        return "PRESENT" if rendered_value else "CONFIRMED_ABSENT"
    if dom_status == "PARTIAL":
        if rendered_value or html_value:
            return "PRESENT"
        return "PENDING"
    return "PRESENT" if html_value else "PENDING"


def _missing_field_evidence(page: WebsitePage, field: str) -> str:
    label = {"title": "title", "meta_description": "meta description", "h1": "H1"}[
        field
    ]
    html_value: str | tuple[str, ...] | None = getattr(
        page, "h1_headings" if field == "h1" else field
    )
    html_text = ", ".join(html_value) if isinstance(html_value, tuple) else html_value
    dom_status = getattr(page, "rendered_dom_status", "HTML_ONLY")
    if dom_status == "HTML_ONLY":
        verb = "no encontrada" if field == "meta_description" else "no encontrado"
        return f"{label} {verb} en HTML recibido; ausencia en DOM sin verificar (HTML_ONLY)"
    if dom_status == "PARTIAL":
        partial_note = f"{label} no observado en DOM parcial; verificación pendiente"
        return (
            f"{partial_note}; HTML recibido: {html_text!r}"
            if html_text
            else partial_note
        )
    if html_text:
        return f"{label} ausente en DOM renderizado; HTML recibido: {html_text!r}"
    return f"{label} ausente en HTML recibido y DOM renderizado"


def _page_is_potentially_indexable(page: WebsitePage) -> bool:
    return page.status_code == 200 and not _page_has_noindex(page)


def _page_indexability_basis(page: WebsitePage) -> str:
    if page.status_code != 200:
        return "No se recibió HTTP 200; estado de indexación no evaluado"
    if _page_has_noindex(page):
        return "Se observó noindex en HTML o cabecera X-Robots-Tag"
    return "HTTP 200 y noindex no encontrado en HTML/cabecera recibidos; indexación no confirmada"


def _rendered_value(page: Mapping[str, object], field: str) -> str:
    rendered = cast_mapping(page.get("rendered_dom"))
    status = rendered.get("status")
    if status == "HTML_ONLY":
        return "no comprobado (HTML_ONLY)"
    if status not in {"RENDERED", "PARTIAL"}:
        return "no comprobado (estado DOM desconocido)"
    partial = status == "PARTIAL"
    if field == "h1":
        values = cast_list(rendered.get("h1"))
        if values:
            return ", ".join(str(value) for value in values)
        return (
            "sin dato observado en DOM parcial (indeterminado)"
            if partial
            else "sin H1 con texto"
        )
    value = rendered.get(field)
    if isinstance(value, str) and value:
        return value
    return "sin dato observado en DOM parcial (indeterminado)" if partial else "ausente"


def _report_page_url(page: WebsitePage) -> str:
    return safe_url_for_report(page.url) or "[URL omitted]"


def _field_label(field: str) -> str:
    return "meta description" if field == "meta_description" else field


def _duplicate_values_for_prompt(
    groups: list[tuple[str, str, tuple[WebsitePage, ...], str]],
) -> str:
    values = dict.fromkeys(
        f"{_field_label(field)}={value[:100]!r}" for field, value, _, _ in groups
    )
    return "; ".join(values)


def _website_claims(inspection: WebsiteInspectionResult) -> list[dict[str, object]]:
    claims: list[dict[str, object]] = []
    for item in inspection.services:
        claims.append(
            {
                "field": "service",
                "value": safe_text_for_report(item.service),
                "classification": "WEBSITE_REPORTED",
                "source_url": safe_url_for_report(item.source_url),
                "evidence": safe_text_for_report(item.supporting_text),
            }
        )
    for item in inspection.locations:
        if item.location_type.value not in {
            LocationType.SERVICE_AREA.value,
            LocationType.EXPLICITLY_SERVED_CITY.value,
            "REGIONAL_SERVICE_AREA",
        }:
            continue
        location = ", ".join(part for part in (item.city, item.state) if part)
        claims.append(
            {
                "field": "service_area",
                "value": safe_text_for_report(location),
                "classification": "WEBSITE_REPORTED",
                "source_url": safe_url_for_report(item.source_url),
                "evidence": safe_text_for_report(item.supporting_text),
            }
        )
    return claims


def _website_prompt_context(
    profile: BusinessProfile | None,
    inspection: WebsiteInspectionResult,
) -> str:
    claims = _website_claims(inspection)
    parts = [
        f"WEBSITE_REPORTED {item['field']}={item['value']} "
        f"(fuente: {item['source_url']}; fragmento: {item['evidence']})"
        for item in claims
    ]
    profile_context = _reported_context_for_prompt(profile)
    if profile_context:
        parts.append(f"REPORTED en el perfil adjunto: {profile_context}")
    if not parts:
        return "No se extrajeron servicios o áreas de servicio en las páginas recibidas; solicita confirmación al propietario antes de redactar afirmaciones"
    return "; ".join(dict.fromkeys(parts))


def _duplicate_metadata(
    pages: list[WebsitePage],
) -> list[tuple[str, str, tuple[WebsitePage, ...], str]]:
    duplicates: list[tuple[str, str, tuple[WebsitePage, ...], str]] = []
    for field, label in (
        ("title", "title"),
        ("meta_description", "meta description"),
    ):
        values: dict[str, list[WebsitePage]] = {}
        original_values: dict[str, str] = {}
        for page in pages:
            raw = _page_inspection_value(page, field)
            if not isinstance(raw, str):
                continue
            if not raw or not raw.strip():
                continue
            method = (
                "HTTP_AND_RENDERED_DOM"
                if getattr(page, "rendered_dom_status", "HTML_ONLY") == "RENDERED"
                or _normalized_page_field_value(page, field, rendered=True)
                else "HTML_ONLY"
            )
            normalized = method + ":" + " ".join(raw.split()).casefold()
            values.setdefault(normalized, []).append(page)
            original_values.setdefault(normalized, " ".join(raw.split()))
        for normalized, matches in values.items():
            if len(matches) > 1:
                method = normalized.split(":", 1)[0]
                duplicates.append(
                    (label, original_values[normalized], tuple(matches), method)
                )
    return duplicates


def _business_context(
    profile: BusinessProfile | None,
    classified: ClassifiedBusinessURL,
) -> dict[str, object]:
    if profile is None:
        return {
            "status": "NO_PROFILE_PROVIDED",
            "reported": [],
            "observed": [],
            "inferred": [],
            "digital_presence": {},
        }
    included_fields = {
        "business_name",
        "legal_name",
        "registration_id",
        "legal_entity_status",
        "registered_address",
        "registered_agent",
        "reinstatement_filed_date",
        "reported_prior_names",
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
    grouped: dict[str, list[dict[str, object]]] = {
        "reported": [],
        "observed": [],
        "inferred": [],
    }
    for evidence in profile.field_evidence:
        if evidence.field not in included_fields:
            continue
        grouped[evidence.kind.value.casefold()].append(
            {
                "field": evidence.field,
                "value": _safe_value(evidence.value),
                "classification": evidence.kind.value,
                "source_name": safe_text_for_report(evidence.source_name),
                "source_url": safe_url_for_report(evidence.source_url),
                "excerpt": safe_text_for_report(evidence.excerpt)
                if evidence.excerpt
                else None,
            }
        )
    digital = {
        "website": _presence_entry(
            profile.website_url,
            getattr(profile, "website_presence", None),
            _profile_status(profile, "website_presence"),
            _profile_status(profile, "website_url"),
            classified,
        ),
        "google_business_profile": _presence_entry(
            profile.google_business_profile_url,
            getattr(profile, "google_business_profile_present", None),
            _profile_status(profile, "google_business_profile_present"),
            _profile_status(profile, "google_business_profile_url"),
            classified,
        ),
        "social_media_urls": [
            safe_url_for_report(item) or "[URL omitted]"
            for item in (profile.social_media_urls or ())
        ],
        "instagram_url_status": (
            "URL_NOT_PROVIDED_NOT_INSPECTED"
            if getattr(profile, "instagram_url", None) is None
            else "REPORTED_URL_NOT_INSPECTED"
        ),
    }
    return {
        "status": "PROFILE_ATTACHED",
        **grouped,
        "digital_presence": digital,
    }


def _presence_entry(
    url: str | None,
    reported_presence: bool | None,
    presence_field_status: ProfileFieldStatus | None,
    url_field_status: ProfileFieldStatus | None,
    classified: ClassifiedBusinessURL,
) -> dict[str, object]:
    if url is None:
        url_status = "URL_NOT_PROVIDED_NOT_INSPECTED"
    elif safe_url_for_report(url) == classified.url:
        url_status = "URL_SUBMITTED_FOR_THIS_DIAGNOSIS"
    else:
        url_status = "REPORTED_URL_NOT_INSPECTED"
    reported_value = (
        {
            "value": reported_presence,
            "classification": presence_field_status.value,
            "interpretation": "Dato reportado; no establece por sí solo que un perfil o sitio no exista.",
        }
        if reported_presence is not None and presence_field_status is not None
        else None
    )
    return {
        "url": safe_url_for_report(url),
        "url_status": url_status,
        "url_field_status": url_field_status.value if url_field_status else "UNKNOWN",
        "reported_presence": reported_value,
        "existence_verified": None,
    }


def _reported_context_for_prompt(profile: BusinessProfile | None) -> str:
    if profile is None:
        return ""
    values: list[str] = []
    for evidence in profile.field_evidence:
        if evidence.kind is EvidenceKind.REPORTED and evidence.field in {
            "legal_name",
            "business_name",
            "industry",
            "vertical",
            "primary_services",
            "additional_service_areas",
            "city",
            "state_region",
        }:
            values.append(f"{evidence.field}={evidence.value}")
    return "; ".join(dict.fromkeys(values))


def _profile_status(profile: BusinessProfile, field: str) -> ProfileFieldStatus | None:
    return profile.field_statuses.get(field)


def _host_is(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _safe_value(value: object) -> object:
    if isinstance(value, str):
        return safe_text_for_report(value)
    if isinstance(value, tuple | list):
        return [_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    return value


def cast_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def cast_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}
