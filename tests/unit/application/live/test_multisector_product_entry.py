"""Acceptance of product and service businesses through the public URL entry."""

from urllib.parse import urlsplit

import pytest

from aeos.live.adapters.website_inspector import FetchResponse, WebsiteInspector
from aeos.live.public_beta import PublicBetaService


@pytest.mark.parametrize(
    ("name", "offer", "route"),
    [
        (
            "Synthetic Tool Shop",
            "Buy power tools and construction supplies",
            "/products",
        ),
        ("Synthetic Toy Store", "Buy educational toys", "/catalogo"),
        ("Synthetic Advisory", "Commercial strategy consulting services", "/servicios"),
        ("Synthetic HVAC", "Air conditioning repair services", "/offer"),
    ],
)
def test_public_diagnosis_returns_evidence_and_prompt_across_sectors(
    name: str, offer: str, route: str
) -> None:
    root = "https://business.example/"
    requested: list[str] = []

    def fetch(url: str, timeout: int, byte_limit: int, root_host: str) -> FetchResponse:
        requested.append(url)
        path = urlsplit(url).path
        if path == "/robots.txt":
            return FetchResponse(b"User-agent: *\nAllow: /\n", 200, url)
        if path == "/sitemap.xml":
            return FetchResponse(
                (
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    f"<url><loc>https://business.example{route}</loc></url></urlset>"
                ).encode(),
                200,
                url,
                "application/xml",
            )
        if path not in {"/", route}:
            return FetchResponse(b"", 404, url, "text/plain")
        html = (
            f"<html><head><title>{name}</title>"
            f'<meta name="description" content="{offer}"></head>'
            f'<body><h1>{offer}</h1><a href="{route}">Offer</a></body></html>'
        )
        return FetchResponse(html.encode(), 200, url, "text/html")

    service = PublicBetaService(
        inspector_factory=lambda: WebsiteInspector(transport=fetch)
    )
    result = service.diagnose(root)
    assert result["inspection_status"] == "SUCCEEDED"
    assert result["pages_received"] == 2
    findings = result["confirmed_findings"]
    assert isinstance(findings, list) and findings
    assert all(item["sources"] for item in findings)
    assert all(item["correction_prompt"] for item in findings)
    assert any(url.endswith("/robots.txt") for url in requested)
    assert any(url.endswith("/sitemap.xml") for url in requested)
    assert "cleaning" not in str(findings).lower()
