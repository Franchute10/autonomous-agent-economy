"""Evidence-bound, page-by-page deliverable for AEOS Fix Pack v1."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict


class FixPage(TypedDict):
    url: str
    finding: str
    evidence: str
    title_template: str
    description_template: str
    implementation_steps: list[str]


class FixPack(TypedDict):
    product: str
    version: str
    currency: str
    amount_minor: int
    language: str
    pages: list[FixPage]
    quality_checks: list[str]
    limitations: list[str]


def build_fix_pack(
    report: Mapping[str, object], *, language: str = "es"
) -> FixPack | None:
    """Create a practical implementation worksheet from confirmed free findings.

    This deterministic product never invents business claims. Templates use
    explicit placeholders where page-specific content needs owner confirmation.
    """
    if language not in {"es", "en"}:
        raise ValueError("language must be 'es' or 'en'")
    if report.get("platform") != "WEBSITE":
        return None
    if report.get("inspection_status") != "SUCCEEDED":
        return None

    raw_findings = report.get("confirmed_findings")
    if not isinstance(raw_findings, list):
        return None

    pages: list[FixPage] = []
    seen: set[tuple[str, str]] = set()
    for raw_finding in raw_findings:
        if not isinstance(raw_finding, Mapping):
            continue
        status = raw_finding.get("status")
        if status != "OBSERVED":
            continue
        finding_title = _localized(raw_finding.get("title"), language)
        if not _is_actionable_finding(finding_title):
            continue
        sources = raw_finding.get("sources")
        if not isinstance(sources, list):
            continue
        evidence = _localized(raw_finding.get("evidence"), language)
        for raw_source in sources:
            if not isinstance(raw_source, Mapping):
                continue
            url = raw_source.get("url")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                continue
            key = (url, finding_title)
            if key in seen:
                continue
            seen.add(key)
            pages.append(
                {
                    "url": url,
                    "finding": finding_title,
                    "evidence": _localized(raw_source.get("evidence"), language)
                    or evidence,
                    "title_template": _title_template(language),
                    "description_template": _description_template(language),
                    "implementation_steps": _implementation_steps(language),
                }
            )

    if not pages:
        return None
    return {
        "product": "AEOS Fix Pack",
        "version": "1",
        "currency": "usd",
        "amount_minor": 500,
        "language": language,
        "pages": pages[:15],
        "quality_checks": _quality_checks(language),
        "limitations": _limitations(language),
    }


def render_fix_pack_markdown(pack: FixPack) -> str:
    """Render a portable Markdown worksheet for the buyer."""
    language = pack["language"]
    lines = [
        "# AEOS Fix Pack",
        "",
        "Paquete de implementación basado solo en hallazgos confirmados."
        if language == "es"
        else "Implementation pack based only on confirmed findings.",
        "",
    ]
    for index, page in enumerate(pack["pages"], start=1):
        lines.extend(
            [
                f"## {index}. {page['url']}",
                "",
                f"**{page['finding']}**",
                "",
                f"Evidence: {page['evidence']}",
                "",
                "**Title template**" if language == "en" else "**Plantilla de título**",
                "",
                f"`{page['title_template']}`",
                "",
                "**Meta description template**"
                if language == "en"
                else "**Plantilla de meta descripción**",
                "",
                f"`{page['description_template']}`",
                "",
                "**Implementation**" if language == "en" else "**Implementación**",
                "",
                *[f"- {step}" for step in page["implementation_steps"]],
                "",
            ]
        )
    lines.extend(
        [
            "## Quality checks" if language == "en" else "## Comprobaciones finales",
            "",
            *[f"- {item}" for item in pack["quality_checks"]],
            "",
            "## Limits" if language == "en" else "## Límites",
            "",
            *[f"- {item}" for item in pack["limitations"]],
            "",
        ]
    )
    return "\n".join(lines)


def _localized(value: object, language: str) -> str:
    if isinstance(value, Mapping):
        selected = value.get(language) or value.get("es")
        return selected if isinstance(selected, str) else ""
    return value if isinstance(value, str) else ""


def _is_actionable_finding(title: str) -> bool:
    normalized = title.casefold()
    return any(
        marker in normalized
        for marker in (
            "repeated titles",
            "repeated metadata",
            "títulos o descripciones repetidos",
            "títulos o meta descripciones repetidos",
            "missing metadata",
            "metadatos confirmados",
            "falta el encabezado h1",
            "missing h1",
        )
    )


def _title_template(language: str) -> str:
    if language == "en":
        return "{{ page-specific service or topic }} | {{ verified business name }}"
    return "{{ servicio o tema específico de esta página }} | {{ nombre comercial verificado }}"


def _description_template(language: str) -> str:
    if language == "en":
        return (
            "{{ what this page actually offers }}. "
            "{{ location or audience, only if confirmed for this page }}. "
            "{{ accurate next step or contact option }}."
        )
    return (
        "{{ qué ofrece realmente esta página }}. "
        "{{ ubicación o público, solo si está confirmado para esta página }}. "
        "{{ siguiente paso o contacto real }}."
    )


def _implementation_steps(language: str) -> list[str]:
    if language == "en":
        return [
            "Open this exact page in the website CMS and edit its SEO title and meta description.",
            "Replace every placeholder only with facts visible on this page or confirmed by the owner.",
            "Save, publish, and clear the site's cache if the CMS uses one.",
            "Run the free AEOS review again after the public page updates.",
        ]
    return [
        "Abre esta página exacta en el CMS del sitio y edita su título SEO y meta descripción.",
        "Sustituye cada marcador solo con datos visibles en esta página o confirmados por el propietario.",
        "Guarda, publica y limpia la caché del sitio si el CMS la utiliza.",
        "Vuelve a ejecutar la revisión gratis de AEOS cuando se actualice la página pública.",
    ]


def _quality_checks(language: str) -> list[str]:
    if language == "en":
        return [
            "Each page has a distinct title and description that match its own content.",
            "No placeholder remains in the published metadata.",
            "The page still has one clear, content-matching H1.",
            "Recheck the published URLs; AEOS reports observed HTML/DOM only and does not promise search ranking changes.",
        ]
    return [
        "Cada página tiene un título y una descripción distintos que corresponden a su contenido.",
        "No queda ningún marcador sin completar en los metadatos publicados.",
        "La página conserva un H1 claro y coherente con su contenido.",
        "Vuelve a revisar las URLs publicadas; AEOS informa HTML/DOM observado y no promete cambios de posicionamiento.",
    ]


def _limitations(language: str) -> list[str]:
    if language == "en":
        return [
            "Draft copy is intentionally a fill-in template because the inspection does not verify business claims or page intent.",
            "No CMS access or changes are included; the owner or web administrator publishes the edits.",
            "Inconclusive findings are excluded until a complete inspection confirms them.",
        ]
    return [
        "El texto es una plantilla para completar porque la inspección no verifica afirmaciones del negocio ni la intención de cada página.",
        "No incluye acceso ni cambios al CMS; el propietario o administrador web publica las ediciones.",
        "Los hallazgos inconclusos se excluyen hasta que una inspección completa los confirme.",
    ]
