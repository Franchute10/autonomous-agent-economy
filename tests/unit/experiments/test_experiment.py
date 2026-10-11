from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from aeos.core import ExperimentId, OrganizationId, ResourceId, ResourceQuantity
from aeos.experiments import (
    Experiment,
    ExperimentCriterion,
    ExperimentPreregistration,
    ExperimentResourceExposureLimit,
    ExperimentStatus,
    InvalidExperimentState,
    InvalidExperimentTimestamp,
    InvalidExperimentTransition,
)


WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)


def preregistration() -> ExperimentPreregistration:
    return ExperimentPreregistration(
        ExperimentId("exp-1"),
        OrganizationId("org-1"),
        "  hypothesis  ",
        "  objective  ",
        (ExperimentCriterion("  success  "),),
        (ExperimentCriterion("  stop  "),),
        (
            ExperimentResourceExposureLimit(
                ResourceId("tokens"), ResourceQuantity("100", "input_tokens")
            ),
        ),
        WHEN,
    )


def test_status_vocabulary_is_exactly_six_states() -> None:
    assert set(ExperimentStatus) == {
        ExperimentStatus.PREREGISTERED,
        ExperimentStatus.RUNNING,
        ExperimentStatus.SUCCEEDED,
        ExperimentStatus.FAILED,
        ExperimentStatus.KILLED,
        ExperimentStatus.CANCELLED,
    }


def test_preregistered_experiment_starts_with_empty_lifecycle_timestamps() -> None:
    value = Experiment(preregistration())
    assert value.status is ExperimentStatus.PREREGISTERED
    assert value.started_at is None
    assert value.finished_at is None
    assert value.hypothesis == "hypothesis"
    assert value.objective == "objective"


def test_lifecycle_returns_snapshots_and_preserves_preregistration() -> None:
    original = Experiment(preregistration())
    running = original.start(WHEN)
    succeeded = running.succeed(WHEN)

    assert original.status is ExperimentStatus.PREREGISTERED
    assert original.started_at is None
    assert running.status is ExperimentStatus.RUNNING
    assert running.started_at == WHEN
    assert running.finished_at is None
    assert succeeded.status is ExperimentStatus.SUCCEEDED
    assert succeeded.started_at == WHEN
    assert succeeded.finished_at == WHEN
    assert succeeded is not running
    assert succeeded.preregistration is original.preregistration


@pytest.mark.parametrize(
    "method",
    ["succeed", "fail", "kill"],
)
def test_preregistered_cannot_skip_running(method: str) -> None:
    with pytest.raises(InvalidExperimentTransition):
        cast(Any, getattr(Experiment(preregistration()), method))(WHEN)


def test_running_can_fail_kill_or_cancel() -> None:
    running = Experiment(preregistration()).start(WHEN)
    assert running.fail(WHEN).status is ExperimentStatus.FAILED
    assert running.kill(WHEN).status is ExperimentStatus.KILLED
    cancelled = running.cancel(WHEN)
    assert cancelled.status is ExperimentStatus.CANCELLED
    assert cancelled.started_at == WHEN
    assert cancelled.finished_at == WHEN


def test_cancel_before_start_is_valid() -> None:
    cancelled = Experiment(preregistration()).cancel(WHEN)
    assert cancelled.status is ExperimentStatus.CANCELLED
    assert cancelled.started_at is None
    assert cancelled.finished_at == WHEN


@pytest.mark.parametrize(
    ("method", "status"),
    [
        ("succeed", ExperimentStatus.SUCCEEDED),
        ("fail", ExperimentStatus.FAILED),
        ("kill", ExperimentStatus.KILLED),
        ("cancel", ExperimentStatus.CANCELLED),
    ],
)
def test_preregistration_survives_every_running_lifecycle_outcome(
    method: str, status: ExperimentStatus
) -> None:
    prereg = preregistration()
    original = Experiment(prereg)
    result = cast(Any, getattr(original.start(WHEN), method))(WHEN)

    assert result.status is status
    assert result.preregistration is prereg
    assert result.preregistration == original.preregistration


def test_preregistration_survives_cancellation_before_start() -> None:
    prereg = preregistration()
    result = Experiment(prereg).cancel(WHEN)

    assert result.preregistration is prereg
    assert result.preregistration == prereg


