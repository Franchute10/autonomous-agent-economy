from dataclasses import replace
from datetime import datetime, timezone
import errno
import json
from pathlib import Path
import socket
import ssl

import pytest

from aeos.application.live.assess_business import (
    assess_business,
    render_assessment_summary,
)
from aeos.live.adapters.overpass import (
    ORLANDO_RADIUS_MILES,
    OverpassMarketDiscovery,
    OverpassRequestError,
    OverpassResponseError,
    _http_post,
    build_orlando_query,
)
from aeos.live.domain import (
    AssessmentStatus,
    BusinessInput,
    EvidenceKind,
    InvalidLiveContract,
    MarketEntityType,
    OpportunityType,
)
from aeos.live.ports import MarketDiscoveryResult
from aeos.live.real_demo import _merge_port_results, main as real_demo_main

RETRIEVED_AT = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        reason: str = "OK",
        body: bytes = b"{}",
        read_error: Exception | None = None,
    ) -> None:
        self.status = status
        self.reason = reason
        self.body = body
        self.read_error = read_error

    def read(self, max_bytes: int) -> bytes:
        if self.read_error is not None:
            raise self.read_error
        return self.body[:max_bytes]


class _FakeHTTPSConnection:
    def __init__(
        self,
        *,
        response: _FakeResponse | None = None,
        connect_error: Exception | None = None,
        request_error: Exception | None = None,
        response_error: Exception | None = None,
    ) -> None:
        self.response = response or _FakeResponse()
        self.connect_error = connect_error
        self.request_error = request_error
        self.response_error = response_error
        self.connected = False
        self.request_calls = 0
        self.closed = False
        self.host: str | None = None
        self.port: int | None = None
        self.timeout: int | None = None

    def connect(self) -> None:
        if self.connect_error is not None:
            raise self.connect_error
        self.connected = True

    def request(
        self,
        method: str,
        target: str,
        *,
        body: bytes,
        headers: dict[str, str],
    ) -> None:
        self.request_calls += 1
        if self.request_error is not None:
            raise self.request_error

    def getresponse(self) -> _FakeResponse:
        if self.response_error is not None:
            raise self.response_error
        return self.response

    def close(self) -> None:
        self.closed = True


def _element(
    element_id: int,
    tags: dict[str, str],
    *,
    element_type: str = "node",
    latitude: float | None = 28.54,
    longitude: float | None = -81.38,
) -> dict[str, object]:
    result: dict[str, object] = {
        "type": element_type,
        "id": element_id,
        "tags": tags,
    }
    if latitude is not None:
        result["lat"] = latitude
    if longitude is not None:
        result["lon"] = longitude
    return result


def _payload(*elements: dict[str, object]) -> bytes:
    return json.dumps({"elements": list(elements)}).encode("utf-8")


def _install_connection(
    monkeypatch: pytest.MonkeyPatch, connection: _FakeHTTPSConnection
) -> list[tuple[str, int, int]]:
    settings: list[tuple[str, int, int]] = []

    def factory(host: str, port: int, *, timeout: int) -> _FakeHTTPSConnection:
        settings.append((host, port, timeout))
        return connection

    monkeypatch.setattr("aeos.live.adapters.overpass.HTTPSConnection", factory)
    return settings


def _adapter(body: bytes) -> OverpassMarketDiscovery:
    return OverpassMarketDiscovery(
        transport=lambda query, endpoint, timeout, max_bytes: body,
        clock=lambda: RETRIEVED_AT,
    )


def _business() -> BusinessInput:
    return BusinessInput(
        business_name="Unidentified Orlando house-cleaning business (assessment profile only)",
        industry="HOUSE_CLEANING",
        city="Orlando",
        state="FL",
    )


