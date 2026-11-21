"""Bounded, same-site public website inspection with SSRF safeguards."""

from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from http.client import HTTPMessage
from importlib import import_module
import ipaddress
import os
from pathlib import Path
from typing import IO
import json
import re
import socket
import time
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urldefrag, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)
import xml.etree.ElementTree as ET

from aeos.live.domain.evidence import EvidenceKind, JsonScalar, SourceEvidence
from aeos.live.domain.url_policy import (
    has_sensitive_query_parameter,
    strip_tracking_parameters,
)
from aeos.live.domain.location_candidate import (
    LocationCandidate,
    LocationType,
    ServiceCandidate,
    VerificationStatus,
)
from aeos.live.domain.website_inspection import (
    WebsiteInspectionDetails,
    WebsitePage,
)
from aeos.live.ports.website import WebsiteInspectionResult, WebsiteSignal

MAX_PAGES = 20
MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_TIMEOUT_SECONDS = 10
MAX_RENDERED_DOM_SECONDS = 20
MAX_RENDERED_DOM_REQUESTS = 1000
MAX_SITEMAPS = 5
MAX_SITEMAP_URLS = 500
USER_AGENT = "AEOSLiveWebsiteInspector/1.0"
_MAX_TEXT_CHARS = 20_000
_MAX_EVIDENCE_EXCERPT = 1200
_STATE_NAMES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}
_STATE_ALIASES = {
    alias.casefold(): name
    for abbreviation, name in _STATE_NAMES.items()
    for alias in (abbreviation, name)
}
_NEIGHBORHOOD_NAMES = frozenset(
    {
        "los rios",
        "treyburn",
        "cross bend",
        "timber brook",
        "hunters glen",
        "carriage hill",
        "wind meadow",
        "madison estates",
        "dallas north estates",
        "park forest",
    }
)
_GENERIC_PLACE_WORDS = frozenset(
    {
        "area",
        "areas",
        "call",
        "contact",
        "estimate",
        "free",
        "gallery",
        "galleries",
        "get",
        "home",
        "learn",
        "links",
        "more",
        "our",
        "page",
        "pages",
        "project",
        "projects",
        "quick",
        "service",
        "services",
        "serve",
        "serves",
        "serving",
        "testimonials",
        "the",
        "touch",
        "welcome",
        "we",
    }
)
_SERVICE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "Full home remodeling",
        re.compile(r"\bfull\s+(?:home|house)\s+remodel(?:ing|s)?\b", re.I),
    ),
    (
        "Home remodeling",
        re.compile(
            r"\b(?:(?:home|house)\s+remodel(?:ing|s)?|remodeling\s+services?)\b",
            re.I,
        ),
    ),
    (
        "Kitchen remodeling",
        re.compile(r"\bkitchen\s+(?:remodeling|renovations?)\b", re.I),
    ),
    (
        "Bathroom remodeling",
        re.compile(r"\bbathroom\s+(?:remodeling|renovations?)\b", re.I),
    ),
    ("Room additions", re.compile(r"\broom\s+additions?\b", re.I)),
    ("Home additions", re.compile(r"\bhome\s+additions?\b", re.I)),
    ("New home construction", re.compile(r"\bnew\s+home\s+construction\b", re.I)),
    ("Pools", re.compile(r"\bpools?(?:\s+construction)?\b", re.I)),
    (
        "Investor flip projects",
        re.compile(r"\binvestors?\s+flips?(?:\s+projects?)?\b", re.I),
    ),
    (
        "Residential cleaning",
        re.compile(
            r"\b(?:"
            r"(?:residential|house|home)\s+(?:(?:recurring|weekly|biweekly|bi-weekly|monthly)\s+)?"
            r"|(?:recurring|weekly|biweekly|bi-weekly|monthly)\s+(?:residential|house|home)\s+"
            r")clean(?:ing|ings)\b",
            re.I,
        ),
    ),
    (
        "Recurring house cleaning",
        re.compile(
            r"\b(?:(?:recurring|weekly|biweekly|bi-weekly|monthly)\s+(?:residential|house|home)|(?:residential|house|home)\s+(?:recurring|weekly|biweekly|bi-weekly|monthly))\s+clean(?:ing|ings)\b",
            re.I,
        ),
    ),
    (
        "Recurring cleaning",
        re.compile(
            r"\b(?:recurring|weekly|biweekly|bi-weekly|monthly)\s+clean(?:ing|ings)\b",
            re.I,
        ),
    ),
    ("Deep cleaning", re.compile(r"\bdeep\s+clean(?:ing|ings)\b", re.I)),
    (
        "Move-in / Move-out cleaning",
        re.compile(
            r"\bmove[ -]?(?:in|out)\b.{0,24}\bclean(?:ing|ings)\b|\bmove[ -]?(?:in|out)\s+clean(?:ing|ings)\b",
            re.I,
        ),
    ),
    ("Commercial cleaning", re.compile(r"\bcommercial\s+clean(?:ing|ings)\b", re.I)),
    ("Office cleaning", re.compile(r"\boffice\s+clean(?:ing|ings)\b", re.I)),
    (
        "Airbnb / VRBO turnover cleaning",
        re.compile(
            r"\b(?:airbnb|vrbo|vacation rental|short[ -]term rental)\b[^.!?\n]{0,90}\bturn(?:over|around)\s+cleaning\b|\bturn(?:over|around)\s+cleaning\b[^.!?\n]{0,90}\b(?:airbnb|vrbo|vacation rental|short[ -]term rental)\b",
            re.I,
        ),
    ),
    (
        "Vacation rental cleaning",
        re.compile(
            r"\b(?:vacation|short[ -]term)\s+rental\s+clean(?:ing|ings)\b|\b(?:airbnb|vrbo)\b[^.!?\n]{0,70}\bclean(?:ing|ings)\b",
            re.I,
        ),
    ),
    (
        "Carpet cleaning",
        re.compile(r"\bcarpets?\b[^.!?\n]{0,35}\bclean(?:ing|ings)\b", re.I),
    ),
    (
        "Upholstery cleaning",
        re.compile(
            r"\bupholster(?:y|ed|ies)\b[^.!?\n]{0,40}\bclean(?:ing|ings|ed)?\b|\bclean(?:ing|ings)\b[^.!?\n]{0,40}\bupholster(?:y|ed|ies)\b",
            re.I,
        ),
    ),
    (
        "Post-construction cleaning",
        re.compile(r"\bpost[ -]construction\s+clean(?:ing|ings)\b", re.I),
    ),
    (
        "Other specialized cleaning",
        re.compile(
            r"\b(?:window|tile(?:\s+and\s+grout)?|grout|floor|appliance|dryer vent|pressure wash(?:ing)?|janitorial|disinfection|sanitization)\s+(?:clean(?:ing|ings)|service(?:s)?)\b",
            re.I,
        ),
    ),
)
_SERVICE_LIST_TERMS = (
    r"(?:residential|home|house|office|commercial|airbnb|vrbo|"
    r"vacation\s+rental|short[ -]term\s+rental)"
)
_SERVICE_LIST_PATTERN = re.compile(
    rf"\b(?P<services>{_SERVICE_LIST_TERMS}"
    rf"(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+|\s*&\s*)"
    rf"(?:{_SERVICE_LIST_TERMS}))+)\s+clean(?:ing|ings)\b",
    re.I,
)
_SERVICE_LIST_ITEM_PATTERN = re.compile(rf"\b(?P<item>{_SERVICE_LIST_TERMS})\b", re.I)
_SERVICE_LIST_CATEGORIES = {
    "residential": "Residential cleaning",
    "home": "Residential cleaning",
    "house": "Residential cleaning",
    "office": "Office cleaning",
    "commercial": "Commercial cleaning",
    "airbnb": "Vacation rental cleaning",
    "vrbo": "Vacation rental cleaning",
    "vacation rental": "Vacation rental cleaning",
    "short term rental": "Vacation rental cleaning",
    "short-term rental": "Vacation rental cleaning",
}

_SERVICE_OFFER_CONTEXT = re.compile(
    r"\b(?:we\s+(?:offer|provide|perform|specialize in)|our\s+services?\s+"
    r"(?:include|are)|available|book\s+(?:our|a)|schedule\s+(?:our|a)|"
    r"request\s+(?:our|a))\b",
    re.I,
)


class WebsiteInspectionError(RuntimeError):
    """A categorized and safe-to-report inspection failure."""

    def __init__(
        self, message: str, *, category: str, stage: str | None = None
    ) -> None:
        super().__init__(message)
        self.category = category
        self.stage = stage


@dataclass(frozen=True, slots=True)
class FetchResponse:
    body: bytes
    status_code: int
    final_url: str
    content_type: str | None = None
    x_robots_tag: str | None = None


Transport = Callable[[str, int, int, str], FetchResponse]
Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class RenderedDOM:
    title: str | None
    meta_description: str | None
    h1_headings: tuple[str, ...] = ()
    h2_headings: tuple[str, ...] = ()
    link_texts: tuple[str, ...] = ()
    link_urls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RenderedDOMOutcome:
    dom: RenderedDOM | None
    error_category: str | None = None
    error_message: str | None = None


def _rendered_dom_fields(dom: RenderedDOM) -> tuple[str, ...]:
    fields: list[str] = []
    if dom.title:
        fields.append("title")
    if dom.meta_description:
        fields.append("meta_description")
    if dom.h1_headings:
        fields.append("h1")
    if dom.h2_headings:
        fields.append("h2")
    if dom.link_texts or dom.link_urls:
        fields.append("links")
    return tuple(fields)


def _is_navigation_timeout(error: BaseException) -> bool:
    return (
        "timeout" in type(error).__name__.casefold()
        or "timed out" in str(error).casefold()
    )


class DOMRenderer(Protocol):
    def __call__(
        self,
        urls: tuple[str, ...],
        root_host: str,
        timeout_seconds: int,
    ) -> Mapping[str, RenderedDOMOutcome]: ...


