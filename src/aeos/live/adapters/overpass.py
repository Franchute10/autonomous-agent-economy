"""Small, bounded OpenStreetMap/Overpass market discovery adapter.

This adapter is for an explicit, one-off internal pilot. It makes one HTTP
request per instance and does not retry. The selected public instance is not
an assumed production dependency for a future commercial service.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import errno
from http.client import HTTPSConnection
import json
import math
import re
import socket
import ssl
import time
from typing import TypeAlias
from urllib.parse import urlencode
from urllib.parse import urlsplit

from aeos.live.domain import (
    BusinessInput,
    EvidenceKind,
    MarketEntity,
    MarketEntityType,
    SourceEvidence,
)
from aeos.live.ports import MarketDiscoveryResult

ORLANDO_LATITUDE = 28.5383
ORLANDO_LONGITUDE = -81.3792
ORLANDO_RADIUS_MILES = 15.0
METERS_PER_MILE = 1609.344
SEARCH_RADIUS_METERS = ORLANDO_RADIUS_MILES * METERS_PER_MILE
MAX_PER_QUERY = 5
MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_TIMEOUT_SECONDS = 25
DEFAULT_ENDPOINT = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
APPLICATION_USER_AGENT = "AEOS-LIVE-001C/1.0 (Orlando one-off market research pilot)"
PROFILE_APPLICATION_USER_AGENT = (
    "AEOS-LIVE-002A/1.0 (profile-scoped one-off market research)"
)
OSM_BROWSE_ROOT = "https://www.openstreetmap.org"
_US_STATE_NAMES = {
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


@dataclass(frozen=True, slots=True)
class _HttpResult:
    body: bytes
    status_code: int


Transport: TypeAlias = Callable[[str, str, int, int], bytes | _HttpResult]
Clock: TypeAlias = Callable[[], datetime]


def _sanitize_error_message(message: str) -> str:
    """Remove URL credentials and common secret-like values from diagnostics."""

    sanitized = re.sub(r"https?://[^\s'\"<>]+", "<url-redacted>", message)
    sanitized = re.sub(
        r"(?i)(authorization|password|token|api[_-]?key)(\s*[:=]\s*)\S+",
        r"\1\2[redacted]",
        sanitized,
    )
    return sanitized[:300]


class _OverpassError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        category: str,
        exception_type: str,
        http_status: int | None = None,
        request_reached_http_server: bool | None = None,
        phase: str | None = None,
    ) -> None:
        safe_message = _sanitize_error_message(message)
        super().__init__(safe_message)
        self.category = category
        self.exception_type = exception_type
        self.sanitized_error_message = safe_message
        self.http_status = http_status
        self.status_code = http_status
        self.request_reached_http_server = request_reached_http_server
        self.phase = phase


class OverpassRequestError(_OverpassError):
    """A bounded Overpass request failed; the adapter never retries it."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        category: str = "request_error",
        exception_type: str = "OverpassRequestError",
        request_reached_http_server: bool | None = None,
        phase: str | None = None,
    ) -> None:
        super().__init__(
            message,
            category=category,
            exception_type=exception_type,
            http_status=status_code,
            request_reached_http_server=request_reached_http_server,
            phase=phase,
        )


class OverpassResponseError(_OverpassError):
    """The provider response was too large or did not match its JSON contract."""

    def __init__(
        self,
        message: str,
        *,
        category: str = "invalid_response",
        exception_type: str = "OverpassResponseError",
        http_status: int | None = None,
        request_reached_http_server: bool | None = None,
        phase: str | None = None,
    ) -> None:
        super().__init__(
            message,
            category=category,
            exception_type=exception_type,
            http_status=http_status,
            request_reached_http_server=request_reached_http_server,
            phase=phase,
        )