def _sample_elements() -> tuple[dict[str, object], ...]:
    return (
        _element(
            100,
            {
                "name": "Possible Cleaning Company",
                "craft": "cleaning",
                "addr:city": "Orlando",
                "addr:state": "Florida",
                "addr:street": "Orange Avenue",
                "addr:housenumber": "10",
                "website": "https://cleaner.example",
                "phone": "+1 407 555 0100",
            },
        ),
        _element(
            200,
            {
                "name": "Property Manager Orlando",
                "office": "property_management",
                "addr:city": "Orlando",
                "addr:state": "FL",
                "contact:phone": "+1 407 555 0200",
            },
        ),
        _element(
            300,
            {
                "name": "Orlando Real Estate",
                "office": "estate_agent",
                "addr:city": "Orlando",
                "addr:state": "FL",
            },
        ),
        _element(
            400,
            {
                "name": "Cleaning Supply Store",
                "shop": "cleaning_supplies",
                "addr:city": "Orlando",
                "addr:state": "Florida",
            },
        ),
    )


def test_query_is_one_bounded_orlando_request_with_named_categories() -> None:
    query = build_orlando_query()

    assert "around:24140.16,28.538300,-81.379200" in query
    assert query.count("out center 5;") == 5
    assert '"craft"="cleaning"' in query
    assert '"office"="property_management"' in query
    assert '"office"="estate_agent"' in query
    assert '"shop"="estate_agent"' in query
    assert '"shop"="cleaning_supplies"' in query


def test_normalization_preserves_observed_fields_and_traceable_source_evidence() -> (
    None
):
    adapter = _adapter(_payload(*_sample_elements()))
    result = adapter.discover_all()

    competitor = next(
        entity
        for entity in result.entities
        if entity.entity_type is MarketEntityType.COMPETITOR
    )
    evidence = {item.evidence_id: item for item in result.evidence}
    assert competitor.entity_id == "osm:node:100"
    assert competitor.category == "cleaning services"
    assert competitor.address == "10, Orange Avenue, Orlando, Florida"
    assert competitor.phone == "+1 407 555 0100"
    assert competitor.website == "https://cleaner.example"
    assert competitor.rating is None
    assert competitor.review_count is None
    assert all(
        evidence[item].owner_entity_id == competitor.entity_id
        for item in competitor.evidence_ids
    )
    assert evidence["osm:node:100:category"].value == "cleaning services"
    assert (
        evidence["osm:node:100:category"].excerpt
        == "OpenStreetMap tags: craft=cleaning"
    )
    assert (
        evidence["osm:node:100:category"].source_url
        == "https://www.openstreetmap.org/node/100"
    )
    assert evidence["osm:node:100:latitude"].kind is EvidenceKind.OBSERVED
    assert evidence["osm:node:100:distance_miles"].kind is EvidenceKind.INFERRED
    assert evidence["osm:node:100:distance_miles"].retrieved_at == RETRIEVED_AT
    retrieved_at = evidence["osm:node:100:distance_miles"].retrieved_at
    assert retrieved_at is not None
    offset = retrieved_at.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0
    assert competitor.distance_miles is not None
    assert competitor.distance_miles <= ORLANDO_RADIUS_MILES


def test_ways_use_inferred_center_coordinates() -> None:
    element = _element(
        101,
        {"name": "Property Office", "office": "property_management"},
        element_type="way",
        latitude=None,
        longitude=None,
    )
    element["center"] = {"lat": 28.54, "lon": -81.38}
    result = _adapter(_payload(element)).discover_all()
    record = next(item for item in result.evidence if item.field == "latitude")

    assert record.value == 28.54
    assert record.kind is EvidenceKind.INFERRED
    assert record.assumptions


def test_missing_coordinates_are_preserved_as_none() -> None:
    element = _element(
        102,
        {"name": "Cleaning Services", "craft": "cleaning"},
        latitude=None,
        longitude=None,
    )
    result = _adapter(_payload(element)).discover_all()

    assert len(result.entities) == 1
    assert result.entities[0].latitude is None
    assert result.entities[0].longitude is None
    assert result.entities[0].distance_miles is None
    assert any("no usable coordinates" in item for item in result.limitations)


