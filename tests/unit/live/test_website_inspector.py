"""Offline fixtures for the bounded website inspection adapter."""

from pathlib import Path
from urllib.parse import urlsplit

import pytest

from aeos.live.adapters.website_inspector import (
    FetchResponse,
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
        result.details.address
        == "100 Example Street, Sample City Four, Example Region, 00000"
    )
    assert result.details.latitude == 27.12
    assert result.details.longitude == -82.45
    assert result.details.opening_hours == ("Mo-Fr 08:00-18:00",)
    assert result.details.same_as == ("https://www.facebook.com/sample-cleaning",)
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
        "Example Region",
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
    assert all(item.verification_status.value == "UNVERIFIED" for item in mentions)
    assert not any(
        item.city == "Sample City One"
        and item.location_type
        in {LocationType.SERVICE_AREA, LocationType.EXPLICITLY_SERVED_CITY}
        for item in result.locations
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


def test_service_route_slug_is_inferred_and_keeps_its_source_url() -> None:
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
    for category in ("Carpet cleaning", "Upholstery cleaning"):
        candidate = next(item for item in result.services if item.service == category)
        assert candidate.source_url == BASE + route
        assert candidate.supporting_text == (
            "Service-page URL slug: carpet upholstery cleaning"
        )
        assert candidate.evidence_classification is EvidenceKind.INFERRED
        assert candidate.verification_status is VerificationStatus.UNVERIFIED


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
    assert any(item.service == "Recurring cleaning" for item in result.services)
    assert not any(
        item.service == "Recurring house cleaning" for item in result.services
    )


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


def test_conflicting_service_evidence_is_left_unverified() -> None:
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
    candidate = next(
        item for item in result.services if item.service == "Carpet cleaning"
    )
    assert candidate.evidence_classification is EvidenceKind.INFERRED
    assert candidate.verification_status is VerificationStatus.UNVERIFIED
    assert candidate.confidence <= 0.6
    assert result.details is not None
    assert any(
        "Conflicting evidence for Carpet cleaning" in item
        for item in result.details.limitations
    )


def test_visible_contact_page_address_is_preserved_as_website_observation() -> None:
    inspector, _ = _inspector(
        {
            "/contact": b"<html><body><h1>Contact</h1><p>Office: 25 Palm Avenue, Sample City Three, FL 34285</p></body></html>",
        }
    )
    result = inspector.inspect(BASE)
    candidate = next(
        item
        for item in result.locations
        if item.location_type is LocationType.BUSINESS_ADDRESS
        and item.city == "Sample City Three"
    )
    assert candidate.evidence_classification is EvidenceKind.OBSERVED
    assert candidate.postal_code == "34285"


def test_malformed_html_is_parsed_without_crashing() -> None:
    inspector, _ = _inspector(
        {"/": b"<html><head><title>Broken title<body><h1>Still readable"}
    )
    result = inspector.inspect(BASE)
    assert result.pages[0].title == "Broken title"
    assert result.pages[0].status_code == 200


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
