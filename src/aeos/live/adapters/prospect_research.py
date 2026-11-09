"""Single-tenant legacy prospect loader; it does not authorize tenant access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from typing import cast

from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind
from aeos.live.domain.market_intelligence import (
    CityMarketResearch,
    MarketEvidence,
)
from aeos.live.domain.opportunity_activation import (
    ActivationProspect,
    ProspectEvidence,
    VendorOnboardingState,
)


@dataclass(frozen=True, slots=True)
class ProspectResearchUpdate:
    entity_id: str
    vendor_onboarding: VendorOnboardingState
    vendor_onboarding_evidence_ids: tuple[str, ...]
    external_cleaning_vendor_evidence_ids: tuple[str, ...]
    cleaning_delivery_model: str
    operational_scale: str
    public_contact_channels: tuple[str, ...]
    public_contact_details: tuple[str, ...]
    relevant_public_contact_role: str
    recommended_approach: str
    validation_question: str
    limitations: tuple[str, ...]
    contact_revalidation_required: bool
    contact_revalidation_note: str | None
    synthetic_record: bool = False


@dataclass(frozen=True, slots=True)
class ProspectResearchCorpus:
    verified_on: date
    updates: tuple[ProspectResearchUpdate, ...]
    evidence: tuple[ProspectEvidence, ...]
    synthetic_fixture: bool = False


def load_prospect_research(path: Path) -> ProspectResearchCorpus:
    """Read local research without fetching or crawling any source URL."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InvalidLiveContract(
            f"could not read prospect research: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise InvalidLiveContract("prospect research must be a JSON object")
    verified_on = _date(payload.get("verified_on"), "verified_on")
    synthetic_fixture = _optional_boolean(payload, "synthetic_fixture")
    raw_updates = payload.get("prospects")
    raw_evidence = payload.get("evidence")
    if not isinstance(raw_updates, list) or not isinstance(raw_evidence, list):
        raise InvalidLiveContract(
            "prospect research needs prospects and evidence arrays"
        )
    if synthetic_fixture and any(
        not isinstance(item, dict) or item.get("synthetic_record") is not True
        for item in (*raw_updates, *raw_evidence)
    ):
        raise InvalidLiveContract(
            "synthetic fixtures need explicit synthetic_record markers"
        )
    updates = tuple(
        _update_from_dict(cast(dict[str, object], item)) for item in raw_updates
    )
    evidence = tuple(
        _evidence_from_dict(cast(dict[str, object], item)) for item in raw_evidence
    )
    update_ids = [item.entity_id for item in updates]
    evidence_ids = [item.evidence_id for item in evidence]
    if len(set(update_ids)) != len(update_ids):
        raise InvalidLiveContract("prospect updates must be unique by entity_id")
    if len(set(evidence_ids)) != len(evidence_ids):
        raise InvalidLiveContract("supplemental evidence IDs must be unique")
    known_entities = set(update_ids)
    if any(item.entity_id not in known_entities for item in evidence):
        raise InvalidLiveContract(
            "every supplemental evidence item needs a prospect update"
        )
    evidence_by_id = {item.evidence_id: item for item in evidence}
    for update in updates:
        refs = (
            *update.vendor_onboarding_evidence_ids,
            *update.external_cleaning_vendor_evidence_ids,
        )
        if set(refs) - evidence_by_id.keys():
            raise InvalidLiveContract(
                f"update for {update.entity_id} references unknown supplemental evidence"
            )
        if any(
            evidence_by_id[reference].entity_id != update.entity_id
            for reference in refs
        ):
            raise InvalidLiveContract(
                f"update for {update.entity_id} references another prospect's evidence"
            )
        if update.vendor_onboarding is VendorOnboardingState.PUBLIC_VENDOR_ROUTE:
            if not update.vendor_onboarding_evidence_ids:
                raise InvalidLiveContract("a public vendor route requires evidence")
    return ProspectResearchCorpus(
        verified_on, updates, evidence, synthetic_fixture=synthetic_fixture
    )


