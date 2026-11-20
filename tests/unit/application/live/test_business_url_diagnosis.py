from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

import pytest

from aeos.application.live.business_url_diagnosis import (
    BusinessURLPlatform,
    build_business_url_diagnosis_report,
    classify_business_url,
)
from aeos.live.domain.evidence import EvidenceKind
from aeos.live.domain.location_candidate import (
    LocationCandidate,
    LocationType,
    ServiceCandidate,
    VerificationStatus,
)
from aeos.live.adapters.website_inspector import (
    DOMRenderer,
    FetchResponse,
    RenderedDOM,
    RenderedDOMOutcome,
    WebsiteInspectionError,
    WebsiteInspector,
)
from aeos.live.domain.website_inspection import (
    WebsiteInspectionDetails,
    WebsitePage,
)
from aeos.live.ports.website import WebsiteInspectionResult
from aeos.live import real_demo
from aeos.live import url_diagnosis


def _inspection(url: str) -> WebsiteInspectionResult:
    return WebsiteInspectionResult(
        signals=(),
        evidence=(),
        details=WebsiteInspectionDetails(
            requested_url=url,
            final_url=url,
            inspected_at=datetime(2026, 11, 9, tzinfo=timezone.utc),
            business_name="Example Business",
            phone="555-0100",
            email=None,
            address=None,
            robots_status="found",
            robots_sitemaps=("https://example.com/sitemap.xml",),
            sitemap_urls=("https://example.com/sitemap.xml",),
            structured_data_types=("WebSite",),
        ),
        pages=(
            WebsitePage(
                url=url,
                status_code=200,
                title=None,
                meta_description=None,
                h1_headings=(),
                h2_headings=("Services",),
                link_texts=("Contact",),
                link_urls=("https://example.com/contact",),
            ),
        ),
    )


def _cmimbela_offline_inspection_fixture() -> WebsiteInspectionResult:
    # Synthetic HTML-derived candidates for the prompt regression; the saved
    # Windows report itself has no HTML because DNS resolution failed.
    home = "https://cmimbelacleaningllc.com/"
    services_page = "https://cmimbelacleaningllc.com/services"
    areas_page = "https://cmimbelacleaningllc.com/service-areas"
    claims = (
        ServiceCandidate(
            service="Interior/residential cleaning",
            source_url=services_page,
            supporting_text="Interior/residential cleaning",
            evidence_classification=EvidenceKind.REPORTED,
            confidence=0.9,
            verification_status=VerificationStatus.WEBSITE_REPORTED,
            evidence_id="cmimbela-service",
        ),
    )
    areas = tuple(
        LocationCandidate(
            city=city,
            state="Florida",
            postal_code=None,
            location_type=LocationType.EXPLICITLY_SERVED_CITY,
            source_url=areas_page,
            supporting_text=f"Service area: {city}, Florida",
            evidence_classification=EvidenceKind.REPORTED,
            confidence=0.9,
            verification_status=VerificationStatus.WEBSITE_REPORTED,
            evidence_id=f"cmimbela-area-{city.casefold()}",
        )
        for city in ("Sarasota", "Bradenton")
    )
    return WebsiteInspectionResult(
        signals=(),
        evidence=(),
        details=WebsiteInspectionDetails(
            requested_url=home,
            final_url=home,
            inspected_at=datetime(2026, 11, 9, tzinfo=timezone.utc),
            robots_status="found",
        ),
        pages=(
            WebsitePage(
                url=home,
                status_code=200,
                title="CMIMBELA",
                meta_description=None,
                h1_headings=("Interior cleaning",),
            ),
            WebsitePage(
                url=services_page,
                status_code=200,
                title="Services",
                meta_description="Interior/residential cleaning in Florida.",
                h1_headings=("Services",),
            ),
            WebsitePage(
                url=areas_page,
                status_code=200,
                title="Service areas",
                meta_description="Areas served by CMIMBELA.",
                h1_headings=("Where we serve",),
            ),
        ),
        locations=areas,
        services=claims,
    )


