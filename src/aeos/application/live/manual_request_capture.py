"""Traceable capture of manually reviewed public service-request posts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
import hashlib
import re
from urllib.parse import urlsplit

from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.url_policy import (
    has_sensitive_query_parameter,
    safe_text_for_report,
    safe_url_for_report,
)


_ACCESS_STATUSES = frozenset(
    {"PUBLIC_POST_MANUALLY_VIEWED", "USER_SUPPLIED_TEXT_LINK_NOT_VERIFIED"}
)
_REQUEST_PREFIX = re.compile(
    r"\b(?:i(?:'m| am)?\s+looking\s+for|looking\s+for|seeking|"
    r"i\s+need|we\s+need|need\s+(?:a|an|someone|somebody|to\s+hire)?|"
    r"want\s+to\s+hire|hiring|busco|buscamos|estoy\s+buscando|"
    r"necesito|necesitamos|solicito|solicitamos|se\s+busca|"
    r"anyone\s+(?:know|recommend)|can\s+anyone\s+recommend|"
    r"could\s+someone\s+recommend|request(?:ing)?(?:\s+(?:a|an))?|"
    r"please\s+send(?:\s+me)?|send\s+me|can\s+you|could\s+you)\b",
    re.IGNORECASE,
)
_SERVICE_OR_QUOTE = re.compile(
    r"\b(?:quote|estimate|bid|proposal|cotizaci[oó]n|presupuesto|"
    r"service\s+provider|provider|vendor|contractor|clean(?:er|ing)?|"
    r"limpieza|limpiar|hvac|air\s+conditioning|heating|ac\s+(?:repair|service)|"
    r"repair|installation|install|maintenance|remodel(?:ing)?|construction|"
    r"plumb(?:er|ing)|electric(?:ian|al)?|handyman|landscap(?:e|ing)|"
    r"pest\s+control|painting|roof(?:er|ing)|moving\s+company)\b",
    re.IGNORECASE,
)


def capture_manual_request(
    payload: Mapping[str, object],
    *,
    captured_at: datetime | None = None,
) -> dict[str, object]:
    """Validate user-pasted public-post evidence without fetching its URL."""

    source_url = _public_url(payload.get("source_url"))
    access_status = _required_text(payload.get("access_status"), "access_status")
    if access_status not in _ACCESS_STATUSES:
        raise InvalidLiveContract(
            "access_status must be PUBLIC_POST_MANUALLY_VIEWED or USER_SUPPLIED_TEXT_LINK_NOT_VERIFIED"
        )
    visible_text = _required_text(payload.get("visible_text"), "visible_text")
    if len(visible_text) > 12_000:
        raise InvalidLiveContract("visible_text must not exceed 12000 characters")

    excerpt_value = payload.get("evidence_excerpt")
    excerpt = (
        visible_text[:500]
        if excerpt_value is None
        else _required_text(excerpt_value, "evidence_excerpt")
    )
    if len(excerpt) > 500 or excerpt not in visible_text:
        raise InvalidLiveContract(
            "evidence_excerpt must be an exact substring of visible_text with at most 500 characters"
        )
    city = _optional_visible_text(payload.get("city"), "city", visible_text)
    state = _optional_visible_text(payload.get("state"), "state", visible_text)
    service = _optional_visible_text(
        payload.get("service_requested"), "service_requested", visible_text
    )
    publication_date = _publication_date(payload.get("publication_date"))
    timestamp = _capture_timestamp(payload.get("captured_at"), captured_at)

    intent_match = _explicit_request_match(visible_text, service)
    intent_excerpt = (
        _excerpt_around(visible_text, intent_match.start(), intent_match.end())
        if intent_match
        else None
    )
    capture_id = hashlib.sha256(
        f"{source_url}\0{timestamp.isoformat()}\0{excerpt}".encode("utf-8")
    ).hexdigest()[:20]
    return {
        "record_type": "MANUAL_PUBLIC_REQUEST_CAPTURE",
        "capture_id": capture_id,
        "source_url": source_url,
        "captured_at": timestamp.isoformat(),
        "publication_date": publication_date.isoformat() if publication_date else None,
        "access_status": access_status,
        "city": city,
        "state": state,
        "service_requested": service,
        "evidence": {
            "classification": "REPORTED_VISIBLE_TEXT",
            "source_url": source_url,
            "excerpt": safe_text_for_report(excerpt),
        },
        "intent_assessment": {
            "classification": "EXPLICIT_REQUEST_IN_TEXT"
            if intent_match
            else "NO_EXPLICIT_REQUEST_FOUND",
            "explicit_intent": intent_match is not None,
            "evidence_excerpt": safe_text_for_report(intent_excerpt)
            if intent_excerpt
            else None,
            "buyer_confirmed": False,
            "buyer_status": "NOT_CONFIRMED",
        },
        "collection_method": "MANUAL_USER_ENTRY_NO_FETCH_NO_SCRAPING",
        "contact_sent": False,
        "limitations": [
            "AEOS no abrió ni verificó el enlace; el estado de acceso procede de la entrada manual.",
            "La intención explícita describe el texto observado y no confirma identidad, disponibilidad ni compra.",
            "No se contactó al autor ni se automatizó la lectura de grupos.",
        ],
    }


def _explicit_request_match(text: str, service: str | None) -> re.Match[str] | None:
    service_term = re.escape(service) if service else None
    suffix = _SERVICE_OR_QUOTE.pattern[2:-2]
    if service_term:
        suffix = rf"(?:{suffix}|{service_term})"
    pattern = re.compile(
        rf"{_REQUEST_PREFIX.pattern}[^.!?\n]{{0,220}}?\b{suffix}\b",
        re.IGNORECASE,
    )
    return pattern.search(text)


def _excerpt_around(text: str, start: int, end: int, limit: int = 500) -> str:
    if end - start >= limit:
        return text[start : start + limit]
    left = max(0, start - (limit - (end - start)) // 2)
    right = min(len(text), left + limit)
    left = max(0, right - limit)
    return text[left:right].strip()


def _public_url(value: object) -> str:
    raw = _required_text(value, "source_url")
    try:
        parts = urlsplit(raw)
        _ = parts.port
    except ValueError as error:
        raise InvalidLiveContract(
            "source_url must be a valid public HTTP(S) URL"
        ) from error
    if (
        parts.scheme.casefold() not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or has_sensitive_query_parameter(raw)
    ):
        raise InvalidLiveContract(
            "source_url must be a public HTTP(S) URL without credentials"
        )
    clean = safe_url_for_report(raw)
    if clean is None or clean == "[URL omitted]":
        raise InvalidLiveContract("source_url could not be normalized safely")
    return clean


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{field} must be non-blank text")
    return value.strip()


def _optional_visible_text(value: object, field: str, visible_text: str) -> str | None:
    if value is None or value == "":
        return None
    result = _required_text(value, field)
    if result.casefold() not in visible_text.casefold():
        raise InvalidLiveContract(
            f"{field} must be copied from the supplied visible_text"
        )
    return result


def _publication_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise InvalidLiveContract("publication_date must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise InvalidLiveContract("publication_date must use YYYY-MM-DD") from error


def _capture_timestamp(value: object, default: datetime | None) -> datetime:
    if value is None:
        result = default or datetime.now(timezone.utc)
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise InvalidLiveContract(
                "captured_at must be an ISO-8601 timestamp"
            ) from error
    else:
        raise InvalidLiveContract("captured_at must be an ISO-8601 timestamp")
    if result.tzinfo is None:
        raise InvalidLiveContract("captured_at must include a timezone")
    return result.astimezone(timezone.utc)
