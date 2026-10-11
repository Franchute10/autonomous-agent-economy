"""Immutable experiment lifecycle snapshots."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from aeos.core import (
    ExperimentId,
    OrganizationId,
    UtcTimestamp,
    normalize_utc,
)
from aeos.experiments.domain.criterion import ExperimentCriterion
from aeos.experiments.domain.errors import (
    InvalidExperimentState,
    InvalidExperimentTimestamp,
    InvalidExperimentTransition,
)
from aeos.experiments.domain.preregistration import ExperimentPreregistration
from aeos.experiments.domain.exposure import ExperimentResourceExposureLimit


class ExperimentStatus(StrEnum):
    PREREGISTERED = "preregistered"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    KILLED = "killed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Experiment:
    """One immutable lifecycle snapshot associated with preregistered terms."""

    preregistration: ExperimentPreregistration
    status: ExperimentStatus = ExperimentStatus.PREREGISTERED
    started_at: UtcTimestamp | None = None
    finished_at: UtcTimestamp | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.preregistration, ExperimentPreregistration):
            raise InvalidExperimentState(
                "preregistration must be an ExperimentPreregistration"
            )
        if not isinstance(self.status, ExperimentStatus):
            raise InvalidExperimentState("status must be an ExperimentStatus")
        started = self._timestamp(self.started_at, "started_at")
        finished = self._timestamp(self.finished_at, "finished_at")
        preregistered = self.preregistration.preregistered_at
        if started is not None and started < preregistered:
            raise InvalidExperimentTimestamp(
                "started_at cannot precede preregistered_at"
            )
        if finished is not None and finished < preregistered:
            raise InvalidExperimentTimestamp(
                "finished_at cannot precede preregistered_at"
            )
        if started is not None and finished is not None and finished < started:
            raise InvalidExperimentTimestamp("finished_at cannot precede started_at")
        if self.status is ExperimentStatus.PREREGISTERED and (
            started is not None or finished is not None
        ):
            raise InvalidExperimentState(
                "PREREGISTERED cannot have started_at or finished_at"
            )
        if self.status is ExperimentStatus.RUNNING and (
            started is None or finished is not None
        ):
            raise InvalidExperimentState(
                "RUNNING requires started_at and no finished_at"
            )
        if self.status in {
            ExperimentStatus.SUCCEEDED,
            ExperimentStatus.FAILED,
            ExperimentStatus.KILLED,
        } and (started is None or finished is None):
            raise InvalidExperimentState(
                "SUCCEEDED, FAILED, and KILLED require started_at and finished_at"
            )
        if self.status is ExperimentStatus.CANCELLED and finished is None:
            raise InvalidExperimentState("CANCELLED requires finished_at")
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "finished_at", finished)

    @staticmethod
    def _timestamp(value: datetime | None, field: str) -> UtcTimestamp | None:
        if value is None:
            return None
        try:
            return normalize_utc(value)
        except (AttributeError, TypeError, ValueError) as exc:
            raise InvalidExperimentTimestamp(
                f"{field} must be a timezone-aware datetime"
            ) from exc

    @property
    def experiment_id(self) -> ExperimentId:
        return self.preregistration.experiment_id

    @property
    def organization_id(self) -> OrganizationId:
        return self.preregistration.organization_id

    @property
    def hypothesis(self) -> str:
        return self.preregistration.hypothesis

    @property
    def objective(self) -> str:
        return self.preregistration.objective

    @property
    def success_criteria(self) -> tuple[ExperimentCriterion, ...]:
        return self.preregistration.success_criteria

    @property
    def kill_criteria(self) -> tuple[ExperimentCriterion, ...]:
        return self.preregistration.kill_criteria

    @property
    def maximum_resource_exposure(
        self,
    ) -> tuple[ExperimentResourceExposureLimit, ...]:
        return self.preregistration.maximum_resource_exposure

    @property
    def preregistered_at(self) -> UtcTimestamp:
        return self.preregistration.preregistered_at

    def _transition(self, status: ExperimentStatus, at: datetime) -> "Experiment":
        allowed = {
            ExperimentStatus.PREREGISTERED: {
                ExperimentStatus.RUNNING,
                ExperimentStatus.CANCELLED,
            },
            ExperimentStatus.RUNNING: {
                ExperimentStatus.SUCCEEDED,
                ExperimentStatus.FAILED,
                ExperimentStatus.KILLED,
                ExperimentStatus.CANCELLED,
            },
        }
        if status not in allowed.get(self.status, set()):
            raise InvalidExperimentTransition(
                f"{self.status} cannot transition to {status}"
            )
        event_time = self._timestamp(at, "transition timestamp")
        if event_time is None:
            raise InvalidExperimentTimestamp("transition timestamp is required")
        started = event_time if status is ExperimentStatus.RUNNING else self.started_at
        finished = (
            event_time
            if status
            in {
                ExperimentStatus.SUCCEEDED,
                ExperimentStatus.FAILED,
                ExperimentStatus.KILLED,
                ExperimentStatus.CANCELLED,
            }
            else self.finished_at
        )
        return replace(self, status=status, started_at=started, finished_at=finished)

    def start(self, at: datetime) -> "Experiment":
        return self._transition(ExperimentStatus.RUNNING, at)

    def succeed(self, at: datetime) -> "Experiment":
        return self._transition(ExperimentStatus.SUCCEEDED, at)

    def fail(self, at: datetime) -> "Experiment":
        return self._transition(ExperimentStatus.FAILED, at)

    def kill(self, at: datetime) -> "Experiment":
        return self._transition(ExperimentStatus.KILLED, at)

    def cancel(self, at: datetime) -> "Experiment":
        return self._transition(ExperimentStatus.CANCELLED, at)
