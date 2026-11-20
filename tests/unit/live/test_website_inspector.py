"""Offline fixtures for the bounded website inspection adapter."""

import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

import aeos.live.adapters.website_inspector as website_inspector
from aeos.live.adapters.website_inspector import (
    FetchResponse,
    PlaywrightDOMRenderer,
    Transport,
    WebsiteInspectionError,
    WebsiteInspector,
)
from aeos.live.domain.evidence import EvidenceKind
from aeos.live.domain.location_candidate import LocationType, VerificationStatus
from aeos.live.ports.website import WebsiteInspectionResult

FIXTURES = Path(__file__).parent / "fixtures" / "website"
BASE = "https://sample-cleaning.example"


def _fixture_transport(
    overrides: dict[str, bytes] | None = None,
) -> tuple[Transport, list[str]]:
    data = {
        "/": (FIXTURES / "home.html").read_bytes(),
        "/robots.txt": (FIXTURES / "robots.txt").read_bytes(),
        "/sitemap-index.xml": (FIXTURES / "sitemap-index.xml").read_bytes(),
        "/sitemap-pages.xml": (FIXTURES / "sitemap-pages.xml").read_bytes(),
        "/services": (FIXTURES / "services.html").read_bytes(),
        "/service-areas": (FIXTURES / "service-areas.html").read_bytes(),
        "/contact": (FIXTURES / "contact.html").read_bytes(),
    }
    if overrides:
        data.update(overrides)
    requested: list[str] = []

    def fetch(url: str, timeout: int, limit: int, root_host: str) -> FetchResponse:
        assert timeout == 10
        assert limit == 2_000_000
        assert root_host == "sample-cleaning.example"
        path = urlsplit(url).path or "/"
        requested.append(path)
        body = data.get(path)
        if body is None:
            return FetchResponse(b"", 404, url, "text/plain")
        return FetchResponse(body, 200, url, "text/html")

    return fetch, requested


def _inspector(
    overrides: dict[str, bytes] | None = None,
) -> tuple[WebsiteInspector, list[str]]:
    transport, requested = _fixture_transport(overrides)
    return WebsiteInspector(transport=transport), requested


def _inspect_pages(
    home: bytes,
    pages: dict[str, bytes],
    *,
    sitemap_paths: tuple[str, ...] = (),
) -> tuple[WebsiteInspectionResult, list[str]]:
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{BASE}{path}</loc></url>" for path in sitemap_paths)
        + "</urlset>"
    ).encode()
    overrides = {
        "/": home,
        "/sitemap-index.xml": FIXTURES.joinpath("sitemap-index.xml").read_bytes(),
        "/sitemap-pages.xml": sitemap,
        "/services": b"<h1>Services</h1>",
        "/service-areas": b"<h1>Service areas</h1>",
        "/contact": b"<h1>Contact</h1>",
        **pages,
    }
    inspector, requested = _inspector(overrides)
    return inspector.inspect(BASE), requested


def test_inspects_structured_business_data_services_and_multiple_areas() -> None:
    inspector, _ = _inspector()
    result = inspector.inspect(BASE + "/")

    assert result.details is not None
    assert result.details.business_name == "Sample Cleaning Company (Fictional)"
    assert result.details.phone == "+1-202-555-0100"
    assert result.details.email == "contact@sample-cleaning.example"
    assert (
        result.details.address == "100 Example Street, Sample City Four, Florida, 00000"
    )
    assert result.details.latitude == 27.12
    assert result.details.longitude == -82.45
    assert result.details.opening_hours == ("Mo-Fr 08:00-18:00",)
    assert result.details.same_as == ("https://www.facebook.com/sample-cleaning",)
    assert "CleaningService" in result.details.structured_data_types
    assert {page.title for page in result.pages} >= {
        "Services",
        "Service areas",
        "Contact",
    }

    address = next(
        item
        for item in result.locations
        if item.location_type is LocationType.BUSINESS_ADDRESS
    )
    assert (address.city, address.state, address.postal_code) == (
        "Sample City Four",
        "Florida",
        "00000",
    )
    areas = {
        item.city
        for item in result.locations
        if item.location_type
        in {LocationType.SERVICE_AREA, LocationType.EXPLICITLY_SERVED_CITY}
    }
    assert {
        "Sample City Two",
        "Sample City Three",
        "Sample City Four",
        "Sample City Five",
    } <= areas
    assert "and Sample City Five" not in areas
    assert "Sample City Four" in areas and address.city == "Sample City Four"
    assert any(item.service == "Deep cleaning" for item in result.services)
    assert any(item.service == "Office cleaning" for item in result.services)
    assert any(item.service == "Carpet cleaning" for item in result.services)
    assert all(item.evidence_id for item in result.services)
    assert "https://sample-cleaning.example/services" in result.pages[0].link_urls
    assert all(item.source_url.startswith(BASE) for item in result.locations)
    assert any(item.kind is EvidenceKind.REPORTED for item in result.evidence)
    assert not any(
        item.field == "geographic_reference" and "latitude" in str(item.value)
        for item in result.evidence
    )