def _connection_error(
    error: Exception,
    *,
    phase: str,
    reached_http_server: bool | None,
    http_status: int | None = None,
) -> OverpassRequestError:
    if isinstance(error, socket.gaierror):
        category = "dns_resolution_failure"
    elif isinstance(error, ssl.SSLCertVerificationError):
        category = "tls_certificate_error"
    elif isinstance(error, ssl.SSLError):
        category = "tls_error"
    elif isinstance(error, (TimeoutError, socket.timeout)):
        category = "connection_timeout" if phase == "connect" else "read_timeout"
    elif (
        isinstance(error, ConnectionRefusedError)
        or getattr(error, "errno", None) == errno.ECONNREFUSED
    ):
        category = "connection_refused"
    elif getattr(error, "errno", None) in {
        errno.ENETUNREACH,
        errno.EHOSTUNREACH,
    }:
        category = "connection_unreachable"
    elif isinstance(error, ConnectionResetError):
        category = "connection_reset"
    elif phase == "connect":
        category = "connection_error"
    else:
        category = "request_or_response_error"
    detail = _sanitize_error_message(str(error)) or type(error).__name__
    return OverpassRequestError(
        f"{category.replace('_', ' ').capitalize()}: {detail}",
        status_code=http_status,
        category=category,
        exception_type=type(error).__name__,
        request_reached_http_server=reached_http_server,
        phase=phase,
    )


def _http_post(
    query: str,
    endpoint: str,
    timeout: int,
    max_bytes: int,
    *,
    user_agent: str = APPLICATION_USER_AGENT,
) -> _HttpResult:
    parsed = urlsplit(endpoint)
    hostname = parsed.hostname
    if parsed.scheme != "https" or hostname is None:
        raise OverpassRequestError(
            "The configured Overpass endpoint must be an HTTPS URL with a hostname.",
            category="invalid_endpoint",
            exception_type="InvalidEndpoint",
            request_reached_http_server=False,
            phase="configuration",
        )
    if parsed.username is not None or parsed.password is not None:
        raise OverpassRequestError(
            "Credentials in the Overpass endpoint URL are not accepted or reported.",
            category="invalid_endpoint_credentials",
            exception_type="InvalidEndpointCredentials",
            request_reached_http_server=False,
            phase="configuration",
        )
    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"
    payload = urlencode({"data": query}).encode("utf-8")
    connection = HTTPSConnection(hostname, parsed.port or 443, timeout=timeout)
    try:
        try:
            connection.connect()
        except (OSError, ssl.SSLError) as error:
            raise _connection_error(
                error, phase="connect", reached_http_server=False
            ) from error
        try:
            connection.request(
                "POST",
                target,
                body=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                    "User-Agent": user_agent,
                },
            )
        except (OSError, ssl.SSLError) as error:
            raise _connection_error(
                error, phase="request_send", reached_http_server=None
            ) from error
        try:
            response = connection.getresponse()
        except (OSError, ssl.SSLError) as error:
            raise _connection_error(
                error, phase="awaiting_response_headers", reached_http_server=None
            ) from error
        status_code = response.status
        if not 200 <= status_code < 300:
            raise OverpassRequestError(
                f"Overpass returned HTTP {status_code} {response.reason}; no retry was attempted.",
                status_code=status_code,
                category="http_status_error",
                exception_type="HTTPStatusError",
                request_reached_http_server=True,
                phase="response_headers",
            )
        try:
            body = response.read(max_bytes + 1)
        except (OSError, ssl.SSLError) as error:
            raise _connection_error(
                error,
                phase="reading_response_body",
                reached_http_server=True,
                http_status=status_code,
            ) from error
        if len(body) > max_bytes:
            raise OverpassResponseError(
                f"Overpass response exceeded the {max_bytes}-byte safety limit.",
                category="response_size_limit_exceeded",
                exception_type="ResponseSizeLimitExceeded",
                http_status=status_code,
                request_reached_http_server=True,
                phase="reading_response_body",
            )
        return _HttpResult(body=body, status_code=status_code)
    finally:
        connection.close()


_DEFAULT_HTTP_POST = _http_post