def _is_windows_environment() -> bool:
    return os.name == "nt"


@contextmanager
def _playwright_browser_cache_environment() -> Iterator[None]:
    """Temporarily select the normal profile cache when LOCALAPPDATA is sandboxed."""
    original_browser_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    profile = os.environ.get("USERPROFILE")
    browser_cache = (
        Path(profile) / "AppData" / "Local" / "ms-playwright"
        if profile
        else Path.home() / "AppData" / "Local" / "ms-playwright"
    )
    if (
        _is_windows_environment()
        and not original_browser_path
        and browser_cache.is_dir()
    ):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_cache)
    try:
        yield
    finally:
        if original_browser_path is None:
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        else:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = original_browser_path


def _dom_request_block_reason(
    *,
    url: str,
    root_host: str,
    method: str,
    resource_type: str,
    is_navigation: bool,
) -> str | None:
    if method.upper() != "GET":
        return "non_get_request_blocked"
    try:
        safe_url = _validate_url(url, resolve_host=False)
    except WebsiteInspectionError as error:
        return error.category
    if not _same_site(safe_url, root_host):
        if is_navigation:
            return "external_navigation_blocked"
        if resource_type in {"xhr", "fetch", "websocket", "eventsource"}:
            return "external_data_request_blocked"
        query_parameters = parse_qsl(urlsplit(safe_url).query, keep_blank_values=True)
        safe_query_values = {
            "v": r"[A-Za-z0-9._-]{1,40}",
            "ver": r"[A-Za-z0-9._-]{1,40}",
            "version": r"[A-Za-z0-9._-]{1,40}",
            "rev": r"[A-Za-z0-9._-]{1,40}",
            "family": r"[A-Za-z0-9 ._+:;,@-]{1,160}",
            "display": r"(?:swap|block|fallback|optional)",
        }
        safe_query = all(
            key.casefold() in safe_query_values
            and re.fullmatch(safe_query_values[key.casefold()], value) is not None
            for key, value in query_parameters
        )
        if resource_type not in {"script", "stylesheet", "font"} or not safe_query:
            return "external_resources_blocked"
    return None


class PlaywrightDOMRenderer:
    """Capture public same-site DOM with a bounded, non-interactive browser pass."""

    def __call__(
        self,
        urls: tuple[str, ...],
        root_host: str,
        timeout_seconds: int,
    ) -> Mapping[str, RenderedDOMOutcome]:
        try:
            sync_playwright: Any = getattr(
                import_module("playwright.sync_api"), "sync_playwright"
            )
        except ImportError as error:
            raise WebsiteInspectionError(
                f"Playwright is not installed: {type(error).__name__}: {error}",
                category="browser_unavailable",
            ) from error

        outcomes: dict[str, RenderedDOMOutcome] = {}
        deadline = time.monotonic() + min(
            max(timeout_seconds * 2, 1), MAX_RENDERED_DOM_SECONDS
        )
        try:
            with (
                _playwright_browser_cache_environment(),
                sync_playwright() as playwright,
            ):
                try:
                    browser = playwright.chromium.launch(
                        headless=True,
                        timeout=min(timeout_seconds * 1000, 5000),
                    )
                except Exception as error:
                    detail = f"{type(error).__name__}: {error}"
                    raise WebsiteInspectionError(
                        f"The local Playwright browser is unavailable: {detail}",
                        category="browser_unavailable",
                    ) from error
                try:
                    context = browser.new_context(
                        java_script_enabled=True,
                        service_workers="block",
                        user_agent=USER_AGENT,
                        accept_downloads=False,
                    )
                    if hasattr(context, "route_web_socket"):
                        context.route_web_socket(
                            "**/*",
                            lambda socket_route: socket_route.close(
                                code=1008,
                                reason="AEOS blocks WebSocket traffic",
                            ),
                        )
                    requests_seen = 0
                    current_url: str | None = None
                    blocked_resources: dict[str, set[str]] = {}
                    request_budget_exhausted: set[str] = set()

                    def route_request(route: Any) -> None:
                        nonlocal current_url, requests_seen
                        request = route.request
                        requests_seen += 1
                        if requests_seen > MAX_RENDERED_DOM_REQUESTS:
                            if current_url is not None:
                                request_budget_exhausted.add(current_url)
                                blocked_resources.setdefault(current_url, set()).add(
                                    "request_budget:render_request_budget_exhausted"
                                )
                            route.abort()
                            return
                        reason = _dom_request_block_reason(
                            url=request.url,
                            root_host=root_host,
                            method=request.method,
                            resource_type=request.resource_type,
                            is_navigation=request.is_navigation_request(),
                        )
                        if reason:
                            if current_url is not None:
                                resource_label = f"{request.resource_type}:{reason}"
                                blocked_resources.setdefault(current_url, set()).add(
                                    resource_label
                                )
                            route.abort()
                            return
                        headers = {
                            name: value
                            for name, value in request.headers.items()
                            if name.casefold()
                            not in {
                                "authorization",
                                "cookie",
                                "origin",
                                "proxy-authorization",
                                "referer",
                            }
                        }
                        route.continue_(headers=headers)

                    context.route("**/*", route_request)
                    context.add_init_script(
                        """(() => {
                          const stopForm = event => {
                            event.preventDefault();
                            event.stopImmediatePropagation();
                          };
                          document.addEventListener('submit', stopForm, true);
                          HTMLFormElement.prototype.submit = function () {};
                          HTMLFormElement.prototype.requestSubmit = function () {};
                        })();"""
                    )
                    page = context.new_page()
                    page.set_default_timeout(1500)
                    page.set_default_navigation_timeout(timeout_seconds * 1000)
                    for url in urls[:MAX_PAGES]:
                        current_url = url
                        remaining_ms = int((deadline - time.monotonic()) * 1000)
                        if remaining_ms <= 0:
                            outcomes[url] = RenderedDOMOutcome(
                                None,
                                "render_time_budget_exhausted",
                                "The site-wide DOM rendering time budget was exhausted.",
                            )
                            continue
                        previous_page_url = page.url
                        response: Any = None
                        navigation_error: Exception | None = None
                        try:
                            response = page.goto(
                                url,
                                wait_until="domcontentloaded",
                                timeout=min(timeout_seconds * 1000, remaining_ms),
                            )
                        except Exception as error:
                            navigation_error = error

                        remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
                        hydration_wait_ms = min(350, remaining_ms)
                        if hydration_wait_ms:
                            try:
                                page.wait_for_timeout(hydration_wait_ms)
                            except Exception:
                                pass

                        try:
                            page_url = page.url
                            if (
                                navigation_error is not None
                                and page_url == previous_page_url
                                and page_url != url
                            ):
                                raise WebsiteInspectionError(
                                    "Navigation did not commit a new document.",
                                    category="render_timeout"
                                    if _is_navigation_timeout(navigation_error)
                                    else "render_failed",
                                )
                            raw = page.evaluate(
                                """() => {
                                  if (!document.documentElement) {
                                    return {document_available: false};
                                  }
                                  const visible = (element) => {
                                    if (element.getClientRects().length === 0) return false;
                                    let current = element;
                                    while (current instanceof Element) {
                                      const style = getComputedStyle(current);
                                      if (current.hidden || style.display === 'none' ||
                                          style.visibility === 'hidden' ||
                                          style.visibility === 'collapse' ||
                                          style.opacity === '0') return false;
                                      current = current.parentElement;
                                    }
                                    return true;
                                  };
                                  const text = (element) =>
                                    (element.innerText || element.textContent || '')
                                      .replace(/\\s+/g, ' ').trim();
                                  const description = document.querySelector(
                                    'meta[name="description" i]'
                                  );
                                  const links = Array.from(
                                    document.querySelectorAll('a[href]')
                                  ).filter(visible);
                                  return {
                                    document_available: true,
                                    ready_state: document.readyState,
                                    title: document.title.trim() || null,
                                    meta_description: description?.content.trim() || null,
                                    h1_headings: Array.from(
                                      document.querySelectorAll('h1')
                                    ).filter(visible).map(text).filter(Boolean),
                                    h2_headings: Array.from(
                                      document.querySelectorAll('h2')
                                    ).filter(visible).map(text).filter(Boolean),
                                    link_texts: links.map(text).filter(Boolean).slice(0, 1000),
                                    link_urls: links.map((link) => link.href)
                                      .filter(Boolean).slice(0, 1000)
                                  };
                                }"""
                            )
                            if (
                                not isinstance(raw, dict)
                                or raw.get("document_available") is not True
                                or page_url == "about:blank"
                            ):
                                raise WebsiteInspectionError(
                                    "No readable document was available after navigation.",
                                    category="render_timeout"
                                    if navigation_error
                                    and _is_navigation_timeout(navigation_error)
                                    else "render_unreadable",
                                )
                            rendered = RenderedDOM(
                                title=_optional_text(raw.get("title")),
                                meta_description=_optional_text(
                                    raw.get("meta_description")
                                ),
                                h1_headings=_unique_texts(raw.get("h1_headings")),
                                h2_headings=_unique_texts(raw.get("h2_headings")),
                                link_texts=_unique_texts(raw.get("link_texts")),
                                link_urls=_unique_texts(raw.get("link_urls")),
                            )
                            observed_fields = _rendered_dom_fields(rendered)
                            blocked_resources_for_page = sorted(
                                blocked_resources.get(url, set())
                            )
                            blocked_message = (
                                "Blocked requests (warnings): "
                                + ", ".join(blocked_resources_for_page)
                                if blocked_resources_for_page
                                else None
                            )
                            warning_category: str | None = None
                            warning_messages: list[str] = []
                            if navigation_error is not None:
                                warning_category = (
                                    "render_timeout"
                                    if _is_navigation_timeout(navigation_error)
                                    else "render_failed"
                                )
                                warning_messages.append(
                                    "Partial DOM was readable after navigation "
                                    f"ended with {type(navigation_error).__name__}; "
                                    "fields observed: "
                                    + (", ".join(observed_fields) or "none")
                                    + "."
                                )
                            elif response is not None and response.status != 200:
                                warning_category = "render_http_error"
                                warning_messages.append(
                                    f"DOM navigation returned HTTP {response.status}; "
                                    "readable fields were retained."
                                )
                            elif url in request_budget_exhausted:
                                warning_category = "render_request_budget_exhausted"
                                warning_messages.append(
                                    "The browser request budget was exhausted after "
                                    "a readable DOM was captured."
                                )
                            elif blocked_message:
                                warning_category = "external_resources_blocked"
                            if not observed_fields and warning_category is None:
                                warning_category = "render_empty"
                                warning_messages.append(
                                    "A document was readable but contained no non-empty "
                                    "requested fields."
                                )
                            if blocked_message:
                                warning_messages.append(blocked_message)
                            outcomes[url] = RenderedDOMOutcome(
                                rendered,
                                warning_category,
                                " ".join(warning_messages) or None,
                            )
                        except Exception as error:
                            blocked_types = blocked_resources.get(url, set())
                            category = getattr(error, "category", None) or (
                                "external_navigation_blocked"
                                if any(
                                    item.startswith(
                                        "document:external_navigation_blocked"
                                    )
                                    for item in blocked_types
                                )
                                else "render_timeout"
                                if _is_navigation_timeout(error)
                                else "render_failed"
                            )
                            detail = f"{type(error).__name__}: {error}"
                            all_blocked_resources = blocked_resources.get(url, set())
                            if all_blocked_resources:
                                detail += " Blocked requests (warnings): " + ", ".join(
                                    sorted(all_blocked_resources)
                                )
                            outcomes[url] = RenderedDOMOutcome(None, category, detail)
                    context.close()
                finally:
                    browser.close()
        except WebsiteInspectionError:
            raise
        except Exception as error:
            if not outcomes:
                raise WebsiteInspectionError(
                    "The local Playwright browser is unavailable: "
                    f"{type(error).__name__}: {error}",
                    category="browser_unavailable",
                ) from error
        for url in urls:
            outcomes.setdefault(
                url,
                RenderedDOMOutcome(
                    None,
                    "render_unavailable",
                    "No DOM capture outcome was returned for this URL.",
                ),
            )
        return outcomes