def test_does_not_crawl_entire_site_and_respects_robots_restrictions() -> None:
    inspector, requested = _inspector()
    result = inspector.inspect(BASE)

    assert result.details is not None
    assert result.details.robots_status == "found"
    assert "Disallow: /private/" in result.details.robots_restrictions
    assert "/private/locations" not in requested
    assert len(result.pages) <= 20
    assert result.details.sitemap_urls


def test_playwright_dependency_missing_is_an_explicit_browser_unavailable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_dependency(module_name: str) -> object:
        raise ModuleNotFoundError(module_name)

    monkeypatch.setattr(website_inspector, "import_module", missing_dependency)

    with pytest.raises(WebsiteInspectionError) as failure:
        PlaywrightDOMRenderer()((BASE + "/",), "sample-cleaning.example", 10)

    assert failure.value.category == "browser_unavailable"
    assert "ModuleNotFoundError" in str(failure.value)


def test_playwright_browser_unavailable_keeps_the_complete_launch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch_error = "Chromium executable is missing at C:/cache/chromium/chrome.exe"

    class FakePlaywrightContext:
        def __enter__(self) -> object:
            def launch(**kwargs: object) -> object:
                raise RuntimeError(launch_error)

            return SimpleNamespace(chromium=SimpleNamespace(launch=launch))

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        website_inspector,
        "import_module",
        lambda _: SimpleNamespace(sync_playwright=FakePlaywrightContext),
    )
    with pytest.raises(WebsiteInspectionError) as failure:
        PlaywrightDOMRenderer()((BASE + "/",), "sample-cleaning.example", 10)

    assert failure.value.category == "browser_unavailable"
    assert "RuntimeError" in str(failure.value)
    assert launch_error in str(failure.value)


def test_playwright_browser_cache_uses_the_installed_profile_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    browser_cache = tmp_path / "profile" / "AppData" / "Local" / "ms-playwright"
    browser_cache.mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "profile"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "sandboxed-local-appdata"))
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)

    with website_inspector._playwright_browser_cache_environment():
        assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(
            browser_cache
        )
    assert "PLAYWRIGHT_BROWSERS_PATH" not in os.environ


def test_dom_request_policy_blocks_data_and_navigation_but_allows_required_get_assets() -> (
    None
):
    root = "sample-cleaning.example"

    assert (
        website_inspector._dom_request_block_reason(
            url="https://cdn.example/static/site.js",
            root_host=root,
            method="GET",
            resource_type="script",
            is_navigation=False,
        )
        is None
    )
    assert (
        website_inspector._dom_request_block_reason(
            url="https://cdn.example/static/site.js?email=user@example.com",
            root_host=root,
            method="GET",
            resource_type="script",
            is_navigation=False,
        )
        == "external_resources_blocked"
    )
    assert (
        website_inspector._dom_request_block_reason(
            url="https://cdn.example/static/site.css?version=2",
            root_host=root,
            method="GET",
            resource_type="stylesheet",
            is_navigation=False,
        )
        is None
    )
    assert (
        website_inspector._dom_request_block_reason(
            url=("https://fonts.example/css2?family=Roboto:wght@400;700&display=swap"),
            root_host=root,
            method="GET",
            resource_type="stylesheet",
            is_navigation=False,
        )
        is None
    )
    assert (
        website_inspector._dom_request_block_reason(
            url="https://api.example/content",
            root_host=root,
            method="GET",
            resource_type="fetch",
            is_navigation=False,
        )
        == "external_data_request_blocked"
    )
    assert (
        website_inspector._dom_request_block_reason(
            url="https://outside.example/",
            root_host=root,
            method="GET",
            resource_type="document",
            is_navigation=True,
        )
        == "external_navigation_blocked"
    )
    assert (
        website_inspector._dom_request_block_reason(
            url=f"https://{root}/submit",
            root_host=root,
            method="POST",
            resource_type="document",
            is_navigation=True,
        )
        == "non_get_request_blocked"
    )
    assert (
        website_inspector._dom_request_block_reason(
            url="https://tracker.example/pixel?data=page-content",
            root_host=root,
            method="GET",
            resource_type="image",
            is_navigation=False,
        )
        == "external_resources_blocked"
    )
    assert (
        website_inspector._dom_request_block_reason(
            url="https://cdn.example/fonts/site.woff2?user=123",
            root_host=root,
            method="GET",
            resource_type="font",
            is_navigation=False,
        )
        == "external_resources_blocked"
    )


