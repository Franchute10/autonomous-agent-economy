from datetime import datetime, timezone
from typing import Any, cast

import pytest

from aeos.core import (
    ActorKind,
    ActorRef,
    CorrelationId,
    ExperimentId,
    IdempotencyKey,
    OrganizationId,
    ResourceId,
    ResourceQuantity,
    TraceContext,
)
from aeos.experiments import (
    ExperimentCriterion,
    ExperimentPreregistration,
    ExperimentResourceExposureLimit,
    InvalidExperimentCriterion,
    InvalidExperimentPreregistration,
)


def make_preregistration(**changes: object) -> ExperimentPreregistration:
    values: dict[str, object] = {
        "experiment_id": ExperimentId("exp-1"),
        "organization_id": OrganizationId("org-1"),
        "hypothesis": "hypothesis",
        "objective": "objective",
        "success_criteria": (ExperimentCriterion("success"),),
        "kill_criteria": (ExperimentCriterion("kill"),),
        "maximum_resource_exposure": (
            ExperimentResourceExposureLimit(
                ResourceId("r-1"), ResourceQuantity("1", "unit")
            ),
        ),
        "preregistered_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    values.update(changes)
    return ExperimentPreregistration(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["hypothesis", "objective"])
@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_text_fields_reject_blank_and_whitespace(field: str, value: str) -> None:
    with pytest.raises(InvalidExperimentPreregistration):
        make_preregistration(**{field: value})


@pytest.mark.parametrize("field", ["hypothesis", "objective"])
def test_text_fields_require_strings(field: str) -> None:
    with pytest.raises(InvalidExperimentPreregistration):
        make_preregistration(**{field: object()})


def test_criteria_are_trimmed_immutable_and_ordered() -> None:
    value = make_preregistration(
        success_criteria=(
            ExperimentCriterion(" first "),
            ExperimentCriterion("second"),
        ),
        kill_criteria=(ExperimentCriterion(" stop "),),
    )
    assert [criterion.text for criterion in value.success_criteria] == [
        "first",
        "second",
    ]
    with pytest.raises(AttributeError):
        value.success_criteria += (ExperimentCriterion("third"),)  # type: ignore[misc]


@pytest.mark.parametrize("field", ["success_criteria", "kill_criteria"])
def test_criteria_require_non_empty_tuples(field: str) -> None:
    with pytest.raises(InvalidExperimentPreregistration):
        make_preregistration(**{field: ()})
    with pytest.raises(InvalidExperimentPreregistration):
        make_preregistration(**{field: [ExperimentCriterion("x")]})
    with pytest.raises(InvalidExperimentPreregistration):
        make_preregistration(**{field: (cast(Any, object()),)})


def test_criterion_rejects_wrong_or_blank_text() -> None:
    with pytest.raises(InvalidExperimentCriterion):
        ExperimentCriterion("")
    with pytest.raises(InvalidExperimentCriterion):
        ExperimentCriterion(cast(Any, object()))


def test_preregistration_rejects_wrong_typed_ids_and_trace_values() -> None:
    with pytest.raises(InvalidExperimentPreregistration):
        make_preregistration(experiment_id=OrganizationId("wrong"))
    with pytest.raises(InvalidExperimentPreregistration):
        make_preregistration(organization_id=ExperimentId("wrong"))
    with pytest.raises(InvalidExperimentPreregistration):
        make_preregistration(trace_context=cast(Any, object()))


def test_preregistration_is_immutable_and_normalizes_timestamp() -> None:
    value = make_preregistration()
    assert value.preregistered_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert not hasattr(value, "created_at")
    assert not hasattr(value, "failure_criteria")
    with pytest.raises(AttributeError):
        value.objective = "changed"  # type: ignore[misc]


def test_valid_trace_context_is_accepted_and_preserved() -> None:
    trace = TraceContext(
        ActorRef(OrganizationId("actor"), ActorKind.SYSTEM),
        CorrelationId("correlation"),
        IdempotencyKey("idempotency"),
    )
    value = make_preregistration(trace_context=trace)

    assert value.trace_context is trace
