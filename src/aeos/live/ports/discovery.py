"""Abstract market discovery contract; no provider is assumed."""

from dataclasses import dataclass
from typing import Protocol

from aeos.live.domain.business import BusinessInput
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import SourceEvidence
from aeos.live.domain.market import MarketEntity


@dataclass(frozen=True, slots=True)
class MarketDiscoveryResult:
    """A traceable provider result; every discovered entity owns its evidence."""

    entities: tuple[MarketEntity, ...]
    evidence: tuple[SourceEvidence, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entities, tuple) or any(
            not isinstance(item, MarketEntity) for item in self.entities
        ):
            raise InvalidLiveContract("entities must be a tuple of MarketEntity values")
        if not isinstance(self.evidence, tuple) or any(
            not isinstance(item, SourceEvidence) for item in self.evidence
        ):
            raise InvalidLiveContract(
                "evidence must be a tuple of SourceEvidence values"
            )
        if not isinstance(self.limitations, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.limitations
        ):
            raise InvalidLiveContract(
                "limitations must be a tuple of non-blank strings"
            )

        entity_ids = [entity.entity_id for entity in self.entities]
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(set(entity_ids)) != len(entity_ids):
            raise InvalidLiveContract("entity identifiers must be unique")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise InvalidLiveContract("evidence identifiers must be unique")

        entities_by_id = {entity.entity_id: entity for entity in self.entities}
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        for entity in self.entities:
            if not entity.evidence_ids:
                raise InvalidLiveContract(
                    f"entity {entity.entity_id} must reference source evidence"
                )
            for evidence_id in entity.evidence_ids:
                evidence = evidence_by_id.get(evidence_id)
                if evidence is None:
                    raise InvalidLiveContract(
                        f"entity {entity.entity_id} references unknown evidence: {evidence_id}"
                    )
                if evidence.owner_entity_id != entity.entity_id:
                    raise InvalidLiveContract(
                        f"entity {entity.entity_id} references evidence it does not own"
                    )
        for evidence in self.evidence:
            if evidence.owner_entity_id is None:
                raise InvalidLiveContract(
                    f"discovery evidence {evidence.evidence_id} must have an owner entity"
                )
            owner = entities_by_id.get(evidence.owner_entity_id)
            if owner is None:
                raise InvalidLiveContract(
                    f"evidence {evidence.evidence_id} references an unknown owner entity"
                )
            if evidence.evidence_id not in owner.evidence_ids:
                raise InvalidLiveContract(
                    f"evidence {evidence.evidence_id} is not associated with its owner entity"
                )


class MarketDiscoveryPort(Protocol):
    def discover_competitors(
        self, business: BusinessInput
    ) -> MarketDiscoveryResult: ...

    def discover_potential_customers(
        self, business: BusinessInput
    ) -> MarketDiscoveryResult: ...

    def discover_partners(self, business: BusinessInput) -> MarketDiscoveryResult: ...

    def discover_suppliers(self, business: BusinessInput) -> MarketDiscoveryResult: ...