def test_playwright_set_content_offline_smoke_captures_expected_fields() -> None:
    playwright_api = pytest.importorskip("playwright.sync_api")
    html = """<html><head><title>Offline smoke</title>
    <meta name='description' content='Local description'></head><body>
    <h1>Local heading</h1><a href='/next'>Local link</a></body></html>"""

    with website_inspector._playwright_browser_cache_environment():
        with playwright_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content(html, wait_until="domcontentloaded", timeout=5000)
                parsed = WebsiteInspector._parse_html(page.content().encode("utf-8"))
            finally:
                browser.close()

    assert "".join(parsed.title) == "Offline smoke"
    assert parsed.description == "Local description"
    assert parsed.h1 == ["Local heading"]
    assert parsed.links == ["/next"]


def test_follows_a_sitemap_index_and_prioritizes_relevant_pages() -> None:
    inspector, requested = _inspector()
    result = inspector.inspect(BASE)

    assert "/sitemap-index.xml" in requested
    assert "/sitemap-pages.xml" in requested
    assert "/services" in requested
    assert "/contact" in requested
    assert len(result.pages) <= 20
    assert requested.index("/robots.txt") < requested.index("/")


def test_robots_disallow_prevents_even_the_homepage_fetch() -> None:
    inspector, requested = _inspector({"/robots.txt": b"User-agent: *\nDisallow: /\n"})
    with pytest.raises(WebsiteInspectionError) as failure:
        inspector.inspect(BASE)
    assert failure.value.category == "robots_disallowed"
    assert failure.value.stage == "robots.txt"
    assert requested == ["/robots.txt"]


def test_without_structured_data_extracts_visible_contact_and_service_claims() -> None:
    html = b"""<html><head><title>Bright Home Cleaning</title></head><body>
    <h1>Home cleaning in Sample City Two, FL</h1>
    <p>Weekly house cleaning is available. Call (941) 555-0123 or
    email hello@example.com.</p><a href='/services'>Services</a></body></html>"""
    inspector, _ = _inspector(
        {
            "/": html,
            "/services": b"<h1>Deep cleaning</h1><p>Deep cleaning is offered.</p>",
            "/service-areas": b"<h1>Service areas</h1>",
            "/contact": b"<h1>Contact</h1>",
            "/sitemap-index.xml": b"",
            "/sitemap-pages.xml": b"",
        }
    )
    result = inspector.inspect(BASE)

    assert result.details is not None
    assert result.details.business_name == "Bright Home Cleaning"
    assert result.details.phone == "(941) 555-0123"
    assert result.details.email == "hello@example.com"
    assert result.details.address is None
    assert any(item.service == "Residential cleaning" for item in result.services)
    assert any(item.service == "Recurring house cleaning" for item in result.services)
    assert any(item.service == "Deep cleaning" for item in result.services)


def test_a_city_mention_is_not_promoted_to_a_confirmed_service_area() -> None:
    inspector, _ = _inspector()
    result = inspector.inspect(BASE)

    mentions = [
        item
        for item in result.locations
        if item.city == "Sample City One"
        and item.location_type is LocationType.CITY_MENTION
    ]
    assert mentions
    assert all(
        item.verification_status is VerificationStatus.WEBSITE_REPORTED
        for item in mentions
    )
    assert not any(
        item.city == "Sample City One"
        and item.location_type
        in {LocationType.SERVICE_AREA, LocationType.EXPLICITLY_SERVED_CITY}
        for item in result.locations
    )