def test_unsupported_business_category_is_skipped_without_reclassification() -> None:
    element = _element(103, {"name": "General Business", "office": "company"})
    result = _adapter(_payload(element)).discover_all()

    assert result.entities == ()
    assert any(
        "without a supported business category" in item for item in result.limitations
    )


def test_deduplication_uses_exact_osm_identity_not_similar_names() -> None:
    first = _element(104, {"name": "Clean & Go", "craft": "cleaning"})
    same_object = _element(104, {"name": "Clean & Go", "craft": "cleaning"})
    similar_name = _element(105, {"name": "Clean and Go", "craft": "cleaning"})
    result = _adapter(_payload(first, same_object, similar_name)).discover_all()

    assert tuple(item.entity_id for item in result.entities) == (
        "osm:node:104",
        "osm:node:105",
    )


def test_provider_category_mapping_is_narrow_and_explicit() -> None:
    result = _adapter(_payload(*_sample_elements())).discover_all()

    assert {item.entity_type for item in result.entities} == {
        MarketEntityType.COMPETITOR,
        MarketEntityType.POTENTIAL_CUSTOMER,
        MarketEntityType.PARTNER,
        MarketEntityType.SUPPLIER,
    }
    assert (
        next(
            item for item in result.entities if item.entity_id.endswith(":200")
        ).category
        == "property management"
    )
    assert (
        next(
            item for item in result.entities if item.entity_id.endswith(":300")
        ).category
        == "real estate agencies"
    )
    assert (
        next(
            item for item in result.entities if item.entity_id.endswith(":400")
        ).category
        == "cleaning supplies"
    )


def test_missing_website_and_phone_are_unknown() -> None:
    element = _element(
        106,
        {"name": "Property Office", "office": "property_management"},
    )
    entity = _adapter(_payload(element)).discover_all().entities[0]

    assert entity.website is None
    assert entity.phone is None
    assert all(not item.endswith(":website") for item in entity.evidence_ids)


def test_wrong_evidence_owner_is_rejected_by_discovery_contract() -> None:
    result = _adapter(_payload(*_sample_elements())).discover_all()
    broken = replace(result.evidence[0], owner_entity_id="osm:node:does-not-own-this")

    with pytest.raises(InvalidLiveContract, match="does not own"):
        MarketDiscoveryResult(
            entities=result.entities,
            evidence=(broken, *result.evidence[1:]),
            limitations=result.limitations,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (("phone", "cleaning services"), ("category", "roofing suppliers")),
)
def test_wrong_field_or_value_does_not_support_competitor_comparison(
    field: str, value: str
) -> None:
    result = _adapter(_payload(*_sample_elements())).discover_all()
    broken_evidence = replace(
        next(
            item
            for item in result.evidence
            if item.evidence_id == "osm:node:100:category"
        ),
        field=field,
        value=value,
    )
    broken = MarketDiscoveryResult(
        entities=result.entities,
        evidence=tuple(
            broken_evidence if item.evidence_id == broken_evidence.evidence_id else item
            for item in result.evidence
        ),
        limitations=result.limitations,
    )
    assessment = assess_business(_business(), broken)

    assert assessment.market_position.comparable_competitor_ids == ()
    assert assessment.status is AssessmentStatus.READY


def test_category_fit_never_claims_a_confirmed_lead_or_buying_intent() -> None:
    discovery = _adapter(_payload(*_sample_elements())).discover_all()
    assessment = assess_business(_business(), discovery)
    customer_opportunity = next(
        item
        for item in assessment.opportunities
        if item.opportunity_type is OpportunityType.CUSTOMER_ACQUISITION
    )
    summary = render_assessment_summary(assessment)

    assert "potential fit only" in customer_opportunity.description
    assert "buying intent are not verified" in customer_opportunity.description
    assert "Potential prospects (not qualified leads)" in summary
    assert "not qualified leads" in summary


