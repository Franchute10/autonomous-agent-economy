"""Source-labeled evidence, including explicit inference assumptions."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite

from aeos.core.time import normalize_utc
from aeos.live.domain.errors import InvalidLiveContract

JsonScalar = str | int | float | bool | None


class EvidenceKind(StrEnum):
    OBSERVED = "OBSERVED"
    REPORTED = "REPORTED"
    INFERRED = "INFERRED"
    ESTIMATED = "ESTIMATED"


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    evidence_id: str
    kind: EvidenceKind
    subject: str
    field: str
    value: JsonScalar
    source_name: str
    source_url: str | None = None
    retrieved_at: datetime | None = None
    excerpt: str | None = None
    confidence: float | None = None
    assumptions: tuple[str, ...] = ()
    owner_entity_id: str | None = None

    def __post_init__(self) -> None:
        for field in ("evidence_id", "subject", "field", "source_name"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidLiveContract(f"{field} must be a non-blank string")
            object.__setattr__(self, field, value.strip())
        if not isinstance(self.kind, EvidenceKind):
            raise InvalidLiveContract("kind must be an EvidenceKind")
        if self.value is not None and type(self.value) not in (str, int, float, bool):
            raise InvalidLiveContract("value must be a JSON scalar")
        if type(self.value) is float and not isfinite(self.value):
            raise InvalidLiveContract("value must be finite")
        for field in ("source_url", "owner_entity_id", "excerpt"):
            value = getattr(self, field)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise InvalidLiveContract(
                        f"{field} must be a non-blank string or None"
                    )
                object.__setattr__(self, field, value.strip())
        if self.retrieved_at is not None:
            if not isinstance(self.retrieved_at, datetime):
                raise InvalidLiveContract("retrieved_at must be a datetime or None")
            try:
                object.__setattr__(
                    self, "retrieved_at", normalize_utc(self.retrieved_at)
                )
            except ValueError as error:
                raise InvalidLiveContract(str(error)) from error
        if self.confidence is not None:
            if (
                isinstance(self.confidence, bool)
                or not isinstance(self.confidence, (float, int))
                or not isfinite(self.confidence)
                or not 0 <= self.confidence <= 1
            ):
                raise InvalidLiveContract("confidence must be between 0 and 1 or None")
        if not isinstance(self.assumptions, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.assumptions
        ):
            raise InvalidLiveContract(
                "assumptions must be a tuple of non-blank strings"
            )
        object.__setattr__(
            self, "assumptions", tuple(item.strip() for item in self.assumptions)
        )
        if self.kind is EvidenceKind.ESTIMATED and not self.assumptions:
            raise InvalidLiveContract("estimated evidence must record its assumptions")