def build_orlando_query() -> str:
    """Build five documented tag searches within 15 miles of Downtown Orlando."""

    radius = f"{SEARCH_RADIUS_METERS:.2f}"
    latitude = f"{ORLANDO_LATITUDE:.6f}"
    longitude = f"{ORLANDO_LONGITUDE:.6f}"
    return (
        f"[out:json][timeout:{DEFAULT_TIMEOUT_SECONDS}]"
        "[maxsize:16777216];\n"
        f'nwr(around:{radius},{latitude},{longitude})["craft"="cleaning"];\n'
        f"out center {MAX_PER_QUERY};\n"
        f"nwr(around:{radius},{latitude},{longitude})"
        '["office"="property_management"];\n'
        f"out center {MAX_PER_QUERY};\n"
        f"nwr(around:{radius},{latitude},{longitude})"
        '["office"="estate_agent"];\n'
        f"out center {MAX_PER_QUERY};\n"
        f"nwr(around:{radius},{latitude},{longitude})"
        '["shop"="estate_agent"];\n'
        f"out center {MAX_PER_QUERY};\n"
        f"nwr(around:{radius},{latitude},{longitude})"
        '["shop"="cleaning_supplies"];\n'
        f"out center {MAX_PER_QUERY};"
    )


def build_profile_area_query(
    *,
    country: str,
    state_region: str,
    city: str,
    additional_areas: tuple[str, ...] = (),
) -> str:
    """Build one bounded query from named OSM administrative areas.

    This deliberately does not turn an owner-entered radius into a circle: a
    business coordinate is not part of the profile contract, so that distance
    would otherwise be invented.
    """

    def quoted(value: str) -> str:
        return json.dumps(value.strip(), ensure_ascii=False)

    country_name = country.strip()
    if country_name.casefold() in {
        "us",
        "usa",
        "united states",
        "united states of america",
    }:
        country_name = "United States"
        state_region = _US_STATE_NAMES.get(state_region.strip().upper(), state_region)

    lines = [
        f"[out:json][timeout:{DEFAULT_TIMEOUT_SECONDS}][maxsize:16777216];",
        f'area["name"={quoted(country_name)}]["boundary"="administrative"]'
        '["admin_level"="2"]->.profileCountry;',
        f'area["name"={quoted(state_region)}]["boundary"="administrative"]'
        "(area.profileCountry)->.profileState;",
    ]
    areas = tuple(dict.fromkeys((city, *additional_areas)))
    for index, area_name in enumerate(areas):
        lines.append(
            f'area["name"={quoted(area_name)}]["boundary"="administrative"]'
            f"(area.profileState)->.profileArea{index};"
        )
        area_set = f".profileArea{index}"
        for key, value in (
            ("craft", "cleaning"),
            ("office", "property_management"),
            ("office", "estate_agent"),
            ("shop", "estate_agent"),
            ("shop", "cleaning_supplies"),
        ):
            lines.extend(
                (
                    f"nwr(area{area_set})[{json.dumps(key)}={json.dumps(value)}];",
                    f"out center {MAX_PER_QUERY};",
                )
            )
    return "\n".join(lines)


def _classify(tags: Mapping[str, str]) -> tuple[MarketEntityType, str] | None:
    """Apply only the OSM tags documented for this pilot's categories."""

    matches: list[tuple[MarketEntityType, str]] = []
    if tags.get("shop") == "cleaning_supplies":
        matches.append((MarketEntityType.SUPPLIER, "cleaning supplies"))
    if tags.get("office") == "property_management":
        matches.append((MarketEntityType.POTENTIAL_CUSTOMER, "property management"))
    if tags.get("office") == "estate_agent" or tags.get("shop") == "estate_agent":
        matches.append((MarketEntityType.PARTNER, "real estate agencies"))
    if tags.get("craft") == "cleaning":
        matches.append((MarketEntityType.COMPETITOR, "cleaning services"))
    if not matches:
        return None
    # MarketEntity has one role. Keep one source object once and document any
    # overlap rather than manufacturing duplicate entities for the same OSM ID.
    return matches[0]


def _coordinates(element: Mapping[str, object]) -> tuple[float | None, float | None]:
    latitude = element.get("lat")
    longitude = element.get("lon")
    if (
        isinstance(latitude, (int, float))
        and not isinstance(latitude, bool)
        and isinstance(longitude, (int, float))
        and not isinstance(longitude, bool)
        and math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    ):
        return float(latitude), float(longitude)
    center = element.get("center")
    if isinstance(center, Mapping):
        center_lat = center.get("lat")
        center_lon = center.get("lon")
        if (
            isinstance(center_lat, (int, float))
            and not isinstance(center_lat, bool)
            and isinstance(center_lon, (int, float))
            and not isinstance(center_lon, bool)
            and math.isfinite(center_lat)
            and math.isfinite(center_lon)
            and -90 <= center_lat <= 90
            and -180 <= center_lon <= 180
        ):
            return float(center_lat), float(center_lon)
    return None, None


