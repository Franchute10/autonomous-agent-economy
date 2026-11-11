"""Public beta HTTP journey and budget tests using in-memory website evidence."""

from datetime import datetime, timezone
from http.client import HTTPConnection
import json
import threading
from collections.abc import Iterator

import pytest

from aeos.live.domain.website_inspection import (
    WebsiteInspectionDetails,
    WebsitePage,
)
from aeos.live.ports.website import WebsiteInspectionResult
from aeos.live.public_beta import (
    PublicBetaService,
    PublicBetaHTTPServer,
    RequestGate,
    create_server,
)


class FixtureInspector:
    def __init__(self, result: WebsiteInspectionResult) -> None:
        self.result = result
        self.urls: list[str] = []

    def inspect(self, website_url: str) -> WebsiteInspectionResult:
        self.urls.append(website_url)
        return self.result


def _inspection(*, duplicate_titles: bool) -> WebsiteInspectionResult:
    root = "https://example.com/"
    services = "https://example.com/services"
    pages = (
        WebsitePage(
            url=root,
            status_code=200,
            title="Example Service Company",
            meta_description="Services for local customers.",
            h1_headings=("Example Services",),
        ),
        WebsitePage(
            url=services,
            status_code=200,
            title="Example Service Company" if duplicate_titles else "Our Services",
            meta_description="Services for local customers.",
            h1_headings=("Our Services",),
        ),
    )
    return WebsiteInspectionResult(
        signals=(),
        evidence=(),
        details=WebsiteInspectionDetails(
            requested_url=root,
            final_url=root,
            inspected_at=datetime(2026, 11, 10, tzinfo=timezone.utc),
        ),
        pages=pages,
    )


@pytest.fixture
def beta_server() -> Iterator[tuple[PublicBetaHTTPServer, FixtureInspector]]:
    inspector = FixtureInspector(_inspection(duplicate_titles=True))
    service = PublicBetaService(inspector_factory=lambda: inspector)
    server = create_server(
        "127.0.0.1", 0, service=service, gate=RequestGate(daily_limit=20)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, inspector
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _post(
    server: PublicBetaHTTPServer, payload: object
) -> tuple[int, dict[str, str], dict[str, object]]:
    connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
    body = json.dumps(payload).encode("utf-8")
    connection.request(
        "POST",
        "/api/diagnose",
        body=body,
        headers={"Content-Type": "application/json"},
    )
    response = connection.getresponse()
    headers = {key.casefold(): value for key, value in response.getheaders()}
    payload_value = json.loads(response.read())
    connection.close()
    return response.status, headers, payload_value


def _get(server: PublicBetaHTTPServer, path: str) -> tuple[int, dict[str, str], bytes]:
    connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
    connection.request("GET", path)
    response = connection.getresponse()
    headers = {key.casefold(): value for key, value in response.getheaders()}
    body = response.read()
    connection.close()
    return response.status, headers, body


@pytest.mark.parametrize("submitted_url", ["https://example.com/", "example.com"])
def test_website_report_flows_from_form_endpoint_to_bilingual_evidence(
    beta_server: tuple[PublicBetaHTTPServer, FixtureInspector],
    submitted_url: str,
) -> None:
    server, inspector = beta_server
    page_status, page_headers, page_html = _get(server, "/")
    assert page_status == 200
    assert page_headers["content-security-policy"].startswith("default-src 'none'")
    assert b"AEOS" in page_html and b"/app.js" in page_html
    assert b'class="input-prefix"' not in page_html
    assert b'placeholder="https://tusitio.com"' in page_html
    status, headers, report = _post(server, {"url": submitted_url, "language": "en"})

    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert inspector.urls == ["https://example.com/"]
    assert report["platform"] == "WEBSITE"
    assert report["language"] == "en"
    findings = report["confirmed_findings"]
    assert isinstance(findings, list) and len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, dict)
    title = finding.get("title")
    prompt = finding.get("correction_prompt")
    sources = finding.get("sources")
    assert (
        isinstance(title, dict) and title.get("en") == "Repeated titles or descriptions"
    )
    assert isinstance(prompt, dict) and "https://example.com/" in str(prompt.get("en"))
    assert isinstance(sources, list)
    assert all(isinstance(source, dict) for source in sources)
    assert {
        source["url"]
        for source in sources
        if isinstance(source, dict) and isinstance(source.get("url"), str)
    } == {
        "https://example.com/",
        "https://example.com/services",
    }
    assert report["pending_verifications"] == []


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://www.linkedin.com/company/example/", "LINKEDIN"),
        ("https://lnkd.in/example", "LINKEDIN"),
        ("https://www.instagram.com/example/", "INSTAGRAM"),
        ("https://instagr.am/example", "INSTAGRAM"),
        ("https://business.google.com/profile/example", "GOOGLE_BUSINESS_PROFILE"),
        ("https://share.google/example", "GOOGLE_BUSINESS_PROFILE"),
    ],
)
def test_social_urls_request_owner_evidence_without_calling_inspector(
    url: str, platform: str
) -> None:
    def inspector_must_not_run() -> FixtureInspector:
        pytest.fail("social URLs must never be fetched")

    service = PublicBetaService(inspector_factory=inspector_must_not_run)
    report = service.diagnose(url, "es")

    assert report["platform"] == platform
    assert report["inspection_status"] == "OWNER_EVIDENCE_REQUIRED"
    assert report["confirmed_findings"] == []
    summary = report.get("summary")
    access_request = report.get("access_request")
    assert isinstance(summary, dict) and "No se abrió" in str(summary.get("es"))
    assert isinstance(access_request, dict)
    assert "acceso autorizado" in str(access_request.get("es"))


