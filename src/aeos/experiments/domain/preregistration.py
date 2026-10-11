"""Immutable declaration of an experiment's terms before execution."""

from dataclasses import dataclass
from aeos.core import (
    ExperimentId,
    OrganizationId,
    TraceContext,
    UtcTimestamp,
    normalize_utc,
)
from aeos.experiments.domain.criterion import ExperimentCriterion
from aeos.experiments.domain.errors import (
    DuplicateExperimentResource,
    InvalidExperimentPreregistration,
    InvalidExperimentTimestamp,
)
from aeos.experiments.domain.exposure import ExperimentResourceExposureLimit


@dataclass(frozen=True, slots=True)
class ExperimentPreregistration:
    """The immutable, pre-execution terms for one experiment identity."""

    experiment_id: ExperimentId
    organization_id: OrganizationId
    hypothesis: str
    objective: str
    success_criteria: tuple[ExperimentCriterion, ...]
    kill_criteria: tuple[ExperimentCriterion, ...]
    maximum_resource_exposure: tuple[ExperimentResourceExposureLimit, ...]
    preregistered_at: UtcTimestamp
    trace_context: TraceContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_id, ExperimentId):
            raise InvalidExperimentPreregistration(
                "experiment_id must be an ExperimentId"
            )
        if not isinstance(self.organization_id, OrganizationId):
            raise InvalidExperimentPreregistration(
                "organization_id must be an OrganizationId"
            )
        object.__setattr__(
            self, "hypothesis", self._text(self.hypothesis, "hypothesis")
        )
        object.__setattr__(self, "objective", self._text(self.objective, "objective"))
        self._criteria(self.success_criteria, "success_criteria")
        self._criteria(self.kill_criteria, "kill_criteria")
        self._exposure_limits()
        if self.trace_context is not None and not isinstance(
            self.trace_context, TraceContext
        ):
            raise InvalidExperimentPreregistration(
                "trace_context must be a TraceContext or None"
            )
        try:
            timestamp = normalize_utc(self.preregistered_at)
        except (AttributeError, TypeError, ValueError) as exc:
            raise InvalidExperimentTimestamp(
                "preregistered_at must be a timezone-aware datetime"
            ) from exc
        object.__setattr__(self, "preregistered_at", timestamp)

    @staticmethod
    def _text(value: object, field: str) -> str:
        if not isinstance(value, str):
            raise InvalidExperimentPreregistration(f"{field} must be a string")
        value = value.strip()
        if not value:
            raise InvalidExperimentPreregistration(f"{field} must not be blank")
        return value

    @staticmethod
    def _criteria(values: object, field: str) -> tuple[ExperimentCriterion, ...]:
        if not isinstance(values, tuple):
            raise InvalidExperimentPreregistration(f"{field} must be a tuple")
        if not values:
            raise InvalidExperimentPreregistration(
                f"{field} must contain at least one criterion"
            )
        if any(not isinstance(value, ExperimentCriterion) for value in values):
            raise InvalidExperimentPreregistration(
                f"{field} must contain only ExperimentCriterion values"
            )
        return values

    def _exposure_limits(self) -> None:
        values = self.maximum_resource_exposure
        if not isinstance(values, tuple):
            raise InvalidExperimentPreregistration(
                "maximum_resource_exposure must be a tuple"
            )
        if not values:
            raise InvalidExperimentPreregistration(
                "maximum_resource_exposure must contain at least one limit"
            )
        if any(
            not isinstance(value, ExperimentResourceExposureLimit) for value in values
        ):
            raise InvalidExperimentPreregistration(
                "maximum_resource_exposure must contain only exposure limits"
            )
        resource_ids = {value.resource_id for value in values}
        if len(resource_ids) != len(values):
            raise DuplicateExperimentResource()