def test_explicit_state_aliases_replace_placeholders_and_unknown_regions() -> None:
    home = b"""<html><head><title>Cleaning</title>
    <script type='application/ld+json'>
    {"@type":"LocalBusiness","name":"Test Cleaning",
     "address":{"@type":"PostalAddress","addressLocality":"Sarasota",
                "addressRegion":"FL","addressCountry":"US"},
     "areaServed":{"@type":"City","name":"Sample City Two",
                   "addressRegion":"Example Region"}}
    </script></head><body><h1>Cleaning</h1></body></html>"""
    result, _ = _inspect_pages(home, {})

    address = next(
        item
        for item in result.locations
        if item.location_type is LocationType.BUSINESS_ADDRESS
    )
    area = next(
        item
        for item in result.locations
        if item.location_type is LocationType.SERVICE_AREA
    )
    assert address.state == "Florida"
    assert area.city == "Sample City Two"
    assert area.state is None
    assert all(item.state != "Example Region" for item in result.locations)
    assert all(
        item.verification_status is VerificationStatus.WEBSITE_REPORTED
        for item in result.locations
    )


def test_mixed_city_and_neighborhood_list_keeps_types_and_page_provenance() -> None:
    home = b"""<html><head><title>Construction Nation</title></head><body>
    <a href="/service-areas">Area We Serve</a></body></html>"""
    service_areas = b"""<html><body><h2>Area We Serve</h2>
    <p>Plano, TX Los Rios, TX Treyburn, TX Cross Bend, TX Timber Brook, TX
    Hunters Glen, TX Richardson, TX Carriage Hill, TX Wind Meadow, TX
    Madison Estates, TX Dallas North Estates, TX Park Forest, TX.
    Welcome to Construction Nation Group.</p></body></html>"""
    result, requested = _inspect_pages(home, {"/service-areas": service_areas})

    assert "/service-areas" in requested
    explicit_cities = {
        item.city
        for item in result.locations
        if item.location_type is LocationType.EXPLICITLY_SERVED_CITY
    }
    neighborhoods = {
        item.city
        for item in result.locations
        if item.location_type is LocationType.NEIGHBORHOOD_MENTION
    }
    assert explicit_cities == {"Plano", "Richardson"}
    assert neighborhoods == {
        "Los Rios",
        "Treyburn",
        "Cross Bend",
        "Timber Brook",
        "Hunters Glen",
        "Carriage Hill",
        "Wind Meadow",
        "Madison Estates",
        "Dallas North Estates",
        "Park Forest",
    }
    assert not any(
        item.city in neighborhoods
        and item.location_type is not LocationType.NEIGHBORHOOD_MENTION
        for item in result.locations
    )
    area_candidates = [
        item
        for item in result.locations
        if item.location_type
        in {
            LocationType.EXPLICITLY_SERVED_CITY,
            LocationType.NEIGHBORHOOD_MENTION,
        }
    ]
    assert all(item.state == "Texas" for item in area_candidates)
    assert all(item.source_url == BASE + "/service-areas" for item in area_candidates)
    evidence = {item.evidence_id: item for item in result.evidence}
    assert all(
        evidence[item.evidence_id].source_url == item.source_url
        and evidence[item.evidence_id].kind is EvidenceKind.REPORTED
        and item.verification_status is VerificationStatus.WEBSITE_REPORTED
        for item in area_candidates
    )


def test_generic_headings_and_short_fragments_are_not_locations() -> None:
    home = b"""<html><head><title>Construction Nation</title></head><body>
    <a href="/service-areas">Service Areas</a></body></html>"""
    service_areas = b"""<html><body><h2>Area We Serve</h2>
    <p>Our Services Project Gallery, Tes, P, TX.</p></body></html>"""
    result, _ = _inspect_pages(home, {"/service-areas": service_areas})

    assert not result.locations