def _distance_miles(
    latitude: float, longitude: float, origin_latitude: float, origin_longitude: float
) -> float:
    earth_radius_miles = 3958.7613
    lat1, lat2 = math.radians(origin_latitude), math.radians(latitude)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(longitude - origin_longitude)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_miles * math.asin(math.sqrt(min(1.0, value)))


def _address(tags: Mapping[str, str]) -> str | None:
    parts = tuple(
        tags[key]
        for key in (
            "addr:housenumber",
            "addr:street",
            "addr:unit",
            "addr:suburb",
            "addr:city",
            "addr:state",
            "addr:postcode",
        )
        if tags.get(key)
    )
    return ", ".join(parts) if parts else None


def _element_source_url(element_type: str, element_id: int) -> str:
    return f"{OSM_BROWSE_ROOT}/{element_type}/{element_id}"


def _make_evidence(
    *,
    entity_id: str,
    name: str,
    field: str,
    value: str | int | float | bool,
    source_url: str,
    retrieved_at: datetime,
    excerpt: str,
    kind: EvidenceKind = EvidenceKind.OBSERVED,
    assumptions: tuple[str, ...] = (),
) -> SourceEvidence:
    return SourceEvidence(
        evidence_id=f"{entity_id}:{field}",
        kind=kind,
        subject=name,
        field=field,
        value=value,
        source_name="OpenStreetMap via Overpass",
        source_url=source_url,
        retrieved_at=retrieved_at,
        excerpt=excerpt,
        assumptions=assumptions,
        owner_entity_id=entity_id,
    )