def test_partner_and_supplier_fit_are_assessed_without_invented_prices() -> None:
    elements = (
        *_sample_elements(),
        _element(
            401,
            {
                "name": "Second Cleaning Supply Store",
                "shop": "cleaning_supplies",
                "addr:city": "Orlando",
                "addr:state": "Florida",
            },
        ),
    )
    discovery = _adapter(_payload(*elements)).discover_all()
    assessment = assess_business(_business(), discovery)

    assert any(
        item.opportunity_type is OpportunityType.PARTNERSHIP
        for item in assessment.opportunities
    )
    supplier_opportunity = next(
        item
        for item in assessment.opportunities
        if item.opportunity_type is OpportunityType.SUPPLIER
    )
    assert "prices" in supplier_opportunity.description
    assert "Compare the same" in supplier_opportunity.recommended_action


def test_empty_provider_result_is_valid_and_assessment_is_insufficient_data() -> None:
    discovery = _adapter(_payload()).discover_all()
    assessment = assess_business(_business(), discovery)

    assert discovery.entities == ()
    assert assessment.status is AssessmentStatus.INSUFFICIENT_DATA
    assert assessment.best_next_move is None


@pytest.mark.parametrize("status", (403, 429, 503))
def test_provider_failure_is_not_retried(status: int) -> None:
    def fail(query: str, endpoint: str, timeout: int, max_bytes: int) -> bytes:
        raise OverpassRequestError("provider failure", status_code=status)

    adapter = OverpassMarketDiscovery(transport=fail)
    business = _business()

    with pytest.raises(OverpassRequestError):
        adapter.discover_competitors(business)
    with pytest.raises(OverpassRequestError):
        adapter.discover_suppliers(business)
    assert adapter.request_count == 1


def test_timeout_is_not_retried() -> None:
    def fail(query: str, endpoint: str, timeout: int, max_bytes: int) -> bytes:
        raise OverpassRequestError("timed out")

    adapter = OverpassMarketDiscovery(transport=fail)

    with pytest.raises(OverpassRequestError, match="timed out"):
        adapter.discover_all()
    assert adapter.request_count == 1


@pytest.mark.parametrize("body", (b"{not json", b"[]", b'{"no_elements": []}'))
def test_malformed_external_data_fails_gracefully(body: bytes) -> None:
    adapter = _adapter(body)

    with pytest.raises(OverpassResponseError):
        adapter.discover_all()
    assert adapter.request_count == 1


def test_live_request_is_lazy_and_port_handoff_uses_assessment_engine() -> None:
    calls = 0

    def transport(query: str, endpoint: str, timeout: int, max_bytes: int) -> bytes:
        nonlocal calls
        calls += 1
        return _payload(*_sample_elements())

    adapter = OverpassMarketDiscovery(transport=transport)
    assert calls == 0
    discovery = _merge_port_results(adapter, _business())
    assessment = assess_business(_business(), discovery)

    assert calls == 1
    assert adapter.request_count == 1
    assert assessment.status is AssessmentStatus.READY
    assert assessment.market_position.comparable_competitor_ids == ()
    assert any(
        item.opportunity_type is OpportunityType.CUSTOMER_ACQUISITION
        for item in assessment.opportunities
    )


def test_non_orlando_market_is_rejected_before_request() -> None:
    adapter = _adapter(_payload())
    business = BusinessInput(
        business_name="Other profile",
        industry="HOUSE_CLEANING",
        city="Sample City Nine",
        state="Florida",
    )

    with pytest.raises(ValueError, match="scoped to House Cleaning in Orlando"):
        adapter.discover_competitors(business)
    assert adapter.request_count == 0