def test_remodeling_services_are_extracted_from_navigation_and_headings() -> None:
    home = b"""<html><head><title>Home Remodeling Experts in DFW</title>
    <script type='application/ld+json'>
    {"@type":"HomeAndConstructionBusiness","name":"Construction Nation Group",
     "address":{"@type":"PostalAddress","streetAddress":"704 Central Pkwy E suite 1220",
                "addressLocality":"Plano","addressRegion":"TX",
                "postalCode":"75074","addressCountry":"US"}}
    </script></head>
    <body><nav>
    <a href="/our-services">Our Services</a>
    <a href="/our-services">Home Remodeling</a>
    <a href="/our-services">Kitchen Remodeling</a>
    <a href="/our-services">Bathroom Remodeling</a>
    <a href="/our-services">Home Additions</a>
    <a href="/our-services">New Home Construction</a>
    <a href="/our-services">Pools</a>
    <a href="/our-services">Investors Flip</a>
    <a href="/gallery">Project Gallery &amp; Testimonials</a>
    </nav><h1>Home Remodeling Experts in DFW</h1>
    <h2>Serving the Entire DFW Metro Area</h2>
    <h2>Room Additions</h2><h2>Full Home Remodeling</h2></body></html>"""
    result, _ = _inspect_pages(home, {})

    services = {item.service for item in result.services}
    assert {
        "Home remodeling",
        "Full home remodeling",
        "Kitchen remodeling",
        "Bathroom remodeling",
        "Room additions",
        "Home additions",
        "New home construction",
        "Pools",
        "Investor flip projects",
    } <= services
    assert all(
        item.evidence_classification is EvidenceKind.REPORTED
        and item.verification_status is VerificationStatus.WEBSITE_REPORTED
        and item.source_url.startswith(BASE)
        for item in result.services
    )
    regional_area = next(
        item
        for item in result.locations
        if item.location_type is LocationType.REGIONAL_SERVICE_AREA
    )
    business_address = next(
        item
        for item in result.locations
        if item.location_type is LocationType.BUSINESS_ADDRESS
    )
    assert business_address.city == "Plano"
    assert business_address.state == "Texas"
    assert business_address.verification_status is VerificationStatus.WEBSITE_REPORTED
    assert business_address.source_url == BASE + "/"
    assert business_address.supporting_text == (
        "JSON-LD address: 704 Central Pkwy E suite 1220, Plano, Texas, 75074"
    )
    address_evidence = next(
        item
        for item in result.evidence
        if item.evidence_id == business_address.evidence_id
    )
    assert address_evidence.source_url == business_address.source_url
    assert address_evidence.excerpt == business_address.supporting_text
    assert not any(
        item.city == "Plano" and item.location_type is LocationType.CITY_MENTION
        for item in result.locations
    )
    assert regional_area.city == "DFW Metro Area"
    assert regional_area.state is None
    assert regional_area.verification_status is VerificationStatus.WEBSITE_REPORTED
    assert regional_area.source_url == BASE + "/"
    assert not any(
        "Project Gallery" in item.supporting_text for item in result.services
    )


def test_missing_address_and_contact_are_left_unknown() -> None:
    inspector, _ = _inspector(
        {
            "/": b"<html><title>Cleaning Co</title><body><h1>Cleaning</h1></body></html>",
            "/services": b"<h1>Services</h1>",
            "/service-areas": b"<h1>Service areas</h1>",
            "/contact": b"<h1>Contact</h1>",
            "/sitemap-index.xml": b"",
            "/sitemap-pages.xml": b"",
        }
    )
    result = inspector.inspect(BASE)
    assert result.details is not None
    assert result.details.address is None
    assert result.details.phone is None
    assert result.details.email is None


def test_explicitly_negated_service_is_not_reported_as_offered() -> None:
    inspector, _ = _inspector(
        {
            "/": b"<html><title>Cleaning Co</title><body><p>We do not offer carpet cleaning.</p></body></html>",
            "/services": b"",
            "/service-areas": b"",
            "/contact": b"",
            "/sitemap-index.xml": b"",
            "/sitemap-pages.xml": b"",
        }
    )
    result = inspector.inspect(BASE)
    assert not any(item.service == "Carpet cleaning" for item in result.services)


def test_service_route_slug_alone_does_not_infer_a_service() -> None:
    route = "/services/carpet-upholstery-cleaning"
    result, requested = _inspect_pages(
        b"<html><head><title>Sample City Two Cleaning Services</title></head><body></body></html>",
        {
            route: b"<html><head><title>Sample City Two Cleaning Services</title></head>"
            b"<body><div id='app'></div></body></html>"
        },
        sitemap_paths=(route,),
    )

    assert route in requested
    assert not result.services


def test_service_category_in_page_title_is_reported() -> None:
    result, _ = _inspect_pages(
        b"<html><head><title>Deep Cleaning in Sample City Two</title></head><body></body></html>",
        {},
    )
    candidate = next(
        item for item in result.services if item.service == "Deep cleaning"
    )
    assert candidate.source_url == BASE + "/"
    assert candidate.evidence_classification is EvidenceKind.REPORTED
    assert candidate.verification_status is VerificationStatus.WEBSITE_REPORTED
    assert candidate.supporting_text == "Page title: Deep Cleaning in Sample City Two"