def _canonical_host(host: str) -> str:
    return host.casefold().removeprefix("www.").rstrip(".")


def _validate_url(
    url: str,
    *,
    root_host: str | None = None,
    resolve_host: bool = True,
) -> str:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as error:
        raise WebsiteInspectionError(
            "Malformed website URL.", category="invalid_url"
        ) from error
    if parts.scheme.casefold() not in {"http", "https"} or not parts.hostname:
        raise WebsiteInspectionError(
            "Only absolute HTTP and HTTPS website URLs are supported.",
            category="invalid_url",
        )
    if parts.username is not None or parts.password is not None:
        raise WebsiteInspectionError(
            "Website URLs containing credentials are not allowed.",
            category="invalid_url",
        )
    if has_sensitive_query_parameter(url):
        raise WebsiteInspectionError(
            "Website URLs with authentication-like query parameters are not allowed.",
            category="sensitive_url",
        )
    if port not in {None, 80, 443}:
        raise WebsiteInspectionError(
            "Non-standard destination ports are not allowed.",
            category="invalid_url",
        )
    host = parts.hostname.rstrip(".")
    if host.casefold() == "localhost" or host.casefold().endswith(".local"):
        raise WebsiteInspectionError(
            "Local and private network destinations are not allowed.",
            category="blocked_destination",
        )
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise WebsiteInspectionError(
            "Local and private network destinations are not allowed.",
            category="blocked_destination",
        )
    if root_host is not None and _canonical_host(host) != _canonical_host(root_host):
        raise WebsiteInspectionError(
            "A redirect or page points outside the inspected website domain.",
            category="cross_domain_redirect",
        )
    if resolve_host and address is None:
        try:
            resolved = socket.getaddrinfo(
                host, port or (443 if parts.scheme == "https" else 80)
            )
        except OSError as error:
            raise WebsiteInspectionError(
                "The website host could not be resolved.",
                category="dns_error",
                stage="dns_resolution",
            ) from error
        addresses: set[str] = set()
        for item in resolved:
            sockaddr = item[4]
            if (
                isinstance(sockaddr, tuple)
                and sockaddr
                and isinstance(sockaddr[0], str)
            ):
                addresses.add(sockaddr[0].split("%", 1)[0])
        if not addresses or any(
            not ipaddress.ip_address(item).is_global for item in addresses
        ):
            raise WebsiteInspectionError(
                "The website resolves to a local or private network destination.",
                category="blocked_destination",
            )
    path = parts.path or "/"
    return strip_tracking_parameters(
        urlunsplit((parts.scheme.casefold(), parts.netloc, path, parts.query, ""))
    )


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, root_host: str) -> None:
        super().__init__()
        self.root_host = root_host

    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        target = urljoin(req.full_url, newurl)
        _validate_url(target, root_host=self.root_host)
        return super().redirect_request(req, fp, code, msg, headers, target)


