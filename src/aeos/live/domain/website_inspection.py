"""Bounded website inspection records used by the LIVE website port."""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from aeos.live.domain.errors import InvalidLiveContract


@dataclass(frozen=True, slots=True)
class WebsitePage:
    url: str
    status_code: int
    title: str | None = None
    meta_description: str | None = None
    h1_headings: tuple[str, ...] = ()
    h2_headings: tuple[str, ...] = ()
    main_text: str = ""
    link_texts: tuple[str, ...] = ()
    link_urls: tuple[str, ...] = ()
    robots_directives: tuple[str, ...] = ()
    x_robots_tag: str | None = None
    inspection_method: str = "HTML_ONLY"
    rendered_title: str | None = None
    rendered_meta_description: str | None = None
    rendered_h1_headings: tuple[str, ...] = ()
    rendered_h2_headings: tuple[str, ...] = ()
    rendered_link_texts: tuple[str, ...] = ()
    rendered_link_urls: tuple[str, ...] = ()
    rendered_dom_error: str | None = None
    rendered_dom_error_message: str | None = None

    @property
    def rendered_dom_status(self) -> str:
        if self.inspection_method == "HTML_ONLY":
            return "HTML_ONLY"
        if self.rendered_dom_error in {
            "external_navigation_blocked",
            "render_failed",
            "render_http_error",
            "render_request_budget_exhausted",
            "render_timeout",
        }:
            return "PARTIAL"
        return "RENDERED"

    @property
    def rendered_dom_fields_observed(self) -> tuple[str, ...]:
        if self.inspection_method == "HTML_ONLY":
            return ()
        fields: list[str] = []
        if self.rendered_title:
            fields.append("title")
        if self.rendered_meta_description:
            fields.append("meta_description")
        if self.rendered_h1_headings:
            fields.append("h1")
        if self.rendered_h2_headings:
            fields.append("h2")
        if self.rendered_link_texts or self.rendered_link_urls:
            fields.append("links")
        return tuple(fields)

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url.strip():
            raise InvalidLiveContract("page url must be non-blank")
        if isinstance(self.status_code, bool) or not isinstance(self.status_code, int):
            raise InvalidLiveContract("status_code must be an integer")
        if self.status_code < 100 or self.status_code > 599:
            raise InvalidLiveContract("status_code must be a valid HTTP status")
        for field in ("title", "meta_description"):
            value = getattr(self, field)
            if value is not None and not isinstance(value, str):
                raise InvalidLiveContract(f"{field} must be a string or None")
        if self.inspection_method not in {"HTML_ONLY", "HTTP_AND_RENDERED_DOM"}:
            raise InvalidLiveContract("inspection_method is not supported")
        for field in (
            "rendered_title",
            "rendered_meta_description",
            "rendered_dom_error",
            "rendered_dom_error_message",
        ):
            value = getattr(self, field)
            if value is not None and not isinstance(value, str):
                raise InvalidLiveContract(f"{field} must be a string or None")
        for field in (
            "h1_headings",
            "h2_headings",
            "robots_directives",
            "rendered_h1_headings",
            "rendered_h2_headings",
            "rendered_link_texts",
            "rendered_link_urls",
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not isinstance(item, str) for item in values
            ):
                raise InvalidLiveContract(f"{field} must be a tuple of strings")
        if not isinstance(self.link_texts, tuple) or any(
            not isinstance(item, str) for item in self.link_texts
        ):
            raise InvalidLiveContract("link_texts must be a tuple of strings")
        if not isinstance(self.link_urls, tuple) or any(
            not isinstance(item, str) for item in self.link_urls
        ):
            raise InvalidLiveContract("link_urls must be a tuple of strings")
        if not isinstance(self.main_text, str):
            raise InvalidLiveContract("main_text must be a string")
        if self.x_robots_tag is not None and not isinstance(self.x_robots_tag, str):
            raise InvalidLiveContract("x_robots_tag must be a string or None")


@dataclass(frozen=True, slots=True)
class WebsiteInspectionDetails:
    requested_url: str
    final_url: str
    inspected_at: datetime
    business_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    opening_hours: tuple[str, ...] = ()
    same_as: tuple[str, ...] = ()
    robots_status: str = "unknown"
    robots_sitemaps: tuple[str, ...] = ()
    robots_restrictions: tuple[str, ...] = ()
    sitemap_urls: tuple[str, ...] = ()
    structured_data_types: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in ("requested_url", "final_url"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidLiveContract(f"{field} must be non-blank")
        if not isinstance(self.inspected_at, datetime):
            raise InvalidLiveContract("inspected_at must be a datetime")
        for field in ("business_name", "phone", "email", "address"):
            value = getattr(self, field)
            if value is not None and not isinstance(value, str):
                raise InvalidLiveContract(f"{field} must be a string or None")
        for field in ("latitude", "longitude"):
            value = getattr(self, field)
            limit = 90 if field == "latitude" else 180
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or not -limit <= value <= limit
            ):
                raise InvalidLiveContract(f"{field} must be a valid coordinate or None")
        for field in (
            "opening_hours",
            "same_as",
            "robots_sitemaps",
            "robots_restrictions",
            "sitemap_urls",
            "structured_data_types",
            "limitations",
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not isinstance(item, str) for item in values
            ):
                raise InvalidLiveContract(f"{field} must be a tuple of strings")
        if not isinstance(self.robots_status, str):
            raise InvalidLiveContract("robots_status must be a string")