def test_coordinated_service_names_share_the_cleaning_label() -> None:
    result, _ = _inspect_pages(
        b"<html><head><title>Cleaning company</title>"
        b"<meta name='description' content='Premium home, office, and Airbnb cleaning.'>"
        b"</head><body></body></html>",
        {},
    )
    assert {
        "Residential cleaning",
        "Office cleaning",
        "Vacation rental cleaning",
    } <= {item.service for item in result.services}
    assert all(
        item.evidence_classification is EvidenceKind.REPORTED
        for item in result.services
    )


def test_generic_recurring_cleaning_is_not_mislabeled_as_house_cleaning() -> None:
    result, _ = _inspect_pages(
        b"<html><head><title>Cleaning company</title></head><body></body></html>",
        {
            "/services/recurring-cleaning": b"<html><title>Cleaning company</title>"
            b"<body><div id='app'></div></body></html>"
        },
        sitemap_paths=("/services/recurring-cleaning",),
    )
    assert not result.services


def test_service_categories_in_h1_and_h2_are_extracted() -> None:
    result, _ = _inspect_pages(
        b"<html><head><title>Cleaning company</title></head><body>"
        b"<h1>Office Cleaning</h1><h2>Post-construction cleaning</h2></body></html>",
        {},
    )
    assert {item.service for item in result.services} == {
        "Office cleaning",
        "Post-construction cleaning",
    }
    assert {item.supporting_text for item in result.services} == {
        "H1: Office Cleaning",
        "H2: Post-construction cleaning",
    }


def test_service_description_body_text_is_extracted_with_page_evidence() -> None:
    route = "/services/carpet-cleaning"
    result, _ = _inspect_pages(
        b"<html><title>Cleaning company</title><body></body></html>",
        {
            route: b"<html><head><title>Cleaning company</title></head><body>"
            b"<p>We provide carpet cleaning with fabric-safe stain treatment.</p>"
            b"</body></html>"
        },
        sitemap_paths=(route,),
    )
    candidate = next(
        item for item in result.services if item.service == "Carpet cleaning"
    )
    assert candidate.source_url == BASE + route
    assert "We provide carpet cleaning" in candidate.supporting_text
    assert candidate.evidence_classification is EvidenceKind.REPORTED
    assert candidate.verification_status is VerificationStatus.WEBSITE_REPORTED


def test_multiple_service_categories_can_be_found_on_one_page() -> None:
    description = (
        "Our services include weekly house cleaning, deep cleaning, move-in and "
        "move-out cleaning, commercial cleaning, office cleaning, Airbnb turnover "
        "cleaning, carpet cleaning, upholstery cleaning, post-construction "
        "cleaning, and window cleaning."
    )
    result, _ = _inspect_pages(
        (
            "<html><head><title>Cleaning company</title></head><body><p>"
            + description
            + "</p></body></html>"
        ).encode(),
        {},
    )

    assert {
        "Residential cleaning",
        "Recurring house cleaning",
        "Deep cleaning",
        "Move-in / Move-out cleaning",
        "Commercial cleaning",
        "Office cleaning",
        "Vacation rental cleaning",
        "Airbnb / VRBO turnover cleaning",
        "Carpet cleaning",
        "Upholstery cleaning",
        "Post-construction cleaning",
        "Other specialized cleaning",
    } <= {item.service for item in result.services}


def test_ambiguous_blog_mentions_and_unsupported_cleaning_are_not_services() -> None:
    route = "/blog/carpet-cleaning-checklist"
    result, _ = _inspect_pages(
        b"<html><head><title>Cleaning company</title></head><body></body></html>",
        {
            route: b"<html><head><title>Carpet Cleaning Checklist</title></head>"
            b"<body><p>This guide explains carpet cleaning and window washing.</p></body></html>"
        },
        sitemap_paths=(route,),
    )
    assert not result.services


def test_duplicate_service_pages_collapse_to_one_category() -> None:
    routes = ("/services/deep-cleaning", "/services/deep-cleaning-details")
    result, _ = _inspect_pages(
        b"<html><head><title>Cleaning company</title></head><body></body></html>",
        {
            route: b"<html><head><title>Deep Cleaning</title></head>"
            b"<body><h1>Deep cleaning</h1></body></html>"
            for route in routes
        },
        sitemap_paths=routes,
    )
    candidates = [item for item in result.services if item.service == "Deep cleaning"]
    assert len(candidates) == 1
    assert candidates[0].evidence_classification is EvidenceKind.REPORTED
    assert candidates[0].source_url in {BASE + route for route in routes}


