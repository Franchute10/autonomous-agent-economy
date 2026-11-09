"""Use the established LIVE website port to inspect a public business site."""

from aeos.live.ports.website import WebsiteInspectionPort, WebsiteInspectionResult


def inspect_business_website(
    inspector: WebsiteInspectionPort, website_url: str
) -> WebsiteInspectionResult:
    """Inspect a website through its injected adapter and validate the result type."""

    if not isinstance(website_url, str) or not website_url.strip():
        raise ValueError("website_url must be a non-blank string")
    result = inspector.inspect(website_url.strip())
    if not isinstance(result, WebsiteInspectionResult):
        raise TypeError("website inspector must return WebsiteInspectionResult")
    return result