def _construction_omissions_offline_fixture() -> WebsiteInspectionResult:
    # Offline reproduction of the 2026-11-10 23:35Z report's known facts.
    # Non-home routes and test-only values are synthetic; no live site is fetched.
    root = "https://constructionnationgroup.com/"
    other_pages = tuple(
        f"https://constructionnationgroup.com/offline-page-{number}"
        for number in range(2, 7)
    )
    return WebsiteInspectionResult(
        signals=(),
        evidence=(),
        details=WebsiteInspectionDetails(
            requested_url=root,
            final_url=root,
            inspected_at=datetime(2026, 11, 10, 23, 35, tzinfo=timezone.utc),
            robots_status="found",
            structured_data_types=("HomeAndConstructionBusiness",),
        ),
        pages=(
            WebsitePage(
                url=root,
                status_code=200,
                title="Synthetic home title",
                meta_description="Synthetic home description",
                h1_headings=("Home Remodeling Experts in DFW",),
                inspection_method="HTTP_AND_RENDERED_DOM",
                rendered_dom_error="render_timeout",
                rendered_dom_error_message="Synthetic partial DOM for offline regression.",
            ),
            WebsitePage(
                url=other_pages[0],
                status_code=200,
                title="Synthetic page 2 title",
                meta_description=None,
                h1_headings=(),
            ),
            WebsitePage(
                url=other_pages[1],
                status_code=200,
                title="Synthetic page 3 title",
                meta_description=None,
                h1_headings=("Synthetic page 3 H1",),
            ),
            WebsitePage(
                url=other_pages[2],
                status_code=200,
                title="Synthetic page 4 title",
                meta_description=None,
                h1_headings=("Synthetic page 4 H1",),
            ),
            WebsitePage(
                url=other_pages[3],
                status_code=200,
                title="Synthetic page 5 title",
                meta_description=None,
                h1_headings=("Synthetic page 5 H1",),
            ),
            WebsitePage(
                url=other_pages[4],
                status_code=200,
                title="Synthetic page 6 title",
                meta_description="Synthetic description for page 6",
                h1_headings=("Synthetic page 6 H1",),
            ),
        ),
    )


def _simulated_inspection(
    html_by_path: dict[str, str],
    rendered_by_path: dict[str, RenderedDOM] | None = None,
    render_error: str | None = None,
) -> WebsiteInspectionResult:
    root = "https://rendered.example/"
    page_urls = tuple(root.rstrip("/") + path for path in html_by_path if path != "/")
    sitemap = (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{url}</loc></url>" for url in page_urls)
        + "</urlset>"
    ).encode()
    html = {path: value.encode() for path, value in html_by_path.items()}

    def fetch(url: str, timeout: int, byte_limit: int, root_host: str) -> FetchResponse:
        path = urlsplit(url).path or "/"
        if path == "/robots.txt":
            return FetchResponse(b"User-agent: *\nAllow: /\n", 200, url)
        if path == "/sitemap.xml":
            return FetchResponse(sitemap, 200, url, "application/xml")
        body = html.get(path)
        if body is None:
            return FetchResponse(b"", 404, url, "text/plain")
        return FetchResponse(body, 200, url, "text/html")

    renderer: DOMRenderer | None = None
    if rendered_by_path is not None:

        def render(
            urls: tuple[str, ...], host: str, timeout: int
        ) -> dict[str, RenderedDOMOutcome]:
            return {
                root.rstrip("/") + path: RenderedDOMOutcome(dom)
                for path, dom in rendered_by_path.items()
            }

        renderer = render
    elif render_error is not None:

        def unavailable_renderer(
            urls: tuple[str, ...], host: str, timeout: int
        ) -> dict[str, RenderedDOMOutcome]:
            raise WebsiteInspectionError(
                f"Simulated {render_error}: page capture diagnostic details.",
                category=render_error,
            )

        renderer = unavailable_renderer
    return WebsiteInspector(transport=fetch, renderer=renderer).inspect(root)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://cmimbelacleaningllc.com/", BusinessURLPlatform.WEBSITE),
        (
            "https://www.google.com/maps/place/Example",
            BusinessURLPlatform.GOOGLE_BUSINESS_PROFILE,
        ),
        ("https://www.facebook.com/p/example/", BusinessURLPlatform.FACEBOOK),
        ("https://www.instagram.com/example/", BusinessURLPlatform.INSTAGRAM),
        ("https://www.linkedin.com/company/example/", BusinessURLPlatform.LINKEDIN),
    ],
)
def test_classifies_business_urls_without_fetching(
    url: str, expected: BusinessURLPlatform
) -> None:
    assert classify_business_url(url).platform is expected