def _http_get(url: str, timeout: int, byte_limit: int, root_host: str) -> FetchResponse:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml,text/plain,*/*;q=0.5",
            "Accept-Encoding": "identity",
        },
    )
    opener = build_opener(_SafeRedirectHandler(root_host))
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(byte_limit + 1)
            if len(body) > byte_limit:
                raise WebsiteInspectionError(
                    "A website response exceeded the 2 MB response limit.",
                    category="oversized_response",
                )
            return FetchResponse(
                body=body,
                status_code=response.status,
                final_url=response.geturl(),
                content_type=response.headers.get("Content-Type"),
                x_robots_tag=response.headers.get("X-Robots-Tag"),
            )
    except WebsiteInspectionError:
        raise
    except HTTPError as error:
        if error.code == 404:
            return FetchResponse(
                b"", 404, error.geturl(), error.headers.get("Content-Type")
            )
        raise WebsiteInspectionError(
            f"Website returned HTTP {error.code}.", category="http_error"
        ) from error
    except TimeoutError as error:
        raise WebsiteInspectionError(
            "Website request timed out.", category="timeout"
        ) from error
    except socket.timeout as error:
        raise WebsiteInspectionError(
            "Website request timed out.", category="timeout"
        ) from error
    except URLError as error:
        reason = error.reason
        if isinstance(reason, TimeoutError | socket.timeout):
            raise WebsiteInspectionError(
                "Website request timed out.", category="timeout"
            ) from error
        if isinstance(reason, WebsiteInspectionError):
            raise reason from error
        raise WebsiteInspectionError(
            "Website request failed.", category="network_error"
        ) from error
    except OSError as error:
        raise WebsiteInspectionError(
            "Website request failed.", category="network_error"
        ) from error


class _DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: list[str] = []
        self.description: str | None = None
        self.robots_directives: list[str] = []
        self.h1: list[str] = []
        self.h2: list[str] = []
        self.text: list[str] = []
        self.links: list[str] = []
        self.link_texts: list[str] = []
        self._link_depth = 0
        self._link_text: list[str] = []
        self.jsonld: list[str] = []
        self.emails: list[str] = []
        self.phones: list[str] = []
        self.site_name: str | None = None
        self._title_open = False
        self._heading: int | None = None
        self._heading_text: list[str] = []
        self._skip_depth = 0
        self._script_jsonld = False
        self._script_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.casefold(): value for key, value in attrs if value is not None}
        tag = tag.casefold()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            self._script_jsonld = (
                tag == "script"
                and attrs_map.get("type", "").casefold() == "application/ld+json"
            )
            self._script_text = []
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._title_open = True
        elif tag == "body":
            self._title_open = False
        elif tag in {"h1", "h2"}:
            self._heading = int(tag[1])
            self._heading_text = []
        elif tag == "meta":
            name = attrs_map.get("name", "").casefold()
            prop = attrs_map.get("property", "").casefold()
            content = attrs_map.get("content", "").strip()
            if name == "description" and content:
                self.description = content
            if name in {"robots", "googlebot", "bingbot"} and content:
                self.robots_directives.extend(
                    directive.strip().casefold()
                    for directive in content.split(",")
                    if directive.strip()
                )
            if prop == "og:site_name" and content:
                self.site_name = content
        elif tag == "a":
            if self._link_depth == 0:
                self._link_text = []
            self._link_depth += 1
            href = attrs_map.get("href")
            if href:
                self.links.append(href)
                if href.casefold().startswith("mailto:"):
                    self.emails.append(href[7:].split("?", 1)[0])
                if href.casefold().startswith("tel:"):
                    self.phones.append(href[4:].split("?", 1)[0])

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if self._skip_depth:
            if tag in {"script", "style", "noscript", "svg"}:
                self._skip_depth = max(0, self._skip_depth - 1)
                if self._script_jsonld:
                    self.jsonld.append("".join(self._script_text))
                self._script_jsonld = False
            return
        if tag == "a" and self._link_depth:
            self._link_depth -= 1
            if self._link_depth == 0:
                link_text = _normalize_space("".join(self._link_text))
                if link_text:
                    self.link_texts.append(link_text)
                self._link_text = []
        elif tag == "title":
            self._title_open = False
        elif tag in {"h1", "h2"} and self._heading == int(tag[1]):
            heading = _normalize_space("".join(self._heading_text))
            if heading:
                (self.h1 if tag == "h1" else self.h2).append(heading)
            self._heading = None
            self._heading_text = []

    def handle_data(self, data: str) -> None:
        if self._script_jsonld:
            self._script_text.append(data)
        if self._skip_depth:
            return
        if self._title_open:
            self.title.append(data)
        if self._heading is not None:
            self._heading_text.append(data)
        if self._link_depth:
            self._link_text.append(data)
        stripped = data.strip()
        if stripped:
            self.text.append(stripped)


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _optional_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return _normalize_space(value)
    return None


def _unique_texts(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(
        dict.fromkeys(
            normalized
            for item in value
            if isinstance(item, str) and (normalized := _normalize_space(item))
        )
    )


def _relevant_score(url: str) -> int:
    path = urlsplit(url).path.casefold()
    tokens = {
        "service-area": 12,
        "service_area": 12,
        "location": 10,
        "contact": 10,
        "service": 8,
        "servicio": 8,
        "product": 8,
        "catalog": 8,
        "shop": 8,
        "tienda": 8,
        "offer": 8,
        "oferta": 8,
        "solution": 8,
        "solucion": 8,
        "about": 7,
        "residential": 6,
        "commercial": 6,
        "deep": 5,
        "move": 5,
        "vacation": 5,
        "airbnb": 5,
        "vrbo": 5,
        "carpet": 4,
        "upholstery": 4,
        "clean": 3,
    }
    return sum(weight for token, weight in tokens.items() if token in path)


def _same_site(url: str, root_host: str) -> bool:
    host = urlsplit(url).hostname
    return host is not None and _canonical_host(host) == _canonical_host(root_host)


def _jsonld_objects(values: Iterable[str]) -> tuple[dict[str, object], ...]:
    output: list[dict[str, object]] = []

    def collect(node: object) -> None:
        if isinstance(node, dict):
            output.append(cast(dict[str, object], node))
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    for raw in values:
        try:
            collect(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            continue
    return tuple(output)


def _text_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return _normalize_space(value)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    return None


def _number_value(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _field_text(value: object) -> str | None:
    if isinstance(value, dict):
        return _text_value(value.get("name")) or _text_value(value.get("@id"))
    if isinstance(value, list):
        items = [text for item in value if (text := _field_text(item))]
        return ", ".join(items) if items else None
    return _text_value(value)


def _address_parts(
    value: object,
) -> tuple[str | None, str | None, str | None, str | None]:
    if not isinstance(value, dict):
        return None, None, None, None
    street = _text_value(value.get("streetAddress"))
    city = _text_value(value.get("addressLocality"))
    state = _normalized_state(_text_value(value.get("addressRegion")))
    postal = _text_value(value.get("postalCode"))
    return street, city, state, postal


def _normalized_state(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _STATE_ALIASES.get(value.casefold(), value)
    if normalized.casefold() in {
        "example region",
        "sample region",
        "test region",
        "united states",
        "usa",
        "us",
    }:
        return None
    return normalized


def _is_neighborhood_name(value: str) -> bool:
    return _normalize_space(value).casefold() in _NEIGHBORHOOD_NAMES


def _is_usable_place_name(value: str) -> bool:
    normalized = _normalize_space(value).strip(" -:;,.()")
    if len(normalized) < 4:
        return False
    if not re.fullmatch(
        r"[A-Za-z][A-Za-z'’.-]*(?:\s+[A-Za-z][A-Za-z'’.-]*){0,3}",
        normalized,
    ):
        return False
    words = {word.casefold() for word in normalized.split()}
    if any(len(word) < 2 for word in words):
        return False
    if words & _GENERIC_PLACE_WORDS:
        return False
    if any(word in _STATE_ALIASES and len(word) <= 2 for word in words):
        return False
    return True


def _text_addresses(
    text: str,
) -> Iterable[tuple[str, str, str, str | None, int, int]]:
    state_regex = "|".join(
        sorted((re.escape(item) for item in _STATE_ALIASES), key=len, reverse=True)
    )
    suffixes = (
        "Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Court|Ct|Lane|Ln|"
        "Circle|Cir|Way|Parkway|Pkwy|Terrace|Ter|Place|Pl|Highway|Hwy"
    )
    pattern = re.compile(
        rf"(?P<street>\b\d{{1,6}}\s+(?:[A-Z0-9.'#-]+\s+){{1,7}}(?:{suffixes})\.?"
        rf"(?:\s+(?:N|S|E|W|North|South|East|West))?"
        rf"(?:\s+(?:Apt|Apartment|Suite|Ste|Unit|#)\s*[A-Z0-9-]+)?)[, ]+"
        rf"(?P<city>[A-Z][A-Za-z'’.\-]+(?:\s+[A-Z][A-Za-z'’.\-]+){{0,3}}),\s*"
        rf"(?P<state>{state_regex})(?:\s+(?P<zip>\d{{5}}(?:-\d{{4}})?))?\b",
        re.I,
    )
    for match in pattern.finditer(text):
        state = _STATE_ALIASES[match.group("state").casefold()]
        yield (
            _normalize_space(match.group("street")),
            match.group("city"),
            state,
            match.group("zip"),
            match.start(),
            match.end(),
        )


def _schema_string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str) and value.strip():
        return (_normalize_space(value),)
    if isinstance(value, list):
        return tuple(text for item in value for text in _schema_string_values(item))
    if isinstance(value, dict):
        preferred = [
            _text_value(value.get(key))
            for key in ("dayOfWeek", "opens", "closes", "name", "@id")
        ]
        found = tuple(item for item in preferred if item)
        if found:
            return (" ".join(found),)
        return tuple(
            text for item in value.values() for text in _schema_string_values(item)
        )
    return ()


def _place(value: object) -> tuple[str, str | None, str | None] | None:
    if isinstance(value, dict):
        city = _text_value(value.get("name")) or _text_value(
            value.get("addressLocality")
        )
        state = _normalized_state(_text_value(value.get("addressRegion")))
        postal = _text_value(value.get("postalCode"))
        if city:
            return city, state, postal
        address = value.get("address")
        _, city, state, postal = _address_parts(address)
        if city:
            return city, state, postal
        return None
    text = _text_value(value)
    if not text:
        return None
    match = re.match(
        r"^\s*(.+?),\s*([A-Z]{2}|[A-Za-z ]+?)(?:\s+(\d{5}(?:-\d{4})?))?\s*$", text
    )
    if match and match.group(2).casefold() in _STATE_ALIASES:
        return (
            match.group(1).strip(),
            _STATE_ALIASES[match.group(2).casefold()],
            match.group(3),
        )
    return text.strip(), None, None


def _sentence_for(text: str, start: int, end: int) -> str:
    left = (
        max(
            text.rfind(".", 0, start),
            text.rfind("!", 0, start),
            text.rfind("?", 0, start),
            text.rfind("\n", 0, start),
        )
        + 1
    )
    ends = [
        index
        for marker in (".", "!", "?", "\n")
        if (index := text.find(marker, end)) >= 0
    ]
    right = min(ends) + 1 if ends else len(text)
    return _normalize_space(text[left:right])[:_MAX_EVIDENCE_EXCERPT]


def _service_matches(text: str) -> Iterable[tuple[str, re.Match[str]]]:
    matches = [
        (service, match)
        for service, pattern in _SERVICE_PATTERNS
        for match in pattern.finditer(text)
    ]
    for service_list in _SERVICE_LIST_PATTERN.finditer(text):
        list_start, list_end = service_list.span("services")
        for item in _SERVICE_LIST_ITEM_PATTERN.finditer(text, list_start, list_end):
            item_name = _normalize_space(item.group("item")).casefold()
            category = _SERVICE_LIST_CATEGORIES.get(item_name)
            if category:
                matches.append((category, item))
    for service, match in matches:
        if service == "Recurring cleaning" and any(
            other_service == "Recurring house cleaning"
            and other_match.start() <= match.start()
            and match.end() <= other_match.end()
            for other_service, other_match in matches
        ):
            continue
        if service == "Home remodeling" and any(
            other_service == "Full home remodeling"
            and other_match.start() <= match.start()
            and match.end() <= other_match.end()
            for other_service, other_match in matches
        ):
            continue
        yield service, match


def _service_is_negated(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 100) : start].casefold()
    suffix = text[end : min(len(text), end + 80)].casefold()
    negated_before = re.search(
        r"\b(?:do not|don't|does not|doesn't|did not|never|no longer)\s+"
        r"(?:(?:currently|offer|provide|perform|include)\s+){0,3}$",
        prefix,
    )
    negated_after = re.match(
        r"\s*(?:(?:is|are)\s+)?(?:not offered|not available|unavailable|not a service we offer)",
        suffix,
    )
    return negated_before is not None or negated_after is not None


def _place_locations_in_text(
    text: str,
) -> Iterable[tuple[str, str | None, str | None, int, int]]:
    state_regex = "|".join(
        sorted((re.escape(item) for item in _STATE_ALIASES), key=len, reverse=True)
    )
    pattern = re.compile(
        rf"\b(?P<city>[A-Z][A-Za-z'’.\-]+(?:\s+[A-Z][A-Za-z'’.\-]+){{0,3}}),\s*(?P<state>(?i:{state_regex}))(?:\s+(?P<zip>\d{{5}}(?:-\d{{4}})?))?\b"
    )
    for match in pattern.finditer(text):
        city = _normalize_space(match.group("city"))
        if not _is_usable_place_name(city) or _is_neighborhood_name(city):
            continue
        state = _normalized_state(match.group("state"))
        yield city, state, match.group("zip"), match.start(), match.end()


def _explicit_service_area_places(
    text: str,
) -> Iterable[tuple[str, str | None, int, int, LocationType]]:
    lead = re.compile(
        r"\b(?:(?:areas?|cities?)\s+we\s+serve|we\s+serve|we\s+cover|"
        r"service\s+areas?\s+(?:include|are|cover(?:ed)?))\b\s*:?\s*"
        r"(?P<places>[^.!?\n]{2,360})",
        re.I,
    )
    state_expression = "|".join(
        sorted((re.escape(item) for item in _STATE_ALIASES), key=len, reverse=True)
    )
    state_pattern = re.compile(
        rf"(?<![A-Za-z])(?P<state>{state_expression})(?![A-Za-z])", re.I
    )
    for match in lead.finditer(text):
        value = match.group("places")
        value = re.split(
            r"\b(?:welcome to|quick links|contact us|free estimate|"
            r"project gallery|our services)\b",
            value,
            maxsplit=1,
            flags=re.I,
        )[0]
        state_match = state_pattern.search(value)
        state = _normalized_state(state_match.group("state")) if state_match else None
        without_state = state_pattern.sub(" ", value)
        segments = re.split(r"\s*(?:,|\band\b|&|/|\|)\s*", without_state)
        for segment in segments:
            candidate = re.sub(
                r"^(?:in|around|throughout|the|all)\s+", "", segment, flags=re.I
            )
            candidate = _normalize_space(candidate).strip(" -:;,.()")
            if not _is_usable_place_name(candidate):
                continue
            location_type = (
                LocationType.NEIGHBORHOOD_MENTION
                if _is_neighborhood_name(candidate)
                else LocationType.EXPLICITLY_SERVED_CITY
            )
            yield (
                candidate,
                state,
                match.start("places"),
                match.end("places"),
                location_type,
            )


def _regional_service_areas_in_text(
    text: str,
) -> Iterable[tuple[str, int, int]]:
    region_pattern = re.compile(
        r"\b(?P<region>DFW\s+Metro\s+Area|DFW\s+Metroplex|"
        r"Dallas[- ]Fort Worth\s+Metro(?:politan)?\s+Area)\b",
        re.I,
    )
    for match in region_pattern.finditer(text):
        prefix = text[max(0, match.start() - 80) : match.start()]
        if re.search(
            r"\b(?:serving|we\s+serve|areas?\s+we\s+serve|service\s+areas?)\b",
            prefix,
            re.I,
        ):
            yield _normalize_space(match.group("region")), match.start(), match.end()


class WebsiteInspector:
    """Inspect a public site with bounded HTTP and optional local DOM rendering."""

    def __init__(
        self,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        max_pages: int = MAX_PAGES,
        transport: Transport | None = None,
        renderer: DOMRenderer | None = None,
        clock: Clock | None = None,
    ) -> None:
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be at least one second")
        if not 1 <= max_response_bytes <= MAX_RESPONSE_BYTES:
            raise ValueError(
                f"max_response_bytes must be between 1 and {MAX_RESPONSE_BYTES}"
            )
        if not 1 <= max_pages <= MAX_PAGES:
            raise ValueError(f"max_pages must be between 1 and {MAX_PAGES}")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_pages = max_pages
        self._transport = transport
        # Keep browser rendering opt-in until network-level SSRF controls exist.
        self._renderer = renderer
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._request_count = 0

    def _fetch(self, url: str, root_host: str) -> FetchResponse:
        safe_url = _validate_url(
            url,
            root_host=root_host,
            resolve_host=self._transport is None,
        )
        self._request_count += 1
        if self._transport is not None:
            try:
                response = self._transport(
                    safe_url, self.timeout_seconds, self.max_response_bytes, root_host
                )
            except WebsiteInspectionError:
                raise
            except (TimeoutError, socket.timeout) as error:
                raise WebsiteInspectionError(
                    "Website request timed out.", category="timeout"
                ) from error
            except OSError as error:
                raise WebsiteInspectionError(
                    "Website request failed.", category="network_error"
                ) from error
        else:
            response = _http_get(
                safe_url, self.timeout_seconds, self.max_response_bytes, root_host
            )
        if len(response.body) > self.max_response_bytes:
            raise WebsiteInspectionError(
                "A website response exceeded the 2 MB response limit.",
                category="oversized_response",
            )
        safe_final_url = _validate_url(
            response.final_url,
            root_host=root_host,
            resolve_host=self._transport is None,
        )
        return replace(response, final_url=safe_final_url)

    def inspect(self, website_url: str) -> WebsiteInspectionResult:
        if not isinstance(website_url, str) or not website_url.strip():
            raise WebsiteInspectionError(
                "Website URL is required.", category="invalid_url"
            )
        requested_url = _validate_url(
            website_url.strip(), resolve_host=self._transport is None
        )
        root_host = cast(str, urlsplit(requested_url).hostname)
        requested_parts = urlsplit(requested_url)
        origin = f"{requested_parts.scheme}://{requested_parts.netloc}"
        robots_url = urljoin(origin, "/robots.txt")
        limitations: list[str] = []
        try:
            robots_response = self._fetch(robots_url, root_host)
            robot_parser, robots_status, robots_sitemaps, robots_restrictions = (
                _robots_policy(robots_response, robots_url)
            )
        except WebsiteInspectionError as error:
            if error.category in {"cross_domain_redirect", "blocked_destination"}:
                raise
            raise WebsiteInspectionError(
                f"robots.txt could not be checked ({error.category}); crawling stopped.",
                category=error.category,
                stage="robots.txt",
            ) from error
        if not robot_parser.can_fetch(USER_AGENT, requested_url):
            raise WebsiteInspectionError(
                "robots.txt disallows the homepage; no website pages were fetched.",
                category="robots_disallowed",
                stage="robots.txt",
            )
        home_response = self._fetch(requested_url, root_host)
        if home_response.status_code != 200:
            raise WebsiteInspectionError(
                f"Homepage returned HTTP {home_response.status_code}.",
                category="http_error",
            )
        home_parser = self._parse_html(home_response.body)
        final_url = home_response.final_url
        final_parts = urlsplit(final_url)
        final_origin = f"{final_parts.scheme}://{final_parts.netloc}"
        if final_origin.casefold() != origin.casefold():
            final_robots_url = urljoin(final_origin, "/robots.txt")
            try:
                final_robots = self._fetch(final_robots_url, root_host)
                robot_parser, robots_status, robots_sitemaps, robots_restrictions = (
                    _robots_policy(final_robots, final_robots_url)
                )
            except WebsiteInspectionError as error:
                if error.category in {"cross_domain_redirect", "blocked_destination"}:
                    raise
                raise WebsiteInspectionError(
                    f"robots.txt could not be checked ({error.category}); crawling stopped.",
                    category=error.category,
                    stage="robots.txt",
                ) from error
            if not robot_parser.can_fetch(USER_AGENT, final_url):
                raise WebsiteInspectionError(
                    "robots.txt disallows the redirected homepage; crawling stopped.",
                    category="robots_disallowed",
                    stage="robots.txt",
                )
            robots_url = final_robots_url
            origin = final_origin

        pages_raw: list[tuple[str, FetchResponse, _DocumentParser]] = [
            (final_url, home_response, home_parser)
        ]
        sitemap_urls: list[str] = []
        sitemaps_to_check = list(robots_sitemaps)
        sitemaps_to_check.append(urljoin(origin, "/sitemap.xml"))
        seen_sitemaps: set[str] = set()
        sitemap_page_urls: list[str] = []
        while sitemaps_to_check and len(seen_sitemaps) < MAX_SITEMAPS:
            sitemap = sitemaps_to_check.pop(0)
            sitemap, _ = urldefrag(urljoin(final_url, sitemap))
            if sitemap in seen_sitemaps or not _same_site(sitemap, root_host):
                continue
            if not robot_parser.can_fetch(USER_AGENT, sitemap):
                continue
            seen_sitemaps.add(sitemap)
            try:
                response = self._fetch(sitemap, root_host)
            except WebsiteInspectionError as error:
                limitations.append(f"Sitemap unavailable ({error.category}).")
                continue
            if response.status_code != 200:
                continue
            try:
                root = ET.fromstring(response.body)
            except ET.ParseError:
                limitations.append("A sitemap response was malformed XML.")
                continue
            root_name = root.tag.rsplit("}", 1)[-1].casefold()
            children = [
                item.text.strip()
                for item in root.iter()
                if item.tag.rsplit("}", 1)[-1].casefold() == "loc"
                and item.text
                and item.text.strip()
            ]
            if root_name == "sitemapindex":
                sitemaps_to_check.extend(children[:MAX_SITEMAPS])
            else:
                for candidate in children:
                    candidate, _ = urldefrag(urljoin(sitemap, candidate))
                    if (
                        _same_site(candidate, root_host)
                        and candidate not in sitemap_page_urls
                    ):
                        sitemap_page_urls.append(candidate)
                        if len(sitemap_page_urls) >= MAX_SITEMAP_URLS:
                            break
        sitemap_urls = sorted(seen_sitemaps)

        candidates: dict[str, int] = {}
        for candidate in (
            *sitemap_page_urls,
            *(urljoin(final_url, item) for item in home_parser.links),
        ):
            candidate, _ = urldefrag(candidate)
            if not _same_site(candidate, root_host) or candidate == final_url:
                continue
            score = _relevant_score(candidate)
            if score > 0 and robot_parser.can_fetch(USER_AGENT, candidate):
                candidates[candidate] = max(score, candidates.get(candidate, 0))
        ordered = sorted(candidates, key=lambda item: (-candidates[item], item))
        for page_url in ordered[: self.max_pages - 1]:
            try:
                response = self._fetch(page_url, root_host)
            except WebsiteInspectionError as error:
                limitations.append(f"Page could not be inspected ({error.category}).")
                continue
            if response.status_code != 200:
                limitations.append(
                    f"Page returned HTTP {response.status_code}: {page_url}"
                )
                continue
            parser = self._parse_html(response.body)
            pages_raw.append((response.final_url, response, parser))
        if len(candidates) > self.max_pages - 1:
            limitations.append(
                f"Page crawl stopped at the {self.max_pages}-page limit."
            )

        rendered_pages: Mapping[str, RenderedDOMOutcome] = {}
        if self._renderer is not None:
            try:
                rendered_pages = self._renderer(
                    tuple(item[0] for item in pages_raw),
                    root_host,
                    self.timeout_seconds,
                )
            except WebsiteInspectionError as error:
                rendered_pages = {
                    item[0]: RenderedDOMOutcome(
                        None,
                        error.category,
                        str(error),
                    )
                    for item in pages_raw
                }
            except Exception as error:
                rendered_pages = {
                    item[0]: RenderedDOMOutcome(
                        None,
                        "render_failed",
                        f"{type(error).__name__}: {error}",
                    )
                    for item in pages_raw
                }
            rendered_pages = {
                item[0]: rendered_pages.get(
                    item[0],
                    RenderedDOMOutcome(
                        None,
                        "render_unavailable",
                        "No DOM capture outcome was returned for this URL.",
                    ),
                )
                for item in pages_raw
            }
            successful_render_count = sum(
                outcome.dom is not None for outcome in rendered_pages.values()
            )
            if successful_render_count:
                limitations.append(
                    "DOM capturado con Playwright sin interacciones; los recursos de otros dominios y las solicitudes HTTP distintas de GET se bloquearon."
                )
                failed_render_count = len(rendered_pages) - successful_render_count
                if failed_render_count:
                    categories = sorted(
                        {
                            outcome.error_category
                            for outcome in rendered_pages.values()
                            if outcome.dom is None and outcome.error_category
                        }
                    )
                    limitations.append(
                        f"DOM no disponible para {failed_render_count} páginas ({', '.join(categories) or 'fallo de renderizado'}); se informa HTML_ONLY por URL."
                    )
            elif pages_raw:
                categories = sorted(
                    {
                        outcome.error_category
                        for outcome in rendered_pages.values()
                        if outcome.error_category
                    }
                )
                reason = ", ".join(categories) or "browser_unavailable"
                limitations.append(
                    f"DOM renderizado no disponible ({reason}); las páginas quedaron como HTML_ONLY."
                )
            render_errors = [
                f"{url}: {outcome.error_category}: {outcome.error_message}"
                for url, outcome in rendered_pages.items()
                if outcome.error_message
            ]
            if render_errors:
                limitations.append(
                    "Detalle de errores de captura DOM: " + " | ".join(render_errors)
                )

        return self._build_result(
            requested_url=requested_url,
            final_url=final_url,
            pages_raw=pages_raw,
            robots_status=robots_status,
            robots_sitemaps=tuple(robots_sitemaps),
            robots_restrictions=tuple(robots_restrictions),
            sitemap_urls=tuple(sitemap_urls),
            rendered_pages=rendered_pages,
            limitations=tuple(dict.fromkeys(limitations)),
        )

    @staticmethod
    def _parse_html(body: bytes) -> _DocumentParser:
        parser = _DocumentParser()
        html = body.decode("utf-8", errors="replace")
        html = re.sub(
            r"(<title\b[^>]*>)((?:(?!</title>).)*?)(?=<body\b)",
            r"\1\2</title>",
            html,
            flags=re.I | re.S,
        )
        parser.feed(html)
        parser.close()
        return parser

    def _build_result(
        self,
        *,
        requested_url: str,
        final_url: str,
        pages_raw: list[tuple[str, FetchResponse, _DocumentParser]],
        robots_status: str,
        robots_sitemaps: tuple[str, ...],
        robots_restrictions: tuple[str, ...],
        sitemap_urls: tuple[str, ...],
        rendered_pages: Mapping[str, RenderedDOMOutcome],
        limitations: tuple[str, ...],
    ) -> WebsiteInspectionResult:
        retrieved_at = self._clock().astimezone(timezone.utc)
        pages: list[WebsitePage] = []
        all_jsonld: list[tuple[str, dict[str, object]]] = []
        all_text: list[tuple[str, str]] = []
        all_emails: list[str] = []
        all_phones: list[str] = []
        for url, response, parser in pages_raw:
            title_text = re.sub(r"<[^>]*>", "", "".join(parser.title))
            title = _normalize_space(title_text) or None
            text = _normalize_space(" ".join(parser.text))[:_MAX_TEXT_CHARS]
            rendered = rendered_pages.get(url, RenderedDOMOutcome(None))
            rendered_dom = rendered.dom
            pages.append(
                WebsitePage(
                    url=url,
                    status_code=response.status_code,
                    title=title,
                    meta_description=parser.description,
                    h1_headings=tuple(dict.fromkeys(parser.h1)),
                    h2_headings=tuple(dict.fromkeys(parser.h2)),
                    main_text=text,
                    link_texts=tuple(dict.fromkeys(parser.link_texts)),
                    link_urls=_page_link_urls(url, parser.links),
                    robots_directives=tuple(dict.fromkeys(parser.robots_directives)),
                    x_robots_tag=response.x_robots_tag,
                    inspection_method=(
                        "HTTP_AND_RENDERED_DOM"
                        if rendered_dom is not None
                        else "HTML_ONLY"
                    ),
                    rendered_title=rendered_dom.title if rendered_dom else None,
                    rendered_meta_description=(
                        rendered_dom.meta_description if rendered_dom else None
                    ),
                    rendered_h1_headings=(
                        rendered_dom.h1_headings if rendered_dom else ()
                    ),
                    rendered_h2_headings=(
                        rendered_dom.h2_headings if rendered_dom else ()
                    ),
                    rendered_link_texts=(
                        rendered_dom.link_texts if rendered_dom else ()
                    ),
                    rendered_link_urls=(rendered_dom.link_urls if rendered_dom else ()),
                    rendered_dom_error=rendered.error_category,
                    rendered_dom_error_message=rendered.error_message,
                )
            )
            all_jsonld.extend((url, obj) for obj in _jsonld_objects(parser.jsonld))
            all_text.append((url, text))
            all_emails.extend(parser.emails)
            all_phones.extend(parser.phones)
            all_emails.extend(
                re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.I)
            )
            all_phones.extend(
                re.findall(
                    r"(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}\b", text
                )
            )

        home_parser = pages_raw[0][2]
        objects = [obj for _, obj in all_jsonld]
        structured_data_types = tuple(
            sorted(
                {
                    schema_type
                    for obj in objects
                    for schema_type in _schema_type_names(obj)
                },
                key=str.casefold,
            )
        )
        business_object = next(
            (
                obj
                for obj in objects
                if _schema_has_type(
                    obj,
                    {
                        "LocalBusiness",
                        "HomeAndConstructionBusiness",
                        "CleaningService",
                        "Organization",
                    },
                )
            ),
            {},
        )
        business_name = (
            _text_value(business_object.get("name"))
            or home_parser.site_name
            or (
                _normalize_space("".join(home_parser.title))
                .split(" | ")[0]
                .split(" – ")[0]
                .strip()
                or None
            )
        )
        structured_phone = _field_text(business_object.get("telephone"))
        structured_email = _field_text(business_object.get("email"))
        address_obj = business_object.get("address")
        street, address_city, address_state, address_postal = _address_parts(
            address_obj
        )
        address_value = (
            ", ".join(
                item
                for item in (street, address_city, address_state, address_postal)
                if item
            )
            or None
        )
        opening_hours_raw = business_object.get("openingHours") or business_object.get(
            "openingHoursSpecification"
        )
        opening_hours = _schema_string_values(opening_hours_raw)
        same_as = _schema_string_values(business_object.get("sameAs"))
        geo = business_object.get("geo")
        latitude = _number_value(geo.get("latitude")) if isinstance(geo, dict) else None
        longitude = (
            _number_value(geo.get("longitude")) if isinstance(geo, dict) else None
        )
        if latitude is not None and not -90 <= latitude <= 90:
            latitude = None
        if longitude is not None and not -180 <= longitude <= 180:
            longitude = None

        evidence: list[SourceEvidence] = []
        signals: list[WebsiteSignal] = []
        used_evidence: set[str] = set()

        def add_evidence(
            *,
            field: str,
            value: JsonScalar,
            source_url: str,
            excerpt: str,
            kind: EvidenceKind,
            confidence: float,
            assumptions: tuple[str, ...] = (),
        ) -> str:
            base = f"{field}\0{source_url}\0{value!r}\0{excerpt}"
            evidence_id = "website:" + sha256(base.encode("utf-8")).hexdigest()[:24]
            while evidence_id in used_evidence:
                evidence_id += "x"
            used_evidence.add(evidence_id)
            evidence.append(
                SourceEvidence(
                    evidence_id=evidence_id,
                    kind=kind,
                    subject=business_name or urlsplit(final_url).hostname or final_url,
                    field=field,
                    value=value,
                    source_name="Public business website",
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                    excerpt=excerpt[:_MAX_EVIDENCE_EXCERPT],
                    confidence=confidence,
                    assumptions=assumptions,
                )
            )
            return evidence_id

        home_page = pages[0]
        for field, value, excerpt in (
            ("page_title", home_page.title, home_page.title),
            (
                "meta_description",
                home_page.meta_description,
                home_page.meta_description,
            ),
            ("business_name", business_name, business_name),
            (
                "phone",
                structured_phone or _first_unique(all_phones),
                structured_phone or _first_unique(all_phones),
            ),
            (
                "email",
                structured_email or _first_unique(all_emails),
                structured_email or _first_unique(all_emails),
            ),
            ("address", address_value, address_value),
        ):
            if value:
                source_url = final_url
                evidence_id = add_evidence(
                    field=field,
                    value=value,
                    source_url=source_url,
                    excerpt=str(excerpt or value),
                    kind=EvidenceKind.OBSERVED,
                    confidence=0.9,
                )
                signals.append(
                    WebsiteSignal(field=field, value=value, evidence_id=evidence_id)
                )
        for coordinate_field, coordinate_value in (
            ("geo.latitude", latitude),
            ("geo.longitude", longitude),
        ):
            if coordinate_value is not None:
                evidence_id = add_evidence(
                    field=coordinate_field,
                    value=coordinate_value,
                    source_url=final_url,
                    excerpt=f"JSON-LD geo field {coordinate_field}: {coordinate_value}",
                    kind=EvidenceKind.OBSERVED,
                    confidence=0.9,
                )
                signals.append(
                    WebsiteSignal(
                        field=coordinate_field,
                        value=coordinate_value,
                        evidence_id=evidence_id,
                    )
                )

        locations: list[LocationCandidate] = []
        services: list[ServiceCandidate] = []
        service_conflicts: dict[str, set[str]] = {}
        for page in pages:
            candidate_texts = (
                page.title or "",
                page.meta_description or "",
                *page.h1_headings,
                *page.h2_headings,
                page.main_text,
            )
            for text in candidate_texts:
                for service, match in _service_matches(text):
                    if _service_is_negated(text, match.start(), match.end()):
                        service_conflicts.setdefault(service, set()).add(page.url)

        def add_service_candidate(
            *,
            service: str,
            source_url: str,
            supporting_text: str,
            field: str,
            kind: EvidenceKind,
            confidence: float,
            verification_status: VerificationStatus,
            assumptions: tuple[str, ...] = (),
        ) -> None:
            if source_url in service_conflicts.get(service, set()):
                return
            evidence_id = add_evidence(
                field=field,
                value=service,
                source_url=source_url,
                excerpt=supporting_text,
                kind=kind,
                confidence=confidence,
                assumptions=assumptions,
            )
            services.append(
                ServiceCandidate(
                    service=service,
                    source_url=source_url,
                    supporting_text=supporting_text,
                    evidence_classification=kind,
                    confidence=confidence,
                    verification_status=verification_status,
                    evidence_id=evidence_id,
                )
            )

        for source_url, obj in all_jsonld:
            is_business = _schema_has_type(
                obj,
                {
                    "LocalBusiness",
                    "HomeAndConstructionBusiness",
                    "CleaningService",
                    "Organization",
                },
            )
            if is_business and obj.get("address") is not None:
                street_part, city, state, postal = _address_parts(obj.get("address"))
                if city:
                    address_parts = [
                        part for part in (street_part, city, state, postal) if part
                    ]
                    excerpt = "JSON-LD address: " + ", ".join(address_parts)
                    evidence_id = add_evidence(
                        field="address.addressLocality",
                        value=city,
                        source_url=source_url,
                        excerpt=excerpt,
                        kind=EvidenceKind.REPORTED,
                        confidence=0.88,
                    )
                    locations.append(
                        LocationCandidate(
                            city=city,
                            state=state,
                            postal_code=postal,
                            location_type=LocationType.BUSINESS_ADDRESS,
                            source_url=source_url,
                            supporting_text=excerpt,
                            evidence_classification=EvidenceKind.REPORTED,
                            confidence=0.88,
                            verification_status=VerificationStatus.WEBSITE_REPORTED,
                            evidence_id=evidence_id,
                        )
                    )
            if is_business and obj.get("location") is not None:
                operating_location = obj.get("location")
                location_address = (
                    operating_location.get("address")
                    if isinstance(operating_location, dict)
                    else None
                )
                _, city, state, postal = _address_parts(location_address)
                if city:
                    excerpt = "JSON-LD location.address field: " + ", ".join(
                        value for value in (city, state, postal) if value
                    )
                    evidence_id = add_evidence(
                        field="location.addressLocality",
                        value=city,
                        source_url=source_url,
                        excerpt=excerpt,
                        kind=EvidenceKind.REPORTED,
                        confidence=0.88,
                    )
                    locations.append(
                        LocationCandidate(
                            city=city,
                            state=state,
                            postal_code=postal,
                            location_type=LocationType.PHYSICAL_OPERATING_LOCATION,
                            source_url=source_url,
                            supporting_text=excerpt,
                            evidence_classification=EvidenceKind.REPORTED,
                            confidence=0.88,
                            verification_status=VerificationStatus.WEBSITE_REPORTED,
                            evidence_id=evidence_id,
                        )
                    )
            if is_business and obj.get("areaServed") is not None:
                raw_areas = obj.get("areaServed")
                area_values = raw_areas if isinstance(raw_areas, list) else [raw_areas]
                for area in area_values:
                    place = _place(area)
                    if not place:
                        continue
                    city, state, postal = place
                    excerpt = "JSON-LD areaServed field: " + (_field_text(area) or city)
                    evidence_id = add_evidence(
                        field="areaServed",
                        value=city,
                        source_url=source_url,
                        excerpt=excerpt,
                        kind=EvidenceKind.REPORTED,
                        confidence=0.94,
                    )
                    locations.append(
                        LocationCandidate(
                            city=city,
                            state=state,
                            postal_code=postal,
                            location_type=(
                                LocationType.NEIGHBORHOOD_MENTION
                                if _is_neighborhood_name(city)
                                else LocationType.SERVICE_AREA
                            ),
                            source_url=source_url,
                            supporting_text=excerpt,
                            evidence_classification=EvidenceKind.REPORTED,
                            confidence=0.94,
                            verification_status=VerificationStatus.WEBSITE_REPORTED,
                            evidence_id=evidence_id,
                        )
                    )
            service_types = obj.get("serviceType")
            if service_types is not None and is_business:
                raw_services = (
                    service_types
                    if isinstance(service_types, list)
                    else [service_types]
                )
                for raw_service in raw_services:
                    service_text = _field_text(raw_service)
                    if service_text:
                        for service, _ in _service_matches(service_text):
                            add_service_candidate(
                                service=service,
                                source_url=source_url,
                                supporting_text="JSON-LD serviceType field: "
                                + service_text,
                                field="serviceType",
                                kind=EvidenceKind.REPORTED,
                                confidence=0.9,
                                verification_status=VerificationStatus.WEBSITE_REPORTED,
                            )
        for source_url, obj in all_jsonld:
            if _schema_has_type(obj, {"Service"}):
                service_name = _text_value(obj.get("name")) or _field_text(
                    obj.get("serviceType")
                )
                if service_name:
                    for category, _ in _service_matches(service_name):
                        add_service_candidate(
                            service=category,
                            source_url=source_url,
                            supporting_text="JSON-LD Service name: " + service_name,
                            field="Service.name",
                            kind=EvidenceKind.REPORTED,
                            confidence=0.9,
                            verification_status=VerificationStatus.WEBSITE_REPORTED,
                        )

        for page in pages:
            is_editorial_page = (
                re.match(
                    r"^/(?:blog|news|resources?|guides?)(?:/|$)",
                    urlsplit(page.url).path,
                    re.I,
                )
                is not None
            )
            for link_text in page.link_texts:
                for service, _ in _service_matches(link_text):
                    add_service_candidate(
                        service=service,
                        source_url=page.url,
                        supporting_text="Navigation link: " + link_text,
                        field="anchor_text",
                        kind=EvidenceKind.REPORTED,
                        confidence=0.86,
                        verification_status=VerificationStatus.WEBSITE_REPORTED,
                    )
            explicit_fields: tuple[tuple[str, str | None, str], ...] = (
                ("page_title", page.title, "Page title: "),
                ("meta_description", page.meta_description, "Meta description: "),
                *(("h1_heading", heading, "H1: ") for heading in page.h1_headings),
                *(("h2_heading", heading, "H2: ") for heading in page.h2_headings),
            )
            for field, raw_text, prefix in explicit_fields:
                if not raw_text:
                    continue
                if is_editorial_page and not _SERVICE_OFFER_CONTEXT.search(raw_text):
                    continue
                for service, _ in _service_matches(raw_text):
                    add_service_candidate(
                        service=service,
                        source_url=page.url,
                        supporting_text=prefix + raw_text,
                        field=field,
                        kind=EvidenceKind.REPORTED,
                        confidence=0.86 if field != "meta_description" else 0.82,
                        verification_status=VerificationStatus.WEBSITE_REPORTED,
                    )

            page_path = urlsplit(page.url).path.rstrip("/").casefold()
            is_service_page = (
                re.match(r"^/(?:our-)?services(?:/|$)", page_path, re.I) is not None
            )
            for service, match in _service_matches(page.main_text):
                if not is_service_page and not _SERVICE_OFFER_CONTEXT.search(
                    _sentence_for(page.main_text, match.start(), match.end())
                ):
                    continue
                add_service_candidate(
                    service=service,
                    source_url=page.url,
                    supporting_text=_sentence_for(
                        page.main_text, match.start(), match.end()
                    ),
                    field="service_description",
                    kind=EvidenceKind.REPORTED,
                    confidence=0.82,
                    verification_status=VerificationStatus.WEBSITE_REPORTED,
                )

            is_contact_page = any(
                word in page.url.casefold() for word in ("contact", "location", "about")
            )
            contact_addresses = (
                tuple(_text_addresses(page.main_text)) if is_contact_page else ()
            )
            address_spans = tuple(
                (address[4], address[5]) for address in contact_addresses
            )
            for city, state, postal, start, end in _place_locations_in_text(
                page.main_text
            ):
                if any(
                    start < address_end and address_start < end
                    for address_start, address_end in address_spans
                ):
                    continue
                excerpt = _normalize_space(
                    page.main_text[
                        max(0, start - 80) : min(len(page.main_text), end + 80)
                    ]
                )
                evidence_id = add_evidence(
                    field="geographic_reference",
                    value=city,
                    source_url=page.url,
                    excerpt=excerpt,
                    kind=EvidenceKind.REPORTED,
                    confidence=0.55,
                )
                locations.append(
                    LocationCandidate(
                        city=city,
                        state=state,
                        postal_code=postal,
                        location_type=LocationType.CITY_MENTION,
                        source_url=page.url,
                        supporting_text=excerpt,
                        evidence_classification=EvidenceKind.REPORTED,
                        confidence=0.55,
                        verification_status=VerificationStatus.WEBSITE_REPORTED,
                        evidence_id=evidence_id,
                    )
                )
            for city, state, start, end, location_type in _explicit_service_area_places(
                page.main_text
            ):
                excerpt = _normalize_space(
                    page.main_text[
                        max(0, start - 50) : min(len(page.main_text), end + 50)
                    ]
                )
                evidence_id = add_evidence(
                    field="explicit_service_area",
                    value=city,
                    source_url=page.url,
                    excerpt=excerpt,
                    kind=EvidenceKind.REPORTED,
                    confidence=0.88,
                )
                locations.append(
                    LocationCandidate(
                        city=city,
                        state=state,
                        postal_code=None,
                        location_type=location_type,
                        source_url=page.url,
                        supporting_text=excerpt,
                        evidence_classification=EvidenceKind.REPORTED,
                        confidence=0.88,
                        verification_status=VerificationStatus.WEBSITE_REPORTED,
                        evidence_id=evidence_id,
                    )
                )
            for source_text in (*page.h1_headings, *page.h2_headings, page.main_text):
                for region, start, end in _regional_service_areas_in_text(source_text):
                    excerpt = _normalize_space(
                        source_text[
                            max(0, start - 60) : min(len(source_text), end + 40)
                        ]
                    )
                    evidence_id = add_evidence(
                        field="regional_service_area",
                        value=region,
                        source_url=page.url,
                        excerpt=excerpt,
                        kind=EvidenceKind.REPORTED,
                        confidence=0.88,
                    )
                    locations.append(
                        LocationCandidate(
                            city=region,
                            state=None,
                            postal_code=None,
                            location_type=LocationType.REGIONAL_SERVICE_AREA,
                            source_url=page.url,
                            supporting_text=excerpt,
                            evidence_classification=EvidenceKind.REPORTED,
                            confidence=0.88,
                            verification_status=VerificationStatus.WEBSITE_REPORTED,
                            evidence_id=evidence_id,
                        )
                    )
            if is_contact_page:
                for (
                    street_address,
                    city,
                    state,
                    postal,
                    start,
                    end,
                ) in contact_addresses:
                    excerpt = _sentence_for(page.main_text, start, end)
                    evidence_id = add_evidence(
                        field="visible_business_address",
                        value=street_address,
                        source_url=page.url,
                        excerpt=excerpt,
                        kind=EvidenceKind.OBSERVED,
                        confidence=0.82,
                    )
                    locations.append(
                        LocationCandidate(
                            city=city,
                            state=state,
                            postal_code=postal,
                            location_type=LocationType.BUSINESS_ADDRESS,
                            source_url=page.url,
                            supporting_text=excerpt,
                            evidence_classification=EvidenceKind.OBSERVED,
                            confidence=0.82,
                            verification_status=VerificationStatus.WEBSITE_REPORTED,
                            evidence_id=evidence_id,
                        )
                    )
                    if address_value is None:
                        address_value = (
                            street_address
                            + ", "
                            + city
                            + ", "
                            + state
                            + (" " + postal if postal else "")
                        )

        locations = _dedupe_locations(locations)
        if service_conflicts:
            conflicted_evidence_ids: set[str] = set()
            for service, conflict_urls in service_conflicts.items():
                url_list = ", ".join(sorted(conflict_urls))
                limitations = (
                    *limitations,
                    f"Conflicting evidence for {service}: a page states that the service is not offered ({url_list}).",
                )
                services = [
                    candidate
                    for candidate in services
                    if candidate.service != service
                    or candidate.source_url not in conflict_urls
                ]
                updated_services: list[ServiceCandidate] = []
                for candidate in services:
                    if candidate.service == service:
                        conflicted_evidence_ids.add(candidate.evidence_id)
                        candidate = ServiceCandidate(
                            service=candidate.service,
                            source_url=candidate.source_url,
                            supporting_text=candidate.supporting_text,
                            evidence_classification=candidate.evidence_classification,
                            confidence=min(candidate.confidence, 0.6),
                            verification_status=VerificationStatus.WEBSITE_REPORTED,
                            evidence_id=candidate.evidence_id,
                        )
                    updated_services.append(candidate)
                services = updated_services
            evidence = [
                replace(
                    item,
                    confidence=min(item.confidence or 0.0, 0.6),
                    assumptions=(
                        *item.assumptions,
                        "A conflicting page says this service is not offered.",
                    ),
                )
                if item.evidence_id in conflicted_evidence_ids
                else item
                for item in evidence
            ]
        services = _dedupe_services(services)
        structured_locations = [
            item
            for item in locations
            if item.location_type
            in {LocationType.BUSINESS_ADDRESS, LocationType.SERVICE_AREA}
        ]
        for served in (
            item
            for item in locations
            if item.location_type
            in {LocationType.EXPLICITLY_SERVED_CITY, LocationType.SERVICE_AREA}
        ):
            if any(
                item.city.casefold() == served.city.casefold()
                for item in structured_locations
                if item.location_type is LocationType.BUSINESS_ADDRESS
            ):
                limitations = tuple(
                    (
                        *limitations,
                        f"{served.city} appears as both a website business address and a service-area claim; the site's operating geography is ambiguous.",
                    )
                )
        limitations = tuple(dict.fromkeys(limitations))
        details = WebsiteInspectionDetails(
            requested_url=requested_url,
            final_url=final_url,
            inspected_at=retrieved_at,
            business_name=business_name,
            phone=structured_phone or _first_unique(all_phones),
            email=structured_email or _first_unique(all_emails),
            address=address_value,
            latitude=latitude,
            longitude=longitude,
            opening_hours=opening_hours,
            same_as=same_as,
            robots_status=robots_status,
            robots_sitemaps=robots_sitemaps,
            robots_restrictions=robots_restrictions,
            sitemap_urls=sitemap_urls,
            structured_data_types=structured_data_types,
            limitations=limitations,
        )
        return WebsiteInspectionResult(
            signals=tuple(signals),
            evidence=tuple(evidence),
            details=details,
            pages=tuple(pages),
            locations=tuple(locations),
            services=tuple(services),
        )


def _page_link_urls(base_url: str, raw_links: Iterable[str]) -> tuple[str, ...]:
    links: list[str] = []
    for raw_link in raw_links:
        try:
            candidate = urljoin(base_url, raw_link.strip())
            parts = urlsplit(candidate)
            if (
                parts.scheme.casefold() not in {"http", "https"}
                or not parts.hostname
                or parts.username
                or parts.password
            ):
                continue
            candidate, _ = urldefrag(candidate)
            candidate = strip_tracking_parameters(candidate)
        except (AttributeError, TypeError, ValueError):
            continue
        if candidate not in links:
            links.append(candidate)
        if len(links) >= 100:
            break
    return tuple(links)


def _schema_type_names(obj: dict[str, object]) -> tuple[str, ...]:
    value = obj.get("@type")
    items = value if isinstance(value, list) else [value]
    return tuple(
        dict.fromkeys(
            text.rsplit("/", 1)[-1] for item in items if (text := _text_value(item))
        )
    )


def _schema_types(obj: dict[str, object]) -> set[str]:
    value = obj.get("@type")
    items = value if isinstance(value, list) else [value]
    return {
        text.rsplit("/", 1)[-1].casefold()
        for item in items
        if (text := _text_value(item))
    }


def _schema_has_type(obj: dict[str, object], expected: set[str]) -> bool:
    expected_casefold = {item.casefold() for item in expected}
    return bool(_schema_types(obj) & expected_casefold)


def _first_unique(values: Iterable[str]) -> str | None:
    for value in values:
        clean = _normalize_space(value)
        if clean:
            return clean
    return None


def _dedupe_locations(values: list[LocationCandidate]) -> list[LocationCandidate]:
    result: list[LocationCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for value in values:
        key = (
            value.city.casefold(),
            (value.state or "").casefold(),
            value.location_type.value,
        )
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _dedupe_services(values: list[ServiceCandidate]) -> list[ServiceCandidate]:
    result_by_category: dict[str, ServiceCandidate] = {}
    for value in values:
        key = value.service.casefold()
        current = result_by_category.get(key)
        value_score = (
            value.evidence_classification is EvidenceKind.REPORTED,
            value.confidence,
        )
        if current is None:
            result_by_category[key] = value
            continue
        current_score = (
            current.evidence_classification is EvidenceKind.REPORTED,
            current.confidence,
        )
        if value_score > current_score:
            result_by_category[key] = value
    return list(result_by_category.values())


def _robots_policy(
    response: FetchResponse, robots_url: str
) -> tuple[RobotFileParser, str, list[str], list[str]]:
    parser = RobotFileParser()
    sitemaps: list[str] = []
    restrictions: list[str] = []
    if response.status_code == 404:
        return parser, "missing", sitemaps, restrictions
    if response.status_code != 200:
        raise WebsiteInspectionError(
            f"robots.txt returned HTTP {response.status_code}.",
            category="robots_error",
        )
    text = response.body.decode("utf-8", errors="replace")
    parser.set_url(robots_url)
    parser.parse(text.splitlines())
    in_relevant_group = False
    saw_agent = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.casefold().startswith("user-agent:"):
            agent = stripped.split(":", 1)[1].strip().casefold()
            if saw_agent and agent == "*":
                in_relevant_group = True
            else:
                in_relevant_group = agent == "*" or USER_AGENT.casefold() in agent
            saw_agent = True
        elif stripped.casefold().startswith("sitemap:"):
            sitemap = stripped.split(":", 1)[1].strip()
            if sitemap:
                sitemaps.append(urljoin(robots_url, sitemap))
        elif in_relevant_group and stripped.casefold().startswith(
            ("allow:", "disallow:")
        ):
            restrictions.append(stripped)
    return parser, "found", sitemaps, restrictions


def inspect_website(website_url: str) -> WebsiteInspectionResult:
    """Convenience function for the LIVE application service."""

    return WebsiteInspector().inspect(website_url)