def test_conflicting_service_evidence_is_not_reported_as_offered() -> None:
    route = "/services/carpet-cleaning"
    result, _ = _inspect_pages(
        b"<html><head><title>Cleaning company</title></head><body>"
        b"<p>We do not offer carpet cleaning.</p></body></html>",
        {
            route: b"<html><head><title>Cleaning company</title></head>"
            b"<body><div id='app'></div></body></html>"
        },
        sitemap_paths=(route,),
    )
    assert not any(item.service == "Carpet cleaning" for item in result.services)
    assert result.details is not None
    assert any(
        "Conflicting evidence for Carpet cleaning" in item
        for item in result.details.limitations
    )


def test_visible_contact_page_address_is_preserved_as_website_observation() -> None:
    inspector, _ = _inspector(
        {
            "/contact": b"<html><body><h1>Contact</h1><p>Office: 704 Central Pkwy E suite 1220, Plano, TX 75074, United States.</p><p>Our founder grew up in Plano, TX.</p></body></html>",
        }
    )
    result = inspector.inspect(BASE)
    candidate = next(
        item
        for item in result.locations
        if item.location_type is LocationType.BUSINESS_ADDRESS and item.city == "Plano"
    )
    assert candidate.evidence_classification is EvidenceKind.OBSERVED
    assert candidate.postal_code == "75074"
    assert candidate.state == "Texas"
    assert candidate.source_url == BASE + "/contact"
    assert "704 Central Pkwy E suite 1220, Plano, TX 75074" in candidate.supporting_text
    address_evidence = next(
        item for item in result.evidence if item.evidence_id == candidate.evidence_id
    )
    assert address_evidence.source_url == candidate.source_url
    assert address_evidence.excerpt == candidate.supporting_text
    mentions = [
        item
        for item in result.locations
        if item.city == "Plano" and item.location_type is LocationType.CITY_MENTION
    ]
    assert len(mentions) == 1
    assert mentions[0].postal_code is None
    assert "founder grew up" in mentions[0].supporting_text


def test_common_plano_mention_remains_a_city_mention_not_an_address() -> None:
    result, _ = _inspect_pages(
        b"""<html><head><title>Construction Nation</title></head><body>
        <p>Our founder grew up in Plano, TX and still enjoys the local parks.</p>
        </body></html>""",
        {},
    )

    mentions = [
        item
        for item in result.locations
        if item.city == "Plano" and item.location_type is LocationType.CITY_MENTION
    ]
    assert len(mentions) == 1
    assert not any(
        item.city == "Plano" and item.location_type is LocationType.BUSINESS_ADDRESS
        for item in result.locations
    )


def test_malformed_html_is_parsed_without_crashing() -> None:
    inspector, _ = _inspector(
        {"/": b"<html><head><title>Broken title<body><h1>Still readable"}
    )
    result = inspector.inspect(BASE)
    assert result.pages[0].title == "Broken title"
    assert result.pages[0].status_code == 200


def test_meta_robots_directives_are_kept_with_the_inspected_page() -> None:
    html = b"""<html><head><meta name='robots' content='noindex, follow'>
    <title>Private example</title></head><body></body></html>"""
    result, _ = _inspect_pages(html, {})

    assert result.pages[0].robots_directives == ("noindex", "follow")


def test_x_robots_tag_is_kept_with_the_inspected_page() -> None:
    transport, _ = _fixture_transport()

    def fetch(url: str, timeout: int, limit: int, root_host: str) -> FetchResponse:
        response = transport(url, timeout, limit, root_host)
        if (urlsplit(url).path or "/") == "/":
            return FetchResponse(
                response.body,
                response.status_code,
                response.final_url,
                response.content_type,
                "noindex",
            )
        return response

    result = WebsiteInspector(transport=fetch).inspect(BASE)

    assert result.pages[0].x_robots_tag == "noindex"


@pytest.mark.parametrize(
    ("url", "category"),
    [
        ("file:///etc/passwd", "invalid_url"),
        ("https://user:pass@example.com/", "invalid_url"),
        ("http://127.0.0.1/", "blocked_destination"),
        ("http://localhost/", "blocked_destination"),
    ],
)
def test_rejects_invalid_or_private_urls(url: str, category: str) -> None:
    inspector, _ = _inspector()
    with pytest.raises(WebsiteInspectionError) as failure:
        inspector.inspect(url)
    assert failure.value.category == category


