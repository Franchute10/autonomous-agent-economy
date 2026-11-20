"""Resolve website location candidates only after an explicit owner selection."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from aeos.live.domain.market_scope import MarketResearchScope
from aeos.live.domain.location_candidate import LocationCandidate, LocationType
from aeos.live.ports.website import WebsiteInspectionResult

Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class MarketSelectionResolution:
    scope: MarketResearchScope
    original_candidate: LocationCandidate | None
    location_was_corrected_or_added: bool
    user_added_services: tuple[str, ...]


def resolve_business_locations(
    inspection: WebsiteInspectionResult,
    *,
    selected_city: str,
    selected_state: str | None = None,
    corrected_city: str | None = None,
    corrected_state: str | None = None,
    postal_code: str | None = None,
    research_radius: float | None = None,
    radius_unit: str | None = None,
    selected_services: tuple[str, ...] = (),
    use_detected_services: bool = False,
    clock: Clock | None = None,
) -> MarketSelectionResolution:
    """Create a market scope while retaining original website evidence separately."""

    if not isinstance(inspection, WebsiteInspectionResult):
        raise TypeError("inspection must be a WebsiteInspectionResult")
    source_city = selected_city.strip() if isinstance(selected_city, str) else ""
    if not source_city:
        raise ValueError("selected_city must be non-blank")
    match = next(
        (
            item
            for item in inspection.locations
            if item.location_type
            not in {
                LocationType.NEIGHBORHOOD_MENTION,
                LocationType.REGIONAL_SERVICE_AREA,
            }
            if item.city.casefold() == source_city.casefold()
            and (
                selected_state is None
                or item.state is None
                or item.state.casefold() == selected_state.casefold()
            )
        ),
        None,
    )
    city = corrected_city.strip() if corrected_city else source_city
    state = (
        corrected_state
        or selected_state
        or (match.state if match is not None else None)
    )
    corrected = (
        match is None
        or city.casefold() != source_city.casefold()
        or (
            state is not None
            and match.state is not None
            and state.casefold() != match.state.casefold()
        )
    )
    if not state:
        raise ValueError(
            "A state is required when the website does not identify one; supply it as an owner correction."
        )
    if (research_radius is None) != (radius_unit is None):
        raise ValueError("research_radius and radius_unit must be supplied together")
    explicit_services = tuple(
        dict.fromkeys(value.strip() for value in selected_services if value.strip())
    )
    if explicit_services and use_detected_services:
        raise ValueError("choose selected services or use_detected_services, not both")
    detected = tuple(dict.fromkeys(item.service for item in inspection.services))
    services = detected if use_detected_services else explicit_services
    if not services:
        raise ValueError(
            "Confirm at least one service with selected_services or use_detected_services."
        )
    detected_names = {item.casefold() for item in detected}
    added_services = tuple(
        item for item in services if item.casefold() not in detected_names
    )
    scope = MarketResearchScope(
        city=city,
        state=state,
        postal_code=postal_code or (match.postal_code if match is not None else None),
        research_radius=research_radius,
        radius_unit=radius_unit,
        selected_services=services,
        selected_at=(clock or (lambda: datetime.now(timezone.utc)))().astimezone(
            timezone.utc
        ),
        owner_confirmed=True,
        source_evidence_id=match.evidence_id if match is not None else None,
    )
    return MarketSelectionResolution(
        scope=scope,
        original_candidate=match,
        location_was_corrected_or_added=corrected,
        user_added_services=added_services,
    )