@pytest.mark.parametrize(
    "terminal_status",
    [
        ExperimentStatus.SUCCEEDED,
        ExperimentStatus.FAILED,
        ExperimentStatus.KILLED,
        ExperimentStatus.CANCELLED,
    ],
)
@pytest.mark.parametrize("method", ["start", "succeed", "fail", "kill", "cancel"])
def test_every_terminal_experiment_rejects_every_lifecycle_method(
    terminal_status: ExperimentStatus, method: str
) -> None:
    running = Experiment(preregistration()).start(WHEN)
    terminal = {
        ExperimentStatus.SUCCEEDED: running.succeed(WHEN),
        ExperimentStatus.FAILED: running.fail(WHEN),
        ExperimentStatus.KILLED: running.kill(WHEN),
        ExperimentStatus.CANCELLED: running.cancel(WHEN),
    }[terminal_status]
    with pytest.raises(InvalidExperimentTransition):
        cast(Any, getattr(terminal, method))(WHEN + timedelta(seconds=1))


def test_running_cannot_start_again() -> None:
    with pytest.raises(InvalidExperimentTransition):
        Experiment(preregistration()).start(WHEN).start(WHEN)


@pytest.mark.parametrize("method", ["succeed", "fail", "kill"])
def test_preregistered_cannot_transition_directly_to_terminal(method: str) -> None:
    with pytest.raises(InvalidExperimentTransition):
        cast(Any, getattr(Experiment(preregistration()), method))(WHEN)


@pytest.mark.parametrize(
    ("status", "started_at", "finished_at"),
    [
        (ExperimentStatus.PREREGISTERED, WHEN, None),
        (ExperimentStatus.PREREGISTERED, None, WHEN),
        (ExperimentStatus.RUNNING, None, None),
        (ExperimentStatus.RUNNING, WHEN, WHEN),
        (ExperimentStatus.SUCCEEDED, None, WHEN),
        (ExperimentStatus.FAILED, None, WHEN),
        (ExperimentStatus.KILLED, None, WHEN),
        (ExperimentStatus.SUCCEEDED, WHEN, None),
        (ExperimentStatus.FAILED, WHEN, None),
        (ExperimentStatus.KILLED, WHEN, None),
        (ExperimentStatus.CANCELLED, None, None),
    ],
)
def test_direct_state_timestamp_invariants_are_enforced(
    status: ExperimentStatus,
    started_at: datetime | None,
    finished_at: datetime | None,
) -> None:
    with pytest.raises(InvalidExperimentState):
        Experiment(preregistration(), status, started_at, finished_at)


def test_wrong_status_and_preregistration_types_are_rejected() -> None:
    with pytest.raises(InvalidExperimentState):
        Experiment(cast(Any, object()))
    with pytest.raises(InvalidExperimentState):
        Experiment(preregistration(), cast(Any, "running"))


@pytest.mark.parametrize(
    ("started_at", "finished_at"),
    [(WHEN - timedelta(seconds=1), None), (None, WHEN - timedelta(seconds=1))],
)
def test_transition_timestamp_ordering_is_enforced(
    started_at: datetime | None, finished_at: datetime | None
) -> None:
    with pytest.raises(InvalidExperimentTimestamp):
        Experiment(
            preregistration(),
            ExperimentStatus.RUNNING if started_at else ExperimentStatus.CANCELLED,
            started_at,
            finished_at,
        )
    with pytest.raises(InvalidExperimentTimestamp):
        Experiment(
            preregistration(),
            ExperimentStatus.SUCCEEDED,
            WHEN,
            WHEN - timedelta(seconds=1),
        )


def test_terminal_transition_cannot_precede_started_at() -> None:
    running = Experiment(preregistration()).start(WHEN)
    with pytest.raises(InvalidExperimentTimestamp):
        running.succeed(WHEN - timedelta(seconds=1))


def test_naive_and_non_utc_timestamps_follow_shared_kernel_contract() -> None:
    with pytest.raises(InvalidExperimentTimestamp):
        ExperimentPreregistration(
            ExperimentId("exp"),
            OrganizationId("org"),
            "h",
            "o",
            (ExperimentCriterion("s"),),
            (ExperimentCriterion("k"),),
            (
                ExperimentResourceExposureLimit(
                    ResourceId("r"), ResourceQuantity(1, "u")
                ),
            ),
            datetime(2026, 1, 1),
        )
    shifted = Experiment(preregistration()).start(
        datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1)))
    )
    assert shifted.started_at == WHEN
    with pytest.raises(InvalidExperimentTimestamp):
        Experiment(preregistration()).start(datetime(2026, 1, 1))
