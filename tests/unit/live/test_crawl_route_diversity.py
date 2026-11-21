"""Regression tests for a three-page crawl encountering query variants."""

import unittest
from urllib.parse import urlsplit

from aeos.live.adapters.website_inspector import FetchResponse, WebsiteInspector
from aeos.live.public_beta import PublicBetaService


class CrawlRouteDiversityTests(unittest.TestCase):
    def diagnose(self, routes: tuple[str, ...]) -> tuple[dict[str, object], list[str]]:
        requested: list[str] = []
        root = "https://business.example/"

        def fetch(url: str, timeout: int, limit: int, root_host: str) -> FetchResponse:
            requested.append(url)
            path = urlsplit(url).path
            if path == "/robots.txt":
                return FetchResponse(b"User-agent: *\nAllow: /\n", 200, url)
            if path == "/sitemap.xml":
                return FetchResponse(b"", 404, url)
            links = "".join(f'<a href="{route}">Offer</a>' for route in routes)
            body = (
                '<html><head><title>Example business</title>'
                '<meta name="description" content="Example offer"></head>'
                f"<body><h1>Example offer</h1>{links}</body></html>"
            )
            return FetchResponse(body.encode(), 200, url)

        service = PublicBetaService(
            inspector_factory=lambda: WebsiteInspector(transport=fetch, max_pages=3)
        )
        return service.diagnose(root), requested

    def test_contact_variants_do_not_displace_product_route(self) -> None:
        result, requested = self.diagnose(
            ("/contact?cta=one", "/contact?cta=two", "/products?id=42")
        )
        self.assertEqual(result["pages_received"], 3)
        self.assertIn("https://business.example/products?id=42", requested)
        self.assertIn("https://business.example/contact?cta=one", requested)
        self.assertNotIn("https://business.example/contact?cta=two", requested)

    def test_query_based_products_remain_available_when_budget_allows(self) -> None:
        result, requested = self.diagnose(("/products?id=1", "/products?id=2"))
        self.assertEqual(result["pages_received"], 3)
        self.assertIn("https://business.example/products?id=1", requested)
        self.assertIn("https://business.example/products?id=2", requested)

    def test_distinct_service_routes_keep_relevance_order(self) -> None:
        result, requested = self.diagnose(("/about", "/services", "/contact"))
        self.assertEqual(result["pages_received"], 3)
        self.assertNotIn("https://business.example/about", requested)
        self.assertLess(
            requested.index("https://business.example/contact"),
            requested.index("https://business.example/services"),
        )

    def test_duplicate_prompt_requires_content_comparison_in_both_languages(self) -> None:
        result, _ = self.diagnose(("/contact?cta=one", "/contact?cta=two"))
        findings = result["confirmed_findings"]
        assert isinstance(findings, list)
        repeated = next(
            item
            for item in findings
            if item["title"]["es"] == "Títulos o descripciones repetidos"
        )
        prompt = repeated["correction_prompt"]
        self.assertIn("solo cuando su contenido lo justifique", prompt["es"])
        self.assertIn("only when their content supports it", prompt["en"])
        self.assertIn("sin verificar su función", prompt["es"])
        self.assertIn("without verifying their purpose", prompt["en"])


if __name__ == "__main__":
    unittest.main()