def test_rejects_redirect_to_another_public_domain() -> None:
    transport, _ = _fixture_transport()

    def redirects(url: str, timeout: int, limit: int, root_host: str) -> FetchResponse:
        response = transport(url, timeout, limit, root_host)
        if urlsplit(url).path == "/":
            return FetchResponse(
                response.body, 200, "https://malicious.example/", "text/html"
            )
        return response

    with pytest.raises(WebsiteInspectionError) as failure:
        WebsiteInspector(transport=redirects).inspect(BASE)
    assert failure.value.category == "cross_domain_redirect"


def test_rejects_redirect_to_a_private_destination() -> None:
    transport, _ = _fixture_transport()

    def redirects(url: str, timeout: int, limit: int, root_host: str) -> FetchResponse:
        response = transport(url, timeout, limit, root_host)
        if urlsplit(url).path == "/":
            return FetchResponse(response.body, 200, "http://127.0.0.1/", "text/html")
        return response

    with pytest.raises(WebsiteInspectionError) as failure:
        WebsiteInspector(transport=redirects).inspect(BASE)
    assert failure.value.category == "blocked_destination"


def test_oversized_responses_preserve_failure_category() -> None:
    oversized = b"x" * 2_000_001
    inspector, _ = _inspector({"/": oversized})
    with pytest.raises(WebsiteInspectionError) as failure:
        inspector.inspect(BASE)
    assert failure.value.category == "oversized_response"


def test_timeout_preserves_failure_category() -> None:
    def timeout(url: str, limit: int, size: int, root: str) -> FetchResponse:
        raise TimeoutError("offline fixture timeout")

    inspector = WebsiteInspector(transport=timeout)
    with pytest.raises(WebsiteInspectionError) as failure:
        inspector.inspect(BASE)
    assert failure.value.category == "timeout"


def test_conflicting_address_and_service_area_evidence_is_kept_separate() -> None:
    page = b"""<html><head><title>Cleaning</title>
    <script type='application/ld+json'>
    {"@type":"LocalBusiness","name":"Test Cleaning","address":{
      "@type":"PostalAddress","addressLocality":"Sample City Two","addressRegion":"FL"},
     "areaServed":{"@type":"City","name":"Sample City Two"}}
    </script></head><body><p>We serve Sample City Two, FL.</p></body></html>"""
    inspector, _ = _inspector({"/": page})
    result = inspector.inspect(BASE)
    assert any(
        item.location_type is LocationType.BUSINESS_ADDRESS for item in result.locations
    )
    assert any(
        item.location_type is LocationType.SERVICE_AREA for item in result.locations
    )
    assert result.details is not None
    assert any("ambiguous" in item for item in result.details.limitations)


def test_no_schema_coordinates_are_invented() -> None:
    inspector, _ = _inspector(
        {
            "/": b"<html><title>Small business</title></html>",
            "/services": b"",
            "/service-areas": b"",
            "/contact": b"",
            "/sitemap-index.xml": b"",
            "/sitemap-pages.xml": b"",
        }
    )
    result = inspector.inspect(BASE)
    assert result.details is not None
    assert result.details.latitude is None
    assert result.details.longitude is None


def test_robots_timeout_keeps_timeout_category_and_stage() -> None:
    def timeout(url: str, limit: int, size: int, root: str) -> FetchResponse:
        raise TimeoutError("offline fixture timeout")

    inspector = WebsiteInspector(transport=timeout)
    with pytest.raises(WebsiteInspectionError) as failure:
        inspector.inspect(BASE)
    assert failure.value.category == "timeout"
    assert failure.value.stage == "robots.txt"


def test_sensitive_query_is_rejected_before_any_http_request() -> None:
    inspector, requested = _inspector()
    secret = "local-test-token-value"
    with pytest.raises(WebsiteInspectionError) as failure:
        inspector.inspect(f"{BASE}/?access_token={secret}")
    assert failure.value.category == "sensitive_url"
    assert requested == []
    assert secret not in str(failure.value)


def test_tracking_parameters_and_fragments_are_removed_before_fetch() -> None:
    inspector, _ = _inspector()
    result = inspector.inspect(f"{BASE}/?utm_source=local&fbclid=tracker#section")
    assert result.details is not None
    assert result.details.requested_url == f"{BASE}/"
    assert all(
        "utm_" not in page.url and "fbclid" not in page.url for page in result.pages
    )
    assert all("#" not in page.url for page in result.pages)