def build_activation_prospects(
    markets: tuple[CityMarketResearch, ...],
    research: ProspectResearchCorpus,
) -> tuple[ActivationProspect, ...]:
    """Join reviewed prospect candidates to their prior and refreshed evidence."""

    update_by_id = {item.entity_id: item for item in research.updates}
    evidence_by_entity: dict[str, dict[str, ProspectEvidence]] = {
        entity_id: {} for entity_id in update_by_id
    }
    for market in markets:
        for source in market.evidence:
            if source.entity_id in evidence_by_entity:
                converted = _convert_evidence(source)
                evidence_by_entity[source.entity_id].setdefault(
                    converted.evidence_id, converted
                )
    for supplemental in research.evidence:
        evidence_by_entity[supplemental.entity_id].setdefault(
            supplemental.evidence_id, supplemental
        )

    prospects: list[ActivationProspect] = []
    seen: set[str] = set()
    for market in markets:
        for organization in market.organizations:
            update = update_by_id.get(organization.entity_id)
            if update is None or organization.entity_id in seen:
                continue
            seen.add(organization.entity_id)
            prospect_evidence = tuple(
                evidence_by_entity[organization.entity_id].values()
            )
            known_ids = {item.evidence_id for item in prospect_evidence}
            required_ids = (
                *organization.evidence_ids,
                *update.vendor_onboarding_evidence_ids,
                *update.external_cleaning_vendor_evidence_ids,
                *organization.buying_intent_evidence_ids,
            )
            if set(required_ids) - known_ids:
                raise InvalidLiveContract(
                    f"prospect {organization.entity_id} references missing evidence"
                )
            prospects.append(
                ActivationProspect(
                    prospect_id=organization.entity_id,
                    organization=organization.name,
                    market=organization.city,
                    source_role=organization.role,
                    website_url=organization.website_url,
                    services=organization.services,
                    service_areas=organization.service_areas,
                    customer_segments=organization.customer_segments,
                    recurring_options=organization.recurring_options,
                    public_contact_channels=update.public_contact_channels,
                    public_contact_details=update.public_contact_details,
                    relevant_public_contact_role=update.relevant_public_contact_role,
                    vendor_onboarding=update.vendor_onboarding,
                    vendor_onboarding_evidence_ids=(
                        update.vendor_onboarding_evidence_ids
                    ),
                    external_cleaning_vendor_evidence_ids=(
                        update.external_cleaning_vendor_evidence_ids
                    ),
                    buying_intent_evidence_ids=(
                        organization.buying_intent_evidence_ids
                    ),
                    cleaning_delivery_model=update.cleaning_delivery_model,
                    operational_scale=update.operational_scale,
                    buyer_fit_reason=organization.buyer_fit_reason,
                    recommended_action=update.recommended_approach,
                    validation_question=update.validation_question,
                    evidence=prospect_evidence,
                    limitations=tuple(
                        dict.fromkeys((*organization.limitations, *update.limitations))
                    ),
                    contact_revalidation_required=(
                        update.contact_revalidation_required
                    ),
                    contact_revalidation_note=update.contact_revalidation_note,
                    synthetic_fixture=(
                        research.synthetic_fixture and update.synthetic_record
                    ),
                )
            )
    missing = set(update_by_id) - seen
    if missing:
        raise InvalidLiveContract(
            "prospects absent from market intelligence: " + ", ".join(sorted(missing))
        )
    return tuple(prospects)


def _convert_evidence(source: MarketEvidence) -> ProspectEvidence:
    return ProspectEvidence(
        evidence_id=source.evidence_id,
        entity_id=source.entity_id,
        field=source.field,
        value=source.value,
        source_name=source.source_name,
        source_url=source.source_url,
        observed_on=source.retrieved_at.date(),
        classification=source.classification,
        confidence=source.confidence,
        supporting_information=source.supporting_information,
        limitations=source.limitations,
        published_on=source.published_at,
    )


def _update_from_dict(payload: dict[str, object]) -> ProspectResearchUpdate:
    try:
        state = VendorOnboardingState(str(payload["vendor_onboarding"]))
    except (KeyError, ValueError) as error:
        raise InvalidLiveContract("vendor_onboarding is missing or invalid") from error
    return ProspectResearchUpdate(
        entity_id=_string(payload, "entity_id"),
        vendor_onboarding=state,
        vendor_onboarding_evidence_ids=_string_tuple(
            payload, "vendor_onboarding_evidence_ids"
        ),
        external_cleaning_vendor_evidence_ids=_string_tuple(
            payload, "external_cleaning_vendor_evidence_ids"
        ),
        cleaning_delivery_model=_string(payload, "cleaning_delivery_model"),
        operational_scale=_string(payload, "operational_scale"),
        public_contact_channels=_string_tuple(payload, "public_contact_channels"),
        public_contact_details=_string_tuple(payload, "public_contact_details"),
        relevant_public_contact_role=_string(payload, "relevant_public_contact_role"),
        recommended_approach=_string(payload, "recommended_approach"),
        validation_question=_string(payload, "validation_question"),
        limitations=_string_tuple(payload, "limitations"),
        contact_revalidation_required=_boolean(
            payload, "contact_revalidation_required"
        ),
        contact_revalidation_note=_optional_string(
            payload.get("contact_revalidation_note"), "contact_revalidation_note"
        ),
        synthetic_record=_optional_boolean(payload, "synthetic_record"),
    )


def _evidence_from_dict(payload: dict[str, object]) -> ProspectEvidence:
    try:
        classification = EvidenceKind(str(payload["classification"]))
    except (KeyError, ValueError) as error:
        raise InvalidLiveContract(
            "evidence classification is missing or invalid"
        ) from error
    return ProspectEvidence(
        evidence_id=_string(payload, "evidence_id"),
        entity_id=_string(payload, "entity_id"),
        field=_string(payload, "field"),
        value=_string(payload, "value"),
        source_name=_string(payload, "source_name"),
        source_url=_string(payload, "source_url"),
        observed_on=_date(payload.get("observed_on"), "observed_on"),
        classification=classification,
        confidence=_float(payload, "confidence"),
        supporting_information=_string(payload, "supporting_information"),
        limitations=_string_tuple(payload, "limitations"),
        published_on=(
            _date(payload.get("published_on"), "published_on")
            if payload.get("published_on") is not None
            else None
        ),
    )


def _string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{key} must be a non-blank string")
    return value.strip()


def _optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{field} must be a non-blank string or null")
    return value.strip()


def _string_tuple(payload: dict[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise InvalidLiveContract(f"{key} must be an array of non-blank strings")
    return tuple(item.strip() for item in value)


def _boolean(payload: dict[str, object], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise InvalidLiveContract(f"{key} must be a boolean")
    return value


def _optional_boolean(payload: dict[str, object], key: str) -> bool:
    value = payload.get(key, False)
    if not isinstance(value, bool):
        raise InvalidLiveContract(f"{key} must be a boolean")
    return value


def _float(payload: dict[str, object], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidLiveContract(f"{key} must be a number")
    return float(value)


def _date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise InvalidLiveContract(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise InvalidLiveContract(f"{field} must be an ISO date") from error