class OverpassMarketDiscovery:
    """Cached implementation of all four LIVE discovery port methods.

    An instance sends at most one request. The fixed pilot scope is intentional:
    the class does not turn a public instance into a general search service.
    """

    def __init__(
        self,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        transport: Transport | None = None,
        clock: Clock | None = None,
        business: BusinessInput | None = None,
        service_areas: tuple[str, ...] = (),
        user_agent: str = APPLICATION_USER_AGENT,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.request_count = 0
        self.request_elapsed_seconds = 0.0
        self.last_http_status: int | None = None
        self.request_reached_http_server: bool | None = None
        self._transport = transport or _http_post
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._business = business
        self._service_areas = service_areas
        self.user_agent = user_agent
        self._result: MarketDiscoveryResult | None = None
        self._request_error: OverpassRequestError | None = None
        self._response_error: OverpassResponseError | None = None

    def discover_competitors(self, business: BusinessInput) -> MarketDiscoveryResult:
        self._check_pilot_business(business)
        return self._for_type(MarketEntityType.COMPETITOR)

    def discover_potential_customers(
        self, business: BusinessInput
    ) -> MarketDiscoveryResult:
        self._check_pilot_business(business)
        return self._for_type(MarketEntityType.POTENTIAL_CUSTOMER)

    def discover_partners(self, business: BusinessInput) -> MarketDiscoveryResult:
        self._check_pilot_business(business)
        return self._for_type(MarketEntityType.PARTNER)

    def discover_suppliers(self, business: BusinessInput) -> MarketDiscoveryResult:
        self._check_pilot_business(business)
        return self._for_type(MarketEntityType.SUPPLIER)

    def discover_all(self) -> MarketDiscoveryResult:
        """Return the cached one-request result for report construction."""

        if self._result is not None:
            return self._result
        if self._request_error is not None:
            raise self._request_error
        if self._response_error is not None:
            raise self._response_error
        request_started = time.monotonic()
        try:
            self.request_count += 1
            try:
                query = (
                    build_orlando_query()
                    if self._business is None
                    else build_profile_area_query(
                        country=self._business.country,
                        state_region=self._business.state,
                        city=self._business.city,
                        additional_areas=self._service_areas,
                    )
                )
                response: bytes | _HttpResult
                if self._transport is _DEFAULT_HTTP_POST:
                    response = _DEFAULT_HTTP_POST(
                        query,
                        self.endpoint,
                        self.timeout_seconds,
                        self.max_response_bytes,
                        user_agent=self.user_agent,
                    )
                else:
                    response = self._transport(
                        query,
                        self.endpoint,
                        self.timeout_seconds,
                        self.max_response_bytes,
                    )
            finally:
                self.request_elapsed_seconds = time.monotonic() - request_started
            if isinstance(response, _HttpResult):
                body = response.body
                self.last_http_status = response.status_code
            else:
                # Injected offline transports represent a normal HTTP 200.
                body = response
                self.last_http_status = 200
            self.request_reached_http_server = True
            self._result = self._normalize(body)
            return self._result
        except OverpassRequestError as error:
            self._request_error = error
            self.last_http_status = error.http_status
            self.request_reached_http_server = error.request_reached_http_server
            raise
        except OverpassResponseError as error:
            self._response_error = error
            self.last_http_status = error.http_status or self.last_http_status
            self.request_reached_http_server = error.request_reached_http_server
            raise

    def _for_type(self, entity_type: MarketEntityType) -> MarketDiscoveryResult:
        result = self.discover_all()
        entities = tuple(
            item for item in result.entities if item.entity_type is entity_type
        )
        entity_ids = {item.entity_id for item in entities}
        evidence = tuple(
            item for item in result.evidence if item.owner_entity_id in entity_ids
        )
        return MarketDiscoveryResult(
            entities=entities,
            evidence=evidence,
            limitations=result.limitations,
        )

    def _check_pilot_business(self, business: BusinessInput) -> None:
        if not isinstance(business, BusinessInput):
            raise TypeError("business must be a BusinessInput")
        if self._business is None:
            if (
                business.industry not in {"HOUSE_CLEANING", "House Cleaning"}
                or business.city.casefold() != "orlando"
                or business.state.casefold() not in {"fl", "florida"}
            ):
                raise ValueError(
                    "OverpassMarketDiscovery is scoped to House Cleaning in Orlando, FL"
                )
            return
        if (
            business.industry.replace("_", " ").casefold() != "house cleaning"
            or business.city.casefold() != self._business.city.casefold()
            or business.state.casefold() != self._business.state.casefold()
            or business.country.casefold() != self._business.country.casefold()
        ):
            raise ValueError(
                "profile-scoped Overpass discovery requires the configured "
                "House Cleaning business and location"
            )

    def _normalize(self, body: bytes) -> MarketDiscoveryResult:
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            parse_detail = (
                f"line {error.lineno}, column {error.colno}: {error.msg}"
                if isinstance(error, json.JSONDecodeError)
                else "response is not valid UTF-8 JSON"
            )
            raise OverpassResponseError(
                f"Overpass returned invalid JSON ({parse_detail}).",
                category="invalid_json",
                exception_type=type(error).__name__,
                http_status=self.last_http_status,
                request_reached_http_server=True,
                phase="parsing_response",
            ) from error
        if not isinstance(payload, dict) or not isinstance(
            payload.get("elements"), list
        ):
            raise OverpassResponseError(
                "Overpass response did not contain an elements array.",
                category="invalid_response",
                exception_type="InvalidProviderResponse",
                http_status=self.last_http_status,
                request_reached_http_server=True,
                phase="parsing_response",
            )

        retrieved_at = self._clock().astimezone(timezone.utc)
        entities: list[MarketEntity] = []
        evidence: list[SourceEvidence] = []
        limitations: list[str] = [
            "OpenStreetMap is community-maintained; missing entries and stale attributes are possible.",
            "OSM craft=cleaning covers building, industrial, window, and janitorial cleaning; it does not establish residential house-cleaning service.",
            "No established OSM tag was selected for moving companies or vacation-rental operators; those categories were not searched.",
            "Apartment building features are not treated as organizations or confirmed commercial buyers.",
        ]
        if self._business is None:
            limitations.extend(
                (
                    "Only mapped addr:city and addr:state values were used to qualify city/state; coordinates and a search radius do not prove an address city.",
                    "The radius is measured from the approximate Downtown Orlando reference coordinate (28.5383, -81.3792), not a legal city boundary.",
                )
            )
        else:
            limitations.extend(
                (
                    "Profile searches use OSM administrative areas matched by the supplied country, state/region, city, and additional service-area names.",
                    "The declared service radius is owner-reported and is not applied as a distance filter because the profile contains no business coordinates.",
                    "OSM listings do not establish the candidate's residential service scope, target customer segment, business model, or buying intent.",
                )
            )
        seen: set[str] = set()
        category_counts: dict[MarketEntityType, int] = {}
        skipped_malformed = 0
        skipped_unnamed = 0
        skipped_unsupported = 0
        skipped_outside_center_radius = 0
        elements = payload["elements"]
        for raw_element in elements:
            if not isinstance(raw_element, dict):
                skipped_malformed += 1
                continue
            element_type = raw_element.get("type")
            element_id = raw_element.get("id")
            raw_tags = raw_element.get("tags")
            if (
                element_type not in {"node", "way", "relation"}
                or isinstance(element_id, bool)
                or not isinstance(element_id, int)
                or not isinstance(raw_tags, dict)
            ):
                skipped_malformed += 1
                continue
            object_id = f"osm:{element_type}:{element_id}"
            if object_id in seen:
                continue
            seen.add(object_id)
            tags = {
                key: value
                for key, value in raw_tags.items()
                if isinstance(key, str) and isinstance(value, str)
            }
            name = tags.get("name", "").strip()
            if not name:
                skipped_unnamed += 1
                continue
            classification = _classify(tags)
            if classification is None:
                skipped_unsupported += 1
                continue
            entity_type, category = classification
            category_limit = _category_limit(entity_type)
            if self._business is not None:
                category_limit *= 1 + len(self._service_areas)
            if category_counts.get(entity_type, 0) >= category_limit:
                continue

            latitude, longitude = _coordinates(raw_element)
            distance: float | None = None
            if (
                latitude is not None
                and longitude is not None
                and self._business is None
            ):
                distance = _distance_miles(
                    latitude, longitude, ORLANDO_LATITUDE, ORLANDO_LONGITUDE
                )
                if distance > ORLANDO_RADIUS_MILES:
                    skipped_outside_center_radius += 1
                    continue

            source_url = _element_source_url(element_type, element_id)
            entity_evidence: list[SourceEvidence] = []
            classifier_tags = tuple(
                f"{key}={tags[key]}"
                for key in ("craft", "office", "shop")
                if key in tags
            )
            category_excerpt = "OpenStreetMap tags: " + "; ".join(classifier_tags)
            entity_evidence.append(
                _make_evidence(
                    entity_id=object_id,
                    name=name,
                    field="name",
                    value=name,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                    excerpt=f"OpenStreetMap name tag: {name}",
                )
            )
            entity_evidence.append(
                _make_evidence(
                    entity_id=object_id,
                    name=name,
                    field="category",
                    value=category,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                    excerpt=category_excerpt,
                )
            )
            entity_evidence.append(
                _make_evidence(
                    entity_id=object_id,
                    name=name,
                    field="provider_identifier",
                    value=f"{element_type}/{element_id}",
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                    excerpt="The OpenStreetMap element type and ID in the provider response.",
                )
            )

            city = tags.get("addr:city")
            state = tags.get("addr:state")
            address = _address(tags)
            website = tags.get("contact:website") or tags.get("website")
            phone = tags.get("contact:phone") or tags.get("phone")
            for field, value in (
                ("address", address),
                ("city", city),
                ("state", state),
                ("website", website),
                ("phone", phone),
            ):
                if value:
                    entity_evidence.append(
                        _make_evidence(
                            entity_id=object_id,
                            name=name,
                            field=field,
                            value=value,
                            source_url=source_url,
                            retrieved_at=retrieved_at,
                            excerpt=f"OpenStreetMap address/contact tag value for {field}.",
                        )
                    )
            coordinate_kind = (
                EvidenceKind.OBSERVED
                if element_type == "node"
                else EvidenceKind.INFERRED
            )
            coordinate_assumptions = (
                ()
                if element_type == "node"
                else ("Overpass supplied the element's calculated center coordinate.",)
            )
            if latitude is not None and longitude is not None:
                for field, coordinate_value in (
                    ("latitude", latitude),
                    ("longitude", longitude),
                ):
                    entity_evidence.append(
                        _make_evidence(
                            entity_id=object_id,
                            name=name,
                            field=field,
                            value=coordinate_value,
                            source_url=source_url,
                            retrieved_at=retrieved_at,
                            excerpt=(
                                "OpenStreetMap node coordinate."
                                if element_type == "node"
                                else "Overpass calculated center coordinate for a non-node element."
                            ),
                            kind=coordinate_kind,
                            assumptions=coordinate_assumptions,
                        )
                    )
            if distance is not None:
                entity_evidence.append(
                    _make_evidence(
                        entity_id=object_id,
                        name=name,
                        field="distance_miles",
                        value=round(distance, 3),
                        source_url=source_url,
                        retrieved_at=retrieved_at,
                        excerpt=(
                            "Calculated from the OSM coordinate and the documented "
                            "Downtown Orlando pilot reference coordinate."
                        ),
                        kind=EvidenceKind.INFERRED,
                        assumptions=(
                            "Great-circle distance uses OSM coordinates or its reported center.",
                            "The pilot origin is the approximate Downtown Orlando reference coordinate.",
                        ),
                    )
                )

            entity = MarketEntity(
                entity_id=object_id,
                name=name,
                entity_type=entity_type,
                category=category,
                address=address,
                city=city,
                state=state,
                latitude=latitude,
                longitude=longitude,
                distance_miles=round(distance, 3) if distance is not None else None,
                website=website,
                phone=phone,
                evidence_ids=tuple(item.evidence_id for item in entity_evidence),
            )
            entities.append(entity)
            evidence.extend(entity_evidence)
            category_counts[entity_type] = category_counts.get(entity_type, 0) + 1
            if len(classifier_tags) > 1:
                limitations.append(
                    f"{name} ({object_id}) has multiple searched OSM classification tags and is represented once as {entity_type.value}."
                )
            if (latitude is None or longitude is None) and self._business is None:
                limitations.append(
                    f"{name} ({object_id}) has no usable coordinates; its exact radius membership could not be independently checked."
                )
            if city is None or state is None:
                limitations.append(
                    f"{name} ({object_id}) is missing a mapped addr:city or addr:state; location-based fit remains unqualified by the assessment engine."
                )
            if entity_type is MarketEntityType.COMPETITOR:
                limitations.append(
                    f"{name} ({object_id}) is a possible cleaning-services competitor only; OSM does not specify residential house cleaning for this entry."
                )

        if skipped_malformed:
            limitations.append(
                f"Skipped {skipped_malformed} malformed provider element(s)."
            )
        if skipped_unnamed:
            limitations.append(
                f"Skipped {skipped_unnamed} matching element(s) without a business name."
            )
        if skipped_unsupported:
            limitations.append(
                f"Skipped {skipped_unsupported} matching element(s) without a supported business category."
            )
        if skipped_outside_center_radius:
            limitations.append(
                f"Skipped {skipped_outside_center_radius} element center(s) outside the 15-mile pilot radius."
            )
        if isinstance(payload.get("remark"), str) and payload["remark"].strip():
            limitations.append(
                "Overpass returned a remark: " + payload["remark"].strip()
            )
        area_count = 1 + len(self._service_areas) if self._business is not None else 1
        if len(elements) >= MAX_PER_QUERY * 5 * area_count:
            limitations.append(
                "Provider output reached the configured per-query result limit; category coverage may be truncated."
            )

        return MarketDiscoveryResult(
            entities=tuple(entities),
            evidence=tuple(evidence),
            limitations=tuple(dict.fromkeys(limitations)),
        )


def _category_limit(entity_type: MarketEntityType) -> int:
    if entity_type in {
        MarketEntityType.COMPETITOR,
        MarketEntityType.POTENTIAL_CUSTOMER,
    }:
        return 5
    return 3