def test_website_diagnosis_has_evidenced_prioritized_findings() -> None:
    url = "https://example.com/"
    report = build_business_url_diagnosis_report(
        url,
        inspection=_inspection(url),
        inspection_status="SUCCEEDED",
        inspected_at="2026-11-09T00:00:00+00:00",
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    findings = cast(list[dict[str, object]], diagnosis["findings"])
    pending = cast(list[dict[str, object]], diagnosis["pending_verifications"])

    assert findings == []
    assert 1 <= len(pending) <= 3
    all_items = [*findings, *pending]
    assert [item["priority"] for item in findings] == sorted(
        item["priority"] for item in findings
    )
    for item in all_items:
        evidence = cast(dict[str, object], item["evidence"])
        why = cast(dict[str, object], item["why_it_may_matter"])
        assert evidence["classification"] == "OBSERVED"
        assert evidence["source_url"] == url
        assert evidence["excerpt"]
        assert item["observation_status"] == "INCONCLUSIVE"
        assert why["classification"] == "INFERRED"
        assert item["action"]
        assert item["copyable_prompt"]
        assert "verifica" in str(item["copyable_prompt"]).casefold()
        assert "no agregues" in str(item["copyable_prompt"]).casefold()

    signals = cast(dict[str, object], diagnosis["observed_signals"])
    assert signals["structured_data_types"] == ["WebSite"]
    assert signals["sitemaps"] == ["https://example.com/sitemap.xml"]
    page = cast(dict[str, object], cast(list[object], signals["pages"])[0])
    assert page["link_urls"] == ["https://example.com/contact"]
    assert not any(
        key in json.dumps(report).casefold()
        for key in ("search_position", "traffic_loss", "customers_lost")
    )
    assert "requieren acceso autorizado" in " ".join(
        cast(list[str], diagnosis["not_reviewed"])
    )
    markdown = url_diagnosis.render_business_url_diagnosis_markdown(report)
    assert "HTML_ONLY" in markdown
    assert "DOM renderizado no disponible" in markdown


def test_cmimbela_copyable_prompt_stays_specific_to_the_finding() -> None:
    url = "https://cmimbelacleaningllc.com/"
    report = build_business_url_diagnosis_report(
        url,
        inspection=_cmimbela_offline_inspection_fixture(),
        inspection_status="SUCCEEDED",
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    pending = cast(list[dict[str, object]], diagnosis["pending_verifications"])
    prompt = "\n".join(str(item["copyable_prompt"]) for item in pending)

    assert "cmimbelacleaningllc.com/" in prompt
    assert "Sarasota" not in prompt
    assert "Bradenton" not in prompt
    assert "Interior/residential cleaning" not in prompt
    assert len(prompt) < 500
    signals = cast(dict[str, object], diagnosis["observed_signals"])
    website_claims = cast(list[dict[str, object]], signals["website_claims"])
    assert all(item["classification"] == "WEBSITE_REPORTED" for item in website_claims)
    assert all(item["source_url"] and item["evidence"] for item in website_claims)


def test_construction_20261110_report_separates_confirmed_and_pending_fields() -> None:
    url = "https://constructionnationgroup.com/"
    report = build_business_url_diagnosis_report(
        url,
        inspection=_construction_omissions_offline_fixture(),
        inspection_status="SUCCEEDED",
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    findings = cast(list[dict[str, object]], diagnosis["findings"])
    pending = cast(list[dict[str, object]], diagnosis["pending_verifications"])
    rendered = url_diagnosis.render_business_url_diagnosis_markdown(report)

    assert findings == []
    assert len(pending) == 2
    assert all(item["observation_status"] == "INCONCLUSIVE" for item in pending)
    metadata = next(
        item for item in pending if "meta descripciones" in str(item["title"])
    )
    metadata_evidence = cast(dict[str, object], metadata["evidence"])
    metadata_sources = cast(list[dict[str, object]], metadata_evidence["sources"])
    metadata_urls = {str(item["source_url"]) for item in metadata_sources}
    assert len(metadata_urls) == 4
    assert "https://constructionnationgroup.com/" not in metadata_urls
    assert all("offline-page-" in url for url in metadata_urls)
    assert "meta description no encontrada en HTML recibido" in str(
        metadata_evidence["excerpt"]
    )
    assert "ausencia en DOM sin verificar (HTML_ONLY)" in str(
        metadata_evidence["excerpt"]
    )
    assert "Verifica en un DOM completo" in str(metadata["copyable_prompt"])
    assert all(url in str(metadata["copyable_prompt"]) for url in metadata_urls)
    h1_verification = next(item for item in pending if "H1" in str(item["title"]))
    h1_evidence = cast(dict[str, object], h1_verification["evidence"])
    h1_sources = cast(list[dict[str, object]], h1_evidence["sources"])
    assert "https://constructionnationgroup.com/" not in {
        str(item["source_url"]) for item in h1_sources
    }
    assert "Home Remodeling Experts in DFW" not in str(
        h1_verification["copyable_prompt"]
    )
    assert "## Hallazgos confirmados" in rendered
    assert "## Verificaciones pendientes (INCONCLUSIVE)" in rendered
    assert "Prompt de corrección:" not in rendered
    assert "Prompt de verificación:" in rendered
    signals = cast(dict[str, object], diagnosis["observed_signals"])
    pages = cast(list[dict[str, object]], signals["pages"])
    assert len(pages) == 6
    assert sum(not page["meta_description"] for page in pages) == 4
    assert [page["inspection_method"] for page in pages].count("HTML_ONLY") == 5
    homepage = pages[0]
    assert homepage["inspection_method"] == "HTTP_AND_RENDERED_DOM"
    assert homepage["h1"] == ["Home Remodeling Experts in DFW"]
    homepage_dom = cast(dict[str, object], homepage["rendered_dom"])
    assert homepage_dom["status"] == "PARTIAL"
    assert "h1" not in homepage_dom["fields_observed"]
    website = cast(dict[str, object], report["website_inspection"])
    assert website["inspected_at"] == "2026-11-10T23:35:00+00:00"
    assert "causaron pérdida de posiciones" not in rendered.casefold()
    assert "HTML_ONLY" in rendered


def test_rendered_dom_finds_content_injected_after_the_html_response() -> None:
    inspection = _simulated_inspection(
        {"/": "<html><head></head><body><div id='app'></div></body></html>"},
        {
            "/": RenderedDOM(
                title="Rendered home",
                meta_description="Rendered description",
                h1_headings=("Rendered heading",),
                h2_headings=("Rendered subheading",),
                link_texts=("Services",),
                link_urls=("https://rendered.example/services/airbnb-cleaning",),
            )
        },
    )
    report = build_business_url_diagnosis_report(
        "https://rendered.example/",
        inspection=inspection,
        inspection_status="SUCCEEDED",
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    signals = cast(dict[str, object], diagnosis["observed_signals"])
    page = cast(dict[str, object], cast(list[object], signals["pages"])[0])
    html_received = cast(dict[str, object], page["html_received"])
    rendered_dom = cast(dict[str, object], page["rendered_dom"])
    findings = cast(list[dict[str, object]], diagnosis["findings"])

    assert page["inspection_method"] == "HTTP_AND_RENDERED_DOM"
    assert page["h1"] == []
    assert html_received["title"] is None
    assert html_received["meta_description"] is None
    assert rendered_dom["h1"] == ["Rendered heading"]
    assert rendered_dom["title"] == "Rendered home"
    assert rendered_dom["meta_description"] == "Rendered description"
    assert page["h2"] == ["Rendered subheading"]
    assert page["link_urls"] == ["https://rendered.example/services/airbnb-cleaning"]
    assert not any("H1 ausente" in str(item["title"]) for item in findings)
    assert not any("Metadatos ausentes" in str(item["title"]) for item in findings)


def test_missing_fields_in_both_views_are_confirmed_by_the_rendered_dom() -> None:
    inspection = _simulated_inspection(
        {"/": "<html><head></head><body><div id='app'></div></body></html>"},
        {"/": RenderedDOM(title=None, meta_description=None)},
    )
    report = build_business_url_diagnosis_report(
        "https://rendered.example/",
        inspection=inspection,
        inspection_status="SUCCEEDED",
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    findings = cast(list[dict[str, object]], diagnosis["findings"])
    metadata = next(
        item for item in findings if "Metadatos ausentes" in str(item["title"])
    )
    h1 = next(item for item in findings if "H1 ausente" in str(item["title"]))

    assert metadata["observation_status"] == "OBSERVED"
    assert h1["observation_status"] == "OBSERVED"
    assert "ausente en HTML recibido y DOM renderizado" in str(
        cast(dict[str, object], metadata["evidence"])["excerpt"]
    )
    assert "ausente en HTML recibido y DOM renderizado" in str(
        cast(dict[str, object], h1["evidence"])["excerpt"]
    )


def test_correction_prompts_exclude_html_only_pages_pending_dom_verification() -> None:
    root = "https://rendered.example/"
    pending_url = "https://rendered.example/pending"
    inspection = WebsiteInspectionResult(
        signals=(),
        evidence=(),
        details=WebsiteInspectionDetails(
            requested_url=root,
            final_url=root,
            inspected_at=datetime(2026, 11, 10, tzinfo=timezone.utc),
        ),
        pages=(
            WebsitePage(
                url=root,
                status_code=200,
                title="Home",
                inspection_method="HTTP_AND_RENDERED_DOM",
                rendered_title="Home",
            ),
            WebsitePage(
                url=pending_url,
                status_code=200,
                title="Pending",
                inspection_method="HTML_ONLY",
            ),
        ),
    )
    report = build_business_url_diagnosis_report(
        "https://rendered.example/",
        inspection=inspection,
        inspection_status="SUCCEEDED",
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    findings = cast(list[dict[str, object]], diagnosis["findings"])
    pending = cast(list[dict[str, object]], diagnosis["pending_verifications"])

    confirmed_metadata = next(
        item for item in findings if "Metadatos ausentes" in str(item["title"])
    )
    pending_metadata = next(
        item for item in pending if "meta descripciones" in str(item["title"])
    )
    confirmed_sources = cast(
        list[dict[str, object]],
        cast(dict[str, object], confirmed_metadata["evidence"])["sources"],
    )
    pending_sources = cast(
        list[dict[str, object]],
        cast(dict[str, object], pending_metadata["evidence"])["sources"],
    )
    assert [item["source_url"] for item in confirmed_sources] == [
        "https://rendered.example/"
    ]
    assert [item["source_url"] for item in pending_sources] == [
        "https://rendered.example/pending"
    ]
    assert "rendered.example/pending" not in str(confirmed_metadata["copyable_prompt"])
    assert "rendered.example/pending" in str(pending_metadata["copyable_prompt"])
    assert pending_metadata["observation_status"] == "INCONCLUSIVE"


def test_rendered_duplicate_metadata_keeps_each_affected_url() -> None:
    shared_html = (
        "<html><head><title>Same title</title>"
        "<meta name='description' content='Same description'></head>"
        "<body><h1>Page heading</h1></body></html>"
    )
    inspection = _simulated_inspection(
        {"/": shared_html, "/services/airbnb-cleaning": shared_html},
        {
            "/": RenderedDOM("Same title", "Same description", ("Home",)),
            "/services/airbnb-cleaning": RenderedDOM(
                "Same title", "Same description", ("Airbnb Cleaning",)
            ),
        },
    )
    report = build_business_url_diagnosis_report(
        "https://rendered.example/",
        inspection=inspection,
        inspection_status="SUCCEEDED",
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    duplicate = next(
        item
        for item in cast(list[dict[str, object]], diagnosis["findings"])
        if "duplicados" in str(item["title"])
    )
    evidence = cast(dict[str, object], duplicate["evidence"])
    urls = {
        str(cast(dict[str, object], item)["source_url"])
        for item in cast(list[object], evidence["sources"])
    }

    assert urls == {
        "https://rendered.example/",
        "https://rendered.example/services/airbnb-cleaning",
    }
    assert "DOM renderizado" in str(evidence["excerpt"])
    prompt = str(duplicate["copyable_prompt"])
    assert len(prompt) < 500
    assert "airbnb-cleaning" in prompt
    assert "Same title" in prompt


def test_html_only_does_not_confirm_rendered_absence() -> None:
    inspection = _simulated_inspection(
        {"/": "<html><head></head><body></body></html>"},
        render_error="browser_unavailable",
    )
    report = build_business_url_diagnosis_report(
        "https://rendered.example/",
        inspection=inspection,
        inspection_status="SUCCEEDED",
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    signals = cast(dict[str, object], diagnosis["observed_signals"])
    page = cast(dict[str, object], cast(list[object], signals["pages"])[0])
    rendered_dom = cast(dict[str, object], page["rendered_dom"])
    findings = cast(list[dict[str, object]], diagnosis["findings"])
    markdown = url_diagnosis.render_business_url_diagnosis_markdown(report)
    website = cast(dict[str, object], report["website_inspection"])
    website_pages = cast(list[dict[str, object]], website["paginas_revisadas"])

    assert page["inspection_method"] == "HTML_ONLY"
    assert rendered_dom["status"] == "HTML_ONLY"
    assert rendered_dom["error_category"] == "browser_unavailable"
    assert rendered_dom["error_message"] == (
        "Simulated browser_unavailable: page capture diagnostic details."
    )
    assert website_pages[0]["metodo_inspeccion"] == "HTML_ONLY"
    website_dom = cast(dict[str, object], website_pages[0]["dom_renderizado"])
    assert website_dom["status"] == "HTML_ONLY"
    assert website_dom["error_message"] == rendered_dom["error_message"]
    assert (
        website_pages[0]["dom_renderizado_error_mensaje"]
        == rendered_dom["error_message"]
    )
    pending = cast(list[dict[str, object]], diagnosis["pending_verifications"])
    assert findings == []
    assert pending
    assert all(item["observation_status"] == "INCONCLUSIVE" for item in pending)
    assert "no comprobado (HTML_ONLY)" in markdown
    assert "ausente en HTML recibido y DOM renderizado" not in markdown


def test_partial_rendered_dom_reports_state_and_observed_fields() -> None:
    inspection = _simulated_inspection(
        {"/": "<html><head></head><body></body></html>"},
        rendered_by_path={
            "/": RenderedDOM(
                title="DOM title",
                meta_description=None,
                h1_headings=("Observed H1",),
            )
        },
    )
    partial_page = replace(
        inspection.pages[0],
        rendered_dom_error="render_timeout",
        rendered_dom_error_message=(
            "Partial DOM after navigation timeout; fields observed: title, h1."
        ),
    )
    inspection = replace(inspection, pages=(partial_page,))

    report = build_business_url_diagnosis_report(
        "https://rendered.example/",
        inspection=inspection,
        inspection_status="SUCCEEDED",
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    signals = cast(dict[str, object], diagnosis["observed_signals"])
    page = cast(dict[str, object], cast(list[object], signals["pages"])[0])
    rendered_dom = cast(dict[str, object], page["rendered_dom"])
    markdown = url_diagnosis.render_business_url_diagnosis_markdown(report)

    assert rendered_dom["status"] == "PARTIAL"
    assert rendered_dom["fields_observed"] == ["title", "h1"]
    assert rendered_dom["h1"] == ["Observed H1"]
    assert "sin dato observado en DOM parcial (indeterminado)" in markdown
    assert "ausente en HTML recibido y DOM renderizado" not in markdown


@pytest.mark.parametrize(
    "render_error",
    ["render_timeout", "render_time_budget_exhausted", "external_resources_blocked"],
)
def test_dom_render_failures_remain_inconclusive(
    render_error: str,
) -> None:
    inspection = _simulated_inspection(
        {"/": "<html><head></head><body></body></html>"},
        render_error=render_error,
    )

    page = inspection.pages[0]
    assert page.inspection_method == "HTML_ONLY"
    assert page.rendered_dom_error == render_error
    assert page.rendered_dom_error_message == (
        f"Simulated {render_error}: page capture diagnostic details."
    )
    assert not inspection.locations
    assert not inspection.services


@pytest.mark.parametrize(
    "url",
    [
        "https://cmimbelacleaningllc.com/",
        "https://constructionnationgroup.com/",
    ],
)
def test_windows_dns_failure_regression_reports_zero_page_coverage(url: str) -> None:
    report = build_business_url_diagnosis_report(
        url,
        inspection=None,
        inspection_status="FAILED",
        failure_category="dns_error",
        failure_stage="dns_resolution",
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    rendered = url_diagnosis.render_business_url_diagnosis_markdown(report)

    assert diagnosis["findings"] == []
    assert "dns_resolution" in rendered
    assert "no se recibió HTML" in rendered
    assert "páginas recibidas: ninguna" not in rendered
    assert "0 páginas recibidas" in rendered
    assert "comprobaciones completadas: ninguna" in rendered


def test_zero_findings_report_completed_checks_and_coverage() -> None:
    url = "https://example.com/"
    inspection = WebsiteInspectionResult(
        signals=(),
        evidence=(),
        details=WebsiteInspectionDetails(
            requested_url=url,
            final_url=url,
            inspected_at=datetime(2026, 11, 9, tzinfo=timezone.utc),
            structured_data_types=("Organization",),
        ),
        pages=(
            WebsitePage(
                url=url,
                status_code=200,
                title="Example",
                meta_description="Example organization.",
                h1_headings=("Example",),
            ),
        ),
    )
    report = build_business_url_diagnosis_report(
        url, inspection=inspection, inspection_status="SUCCEEDED"
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    assert diagnosis["findings"] == []
    markdown = url_diagnosis.render_business_url_diagnosis_markdown(report)
    assert "No se detectaron problemas" in markdown
    assert "duplicados de títulos y meta descripciones" in markdown
    assert "páginas recibidas: 1" in markdown


def test_noindex_pages_are_excluded_from_missing_metadata_findings() -> None:
    url = "https://example.com/noindex"
    inspection = WebsiteInspectionResult(
        signals=(),
        evidence=(),
        details=WebsiteInspectionDetails(
            requested_url=url,
            final_url=url,
            inspected_at=datetime(2026, 11, 9, tzinfo=timezone.utc),
            structured_data_types=("Organization",),
        ),
        pages=(
            WebsitePage(
                url=url,
                status_code=200,
                robots_directives=("noindex", "follow"),
            ),
        ),
    )
    report = build_business_url_diagnosis_report(
        url, inspection=inspection, inspection_status="SUCCEEDED"
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    assert diagnosis["findings"] == []
    markdown = url_diagnosis.render_business_url_diagnosis_markdown(report)
    assert "0 candidatas potencialmente indexables" in markdown
    assert "1 con noindex" in markdown


def test_social_profile_requires_owner_evidence_without_business_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def should_not_inspect(*_args: object, **_kwargs: object) -> None:
        pytest.fail("social profile inspection must not be attempted")

    monkeypatch.setattr(url_diagnosis, "inspect_business_website", should_not_inspect)
    result = url_diagnosis.run_business_url_diagnosis_command(
        "https://www.facebook.com/p/example-hvac-company/",
        output_directory=tmp_path,
    )
    assert result == 0
    output = capsys.readouterr().out
    assert "Hallazgos confirmados: 0" in output
    assert "Verificaciones pendientes (INCONCLUSIVE): 0" in output
    report_path = next(tmp_path.glob("*.json"))
    report = cast(
        dict[str, object], json.loads(report_path.read_text(encoding="utf-8"))
    )
    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    context = cast(dict[str, object], diagnosis["business_context"])
    assert diagnosis["platform"] == "FACEBOOK"
    assert diagnosis["inspection_status"] == "OWNER_EVIDENCE_REQUIRED"
    assert context["status"] == "NO_PROFILE_PROVIDED"
    assert context["reported"] == []
    assert context["digital_presence"] == {}
    markdown = next(tmp_path.glob("*.md")).read_text(encoding="utf-8")
    assert "No se hizo scraping" in markdown
    assert "No se contactó" in markdown


def test_diagnosis_cli_route_never_enters_market_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Path, Path | None]] = []

    def diagnose(
        url: str, *, output_directory: Path, profile_path: Path | None = None
    ) -> int:
        calls.append((url, output_directory, profile_path))
        return 0

    monkeypatch.setattr(real_demo, "run_business_url_diagnosis_command", diagnose)
    assert (
        real_demo.main(
            [
                "--diagnose-url",
                "https://constructionnationgroup.com/",
                "--output-dir",
                "out",
            ]
        )
        == 0
    )
    assert calls == [("https://constructionnationgroup.com/", Path("out"), None)]