def test_local_address_is_rejected_before_any_inspection() -> None:
    def inspector_must_not_run() -> FixtureInspector:
        pytest.fail("a private URL must be rejected before inspection")

    service = PublicBetaService(inspector_factory=inspector_must_not_run)

    with pytest.raises(ValueError):
        service.diagnose("http://127.0.0.1/admin")


def test_per_ip_rate_limit_rejects_excess_work() -> None:
    server = create_server(
        "127.0.0.1",
        0,
        service=PublicBetaService(
            inspector_factory=lambda: FixtureInspector(
                _inspection(duplicate_titles=False)
            )
        ),
        gate=RequestGate(per_ip_limit=1, window_seconds=60, daily_limit=2),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        first_status, _, _ = _post(server, {"url": "https://example.com/"})
        second_status, second_headers, second_body = _post(
            server, {"url": "https://example.com/"}
        )
        assert first_status == 200
        assert second_status == 429
        assert second_headers["retry-after"]
        assert second_body["error"] == "rate_limit"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_daily_budget_rejects_more_than_its_configured_allowance() -> None:
    gate = RequestGate(per_ip_limit=5, window_seconds=60, daily_limit=1)

    assert gate.consume("203.0.113.10")[0] is True
    allowed, reason, retry_after = gate.consume("203.0.113.11")

    assert allowed is False
    assert reason == "daily_limit"
    assert 0 < retry_after <= 86_400


def test_uncertain_fields_have_no_correction_prompt() -> None:
    page = WebsitePage(
        url="https://example.com/",
        status_code=200,
    )
    result = WebsiteInspectionResult(
        signals=(),
        evidence=(),
        details=WebsiteInspectionDetails(
            requested_url=page.url,
            final_url=page.url,
            inspected_at=datetime(2026, 11, 10, tzinfo=timezone.utc),
        ),
        pages=(page,),
    )
    response = PublicBetaService(
        inspector_factory=lambda: FixtureInspector(result)
    ).diagnose(page.url, "en")

    assert response["confirmed_findings"] == []
    pending = response["pending_verifications"]
    assert pending
    assert isinstance(pending, list)
    pending_items = [item for item in pending if isinstance(item, dict)]
    assert all(item.get("status") == "INCONCLUSIVE" for item in pending_items)
    assert all("correction_prompt" not in item for item in pending_items)
