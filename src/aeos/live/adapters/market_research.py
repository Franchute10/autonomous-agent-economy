"""Single-tenant legacy research loader; it does not authorize tenant access."""

from __future__ import annotations

from datetime import date, datetime
import json
from enum import StrEnum
from pathlib import Path
from typing import TypeVar, cast

from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind
from aeos.live.domain.market_intelligence import (
    CityMarketResearch,
    MarketEvidence,
    MarketOrganization,
    OrganizationRole,
    PublicDemandSignal,
    ResearchStatus,
    SourceCoverage,
    resolve_organization_duplicates,
)

E = TypeVar("E", bound=StrEnum)


def load_manual_market_research(
    path: Path,
) -> tuple[datetime, tuple[CityMarketResearch, ...]]:
    """Load a reviewed, public-URL corpus without fetching source pages."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InvalidLiveContract(
            f"could not read manual research corpus: {error}"
        ) from error
    if not isinstance(payload, dict) or not isinstance(payload.get("markets"), list):
        raise InvalidLiveContract("manual research corpus must contain a markets array")
    synthetic_fixture = payload.get("synthetic_fixture", False)
    if not isinstance(synthetic_fixture, bool):
        raise InvalidLiveContract("synthetic_fixture must be boolean")
    snapshot_at = _datetime(payload.get("snapshot_at"), "snapshot_at")
    markets: list[CityMarketResearch] = []
    for raw_market in payload["markets"]:
        if not isinstance(raw_market, dict):
            raise InvalidLiveContract("each market must be a JSON object")
        markets.append(
            _market_from_dict(raw_market, synthetic_fixture=synthetic_fixture)
        )
    if len({market.city.casefold() for market in markets}) != len(markets):
        raise InvalidLiveContract(
            "market cities must be independently represented once"
        )
    return snapshot_at, tuple(markets)


def _market_from_dict(
    payload: dict[str, object], *, synthetic_fixture: bool = False
) -> CityMarketResearch:
    raw_evidence = _list(payload, "evidence")
    evidence = tuple(
        _evidence_from_dict(
            cast(dict[str, object], item),
            synthetic_fixture=synthetic_fixture,
        )
        for item in raw_evidence
    )
    organizations = tuple(
        _organization_from_dict(
            cast(dict[str, object], item),
            synthetic_fixture=synthetic_fixture,
        )
        for item in _list(payload, "organizations")
    )
    demand_signals = tuple(
        _signal_from_dict(
            cast(dict[str, object], item),
            synthetic_fixture=synthetic_fixture,
        )
        for item in _list(payload, "demand_signals")
    )
    organizations, evidence = resolve_organization_duplicates(organizations, evidence)
    return CityMarketResearch(
        city=_string(payload, "city"),
        state=_string(payload, "state"),
        organizations=organizations,
        demand_signals=demand_signals,
        evidence=evidence,
        source_coverage=tuple(
            _coverage_from_dict(cast(dict[str, object], item))
            for item in _list(payload, "source_coverage")
        ),
        limitations=_string_tuple(payload.get("limitations", []), "limitations"),
    )


def _organization_from_dict(
    payload: dict[str, object], *, synthetic_fixture: bool = False
) -> MarketOrganization:
    return MarketOrganization(
        entity_id=_string(payload, "entity_id"),
        name=_string(payload, "name"),
        city=_string(payload, "city"),
        role=_enum(OrganizationRole, payload.get("role"), "role"),
        website_url=_optional_string(payload.get("website_url"), "website_url"),
        public_address=_optional_string(
            payload.get("public_address"), "public_address"
        ),
        service_areas=_string_tuple(payload.get("service_areas", []), "service_areas"),
        services=_string_tuple(payload.get("services", []), "services"),
        customer_segments=_string_tuple(
            payload.get("customer_segments", []), "customer_segments"
        ),
        vacation_rental_specialization=_boolean(
            payload, "vacation_rental_specialization"
        ),
        recurring_options=_string_tuple(
            payload.get("recurring_options", []), "recurring_options"
        ),
        pricing_model=_optional_string(payload.get("pricing_model"), "pricing_model"),
        public_listing_url=_optional_string(
            payload.get("public_listing_url"), "public_listing_url"
        ),
        rating_claim=_optional_float(payload.get("rating_claim"), "rating_claim"),
        review_count_claim=_optional_int(
            payload.get("review_count_claim"), "review_count_claim"
        ),
        booking_methods=_string_tuple(
            payload.get("booking_methods", []), "booking_methods"
        ),
        conversion_channels=_string_tuple(
            payload.get("conversion_channels", []), "conversion_channels"
        ),
        public_contacts=_string_tuple(
            payload.get("public_contacts", []), "public_contacts"
        ),
        buyer_fit_reason=_optional_string(
            payload.get("buyer_fit_reason"), "buyer_fit_reason"
        ),
        referral_reason=_optional_string(
            payload.get("referral_reason"), "referral_reason"
        ),
        recommended_action=_string(payload, "recommended_action"),
        validation_question=_string(payload, "validation_question"),
        evidence_ids=_string_tuple(payload.get("evidence_ids", []), "evidence_ids"),
        buying_intent_evidence_ids=_string_tuple(
            payload.get("buying_intent_evidence_ids", []),
            "buying_intent_evidence_ids",
        ),
        limitations=_string_tuple(payload.get("limitations", []), "limitations"),
        synthetic_record=(
            synthetic_fixture
            or _optional_boolean(payload.get("synthetic_record"), "synthetic_record")
        ),
    )


def _evidence_from_dict(
    payload: dict[str, object], *, synthetic_fixture: bool = False
) -> MarketEvidence:
    published = payload.get("published_at")
    classification = _enum(
        EvidenceKind, payload.get("classification"), "classification"
    )
    if synthetic_fixture and classification is EvidenceKind.OBSERVED:
        raise InvalidLiveContract(
            "synthetic fixtures cannot contain OBSERVED market evidence"
        )
    return MarketEvidence(
        evidence_id=_string(payload, "evidence_id"),
        entity_id=_string(payload, "entity_id"),
        field=_string(payload, "field"),
        value=_string(payload, "value"),
        source_name=_string(payload, "source_name"),
        source_url=_string(payload, "source_url"),
        retrieved_at=_datetime(payload.get("retrieved_at"), "retrieved_at"),
        published_at=(
            date.fromisoformat(_as_string(published, "published_at"))
            if published
            else None
        ),
        classification=classification,
        confidence=_float(payload, "confidence"),
        supporting_information=_string(payload, "supporting_information"),
        limitations=_string_tuple(payload.get("limitations", []), "limitations"),
    )


def _signal_from_dict(
    payload: dict[str, object], *, synthetic_fixture: bool = False
) -> PublicDemandSignal:
    published = payload.get("publication_date")
    return PublicDemandSignal(
        signal_id=_string(payload, "signal_id"),
        city=_string(payload, "city"),
        platform=_string(payload, "platform"),
        source_url=_string(payload, "source_url"),
        publication_date=(
            date.fromisoformat(_as_string(published, "publication_date"))
            if published
            else None
        ),
        retrieved_at=_datetime(payload.get("retrieved_at"), "retrieved_at"),
        service_requested=_string(payload, "service_requested"),
        supporting_excerpt=_string(payload, "supporting_excerpt"),
        evidence_id=_string(payload, "evidence_id"),
        supporting_excerpt_es=_optional_string(
            payload.get("supporting_excerpt_es"), "supporting_excerpt_es"
        ),
        limitations=_string_tuple(payload.get("limitations", []), "limitations"),
        synthetic_record=(
            synthetic_fixture
            or _optional_boolean(payload.get("synthetic_record"), "synthetic_record")
        ),
    )


def _coverage_from_dict(payload: dict[str, object]) -> SourceCoverage:
    return SourceCoverage(
        source_name=_string(payload, "source_name"),
        status=_enum(ResearchStatus, payload.get("status"), "status"),
        retrieved_at=_datetime(payload.get("retrieved_at"), "retrieved_at"),
        result_count=_optional_int(payload.get("result_count"), "result_count"),
        note=_string(payload, "note"),
        request_count=_int(payload, "request_count"),
    )


def _list(payload: dict[str, object], field: str) -> list[object]:
    value = payload.get(field, [])
    if not isinstance(value, list):
        raise InvalidLiveContract(f"{field} must be a JSON array")
    return value


def _string(payload: dict[str, object], field: str) -> str:
    return _as_string(payload.get(field), field)


def _as_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{field} must be a non-blank string")
    return value.strip()


def _optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _as_string(value, field)


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise InvalidLiveContract(f"{field} must be an array of non-blank strings")
    return tuple(item.strip() for item in value)


def _boolean(payload: dict[str, object], field: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise InvalidLiveContract(f"{field} must be a boolean")
    return value


def _optional_boolean(value: object, field: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise InvalidLiveContract(f"{field} must be a boolean")
    return value


def _enum(enum_type: type[E], value: object, field: str) -> E:
    if not isinstance(value, str):
        raise InvalidLiveContract(f"{field} must be a string enum value")
    try:
        return enum_type(value)
    except ValueError as error:
        raise InvalidLiveContract(f"unsupported {field}: {value!r}") from error


def _datetime(value: object, field: str) -> datetime:
    text = _as_string(value, field)
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidLiveContract(f"{field} must be an ISO datetime") from error
    if result.tzinfo is None:
        raise InvalidLiveContract(f"{field} must include a timezone")
    return result


def _float(payload: dict[str, object], field: str) -> float:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidLiveContract(f"{field} must be numeric")
    return float(value)


def _optional_float(value: object, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidLiveContract(f"{field} must be numeric or null")
    return float(value)


def _int(payload: dict[str, object], field: str) -> int:
    value = payload.get(field, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidLiveContract(f"{field} must be an integer")
    return value


def _optional_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidLiveContract(f"{field} must be an integer or null")
    return value


__all__ = ["load_manual_market_research"]
