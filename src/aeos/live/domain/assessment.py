"""Assessment aggregate and explicit JSON serialization adapter."""

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import StrEnum
import json
from typing import cast

from aeos.live.domain.business import BusinessInput
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import SourceEvidence
from aeos.live.domain.market import (
    MarketEntity,
    MarketPosition,
    MarketStructureObservation,
)
from aeos.live.domain.opportunity import Opportunity


class AssessmentStatus(StrEnum):
    READY = "READY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class BestNextMove:
    selected_opportunity_id: str
    why_this_one: str
    evidence_ids: tuple[str, ...]
    first_action: str
    measurement_kpi: str
    limitations: tuple[str, ...]
    ready_to_use_asset: str | None = None

    def __post_init__(self) -> None:
        for field in (
            "selected_opportunity_id",
            "why_this_one",
            "first_action",
            "measurement_kpi",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidLiveContract(f"{field} must be a non-blank string")
            object.__setattr__(self, field, value.strip())
        for field in ("evidence_ids", "limitations"):
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                raise InvalidLiveContract(
                    f"{field} must be a tuple of non-blank strings"
                )
        if self.ready_to_use_asset is not None and (
            not isinstance(self.ready_to_use_asset, str)
            or not self.ready_to_use_asset.strip()
        ):
            raise InvalidLiveContract("ready_to_use_asset must be non-blank or None")


@dataclass(frozen=True, slots=True)
class BusinessAssessment:
    business: BusinessInput
    evidence: tuple[SourceEvidence, ...]
    market_entities: tuple[MarketEntity, ...]
    market_position: MarketPosition
    market_structure_observations: tuple[MarketStructureObservation, ...]
    opportunities: tuple[Opportunity, ...]
    best_next_move: BestNextMove | None
    limitations: tuple[str, ...] = ()
    status: AssessmentStatus = AssessmentStatus.READY

    def __post_init__(self) -> None:
        if not isinstance(self.business, BusinessInput):
            raise InvalidLiveContract("business must be a BusinessInput")
        if not isinstance(self.market_position, MarketPosition):
            raise InvalidLiveContract("market_position must be a MarketPosition")
        if not isinstance(self.status, AssessmentStatus):
            raise InvalidLiveContract("status must be an AssessmentStatus")
        expected_types = (
            ("evidence", SourceEvidence),
            ("market_entities", MarketEntity),
            ("market_structure_observations", MarketStructureObservation),
            ("opportunities", Opportunity),
        )
        for field, expected in expected_types:
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not isinstance(item, expected) for item in values
            ):
                raise InvalidLiveContract(
                    f"{field} must be a tuple of {expected.__name__} values"
                )
        if not isinstance(self.limitations, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.limitations
        ):
            raise InvalidLiveContract(
                "limitations must be a tuple of non-blank strings"
            )

        if self.status is AssessmentStatus.READY:
            if not isinstance(self.best_next_move, BestNextMove):
                raise InvalidLiveContract(
                    "ready assessment must include a BestNextMove"
                )
            if not self.evidence:
                raise InvalidLiveContract("ready assessment requires evidence")
            if not self.opportunities:
                raise InvalidLiveContract("ready assessment requires opportunities")
            if any(not item.evidence_ids for item in self.opportunities):
                raise InvalidLiveContract(
                    "ready assessment opportunities require supporting evidence"
                )
            if not self.best_next_move.evidence_ids:
                raise InvalidLiveContract(
                    "ready best_next_move requires supporting evidence"
                )
        else:
            if self.best_next_move is not None:
                raise InvalidLiveContract(
                    "insufficient-data assessment cannot select a best next move"
                )
            if self.opportunities:
                raise InvalidLiveContract(
                    "insufficient-data assessment cannot include opportunities"
                )
            if not self.limitations:
                raise InvalidLiveContract(
                    "insufficient-data assessment must explain its limitations"
                )

        evidence_ids = [item.evidence_id for item in self.evidence]
        entity_ids = [item.entity_id for item in self.market_entities]
        opportunity_ids = [item.opportunity_id for item in self.opportunities]
        for label, values in (
            ("evidence", evidence_ids),
            ("entity", entity_ids),
            ("opportunity", opportunity_ids),
        ):
            if len(set(values)) != len(values):
                raise InvalidLiveContract(f"{label} identifiers must be unique")
        known_evidence = set(evidence_ids)
        known_entities = set(entity_ids)
        known_opportunities = set(opportunity_ids)
        entities_by_id = {entity.entity_id: entity for entity in self.market_entities}
        evidence_by_id = {item.evidence_id: item for item in self.evidence}

        def check_evidence_refs(refs: tuple[str, ...], source: str) -> None:
            unknown = set(refs) - known_evidence
            if unknown:
                raise InvalidLiveContract(
                    f"{source} references unknown evidence: {', '.join(sorted(unknown))}"
                )

        for entity in self.market_entities:
            if not entity.evidence_ids:
                raise InvalidLiveContract(
                    f"entity {entity.entity_id} must reference source evidence"
                )
            check_evidence_refs(entity.evidence_ids, f"entity {entity.entity_id}")
            for evidence_id in entity.evidence_ids:
                evidence = evidence_by_id[evidence_id]
                if evidence.owner_entity_id != entity.entity_id:
                    raise InvalidLiveContract(
                        f"entity {entity.entity_id} references evidence it does not own"
                    )
        for evidence in self.evidence:
            if evidence.owner_entity_id is not None:
                owner = entities_by_id.get(evidence.owner_entity_id)
                if owner is None:
                    raise InvalidLiveContract(
                        f"evidence {evidence.evidence_id} references an unknown owner entity"
                    )
                if evidence.evidence_id not in owner.evidence_ids:
                    raise InvalidLiveContract(
                        f"evidence {evidence.evidence_id} is not associated with its owner entity"
                    )
        if not set(self.market_position.comparable_competitor_ids) <= known_entities:
            raise InvalidLiveContract("market_position references an unknown entity")
        comparable_types = {
            item.entity_id: item.entity_type.value for item in self.market_entities
        }
        for entity_id in self.market_position.comparable_competitor_ids:
            if comparable_types[entity_id] != "COMPETITOR":
                raise InvalidLiveContract(
                    "market_position comparables must be competitors"
                )
        for finding in (
            *self.market_position.relative_strengths,
            *self.market_position.relative_weaknesses,
            *self.market_position.market_gaps,
        ):
            check_evidence_refs(finding.evidence_ids, "market position finding")
        for observation in self.market_structure_observations:
            check_evidence_refs(
                observation.evidence_ids, "market structure observation"
            )
        for opportunity in self.opportunities:
            check_evidence_refs(
                opportunity.evidence_ids, f"opportunity {opportunity.opportunity_id}"
            )
        if self.best_next_move is not None:
            check_evidence_refs(self.best_next_move.evidence_ids, "best next move")
            if self.best_next_move.selected_opportunity_id not in known_opportunities:
                raise InvalidLiveContract(
                    "best_next_move must reference an existing opportunity"
                )
            selected_opportunity = next(
                item
                for item in self.opportunities
                if item.opportunity_id == self.best_next_move.selected_opportunity_id
            )
            if not set(self.best_next_move.evidence_ids) <= set(
                selected_opportunity.evidence_ids
            ):
                raise InvalidLiveContract(
                    "best_next_move evidence must support its selected opportunity"
                )


def _json_value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def assessment_to_dict(assessment: BusinessAssessment) -> dict[str, object]:
    """Serialize a validated assessment to JSON-compatible built-in values."""

    if not isinstance(assessment, BusinessAssessment):
        raise InvalidLiveContract("assessment must be a BusinessAssessment")
    return cast(dict[str, object], _json_value(assessment))


def assessment_to_json(assessment: BusinessAssessment, *, indent: int = 2) -> str:
    """Serialize an assessment as readable JSON without domain/provider coupling."""

    if isinstance(indent, bool) or not isinstance(indent, int) or indent < 0:
        raise InvalidLiveContract("indent must be a non-negative integer")
    return json.dumps(assessment_to_dict(assessment), indent=indent, ensure_ascii=False)