def test_cli_writes_review_reports_from_mocked_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    adapter = _adapter(_payload(*_sample_elements()))
    monkeypatch.setattr(
        "aeos.live.real_demo.OverpassMarketDiscovery",
        lambda **kwargs: adapter,
    )

    exit_code = real_demo_main(
        [
            "--city",
            "Orlando",
            "--state",
            "FL",
            "--industry",
            "HOUSE_CLEANING",
            "--output-dir",
            str(tmp_path),
        ]
    )

    output = capsys.readouterr().out
    json_path = next(tmp_path.glob("*.json"))
    markdown_path = next(tmp_path.glob("*.md"))
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert adapter.request_count == 1
    assert "BestNextMove:" in output
    assert report["target_identification"]["target_business"] is None
    assert report["counts"]["exact_comparable_competitors"] == 0
    assert report["provider"]["osm_attribution"] == "© OpenStreetMap contributors"
    assert report["provider"]["endpoint_hostname"] == "maps.mail.ru"
    assert report["provider_diagnostic"]["http_status"] == 200
    assert report["provider_diagnostic"]["request_reached_http_server"] is True
    customer = report["entities_by_category"]["potential_customers"][0]
    assert "Inference" in customer["commercial_fit_explanation"]
    assert "buying intent are unknown" in customer["commercial_fit_explanation"]
    assert "Research whether" in customer["suggested_first_research_step"]
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "not confirmed leads" in markdown
    assert "First research step:" in markdown


def test_cli_failure_still_writes_truthful_insufficient_data_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(query: str, endpoint: str, timeout: int, max_bytes: int) -> bytes:
        raise OverpassRequestError("endpoint unavailable")

    adapter = OverpassMarketDiscovery(transport=fail)
    monkeypatch.setattr(
        "aeos.live.real_demo.OverpassMarketDiscovery",
        lambda **kwargs: adapter,
    )

    exit_code = real_demo_main(["--output-dir", str(tmp_path)])

    capsys.readouterr()
    report = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert exit_code == 2
    assert report["provider_error"] == "endpoint unavailable"
    assert report["assessment"]["status"] == AssessmentStatus.INSUFFICIENT_DATA.value
    assert report["execution"]["provider_requests"] == 1
    diagnostic = report["provider_diagnostic"]
    assert diagnostic["endpoint_hostname"] == "maps.mail.ru"
    assert diagnostic["exception_type"] == "OverpassRequestError"
    assert diagnostic["sanitized_error_message"] == "endpoint unavailable"
    assert diagnostic["http_status"] is None
    assert diagnostic["request_reached_http_server"] is None
    assert diagnostic["elapsed_seconds"] >= 0
    assert report["target_identification"]["cleaning_service_listings_returned"] == 0
    assert "provider request failed" in report["target_identification"]["reason"]
    assert report["entities_by_category"]["potential_customers"] == []
    markdown = next(tmp_path.glob("*.md")).read_text(encoding="utf-8")
    assert (
        "category result is available because the provider request did not return data"
        in markdown
    )


@pytest.mark.parametrize(
    ("error", "category", "exception_type"),
    (
        (
            socket.gaierror(socket.EAI_NONAME, "Name or service not known"),
            "dns_resolution_failure",
            "gaierror",
        ),
        (
            ConnectionRefusedError(errno.ECONNREFUSED, "connection refused"),
            "connection_refused",
            "ConnectionRefusedError",
        ),
        (
            OSError(errno.EHOSTUNREACH, "No route to host"),
            "connection_unreachable",
            "OSError",
        ),
        (
            ssl.SSLCertVerificationError(1, "certificate verify failed"),
            "tls_certificate_error",
            "SSLCertVerificationError",
        ),
        (ssl.SSLError("TLS handshake failed"), "tls_error", "SSLError"),
        (
            TimeoutError(errno.ETIMEDOUT, "connection timed out"),
            "connection_timeout",
            "TimeoutError",
        ),
    ),
)
def test_connection_diagnostics_identify_pre_http_failures(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    category: str,
    exception_type: str,
) -> None:
    connection = _FakeHTTPSConnection(connect_error=error)
    settings = _install_connection(monkeypatch, connection)

    with pytest.raises(OverpassRequestError) as raised:
        _http_post("[out:json];", "https://maps.mail.ru/api/interpreter", 25, 1000)

    diagnostic = raised.value
    assert diagnostic.category == category
    assert diagnostic.exception_type == exception_type
    assert diagnostic.http_status is None
    assert diagnostic.request_reached_http_server is False
    assert diagnostic.phase == "connect"
    assert connection.request_calls == 0
    assert connection.closed is True
    assert settings == [("maps.mail.ru", 443, 25)]


def test_response_body_timeout_is_read_timeout_after_http_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _FakeHTTPSConnection(
        response=_FakeResponse(read_error=TimeoutError("read timed out"))
    )
    _install_connection(monkeypatch, connection)

    with pytest.raises(OverpassRequestError) as raised:
        _http_post("[out:json];", "https://maps.mail.ru/api/interpreter", 25, 1000)

    assert raised.value.category == "read_timeout"
    assert raised.value.exception_type == "TimeoutError"
    assert raised.value.http_status == 200
    assert raised.value.request_reached_http_server is True
    assert raised.value.phase == "reading_response_body"


def test_timeout_waiting_for_http_headers_does_not_claim_server_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _FakeHTTPSConnection(response_error=TimeoutError("timed out"))
    _install_connection(monkeypatch, connection)

    with pytest.raises(OverpassRequestError) as raised:
        _http_post("[out:json];", "https://maps.mail.ru/api/interpreter", 25, 1000)

    assert raised.value.category == "read_timeout"
    assert raised.value.phase == "awaiting_response_headers"
    assert raised.value.request_reached_http_server is None


@pytest.mark.parametrize(
    ("status", "category"), ((429, "http_status_error"), (503, "http_status_error"))
)
def test_http_error_status_records_server_response(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    category: str,
) -> None:
    connection = _FakeHTTPSConnection(
        response=_FakeResponse(status=status, reason="provider error")
    )
    _install_connection(monkeypatch, connection)

    with pytest.raises(OverpassRequestError) as raised:
        _http_post("[out:json];", "https://maps.mail.ru/api/interpreter", 25, 1000)

    assert raised.value.category == category
    assert raised.value.exception_type == "HTTPStatusError"
    assert raised.value.http_status == status
    assert raised.value.request_reached_http_server is True


def test_invalid_json_diagnostic_keeps_status_and_server_reachability() -> None:
    adapter = _adapter(b"{broken")

    with pytest.raises(OverpassResponseError) as raised:
        adapter.discover_all()

    assert raised.value.category == "invalid_json"
    assert raised.value.exception_type == "JSONDecodeError"
    assert raised.value.http_status == 200
    assert raised.value.request_reached_http_server is True
    assert "line 1" in raised.value.sanitized_error_message


def test_response_size_diagnostic_includes_http_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _FakeHTTPSConnection(response=_FakeResponse(body=b"12345"))
    _install_connection(monkeypatch, connection)

    with pytest.raises(OverpassResponseError) as raised:
        _http_post("[out:json];", "https://maps.mail.ru/api/interpreter", 25, 4)

    assert raised.value.category == "response_size_limit_exceeded"
    assert raised.value.exception_type == "ResponseSizeLimitExceeded"
    assert raised.value.http_status == 200
    assert raised.value.request_reached_http_server is True


def test_sanitized_diagnostics_redact_credentials_and_secret_values() -> None:
    error = OverpassRequestError(
        "failed https://pilot:secret@host/path?token=querysecret api_key=keysecret"
    )

    assert "secret" not in error.sanitized_error_message
    assert "keysecret" not in error.sanitized_error_message
    assert "<url-redacted>" in error.sanitized_error_message
